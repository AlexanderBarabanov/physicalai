# CPU LLM inference benchmark

Compares CPU inference of `Qwen/Qwen2.5-1.5B-Instruct` on a GitHub-hosted `ubuntu-latest` runner (4 vCPUs, 16 GB RAM, ~14 GB disk) across:

| Engine key | Engine | Weights |
|---|---|---|
| `openvino_ir_int4` | OpenVINO GenAI | Prebuilt [OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov](https://huggingface.co/OpenVINO/Qwen2.5-1.5B-Instruct-int4-ov) |
| `openvino_gguf` | OpenVINO GenAI GGUF reader | `qwen2.5-1.5b-instruct-q4_k_m.gguf` |
| `pytorch_cpu` | `transformers` + `torch` | Original weights, FP32 (or BF16) |
| `llama_cpp` | `llama-cpp-python` | `qwen2.5-1.5b-instruct-q4_k_m.gguf` |
| `ollama` | Ollama daemon, local HTTP API | The same GGUF file, registered as `qwen-bench` |

The 1.5B model is used because Intel publishes a prebuilt INT4 OpenVINO IR for it; there is none for 0.5B, and exporting on the runner with `optimum-cli` failed.

## Files

- [prepare_models.py](prepare_models.py): downloads the base model, the prebuilt OpenVINO INT4 IR and the GGUF, builds the 32 and 512 token prompts, writes `Modelfile` and runs `ollama create qwen-bench`.
- [benchmark.py](benchmark.py): runs every engine in its own subprocess and writes `results.json` and `results.md`.
- [common.py](common.py): hardware report, disk guard, Ollama daemon helpers.
- [../../.github/workflows/cpu-llm-benchmark.yml](../../.github/workflows/cpu-llm-benchmark.yml): CI workflow.

## Run in CI

The workflow runs on `workflow_dispatch` and on pushes that touch `benchmarks/cpu-llm/**` or the workflow file. The Markdown report is appended to the job summary and `results.json`, `results.md` and the Ollama logs are uploaded as the `cpu-llm-benchmark-results` artifact.

## Run locally (Linux x86_64)

```bash
cd benchmarks/cpu-llm
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install openvino-genai transformers psutil tabulate huggingface_hub
CMAKE_ARGS="-DGGML_NATIVE=ON" python -m pip install llama-cpp-python
# install Ollama from https://ollama.com/download

python prepare_models.py            # add --skip-ollama if Ollama is not installed
python benchmark.py                 # all engines
python benchmark.py --engines llama_cpp ollama --runs 5
```

Useful options: `--threads N` (default: all vCPUs, applied to PyTorch, llama.cpp and Ollama), `--torch-dtype bfloat16`, `--timeout SECONDS` per engine, `--strict` to exit non-zero if any engine fails.

Ollama listens on `127.0.0.1:11435` so it does not collide with a system Ollama on `11434`. The benchmark starts and stops its own `ollama serve`; the `qwen-bench` model lives in `~/.ollama`.

## Protocol

- Greedy decoding (`temperature=0`, top-k 1, repetition penalty 1.0, fixed seed), 128 new tokens.
- Two prompts with identical text for every engine: ~32 tokens (decode-dominated) and ~512 tokens (prefill-dominated). No chat template is applied.
- 1 discarded warmup plus 3 measured runs per prompt; Mean and StdDev (sample) are reported.
- Each engine runs in a fresh subprocess, so memory is returned to the OS between engines. If free disk falls below 3 GB the Hugging Face and pip caches are deleted.
- The CPU model (`lscpu`), ISA flags (AVX2, AVX-512, VNNI, AMX), vCPU count and RAM are printed at the start and stored in `results.json`.

EOS handling: OpenVINO uses `ignore_eos`, PyTorch uses `min_new_tokens`, llama.cpp bans the EOS tokens through `logit_bias`. Ollama has no equivalent option, so the number of generated tokens is recorded and flagged in the report when it differs from 128.

Ollama keeps a KV prefix cache, so a short decoy request precedes every timed request to prevent the prefill from being skipped. Runs where `prompt_eval_count` is below 90% of the prompt length are flagged `prompt_cache_suspected`.

## Metrics

| Metric | Definition | How it is measured |
|---|---|---|
| Load (ms) | Cold-start time to get weights into memory. Python imports are excluded. | OpenVINO: `LLMPipeline(...)`. PyTorch: tokenizer + `from_pretrained`. llama.cpp: `Llama(...)`. Ollama: empty-prompt request that loads the model; `server_start_ms` is stored separately. |
| TTFT (ms) | Request submission to first generated token. | OpenVINO: `perf_metrics.get_ttft().mean`. PyTorch: `TextIteratorStreamer` subclass timestamping each `put()` with `time.perf_counter()` (first token, not first text chunk, since the stock streamer buffers until a word boundary). llama.cpp / Ollama: first non-empty streamed chunk. |
| TPOT (ms/token) | `(E2E - TTFT) / (generated_tokens - 1)` | Derived from the two above. |
| Throughput (tok/s) | `1000 / TPOT` | Derived. |
| E2E (ms) | Wall time of the whole request, including tokenization. | `time.perf_counter()` around the call. |
| Peak RSS (MB) | Highest resident set size. | `psutil` sampling every 10 ms (and `ru_maxrss` for the engine process). Ollama: client process plus `ollama serve` and its runner children. Reported per prompt phase; `peak_rss_mb` in `results.json` is the whole-run peak. |
| Native TTFT / TPOT | Cross-check from the engine itself. | OpenVINO `PerfMetrics`; llama.cpp perf context (`t_p_eval_ms`, `t_eval_ms / n_eval`); Ollama `prompt_eval_duration`, `eval_duration / eval_count`. |

## Interpreting results

- **TTFT on the long prompt** measures prefill. It is compute-bound, so it separates engines by kernel quality and use of AVX-512, VNNI and AMX.
- **TPOT / throughput on the short prompt** measures decode. It is memory-bandwidth-bound, so 4-bit engines should beat FP32 PyTorch by a large factor, and the three GGUF engines should be close to each other.
- **E2E** is the user-visible latency. **Peak RSS** shows the memory cost of precision and runtime overhead; memory-mapped weights count once touched.
- Differences between `openvino_ir_int4` and the GGUF engines mix engine speed with quantization scheme (NNCF INT4 vs Q4_K_M); output text can differ.
- GitHub-hosted runners are shared VMs. Compare engines within one run, check StdDev, and do not compare absolute numbers across different CPU models.

## `results.json` layout

```text
timestamp, environment{cpu_model, vcpus, ram_total_gb, isa_flags, lscpu, ...}, versions, config
engines.<key>: status, load_ms, load_extra, rss_after_load_mb, peak_rss_mb, details,
               prompts.<short|long>: runs[...], stats{ttft_ms, tpot_ms, throughput_tps, e2e_ms, ... {mean, stdev}}, peak_rss_mb
```

A failed engine (for example the OpenVINO GGUF reader not supporting the model on the installed version) is recorded with `status: "failed"` and the traceback, and does not stop the other engines.
