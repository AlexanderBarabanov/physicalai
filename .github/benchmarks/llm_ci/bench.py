"""Benchmark local LLM backends (OpenVINO GenAI, PyTorch, llama.cpp) on CI-style tasks.

Usage:
    python bench.py run --label ov-int4 --backend ov --repo OpenVINO/Qwen3-4B-int4-ov --out results.jsonl
    python bench.py report --in results.jsonl --baseline gguf-q4

Every backend receives the identical, pre-templated prompt (greedy decoding), so
differences come from the runtime and weights, not from prompt handling.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import resource
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path


def _long_log() -> str:
    lines = [f"2026-01-01T10:{i % 60:02d}:00Z INFO  worker-{i % 8} step {i} completed in {100 + i % 37}ms" for i in range(60)]
    lines.insert(45, "2026-01-01T10:30:00Z ERROR tests/test_io.py::test_roundtrip_png FAILED - AssertionError: expected 3 channels, got 4")
    return "\n".join(lines)


def _json_ok(out: str) -> bool:
    m = re.search(r"\{.*\}", out, re.DOTALL)
    if not m:
        return False
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return False
    return d.get("package") == "numpy" and str(d.get("old")) == "1.26.4" and str(d.get("new")) == "2.0.1"


# (name, user prompt, max_new_tokens, checker)
TASKS = [
    (
        "commit_ci",
        "Classify this commit message as one of: feat, fix, docs, refactor, test, chore, ci. "
        "Answer with the label only.\n\nCommit: Update GitHub Actions workflow to cache pip dependencies",
        8,
        lambda o: o.strip().lower().startswith("ci"),
    ),
    (
        "commit_docs",
        "Classify this commit message as one of: feat, fix, docs, refactor, test, chore, ci. "
        "Answer with the label only.\n\nCommit: Add installation section to README",
        8,
        lambda o: o.strip().lower().startswith("docs"),
    ),
    (
        "json_extract",
        'Extract JSON with keys "package", "old", "new" from this text. Output only JSON.\n\n'
        "Text: Bump numpy from 1.26.4 to 2.0.1",
        48,
        _json_ok,
    ),
    (
        "log_failure_long",
        "Here is a CI log. Which test failed? Answer with the test id only.\n\n" + _long_log(),
        32,
        lambda o: "test_roundtrip_png" in o,
    ),
    (
        "release_notes",
        "Write exactly 3 bullet points (each starting with '- ') summarizing this change for release notes: "
        "'Added a camera discovery API, fixed a crash when a USB camera is unplugged, and dropped Python 3.9 support.'",
        96,
        lambda o: sum(1 for ln in o.splitlines() if ln.strip().startswith(("-", "*"))) >= 3,
    ),
]


def load_backend(backend: str, path: str, file: str | None, dtype: str):
    """Return a `generate(prompt, max_new_tokens) -> str` callable."""
    threads = os.cpu_count() or 1
    if backend == "ov":
        import openvino_genai as ov

        pipe = ov.LLMPipeline(path, "CPU")

        def gen(prompt: str, n: int) -> str:
            res = pipe.generate(prompt, max_new_tokens=n, do_sample=False, apply_chat_template=False)
            return res.texts[0] if hasattr(res, "texts") else str(res)

        return gen
    if backend == "hf":
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        torch.set_num_threads(threads)
        tok = AutoTokenizer.from_pretrained(path)
        model = AutoModelForCausalLM.from_pretrained(path, dtype=getattr(torch, dtype)).eval()

        def gen(prompt: str, n: int) -> str:
            ids = tok(prompt, return_tensors="pt")
            with torch.inference_mode():
                out = model.generate(**ids, max_new_tokens=n, do_sample=False)
            return tok.decode(out[0, ids["input_ids"].shape[1] :], skip_special_tokens=True)

        return gen
    if backend == "gguf":
        from llama_cpp import Llama

        llm = Llama(model_path=str(Path(path) / file), n_ctx=4096, n_threads=threads, verbose=False)

        def gen(prompt: str, n: int) -> str:
            llm.reset()  # llama.cpp reuses the KV prefix otherwise, which would hide prefill cost
            toks = llm.tokenize(prompt.encode(), add_bos=False, special=True)
            return llm(toks, max_tokens=n, temperature=0.0)["choices"][0]["text"]

        return gen
    raise SystemExit(f"unknown backend {backend}")


def cmd_run(a: argparse.Namespace) -> None:
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer

    t0 = time.perf_counter()
    path = snapshot_download(a.repo, allow_patterns=[a.file] if a.file else None)
    download_s = time.perf_counter() - t0

    tok = AutoTokenizer.from_pretrained(a.tokenizer)
    prompts = {
        name: tok.apply_chat_template([{"role": "user", "content": p}], tokenize=False, add_generation_prompt=True, enable_thinking=False)
        for name, p, _, _ in TASKS
    }

    t0 = time.perf_counter()
    gen = load_backend(a.backend, path, a.file, a.dtype)
    load_s = time.perf_counter() - t0

    gen(prompts["commit_ci"], 4)  # warmup: kernel compilation, allocator, page cache

    tasks = []
    for name, _, max_new, check in TASKS:
        prompt, ttfts, tps, out, n_new = prompts[name], [], [], "", 0
        for _ in range(a.repeats):
            t0 = time.perf_counter()
            gen(prompt, 1)
            ttft = time.perf_counter() - t0
            t0 = time.perf_counter()
            out = gen(prompt, max_new)
            total = time.perf_counter() - t0
            n_new = len(tok(out, add_special_tokens=False)["input_ids"])
            ttfts.append(ttft)
            if n_new > 1 and total > ttft:
                tps.append((n_new - 1) / (total - ttft))
        tasks.append(
            {
                "name": name,
                "prompt_tokens": len(tok(prompt, add_special_tokens=False)["input_ids"]),
                "new_tokens": n_new,
                "ttft_s": ttfts,
                "decode_tps": tps,
                "passed": bool(check(out)),
                "output": out[:300],
            }
        )
        print(f"[{a.label}] {name}: ttft={statistics.median(ttfts):.2f}s tps={statistics.median(tps) if tps else float('nan'):.1f} pass={tasks[-1]['passed']}", flush=True)

    rec = {
        "label": a.label,
        "backend": a.backend,
        "repo": a.repo,
        "round": a.round,
        "download_s": download_s,
        "load_s": load_s,
        "peak_rss_mb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,  # Linux: KiB
        "cpus": os.cpu_count(),
        "machine": platform.processor() or platform.machine(),
        "tasks": tasks,
    }
    with open(a.out, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def cmd_report(a: argparse.Namespace) -> None:
    recs = defaultdict(list)
    for line in Path(a.inp).read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        recs[r["label"]].append(r)

    rows = {}
    for label, rs in recs.items():
        tasks = [t for r in rs for t in r["tasks"]]
        long_ttft = [x for t in tasks if t["name"] == "log_failure_long" for x in t["ttft_s"]]
        short_ttft = [x for t in tasks if t["name"] != "log_failure_long" for x in t["ttft_s"]]
        rows[label] = {
            "load_s": statistics.median(r["load_s"] for r in rs),
            "ttft_short": statistics.median(short_ttft),
            "ttft_long": statistics.median(long_ttft),
            "tps": statistics.median(x for t in tasks for x in t["decode_tps"]),
            "rss": max(r["peak_rss_mb"] for r in rs),
            "acc": sum(t["passed"] for t in tasks) / len(tasks),
            "n": len(rs),
        }

    base = rows.get(a.baseline)
    out = [
        f"| backend | rounds | load s | TTFT short s | TTFT long s | decode tok/s | peak RSS MB | pass rate |{' decode vs ' + a.baseline + ' |' if base else ''}",
        f"|---|---|---|---|---|---|---|---|{'---|' if base else ''}",
    ]
    for label, r in rows.items():
        rel = f" {r['tps'] / base['tps']:.2f}x |" if base else ""
        out.append(
            f"| {label} | {r['n']} | {r['load_s']:.1f} | {r['ttft_short']:.2f} | {r['ttft_long']:.2f} | "
            f"{r['tps']:.2f} | {r['rss']:.0f} | {r['acc']:.0%} |{rel}"
        )
    print("\n".join(out))


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--backend", choices=["ov", "hf", "gguf"], required=True)
    r.add_argument("--repo", required=True)
    r.add_argument("--file", help="GGUF file name inside the repo")
    r.add_argument("--dtype", default="bfloat16", help="torch dtype for the hf backend")
    r.add_argument("--tokenizer", default="Qwen/Qwen3-4B")
    r.add_argument("--repeats", type=int, default=3)
    r.add_argument("--round", type=int, default=1)
    r.add_argument("--out", default="results.jsonl")
    r.set_defaults(fn=cmd_run)

    g = sub.add_parser("report")
    g.add_argument("--in", dest="inp", default="results.jsonl")
    g.add_argument("--baseline")
    g.set_defaults(fn=cmd_report)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
