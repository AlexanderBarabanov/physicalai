#!/usr/bin/env python
"""Prepare every model artifact used by the CPU LLM benchmark.

Layout produced under --models-dir (default ./models):
    hf_base/                              original HF weights (PyTorch baseline, export source)
    ov_ir_int4/                           prebuilt OpenVINO IR INT4 (OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov)
    qwen2.5-1.5b-instruct-q4_k_m.gguf     shared by openvino_gguf, llama.cpp and Ollama
    prompts.json                          16 unique-start variants each of a 32 and a 512 token prompt
Plus ./Modelfile and the `qwen-bench` model registered in Ollama.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from common import (
    GGUF_FILE,
    GGUF_REPO,
    HF_MODEL,
    OLLAMA_TAG,
    OV_REPO,
    PROMPT_TOKENS,
    ensure_disk,
    ollama_env,
    start_ollama_server,
    stop_ollama_server,
)

LEADS = (
    "Note", "Report", "Memo", "Essay", "Draft", "Brief", "Review", "Article",
    "Summary", "Guide", "Paper", "Study", "Letter", "Journal", "Digest", "Bulletin",
)
SHORT_SOURCE = (
    "The history of computing spans centuries, from early mechanical calculators to modern processors. "
    "In this essay we will examine how engineers made computers faster, smaller and cheaper, and why "
)
LONG_SOURCE = (
    "Modern language models are trained on large text corpora and then deployed on a wide range of hardware. "
    "On a CPU, inference speed is governed by two different bottlenecks. During prompt processing the model "
    "multiplies large matrices of tokens against the weights, which keeps the vector units busy and makes the "
    "work compute bound. During generation each new token needs every weight to be read from memory once, so "
    "the work becomes limited by memory bandwidth instead. Quantization reduces the number of bytes that have "
    "to be streamed per token, which is why four bit weights usually generate faster than sixteen or "
    "thirty-two bit weights even when the arithmetic itself is not any cheaper. Runtimes differ in how well "
    "their kernels use instruction set extensions such as AVX2, AVX-512, VNNI and AMX, in how they schedule "
    "threads across cores, and in how much overhead they add around the core loop. A fair comparison therefore "
    "needs identical prompts, identical decoding settings and a clear definition of every metric. "
)


def run(cmd: list[str], **kwargs) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)  # noqa: S603


def download_base(models_dir: Path, hf_model: str) -> Path:
    from huggingface_hub import snapshot_download

    target = models_dir / "hf_base"
    snapshot_download(
        repo_id=hf_model,
        local_dir=target,
        allow_patterns=["*.safetensors", "*.json", "merges.txt", "vocab.json", "tokenizer*"],
    )
    return target


def download_openvino_int4(out_dir: Path) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(repo_id=OV_REPO, local_dir=out_dir)


def download_gguf(models_dir: Path) -> Path:
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(repo_id=GGUF_REPO, filename=GGUF_FILE, local_dir=models_dir)
    return Path(path)


def build_prompts(base_dir: Path, out_file: Path) -> None:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(base_dir)
    prompts = {}
    for name, source in (("short", SHORT_SOURCE), ("long", LONG_SOURCE)):
        target = PROMPT_TOKENS[name]
        variants = []
        for lead in LEADS:
            # A different first word per variant means no engine can reuse a cached prefix between calls.
            ids = tok(f"{lead}: " + source * (target // 20 + 2), add_special_tokens=False)["input_ids"]
            text, count = None, 0
            # Decode/encode is not always a perfect round trip, so back off until the count matches.
            for cut in range(target, target - 16, -1):
                candidate = tok.decode(ids[:cut])
                count = len(tok(candidate, add_special_tokens=False)["input_ids"])
                text = candidate
                if count == target:
                    break
            variants.append({"text": text, "tokens": count})
        counts = sorted({v["tokens"] for v in variants})
        prompts[name] = {"target_tokens": target, "variants": variants}
        print(f"[prompt] {name}: {len(variants)} variants, token counts {counts} (target {target})", flush=True)
    out_file.write_text(json.dumps(prompts, indent=2), encoding="utf-8")


def register_ollama(models_dir: Path, tag: str, log_dir: Path) -> None:
    if shutil.which("ollama") is None:
        msg = "ollama binary not found on PATH (use --skip-ollama to skip)"
        raise FileNotFoundError(msg)
    modelfile = models_dir.resolve().parent / "Modelfile"
    modelfile.write_text(f"FROM ./{models_dir.name}/{GGUF_FILE}\n", encoding="utf-8")
    server = start_ollama_server(log_dir / "ollama-create.log")
    try:
        run(["ollama", "create", tag, "-f", str(modelfile)], env=ollama_env(), cwd=modelfile.parent)
        run(["ollama", "list"], env=ollama_env())
    finally:
        stop_ollama_server(server)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    parser.add_argument("--hf-model", default=HF_MODEL)
    parser.add_argument("--ollama-tag", default=OLLAMA_TAG)
    parser.add_argument("--skip-ollama", action="store_true")
    args = parser.parse_args()

    models_dir: Path = args.models_dir
    models_dir.mkdir(parents=True, exist_ok=True)

    ensure_disk()
    base_dir = download_base(models_dir, args.hf_model)
    download_openvino_int4(models_dir / "ov_ir_int4")
    ensure_disk()
    download_gguf(models_dir)
    build_prompts(base_dir, models_dir / "prompts.json")
    ensure_disk()
    if not args.skip_ollama:
        register_ollama(models_dir, args.ollama_tag, args.log_dir)

    print("\n=== models ===")
    for path in sorted(models_dir.iterdir()):
        size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else path.stat().st_size
        print(f"{path.name:45s} {size / 1e6:9.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
