"""Shared helpers for the CPU LLM benchmark (hardware info, disk guard, Ollama daemon, prompts)."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from importlib import metadata
from pathlib import Path

import psutil

HF_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
OV_REPO = "OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov"
GGUF_REPO = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
GGUF_FILE = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
OLLAMA_TAG = "qwen-bench"
OLLAMA_HOST = "127.0.0.1:11435"
PROMPT_TOKENS = {"short": 32, "long": 512}

ISA_FLAGS = (
    "sse4_2",
    "avx",
    "avx2",
    "fma",
    "f16c",
    "avx_vnni",
    "avx512f",
    "avx512bw",
    "avx512vl",
    "avx512_vnni",
    "avx512_bf16",
    "amx_tile",
    "amx_int8",
    "amx_bf16",
)

PACKAGES = (
    "openvino",
    "openvino-genai",
    "openvino-tokenizers",
    "torch",
    "transformers",
    "llama-cpp-python",
    "psutil",
    "huggingface-hub",
)


def _run_text(cmd: list[str], timeout: float = 30) -> str:
    try:
        return subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, check=False, timeout=timeout
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def hardware_info() -> dict:
    """Collect CPU model, ISA flags, vCPU count and RAM."""
    lscpu = _run_text(["lscpu"]) if shutil.which("lscpu") else ""
    model = next(
        (line.split(":", 1)[1].strip() for line in lscpu.splitlines() if line.startswith("Model name")),
        platform.processor() or "unknown",
    )
    cpuinfo_flags: set[str] = set()
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(errors="replace").splitlines():
            if line.startswith("flags"):
                cpuinfo_flags = set(line.split(":", 1)[1].split())
                break
    vm = psutil.virtual_memory()
    return {
        "cpu_model": model,
        "vcpus": os.cpu_count(),
        "ram_total_gb": round(vm.total / 1024**3, 2),
        "ram_available_gb": round(vm.available / 1024**3, 2),
        "disk_free_gb": round(free_gb(), 2),
        "isa_flags": {flag: flag in cpuinfo_flags for flag in ISA_FLAGS},
        "os": platform.platform(),
        "python": platform.python_version(),
        "lscpu": lscpu,
    }


def package_versions() -> dict:
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    if shutil.which("ollama"):
        versions["ollama"] = _run_text(["ollama", "--version"]) or None
    return versions


def print_hardware(info: dict) -> None:
    on = [f for f, v in info["isa_flags"].items() if v]
    off = [f for f, v in info["isa_flags"].items() if not v]
    print("=== Hardware ===", flush=True)
    print(info["lscpu"] or f"CPU: {info['cpu_model']}", flush=True)
    print(f"CPU model : {info['cpu_model']}", flush=True)
    print(f"vCPUs     : {info['vcpus']}", flush=True)
    print(f"RAM total : {info['ram_total_gb']} GB (available {info['ram_available_gb']} GB)", flush=True)
    print(f"Disk free : {info['disk_free_gb']} GB", flush=True)
    print(f"ISA yes   : {', '.join(on) or '-'}", flush=True)
    print(f"ISA no    : {', '.join(off) or '-'}", flush=True)


def free_gb(path: str | Path = ".") -> float:
    return shutil.disk_usage(path).free / 1e9


def ensure_disk(min_free_gb: float = 3.0, path: str | Path = ".") -> float:
    """Delete the Hugging Face and pip caches when free disk drops below the threshold."""
    free = free_gb(path)
    if free >= min_free_gb:
        return free
    print(f"[disk] only {free:.1f} GB free (< {min_free_gb} GB); purging HF and pip caches", flush=True)
    hf_home = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
    hub = Path(os.environ.get("HF_HUB_CACHE", hf_home / "hub"))
    for cache in (hub, hf_home / "xet", hf_home / "assets"):
        shutil.rmtree(cache, ignore_errors=True)
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pip", "cache", "purge"], check=False, capture_output=True, timeout=120
    )
    free = free_gb(path)
    print(f"[disk] {free:.1f} GB free after cleanup", flush=True)
    return free


def load_prompts(models_dir: Path) -> dict:
    return json.loads((models_dir / "prompts.json").read_text(encoding="utf-8"))


def ollama_env(threads: int | None = None) -> dict:
    env = os.environ.copy()
    env.update({
        "OLLAMA_HOST": OLLAMA_HOST,
        "OLLAMA_NUM_PARALLEL": "1",
        "OLLAMA_MAX_LOADED_MODELS": "1",
        "OLLAMA_KEEP_ALIVE": "30m",
    })
    if threads:
        env["OMP_NUM_THREADS"] = str(threads)
    return env


def ollama_url(path: str) -> str:
    return f"http://{OLLAMA_HOST}{path}"


def start_ollama_server(log_path: Path, threads: int | None = None, timeout: float = 90) -> subprocess.Popen:
    """Start `ollama serve` on a private port and wait until the API answers."""
    exe = shutil.which("ollama")
    if exe is None:
        msg = "ollama binary not found on PATH"
        raise FileNotFoundError(msg)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log:
        proc = subprocess.Popen(  # noqa: S603
            [exe, "serve"], env=ollama_env(threads), stdout=log, stderr=subprocess.STDOUT
        )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            msg = f"ollama serve exited early with code {proc.returncode}; see {log_path}"
            raise RuntimeError(msg)
        try:
            with urllib.request.urlopen(ollama_url("/api/version"), timeout=2):  # noqa: S310
                return proc
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    stop_ollama_server(proc)
    msg = f"ollama serve did not become ready within {timeout}s; see {log_path}"
    raise TimeoutError(msg)


def stop_ollama_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=15)
