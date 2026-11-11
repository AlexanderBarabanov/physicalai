#!/usr/bin/env python
"""CPU LLM inference benchmark: OpenVINO GenAI vs PyTorch vs llama.cpp vs Ollama.

Orchestrator mode (default): runs each engine in its own subprocess, then writes results.json and results.md.
Worker mode (--worker ENGINE): internal; runs a single engine and writes its JSON to --worker-out.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import resource
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import psutil
from common import (
    GGUF_FILE,
    OLLAMA_TAG,
    ensure_disk,
    hardware_info,
    load_prompts,
    ollama_url,
    package_versions,
    print_hardware,
    start_ollama_server,
    stop_ollama_server,
)

ENGINES = ["openvino_ir_int4", "openvino_gguf", "pytorch_cpu", "llama_cpp", "ollama"]
LABELS = {
    "openvino_ir_int4": "OpenVINO GenAI (IR INT4)",
    "openvino_gguf": "OpenVINO GenAI (GGUF Q4_K_M)",
    "pytorch_cpu": "PyTorch CPU",
    "llama_cpp": "llama.cpp (GGUF Q4_K_M)",
    "ollama": "Ollama (GGUF Q4_K_M)",
}
METRICS = ("ttft_ms", "tpot_ms", "throughput_tps", "e2e_ms", "generated_tokens", "prompt_tokens", "native_ttft_ms", "native_tpot_ms")
MB = 1024 * 1024


# ----------------------------------------------------------------------------- measurement helpers


class PeakRss:
    """Samples RSS of this process plus optional extra process trees (the Ollama daemon)."""

    def __init__(self, extra=None, interval: float = 0.01) -> None:
        self._me = psutil.Process()
        self._extra = extra or (lambda: [])
        self._interval = interval
        self._lock = threading.Lock()
        self._peak = 0
        self._window = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _sample(self) -> int:
        procs = [self._me]
        for proc in self._extra():
            procs.append(proc)
            try:
                procs.extend(proc.children(recursive=True))
            except psutil.Error:
                pass
        total, seen = 0, set()
        for proc in procs:
            if proc.pid in seen:
                continue
            seen.add(proc.pid)
            try:
                total += proc.memory_info().rss
            except psutil.Error:
                continue
        return total

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            sample = self._sample()
            with self._lock:
                self._peak = max(self._peak, sample)
                self._window = max(self._window, sample)

    def start(self) -> None:
        self._peak = self._window = self._sample()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def current_mb(self) -> float:
        return self._sample() / MB

    def take_window_mb(self) -> float:
        """Peak since the previous call; resets the window."""
        current = self._sample()
        with self._lock:
            peak = max(self._window, current)
            self._window = current
        return peak / MB

    def peak_mb(self) -> float:
        with self._lock:
            peak = self._peak
        if sys.platform.startswith("linux"):
            peak = max(peak, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
        return peak / MB


def make_run(prompt_tokens: int, gen_tokens: int, t0: float, t_first: float | None, t_end: float,
             ttft_ms: float | None = None, **native) -> dict:
    """Derive per-run metrics. TPOT = (E2E - TTFT) / (generated - 1); throughput = 1000 / TPOT."""
    e2e = (t_end - t0) * 1000
    if ttft_ms is None and t_first is not None:
        ttft_ms = (t_first - t0) * 1000
    tpot = (e2e - ttft_ms) / (gen_tokens - 1) if ttft_ms is not None and gen_tokens > 1 else None
    return {
        "prompt_tokens": prompt_tokens,
        "generated_tokens": gen_tokens,
        "ttft_ms": ttft_ms,
        "tpot_ms": tpot,
        "throughput_tps": 1000 / tpot if tpot else None,
        "e2e_ms": e2e,
        **native,
    }


def summarize(runs: list[dict]) -> dict:
    stats = {}
    for key in METRICS:
        values = [r[key] for r in runs if r.get(key) is not None]
        if not values:
            stats[key] = None
            continue
        stats[key] = {"mean": statistics.fmean(values), "stdev": statistics.stdev(values) if len(values) > 1 else 0.0}
    return stats


# ----------------------------------------------------------------------------- engines


class OpenVinoEngine:
    def __init__(self, path: Path) -> None:
        if not path.exists():
            raise FileNotFoundError(path)
        import openvino_genai as ov_genai

        self._ov = ov_genai
        self.path = path
        self.pipe = None
        self.details = {"model_path": str(path), "device": "CPU"}

    def load(self) -> None:
        self.pipe = self._ov.LLMPipeline(str(self.path), "CPU")

    def generate(self, prompt: dict, max_new: int) -> dict:
        cfg = self._ov.GenerationConfig()
        cfg.max_new_tokens = max_new
        cfg.do_sample = False
        cfg.ignore_eos = True
        t0 = time.perf_counter()
        result = self.pipe.generate(prompt["text"], cfg)
        t1 = time.perf_counter()
        pm = result.perf_metrics
        ttft = pm.get_ttft().mean
        return make_run(
            pm.get_num_input_tokens(), pm.get_num_generated_tokens(), t0, None, t1, ttft_ms=ttft,
            native_ttft_ms=ttft, native_tpot_ms=pm.get_tpot().mean,
        )

    def close(self) -> None:
        self.pipe = None


def _timed_streamer_cls():
    from transformers import TextIteratorStreamer

    class TimedStreamer(TextIteratorStreamer):
        """TextIteratorStreamer that also records a timestamp for every generated token."""

        def __init__(self, tokenizer) -> None:
            super().__init__(tokenizer, skip_prompt=True)
            self.stamps: list[float] = []
            self._prompt_seen = False

        def put(self, value) -> None:
            if self._prompt_seen:
                self.stamps.append(time.perf_counter())
            self._prompt_seen = True
            super().put(value)

    return TimedStreamer


class PyTorchEngine:
    def __init__(self, path: Path, threads: int, dtype: str) -> None:
        if not path.exists():
            raise FileNotFoundError(path)
        import torch

        torch.set_num_threads(threads)
        self.torch = torch
        self.path = path
        self.dtype = getattr(torch, dtype)
        self.streamer_cls = _timed_streamer_cls()
        self.tok = self.model = None
        self.details = {"dtype": dtype, "threads": threads, "torch": torch.__version__}

    def load(self) -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tok = AutoTokenizer.from_pretrained(self.path)
        try:
            self.model = AutoModelForCausalLM.from_pretrained(self.path, dtype=self.dtype)
        except TypeError:  # older transformers
            self.model = AutoModelForCausalLM.from_pretrained(self.path, torch_dtype=self.dtype)
        self.model.eval()

    def generate(self, prompt: dict, max_new: int) -> dict:
        streamer = self.streamer_cls(self.tok)
        t0 = time.perf_counter()
        enc = self.tok(prompt["text"], return_tensors="pt")
        with self.torch.inference_mode():
            out = self.model.generate(
                **enc, max_new_tokens=max_new, min_new_tokens=max_new, do_sample=False, temperature=None,
                top_p=None, top_k=None, repetition_penalty=1.0, streamer=streamer, pad_token_id=self.tok.eos_token_id,
            )
        t1 = time.perf_counter()
        n_prompt = enc["input_ids"].shape[1]
        return make_run(n_prompt, out.shape[1] - n_prompt, t0, streamer.stamps[0] if streamer.stamps else None, t1)

    def close(self) -> None:
        self.model = self.tok = None


class LlamaCppEngine:
    def __init__(self, path: Path, threads: int) -> None:
        if not path.exists():
            raise FileNotFoundError(path)
        import llama_cpp

        self.lib = llama_cpp
        self.path = path
        self.threads = threads
        self.llm = None
        self.bias: dict[int, float] = {}
        self.details = {"threads": threads, "n_ctx": 2048, "n_batch": 512, "llama_cpp_python": llama_cpp.__version__}

    def load(self) -> None:
        self.llm = self.lib.Llama(
            model_path=str(self.path), n_ctx=2048, n_batch=512, n_threads=self.threads,
            n_threads_batch=self.threads, seed=0, verbose=False,
        )
        # Ban end-of-sequence tokens so exactly max_new tokens are generated.
        ids = {self.llm.token_eos()}
        for special in (b"<|im_end|>", b"<|endoftext|>"):
            toks = self.llm.tokenize(special, add_bos=False, special=True)
            if len(toks) == 1:
                ids.add(toks[0])
        self.bias = {int(i): -100.0 for i in ids}

    def _native(self) -> dict:
        try:
            perf = self.lib.llama_perf_context(self.llm._ctx.ctx)  # noqa: SLF001
            return {
                "native_ttft_ms": perf.t_p_eval_ms,
                "native_tpot_ms": perf.t_eval_ms / perf.n_eval if perf.n_eval else None,
            }
        except Exception:  # noqa: BLE001
            return {}

    def generate(self, prompt: dict, max_new: int) -> dict:
        self.llm.reset()
        try:
            self.lib.llama_perf_context_reset(self.llm._ctx.ctx)  # noqa: SLF001
        except Exception:  # noqa: BLE001, S110
            pass
        n_prompt = len(self.llm.tokenize(prompt["text"].encode("utf-8"), special=True))
        count, first = 0, None
        t0 = time.perf_counter()
        stream = self.llm.create_completion(
            prompt["text"], max_tokens=max_new, temperature=0.0, top_k=1, top_p=1.0, min_p=0.0,
            repeat_penalty=1.0, logit_bias=self.bias, stream=True,
        )
        for chunk in stream:
            choice = chunk["choices"][0]
            if choice.get("finish_reason") is not None:
                continue
            count += 1
            if first is None and choice["text"]:
                first = time.perf_counter()
        t1 = time.perf_counter()
        return make_run(n_prompt, count, t0, first, t1, **self._native())

    def close(self) -> None:
        self.llm = None


class OllamaEngine:
    def __init__(self, threads: int, log_dir: Path) -> None:
        self.threads = threads
        self.log_dir = log_dir
        self.proc = None
        self.ps_proc = None
        self.details = {"model": OLLAMA_TAG, "threads": threads}
        self.load_extra: dict = {}

    def extra_processes(self) -> list:
        return [self.ps_proc] if self.ps_proc is not None else []

    def _options(self, num_predict: int) -> dict:
        return {
            "temperature": 0.0, "top_k": 1, "top_p": 1.0, "min_p": 0.0, "repeat_penalty": 1.0, "seed": 0,
            "num_predict": num_predict, "num_ctx": 2048, "num_thread": self.threads,
        }

    def _post(self, payload: dict):
        req = urllib.request.Request(  # noqa: S310
            ollama_url("/api/generate"), data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        return urllib.request.urlopen(req, timeout=900)  # noqa: S310

    def load(self) -> None:
        t0 = time.perf_counter()
        self.proc = start_ollama_server(self.log_dir / "ollama-serve-bench.log", self.threads)
        self.ps_proc = psutil.Process(self.proc.pid)
        self.load_extra["server_start_ms"] = (time.perf_counter() - t0) * 1000
        # An empty prompt makes Ollama load the model into memory without generating.
        with self._post({"model": OLLAMA_TAG, "prompt": "", "stream": False, "keep_alive": "30m",
                         "options": self._options(1)}) as resp:
            resp.read()

    def _stream(self, prompt: str, num_predict: int, raw: bool = True):
        payload = {"model": OLLAMA_TAG, "prompt": prompt, "raw": raw, "stream": True, "keep_alive": "30m",
                   "options": self._options(num_predict)}
        first, final = None, {}
        t0 = time.perf_counter()
        with self._post(payload) as resp:
            for line in resp:
                if not line.strip():
                    continue
                obj = json.loads(line)
                if first is None and obj.get("response"):
                    first = time.perf_counter()
                if obj.get("done"):
                    final = obj
        return t0, first, time.perf_counter(), final

    def generate(self, prompt: dict, max_new: int) -> dict:
        # Different prompt first so Ollama's KV prefix cache cannot skip the real prefill.
        self._stream("Decoy request used to evict the cached prompt prefix.", 1)
        t0, first, t1, final = self._stream(prompt["text"], max_new)
        n_prompt = final.get("prompt_eval_count", 0)
        n_gen = final.get("eval_count", 0)
        pe_ms = final.get("prompt_eval_duration", 0) / 1e6
        ev_ms = final.get("eval_duration", 0) / 1e6
        return make_run(
            n_prompt, n_gen, t0, first, t1, native_ttft_ms=pe_ms or None,
            native_tpot_ms=ev_ms / n_gen if n_gen else None,
            prompt_cache_suspected=n_prompt < 0.9 * prompt["tokens"], native_load_ms=final.get("load_duration", 0) / 1e6,
        )

    def close(self) -> None:
        if self.proc is not None:
            stop_ollama_server(self.proc)


def make_engine(name: str, args: argparse.Namespace):
    models = Path(args.models_dir)
    if name == "openvino_ir_int4":
        return OpenVinoEngine(models / "ov_ir_int4")
    if name == "openvino_gguf":
        return OpenVinoEngine(models / GGUF_FILE)
    if name == "pytorch_cpu":
        return PyTorchEngine(models / "hf_base", args.threads, args.torch_dtype)
    if name == "llama_cpp":
        return LlamaCppEngine(models / GGUF_FILE, args.threads)
    if name == "ollama":
        return OllamaEngine(args.threads, Path(args.log_dir))
    msg = f"unknown engine {name}"
    raise ValueError(msg)


# ----------------------------------------------------------------------------- worker


def run_worker(name: str, args: argparse.Namespace) -> dict:
    result: dict = {"engine": name, "label": LABELS[name], "status": "failed"}
    engine = None
    sampler = None
    try:
        prompts = load_prompts(Path(args.models_dir))
        engine = make_engine(name, args)
        sampler = PeakRss(getattr(engine, "extra_processes", None))
        sampler.start()
        t0 = time.perf_counter()
        engine.load()
        result["load_ms"] = (time.perf_counter() - t0) * 1000
        result["load_extra"] = getattr(engine, "load_extra", {})
        result["rss_after_load_mb"] = sampler.current_mb()
        sampler.take_window_mb()
        result["prompts"] = {}
        for pname, prompt in prompts.items():
            for _ in range(args.warmup):
                engine.generate(prompt, args.max_new_tokens)
            sampler.take_window_mb()
            runs = [engine.generate(prompt, args.max_new_tokens) for _ in range(args.runs)]
            result["prompts"][pname] = {
                "runs": runs, "stats": summarize(runs), "peak_rss_mb": sampler.take_window_mb(),
            }
            print(f"[{name}] {pname}: {json.dumps(result['prompts'][pname]['stats'], default=str)}", flush=True)
        result["peak_rss_mb"] = sampler.peak_mb()
        result["details"] = engine.details
        result["status"] = "ok"
    except Exception:  # noqa: BLE001
        result["error"] = traceback.format_exc()
        print(result["error"], file=sys.stderr, flush=True)
    finally:
        if sampler is not None and sampler._thread.is_alive():  # noqa: SLF001
            sampler.stop()
        if engine is not None:
            engine.close()
        del engine
        gc.collect()
    return result


# ----------------------------------------------------------------------------- report


def _ms(stat: dict | None, digits: int = 1) -> str:
    if not stat:
        return "n/a"
    return f"{stat['mean']:.{digits}f} ± {stat['stdev']:.{digits}f}"


INTERPRETATION = """\
## How to read these numbers

| Metric | Meaning | Lower/higher is better | What it mostly reflects |
|---|---|---|---|
| Load (ms) | Time to bring weights into memory and build the engine (imports excluded; Ollama: model load request only, daemon start is reported separately). Page cache is warm because the files were just written, so this is a *warm-disk* load. | Lower | Weight size, format conversion at load time, graph compilation (OpenVINO), mmap vs copy |
| TTFT (ms) | Request submission to first generated token. OpenVINO uses its native `PerfMetrics`; the others use the wall clock at the first streamed token. | Lower | Prefill: compute-bound, so ISA extensions (AVX-512 / VNNI / AMX) and kernel quality matter most. Compare the 512-token row. |
| TPOT (ms/token) | `(E2E - TTFT) / (generated - 1)` | Lower | Decode: memory-bandwidth-bound. Smaller weights (INT4 vs FP32) help far more than faster arithmetic. Compare the 32-token row. |
| Throughput (tok/s) | `1000 / TPOT` | Higher | Same as TPOT, inverted |
| E2E (ms) | Wall time for prompt plus 128 generated tokens, including tokenization and API overhead | Lower | Combined effect; the number users actually feel |
| Peak RSS (MB) | Highest resident set size sampled every 10 ms (Ollama: client plus `ollama serve` and runner processes). Memory-mapped weights count as resident once touched. | Lower | Weight precision, KV cache, runtime allocator overhead |

Native columns (`Native TTFT`, `Native TPOT`) come from each engine's own counters (OpenVINO `PerfMetrics`, llama.cpp perf context, Ollama `prompt_eval_duration` / `eval_duration`). Use them to check that the wall-clock numbers are not dominated by wrapper overhead.

### Caveats

- **Not bit-identical weights.** OpenVINO IR INT4 (NNCF) and GGUF Q4_K_M use different 4-bit schemes; PyTorch runs the unquantized model. Speed differences include precision differences, and output text can differ.
- **GitHub-hosted runners are shared VMs.** Expect run-to-run noise; read StdDev and compare engines from the same run, not across runs or CPU models.
- **Decode is bandwidth-bound**, so engines on the same quantized GGUF (llama.cpp, Ollama, OpenVINO GGUF) are expected to land close on TPOT, while TTFT separates kernel quality.
- **Token counts** are reported per run; a count below 128 means the engine stopped on EOS (Ollama cannot ban EOS) and its TPOT is averaged over fewer tokens.
"""


def render_markdown(results: dict) -> str:
    from tabulate import tabulate

    env, cfg = results["environment"], results["config"]
    flags = ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in env["isa_flags"].items())
    lines = [
        "# CPU LLM inference benchmark",
        "",
        f"- **Model:** `{cfg['model']}` (greedy, {cfg['max_new_tokens']} new tokens, {cfg['warmup']} warmup + {cfg['runs']} measured runs per prompt)",
        f"- **CPU:** {env['cpu_model']} ({env['vcpus']} vCPUs, {env['ram_total_gb']} GB RAM)",
        f"- **ISA:** {flags}",
        f"- **Versions:** " + ", ".join(f"{k} {v}" for k, v in results["versions"].items() if v),
        "",
    ]
    notes: list[str] = []
    headers = ["Engine", "Load (ms)", "TTFT (ms)", "TPOT (ms/tok)", "Throughput (tok/s)", "E2E (ms)",
               "Peak RSS (MB)", "Native TTFT (ms)", "Native TPOT (ms/tok)", "Gen. tokens"]
    for pname in ("short", "long"):
        rows = []
        for name, res in results["engines"].items():
            if res["status"] != "ok":
                rows.append([res["label"], "FAILED"] + ["-"] * (len(headers) - 2))
                continue
            p = res["prompts"][pname]
            st = p["stats"]
            tokens = st["generated_tokens"]["mean"] if st["generated_tokens"] else math.nan
            if tokens != cfg["max_new_tokens"]:
                notes.append(f"{res['label']} ({pname}): generated {tokens:.0f} tokens instead of {cfg['max_new_tokens']}.")
            if any(r.get("prompt_cache_suspected") for r in p["runs"]):
                notes.append(f"{res['label']} ({pname}): prompt cache hit suspected, TTFT may be understated.")
            rows.append([
                res["label"], f"{res['load_ms']:.0f}", _ms(st["ttft_ms"]), _ms(st["tpot_ms"], 2),
                _ms(st["throughput_tps"]), _ms(st["e2e_ms"], 0), f"{p['peak_rss_mb']:.0f}",
                _ms(st["native_ttft_ms"]), _ms(st["native_tpot_ms"], 2), f"{tokens:.0f}",
            ])
        n_tok = next((r["prompts"][pname]["stats"]["prompt_tokens"]["mean"] for r in results["engines"].values()
                      if r["status"] == "ok" and r["prompts"][pname]["stats"]["prompt_tokens"]), None)
        title = "Short prompt" if pname == "short" else "Long prompt"
        lines += [f"## {title} (~{n_tok:.0f} input tokens)" if n_tok else f"## {title}", "",
                  tabulate(rows, headers=headers, tablefmt="github"), ""]
    for name, res in results["engines"].items():
        if res["status"] != "ok":
            last = (res.get("error") or "unknown error").strip().splitlines()[-1]
            notes.append(f"{res['label']} failed: `{last}`")
    if notes:
        lines += ["## Notes", ""] + [f"- {n}" for n in notes] + [""]
    lines += [INTERPRETATION]
    return "\n".join(lines)


# ----------------------------------------------------------------------------- orchestrator


def run_orchestrator(args: argparse.Namespace) -> int:
    engines = args.engines or ENGINES
    env = hardware_info()
    print_hardware(env)
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": env,
        "versions": package_versions(),
        "config": {
            "model": "Qwen/Qwen2.5-0.5B-Instruct", "max_new_tokens": args.max_new_tokens, "runs": args.runs,
            "warmup": args.warmup, "threads": args.threads, "torch_dtype": args.torch_dtype, "temperature": 0.0,
        },
        "engines": {},
    }
    forwarded = [
        "--models-dir", str(args.models_dir), "--log-dir", str(args.log_dir), "--runs", str(args.runs),
        "--warmup", str(args.warmup), "--max-new-tokens", str(args.max_new_tokens), "--threads", str(args.threads),
        "--torch-dtype", args.torch_dtype,
    ]
    for name in engines:
        ensure_disk()
        print(f"\n=== {LABELS[name]} ===", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "worker.json"
            cmd = [sys.executable, str(Path(__file__).resolve()), "--worker", name, "--worker-out", str(out), *forwarded]
            try:
                proc = subprocess.run(cmd, check=False, timeout=args.timeout)  # noqa: S603
                if out.exists():
                    res = json.loads(out.read_text(encoding="utf-8"))
                else:
                    res = {"engine": name, "label": LABELS[name], "status": "failed",
                           "error": f"worker exited with code {proc.returncode} without a result (OOM kill?)"}
            except subprocess.TimeoutExpired:
                res = {"engine": name, "label": LABELS[name], "status": "failed", "error": f"timeout after {args.timeout}s"}
        results["engines"][name] = res
        print(f"[{name}] status={res['status']}", flush=True)

    Path(args.output).write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    markdown = render_markdown(results)
    Path(args.markdown).write_text(markdown, encoding="utf-8")
    print("\n" + markdown)
    failed = [n for n, r in results["engines"].items() if r["status"] != "ok"]
    if len(failed) == len(results["engines"]) or (args.strict and failed):
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engines", nargs="+", choices=ENGINES, help="subset of engines (default: all)")
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    parser.add_argument("--output", type=Path, default=Path("results.json"))
    parser.add_argument("--markdown", type=Path, default=Path("results.md"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--max-new-tokens", type=int, default=128)
    parser.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--torch-dtype", choices=["float32", "bfloat16"], default="float32")
    parser.add_argument("--timeout", type=int, default=1800, help="per-engine timeout in seconds")
    parser.add_argument("--strict", action="store_true", help="exit non-zero if any engine fails")
    parser.add_argument("--worker", choices=ENGINES, help=argparse.SUPPRESS)
    parser.add_argument("--worker-out", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        result = run_worker(args.worker, args)
        args.worker_out.write_text(json.dumps(result, default=str), encoding="utf-8")
        return 0
    return run_orchestrator(args)


if __name__ == "__main__":
    sys.exit(main())
