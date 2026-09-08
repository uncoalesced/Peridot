# Changelog

**Engineered by uncoalesced**

All notable changes to the Peridot Sovereign Kernel are documented in this file.

---

## [post-v1.5.4f] - 2026-08-20

**Release Summary:** Chat Ledger Degenerate Feedback Loop Remediation & Response Contract Alignment

### Root Cause Analysis

- **Model generation failures were unrelated to quantization degradation:** Investigations in `[post-v1.5.4e]` treated empty or `<think>`-only completions as instruction-following degradation in `Qwen3.8-27B-UD-IQ1_S` (~1.56 bits/weight). Session audit logs contradict this: failing turns logged explicit premature stop conditions (`Tokens: 0` to `Tokens: 3`) against a 1024-token generation budget. A model degraded by extreme quantization emits random or ungrounded token sequences; immediate cessation indicates a stop-condition signal rather than a loss of reasoning capacity. Consistent `MEMORY MISS` and `L1 MISS` events on failing turns, paired with zero `[ZAT-SCS] Predictive preemption hit!` log entries, also eliminated speculative KV prefetching and semantic cache corruption as contributing factors.
- **Degenerate feedback loop via persisted conversational ledger:** Inspection of `storage/chat_ledger.db` revealed that failing turns occurred when the model generated a complete `[ANALYSIS]` block terminating at an empty `[KERNEL_RESPONSE]` header (~50 tokens matching system prompt boilerplate). `core.py` persisted this raw output—including reasoning scaffolding—directly into the ledger. Subsequent generation requests in `server.py` re-injected the trailing 6 turns into the prompt context. Presenting the model with historical turns terminating at an empty header prompted it to replicate the pattern deterministically. This explains why failures did not correlate with query complexity (e.g., basic arithmetic failed while complex physics queries succeeded) and why outcomes shifted as the 12-message sliding window advanced.
- **Formatting fallback obscured the defect:** `server.py` previously wrapped missing `[ANALYSIS]` tags in boilerplate headers (`[ANALYSIS]\nEnforced kernel formatting fallback.\n\n[KERNEL_RESPONSE]\n{final_response}`). When given an unclosed `<think>` fragment, this generated a syntactically valid structure with an empty body. Downstream components could not differentiate valid responses from empty completions, causing `ui.py` to split on `[KERNEL_RESPONSE]` and render empty chat turns without surfacing errors.

### Fixed

- **Unified response contract in `constitution.py`:** Added `strip_reasoning()`, `parse_kernel_response()`, and `format_kernel_response()` adjacent to kernel prompt definitions. This establishes a single source of truth for response parsing across `server.py` and `core.py`, and properly sanitizes unclosed `<think>` reasoning tails before storage.
- **Empty response detection and retries in `server.py`:** Completions are now parsed structurally rather than matched via string checks. If an assistant turn returns an empty body, the request is automatically retried once with prompt scaffolding pre-seeded into the assistant turn (`<think>\n\n</think>\n\n[ANALYSIS]\n...\n\n[KERNEL_RESPONSE]\n`), preventing premature termination on header tokens. If generation remains empty, the engine returns an explicit `[KERNEL FAULT]` rather than silent whitespace.
- **Structured output telemetry in `server.py`:** Added comprehensive generation logging (`RAW_OUTPUT | <tag> | finish=<reason> | prompt_tokens=N | budget=N | text=<repr>`). Recording `finish_reason` alongside token counts enables clear differentiation between context budget exhaustion and premature stop tokens.
- **Scaffolding isolation in `core.py`:** Chat persistence now extracts and records only the parsed answer body. Internal `[ANALYSIS]` blocks and `<think>` reasoning chains are excluded from `storage/chat_ledger.db`, preventing internal scaffolding from re-entering the prompt context.
- **History sanitization in `chat_ledger.py`:** Updated `get_history()` to filter out historical assistant turns that contain empty bodies along with their corresponding user turns. This preserves strict user/assistant alternation and neutralizes historical corrupted records (135 existing rows) without requiring manual database truncation.
- **Sampling parameter defaults in `config.py`:** Updated default decoding parameters to align with thinking model requirements (`TEMPERATURE` 0.1 -> 0.6, `TOP_P` 0.9 -> 0.95, `TOP_K` = 20) and passed them through `server.py`. Near-greedy sampling previously made the feedback loop deterministic by removing the entropy required to escape repetitive output patterns. All parameters remain configurable via environment variables.
- **FAISS property compatibility in `command_router.py`:** Aliased `ntotal` to `size` on `IdMapIndex`. Resolves `'IdMapIndex' object has no attribute 'ntotal'` crashes when executing `status` and `ingest` commands.
- **Session resumption bounds in `server.py`:** Configured `_ensure_active_session()` to respect `SESSION_RESUME_WINDOW_S` (default 6 hours). Previously, the engine unconditionally resumed the most recent session from `list_sessions(limit=1)`, permanently locking restarts into a single June development session (`55a71b3f`). Implemented `_autotitle_session()` to name new sessions based on their initial user prompt.
- **Explicit failure reporting in `ui.py`:** Blank parsing results now render an explicit `[KERNEL FAULT]` notice pointing to `RAW_OUTPUT` in the console logs, eliminating silent rendering failures.
- **Model selector window dismissal in `ui.py`:** Added `<FocusOut>` binding to withdraw the `ttk::combobox::PopdownWindow` toplevel when the main application window loses focus, preventing the dropdown from floating over other desktop windows during Alt-Tab switching.

### Changed

- **Metrics interpretation clarification:** Clarified that `Kernel Panics: 1` and `Avg Handoff Latency: 1483.37ms` recorded in `logs/stability_metrics.json` represent lifetime aggregate counters across 280 handoffs and 218 inferences, rather than session-specific regressions. `ghost_audit.log` shows zero panic events, and recorded handoff latencies (~2000ms) reflect external Folding@home client release polling reaching the 20-iteration/100ms timeout in `server.py`.

### Testing

- Added `tests/test_response_contract.py` containing 7 test cases validating response parsing against corrupted strings extracted from historical databases, as well as history sanitization filters. All tests pass alongside existing test suites (`tests/test_turbovec_index.py` and `tests/test_vault.py`).

### Known Limitations

- Changes have been validated against recorded failure data, historical ledger entries, and automated unit tests, but await validation under a fresh physical hardware session.
- `scripts/build_llama_cpp_python.ps1` remains unexecuted; testing was conducted against the packaged `llama_cpp_python==0.3.23` wheel and `IQ1_S` quantization.

---

## [post-v1.5.4e] - 2026-08-20

**Release Summary:** Model Support Audit — Metadata-Driven Chat Template Resolution

### Changed

- **GGUF metadata model inspection:** Replaced filename heuristic checks with direct inspection of GGUF headers (`general.architecture` and `tokenizer.ggml.pre`) using `llama.cpp/gguf-py`. Audited all 8 local models; confirmed 4 Llama-family models (`arch=llama, vocab_pre=llama-bpe`) and 2 Qwen2.5 models (`arch=qwen2, vocab_pre=qwen2`) correctly map to expected templates.
- **Dynamic chat template dispatch in `constitution.py`:** `get_model_format()` now inspects `tokenizer.ggml.pre` via `_read_gguf_metadata()` (cached by path) and resolves against `_VOCAB_PRE_TO_FORMAT`. Substring matching (`"llama"` / `"mistral"`) is preserved strictly as a fallback when headers cannot be read.

### Fixed

- **Mistral-Nemo chat template resolution:** Fixed an issue where `Mistral-Nemo-Instruct-2407-Q4_K_M.gguf` defaulted to ChatML (`<|im_start|>` / `<|im_end|>`) because its filename lacked `"llama"` or `"qwen"`. The model specifies `arch=llama, vocab_pre=tekken`, requiring Mistral V3-Tekken formatting (`[INST] ... [/INST]`). Added explicit Mistral formatting support across `constitution.py` (`get_chat_template`), context compilation in `builder.py` (`build_full_context`), and stop token definitions in `server.py`.
- Verified template resolution against all 8 on-disk GGUF files; `Mistral-Nemo-Instruct-2407-Q4_K_M.gguf` successfully returns `mistral` while other formats remain unaffected.

### Known Limitations

- Mistral template syntax and stop tokens (`</s>`) match official V3-Tekken specifications, but have not yet been validated via live inference runs on hardware.
- Native `<think>` handling for Qwen3.5 remains unhandled in prompt builders.
- `get_assistant_start()` and `get_stop_tokens()` utility functions remain unused in `server.py` and `builder.py` in favor of inline token definitions.

---

## [post-v1.5.4d] - 2026-08-20

**Release Summary:** Multi-Token Prediction (MTP) Build Infrastructure for Qwen3.8-27B

### Root Cause Analysis

- **Model load failure traced to runtime support gap:** Verified that the `missing tensor 'blk.64.ssm_conv1d.weight'` error encountered when loading `Qwen3.8-27B-UD-Q2_K_XL.gguf` was neither a truncated download nor a VRAM allocation failure. The vendored `llama.cpp` checkout (`commit 715b86a3`) supports the `qwen35` architecture and its Multi-Token Prediction (MTP) head (`src/models/qwen35.cpp`), loading block 64 via `load_block_mtp()` without requiring `ssm_conv1d`. However, the installed pre-built `llama_cpp_python==0.3.23` wheel predates upstream qwen35 support and fails to recognize MTP layers.

### Added

- **Local compilation script `scripts/build_llama_cpp_python.ps1`:** Added build automation to clone `abetlen/llama-cpp-python`, substitute the bundled `vendor/llama.cpp` submodule with the repository's updated checkout, and compile locally with `GGML_CUDA=on`.
- Documented the `llama_cpp_python==0.3.23` entry in `requirements.txt` as a temporary PyPI fallback pending local CUDA compilation.

### Known Limitations

- The compilation script requires Visual Studio Build Tools and the CUDA Toolkit; compilation has not yet been executed on the host. Hardware validation and VRAM layer derivation for Qwen3.8-27B remain pending.

---

## [post-v1.5.4c] - 2026-08-20

**Release Summary:** Documentation Version Synchronization and Repository Cleanup

### Changed

- **Version alignment across project assets:** Synchronized stale references from v1.5.3 to v1.5.4 across `README.md`, `SECURITY.md`, `docs/architecture/RUNTIME_GUARANTEES.md`, `docs/architecture/v1.5_memory_flow.md`, `docs/markdowns/CONTRIBUTING.md`, `docs/markdowns/MEDICAL_RESEARCH_INTEGRATION.md`, `requirements.txt`, and `cowork/PERIDOT_TRACKER.md`. Historical release records and fixed dependency pins (`joblib==1.5.3`) were preserved.
- **Documentation restructuring:** Updated `README.md` to properly frame ZAT-SCS as a core architectural subsystem in v1.5.4 rather than a past milestone. Aligned the roadmap section with the Frontier Roadmap milestones (v1.6.x multi-engine providers and TurboVec memory, v1.7.x sandboxed REPL and sovereign web gateway, v1.8.x React WebUI).
- **Format standardization:** Replaced emoji glyphs in the Hardware Support matrix with standard markdown badges and text labels.
- **Codebase comment audit:** Audited first-party source trees (`core_system/`, `config.py`, `server.py`, `setup.py`, `ui.py`, `benchmarking/`, `tests/`) to ensure comments remain technical and concise.

### Notes

- Historical `Co-Authored-By` commit trailers from past development cycles were analyzed in Git history. Modifying historical contributor entries would require an interactive rebase and force push, and has been intentionally omitted to preserve commit hash integrity.

---

## [post-v1.5.4b] - 2026-08-20

**Release Summary:** Benchmark Methodology Rectification & Inference Provider Abstraction

### Performance

- **Correction of previously reported inference throughput:** The 62.38 t/s throughput previously reported for `Qwen2.5-14B-Instruct-Q4_K_M.gguf` was determined to be an artifact of benchmark design rather than actual inference speed. `benchmark_inference.py` utilized static prompts across iterations; after the initial turn, `server.py` served cached completions directly from the Layer 1 semantic cache. Logging revealed 3 actual GPU inferences alongside 30 cache hits, yielding an actual decode rate of **4.00 t/s median** (mean 4.03, stdev 0.21, range 3.81-4.27, prefill 23.83 t/s) on an RTX 5050 Laptop GPU. The historical 39 t/s baseline was measured under the same conditions and is similarly retracted as an evaluation baseline.
- **Dedicated benchmark utility `benchmarking/benchmark_decode_rate.py`:** Introduced an isolated benchmarking tool targeting the provider interface directly without HTTP, caching, or RAG layers, using tokenizer token counts and unique prompt sets to measure true decode speed.
- Updated `benchmark_inference.py` documentation to clarify that it evaluates end-to-end request turnaround latency rather than raw generation throughput.

### Added

- **Inference provider abstraction (`BaseInferenceProvider`):** Implemented an extensible provider contract defining `load()`, `unload()`, `generate_stream()`, `tokenize()`, and `ProviderCapabilities` (`engine`, `context_window`, `supports_thinking`, `supports_vision`, `supports_streaming`). Provides the architectural foundation for subsequent ExLlamaV2 and vLLM backends.
- **Concrete LlamaCpp implementation (`LlamaCppProvider`):** Wrapped `llama_cpp_python` within the provider abstraction, incorporating recoverable `ProviderLoadError` handling, engine-agnostic prefill/decode timing metrics, and GhostLogger audit integration.
- **Format-based engine registry:** Configured model routing by file extension (`.gguf` routes to `LlamaCppProvider`, with stubs for `.exl2` and `.safetensors`).

### Security

- **Elimination of test credential fallback:** Removed a legacy fallback API key (`08101954`) and console print statement from `benchmarking/api_client.py`. The client now enforces explicit environment configuration, backed by automated regression tests.

### Known Limitations

- The 25 t/s performance target for default 27B models is physically unreachable on the target 8GB RTX 5050 hardware, where a 14B model achieves 4.00 t/s across 28 offloaded layers. Acceptance criteria will be revised in v1.6.x.
- Integration of `BaseInferenceProvider` into `server.py` lifecycle and `/model/swap` routes is scheduled for the next iteration.

---

## [post-v1.5.4] - 2026-08-19

**Release Summary:** Default Model Reversion to Qwen2.5-14B

### Changed

- **Default model reversion in `config.py`:** Reverted `ACTIVE_MODEL_NAME` to `Qwen2.5-14B-Instruct-Q4_K_M.gguf`. Pending runtime support for MTP layers in the 27B model, the 14B model provides a fully validated operational baseline.
- Retained the provisional 20-layer GPU allocation table for `Qwen3.8-27B-UD-Q2_K_XL.gguf` in `_PROVISIONAL_GPU_LAYERS` (`config.py`) to prepare for future runtime updates.

### Root Cause Analysis

- Confirmed that `Qwen3.8-27B-UD-Q2_K_XL.gguf` (9,828,981,664 bytes) was intact and matching upstream sources. The `missing tensor 'blk.64.ssm_conv1d.weight'` error stems from the runtime treating block 64 as a recurrent layer rather than an MTP layer.

### Benchmarks (RTX 5050 Laptop 8GB, AMD Ryzen 7 250 AI, Windows 11)

Measured on `Qwen2.5-14B-Instruct-Q4_K_M.gguf` with `GPU_LAYERS=28`, `CONTEXT_LENGTH=4096`, 10 iterations per workload:

| Workload | Avg Tokens | Avg Time | Throughput | Std Dev |
|---|---|---|---|---|
| Short | 28 | 3.65s | 7.57 t/s | +/- 0.37 |
| Medium | 79 | 3.65s | 21.34 t/s | +/- 1.07 |
| Long | 231 | 3.66s | 62.38 t/s (median)* | +/- 3.36 |

*\*Note: The long workload throughput figure was subsequently determined to reflect L1 semantic cache hits rather than GPU execution. See entry `[post-v1.5.4b]` for verified throughput metrics.*

### Known Limitations

- The 27B model remains unbootable under `llama-cpp-python==0.3.23`. The model file has been preserved on disk as `Qwen3.8-27B-UD-Q2_K_XL.mtp-head.gguf.bak`.

---

## [v1.5.4-STABLE] - 2026-08-19

**Release Summary:** Linux System Support and Zero-Cloud Sovereignty Lock

### Added

- **Cross-platform desktop session detection:** Implemented automated session classification (`native`, `x11`, `wayland`, `headless`) in `core_system/telemetry/keyboard.py` using `sys.platform`, `XDG_SESSION_TYPE`, `$WAYLAND_DISPLAY`, and `$DISPLAY`.
- **Acoustic-only telemetry degradation under Wayland:** Under Wayland or headless environments where global keystroke interception via `pynput` is restricted by display server security policies, the telemetry engine zeroes the keystroke weighting factor (`w_key -> 0.00`). Interaction probability gracefully transitions to acoustic density tracking:
  ```text
  P(I_t) = min(1.0, P(I_{t-1}) * e^(-lambda * dt) + w_aud * g(A))
  ```
  Prevents missing hardware sensors from falsely reporting system idle states.
- **Subprocess-isolated model acquisition:** Introduced `core_system/model_fetch.py` to handle repository downloads in an isolated short-lived subprocess. Allows network access strictly for downloads while maintaining parent process network isolation.
- **Model acquisition security boundaries:** Added `is_model_download_safe()` to `core_system/security.py`, validating repository and file strings against strict character whitelists to prevent path traversal, shell injection, or extraction outside the target directory.
- **Linux platform deployment documentation:** Added comprehensive deployment guides for Debian 12, Ubuntu 22.04+, and Arch Linux in `docs/markdowns/COMMUNITY_INSTALL.md`.

### Security

- **Enforced offline network lock:** Added mandatory initialization in `config.py` setting `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` immediately following configuration loading, preventing modified `.env` files from opening external connections.
- **Boot-time offline verification:** Integrated `assert_main_process_offline()` in `server.py`, aborting boot with a critical security log if external network flags are altered.
- **Cross-platform path sanitization:** Updated `is_file_safe()` to resolve normalized literal paths alongside resolved paths. Prevents platform-specific traversal vulnerabilities and extends protections to `/sys/`, `/proc/`, and `.ssh/` across Windows and Linux.
- **Expanded security test coverage:** Added 39 automated tests in `tests/test_v154_linux_sovereignty.py` covering session classification, telemetry degradation, network isolation boundaries, and traversal blacklists (expanding the test suite to 50 tests).

### Changed

- **Resilient RAG embedding resolution:** `core_system/memory/embedder.py` now resolves embedding weights locally from `models/embeddings/all-MiniLM-L6-v2/` before attempting remote lookups.
- **Graceful RAG degradation:** Handled runtime embedding failures gracefully in `server.py`, allowing the engine to fall back to direct model inference rather than crashing if vector dependencies are absent.
- **Dynamic path resolution:** Migrated legacy path concatenation across core modules to `pathlib.Path`. Resolved third-party software directories (such as Folding@home) dynamically via environment variables.

### Known Limitations

- Linux deployment paths and security boundaries are fully covered by automated suites, but live GPU inference execution remains unverified on Linux hardware.
- Shipped default model `Qwen3.8-27B-UD-Q2_K_XL.gguf` fails to load under the pinned runtime (see `[post-v1.5.4]` for resolution).

---

## [v1.5.3-ZAT_SCS] - 2026-07-18

**Release Summary:** Zero-Overhead Active Telemetry (ZAT) & Speculative Context Streaming (SCS)

### Added

- **High-frequency telemetry daemon:** Integrated a 10Hz background sensory processing loop tracking real-time operator engagement and calculating interaction probability `P(I_t)`.
- **Asynchronous keystroke cadence monitor:** Deployed an isolated `pynput` listener utilizing a 10-event sliding window to measure typing interval acceleration `f(C)`.
- **Non-blocking acoustic envelope tracker:** Built an acoustic monitor via `sounddevice.InputStream` to capture ambient room sound and track RMS signal density `g(A)`.
- **Engagement decay-acceleration model:** Implemented dynamic temporal modeling:
  ```text
  P(I_t) = min(1.0, P(I_{t-1}) * e^(-lambda * dt) + w_key * f(C) + w_aud * g(A))
  ```
  Automatically transitions the finite state machine to `KernelState.SPECULATIVE_PREPARED` when probability meets or exceeds the 0.65 threshold.
- **Dynamic CUDA compute partitioning:** Integrated GPU workload control, throttling background compute workloads (Folding@home) to 10% Streaming Multiprocessor (SM) capacity when engagement is detected, and fully suspending background compute during inference.
- **Unified memory weight pre-mapping:** Configured `GGML_CUDA_ENABLE_UNIFIED_MEMORY=1` during speculative states to pre-map model weights into physical GPU page tables while typing, eliminating initial cold-start latency.
- **Speculative KV cache context prefetching:** Built an asynchronous background worker communicating with local runtime slots via `/slots/0/restore`, staging KV cache contexts before query submission.
- **Prefill phase bypass:** Optimized `/ask` routing in `server.py` to detect pre-staged states, bypassing VRAM purge checks and executing immediate generation to minimize Time-to-First-Token (TTFT).

### Changed

- **Telemetry architecture modularization:** Refactored `core_system/telemetry.py` into a structured package (`core_system/telemetry/`) containing dedicated configuration, orchestration, and client modules.
- Preserved `StabilityLedger` exports in package root (`__init__.py`) to maintain backward compatibility with external imports.

---

## [v1.5.2-STABLE] - 2026-06-08

**Release Summary:** Dynamic VRAM Partitioning and Stability Enhancements

### Fixed

- **Dynamic VRAM allocation heuristics:** Rewrote `_calculate_gpu_layers` in `config.py` to calculate layer offloading dynamically. Automatically routes excess layers to system RAM when model requirements exceed 75% of available VRAM, preventing out-of-memory errors on 8GB hardware.
- **FAISS ABI C-extension compatibility:** Updated `faiss-cpu` dependencies to eliminate `ValueError: input not a numpy array` exceptions resulting from ABI differences between NumPy 2.x and SWIG bindings on Windows.
- **Context window overflow protection:** Added an automated truncation handler in `server.py` that limits semantic context blocks to 8000 characters and trims conversational history when generation headroom drops below 128 tokens, preventing runtime aborts during dense document retrievals.

### Changed

- **Interface scrolling mechanics:** Refactored text rendering in `ui.py` with dynamic height calculation and sub-pixel scrolling optimization for high-refresh-rate displays.

---

## [v1.5.1-STABLE] - 2026-06-08

**Release Summary:** Security Perimeter Hardening, Dynamic VRAM Auto-Scaling, and Persistent Chat History

### Security

- **Cryptographic API key generation:** Removed legacy static authentication keys (`08101954`). `config.py` now generates a 256-bit entropy key (`secrets.token_hex(32)`) on initial setup, persisting it securely to the local `.env` configuration.
- **Deserialization vulnerability remediation (Pickle to JSON):** Replaced `pickle.load()` and `pickle.dump()` with `json.load()` and `json.dump()` for metadata serialization in `core_system/memory/vault.py`, eliminating remote code execution vectors via modified metadata files.
- **Subprocess invocation hardening:** Eliminated `shell=True` from all `subprocess.check_output()` calls targeting `nvidia-smi` in `ui.py`, passing commands via structured argument lists with window suppression flags (`0x08000000`).
- **CORS boundary restriction:** Restricted CORS headers in `server.py` to allow requests strictly from `http://127.0.0.1:5000` and `http://localhost:5000`, blocking unauthorized cross-origin requests.

### Added

- **Multi-session SQLite conversational ledger:** Implemented `core_system/chat_ledger.py`, providing persistent session management, message logging, and sliding-window history extraction (`get_history(session_id, limit=6)`). Integrated with `/ask` to maintain cross-session context continuity.
- **Dynamic VRAM discovery:** Added `_detect_total_vram_mb()` to `config.py` to inspect available GPU VRAM at boot via direct driver queries.
- **Dynamic layer and context scaling:**
  - Layer offloading: Models consuming <75% of total VRAM are fully offloaded (`GPU_LAYERS=99`); larger models use partial offloading (`GPU_LAYERS=20`), with fallback to CPU execution (`GPU_LAYERS=0`).
  - Context boundaries: Automatically assigned to 8192 tokens for >10GB VRAM, 4096 tokens for <=10GB VRAM, and 2048 tokens for CPU execution.
- **Document provenance tracking:** Enhanced `core_system/memory/vault.py` to prefix ingested text chunks with `[SOURCE DOC: {filename}]`, enabling the model to cite specific source documents during generation.
- **Structured PDF extraction:** Updated PyMuPDF integration in `core_system/memory/vault.py` to use `fitz.get_text("text", sort=True)`, preserving spatial column layouts for tabular documents.

---

## [v1.5.0-STABLE] - 2026-06-03

**Release Summary:** Split-Tensor Allocation, FSM Hardware Watchdogs, and Multi-Sector Interface

### Added

- **14B parameter model support:** Transitioned primary inference weights to `Qwen2.5-14B-Instruct-Q4_K_M.gguf`. Configured `GPU_LAYERS=20` to divide tensor computation safely between 8GB GPU memory and system RAM.
- **Direct driver VRAM monitoring:** Integrated direct NVIDIA NVML driver telemetry in `_execute_vram_purge` via `pynvml`, querying hardware-reclaimed bytes rather than cached operating system metrics before allocating tensors.
- **FSM panic safeguards:** Enforced a 7500MB VRAM hardware ceiling to prevent display driver reset events. Decreased purge activation threshold to 200MB and implemented a 2.0-second timeout that triggers a safe kernel panic state if resources fail to clear.
- **Multi-sector operator interface:** Upgraded UI to a modular `ttk.Notebook` interface divided into dedicated sectors:
  - Chat Matrix: Primary conversational and generation interface.
  - Kernel Vault: Real-time RAG ingestion and status monitor.
  - Settings: Runtime configuration and hardware parameters.
- **Administrative control console:** Added an administrative telemetry dashboard reading from `/telemetry/stability` to track finite-state-machine state, system health indicators, inference metrics, and recovery counts.
- **Background compute toggles:** Added user interface toggles mapped to `/telemetry/enable` and `/research/disable` endpoints, allowing operators to pause or resume background Folding@home processes.
- **Dynamic hardware model evaluation:** Added directory scanning to evaluate local `.gguf` file sizes against current VRAM envelopes, tagging models with compatibility ratings (`[HIGH]`, `[MEDIUM]`, `[LOW/CRITICAL]`).
- **CLI vault ingestion utility (`ingest_vault.py`):** Added a standalone CLI tool to parse, chunk, embed, and index documents directly into the FAISS index without loading the graphical interface.
- **Binary PDF extraction and expanded retrieval depth:** Upgraded PDF ingestion via PyPDF2 and increased FAISS vector retrieval from `top_k=3` to `top_k=6`.
- **Character-bounded sliding window chunking:** Replaced newline-based chunking with bounded segmenting (<800 characters) to optimize vector embedding density.
- **Automated document staging:** Ingested files are moved from `input/` to `input/processed/` automatically after indexing to prevent duplicate processing.
- **Interactive text search:** Added an in-memory search overlay (`Ctrl+F`) with match highlighting and clipboard export.

### Changed

- **Prompt hardening:** Re-engineered `build_system_prompt` to introduce strict operational constraints, restricting model answers to retrieved RAG context and preventing ungrounded knowledge bleed.

### Fixed

- **NumPy AVX2 crash resolution:** Standardized NumPy dependencies on a stable 1.x release to prevent binary ABI crashes during vector indexing.
- **Kernel startup instantiation:** Resolved a runtime `NameError` crash by instantiating `PeridotProductionKernel()` in the global scope before engine initialization.
- **Version control exclusions:** Updated `.gitignore` to exclude transient FAISS index files (`aether_cold_storage.db`).

---

## [v1.4.0-STABLE] - 2026-05-14

**Release Summary:** TurboQuant Architecture & Sovereign Runtime Finalization

### Added

- **Importance matrix quantization (I-Quants):** Integrated support for `IQ3_XXS` and FP4 model architectures, reducing active VRAM allocation overhead by ~1.5GB while improving reasoning throughput.
- **Dual runtime execution profiles:**
  - Deep Thinker: `Llama-3-8B-Instruct (IQ3_XXS)` delivering **60.5 t/s** at ~4.5GB VRAM.
  - Agile / Daily Driver: `Qwen 2.5 3B (Q4_K_M)` delivering **101.9 t/s** at ~2.7GB VRAM.
- **Interactive deployment wizard (`setup.py`):** Rebuilt setup tooling to evaluate host GPU VRAM and recommend optimal execution profiles prior to initialization.
- **Cryptographic environment initialization:** Migrated authentication setup to generate a localized 16-byte hex `API_KEY` stored within `.env`.
- **Network air-gap enforcement:** Automated injection of offline flags (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) during setup to ensure zero telemetry leakage.
- **Licensing:** Distributed officially under the MIT License.

### Changed

- **Quantization format deprecation:** Deprecated standard `Q4_K_M` quantizations for 8B models to eliminate memory bus bottlenecks on 8GB VRAM hardware.
- **Execution limits:** Set context window ceiling to 8192 tokens and generation temperature to 0.1 to maximize document retrieval fidelity.
- **WebSocket background compute handoff:** Finalized WebSocket interrupt mechanisms for background computing tasks, dispatching pause signals in ~21ms and completing VRAM recovery in under 510ms.
- **Idle timeout optimization:** Reduced `RESEARCH_IDLE_THRESHOLD` to 30 seconds to resume background scientific compute promptly after interaction concludes.
- **Dedicated CPU embedding route (Aether-Route):** Configured semantic embedding models (`all-MiniLM-L6-v2`) to run entirely on host CPU and system RAM, reserving GPU memory exclusively for generation and background workloads.
- **Documentation refresh:** Overhauled architecture diagrams, memory flow topologies, and performance benchmarks throughout project documentation.

---

## [v1.3.2-beta] - 2026-05-13

**Release Summary:** Memory Deduplication, Source Attribution & Air-Gapped Operation

### Added

- **SHA-256 memory deduplication:** Added `registry.json` tracking in `vector_store.py` to record SHA-256 hashes of indexed files, preventing duplicate embedding operations.
- **Document source attribution:** Configured RAG context injection in `server.py` to tag document blocks with `[SOURCE: filename]`, instructing the model to cite documentary sources explicitly.
- **Automated directory ingestion (`index_all.py`):** Added a batch ingestion script to process files in `input/`, evaluate duplicates, and index new content into FAISS.

### Security

- **Environment credential management:** Relocated `API_KEY` handling from application source files to `.env`, adding `.env.example` templates and `.gitignore` entries.
- **Authenticated client-server communication:** Configured `core.py` to pass `Authorization: Bearer` headers across standard generation requests and shutdown routines.

### Changed

- **Strict offline mode configuration:** Set global environment variables `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` to disable external network calls in HuggingFace libraries.
- **Context depth increase:** Expanded vector retrieval depth to `top_k=3`.
- **Early configuration bootstrapping:** Reorganized `config.py` to invoke `load_dotenv()` prior to module imports, establishing consistent environment variables during startup.

### Fixed

- **API key desynchronization:** Resolved 403 Forbidden handshake errors caused by independent processes generating differing ephemeral keys; standardized key extraction from `.env`.
- **HTTP payload headers:** Fixed communication errors between client and server by explicitly passing `Content-Type: application/json` headers in `core.py`.

---

## [v1.3.1-beta] - 2026-05-11

**Release Summary:** Aether-Route Architecture & RAG Synchronization

### Added

- **Aether-Route CPU semantic router:** Introduced an embedding pipeline executing vectorization and intent classification on CPU cores, preserving VRAM on systems with 4GB to 6GB GPU memory.
- **Decoupled query and prompt payloads:** Separated communication streams between `core.py` and `server.py`, sending isolated queries for semantic vector search and full prompts for model generation to prevent conversational history from degrading search precision.
- **Unified forensic auditing:** Connected RAG subsystem state tracking to GhostLogger, capturing real-time telemetry on VRAM usage, routing latency, and generation speed.

### Changed

- **Centralized caching:** Consolidated ephemeral L1 memory caching into `server.py`, removing duplicate cache logic from `core.py` to prevent state desynchronization.
- **System instruction context injection:** Positioned retrieved document context inside the system instruction block rather than appending to user prompts, improving model compliance with source material.
- **Vault CLI interface:** Added a standalone command-line entry point to `vault.py` for batch processing via `python core_system/memory/vault.py ingest`.

### Fixed

- **Cache method signature compatibility:** Corrected argument handling across `EphemeralCache.add()` and `EphemeralCache.search()` to resolve `TypeError` exceptions.
- **Telemetry logging format crash:** Resolved a `TypeError: not all arguments converted` logging crash in GhostLogger audit routines.
- **Repetitive context loops:** Corrected an issue where the semantic router vectorized full conversational history rather than the current prompt, leading to high false-positive cache hits and repeated responses.
- **Module import resolution:** Added project root directory resolution (`sys.path.insert`) to `vault.py` and `main.py` to ensure consistent execution regardless of working directory.
- **Windows file handle retention:** Implemented explicit context managers and garbage collection during document processing to ensure PDF file handles are released immediately after vectorization.

### Performance

- Optimized `all-MiniLM-L6-v2` embedding routines for multi-core execution on AMD Ryzen processors, achieving embedding latencies below 30ms.

---

## [v1.3.0-beta] - 2026-03-30

**Release Summary:** Dual-Tier Memory Engine & Sterile RAG Architecture

### Added

- **Two-tier memory subsystem:** Implemented an ephemeral Layer 1 RAM cache for rapid query matching alongside a persistent Layer 2 FAISS vector index for document search.
- **Isolated RAG extraction (`_ask_ai_isolated`):** Created a dedicated execution path in `core.py` that queries document context without injecting conversational history, preventing hallucinations and context pollution.
- **System command router:** Introduced `CommandRouter` to decouple administrative operations from generation requests.
- **UI ingestion command:** Added an `ingest` command to the router interface to trigger document parsing and vectorization directly.
- **Background telemetry auditing (GhostLogger):** Built a non-blocking JSONL audit logger in `core_system/audit.py` that maintains a 1MB rotating log file.
- **Token authentication middleware:** Secured server routes with `@require_auth` Bearer token validation.
- **Stress-testing benchmarks:** Added benchmarking scripts for cold starts, VRAM handoffs, memory stability, and FAISS search latency.

### Changed

- **Explicit vault command routing:** Restricted document retrieval to the explicit `vault [query]` syntax, preserving resources during ordinary chat.
- **FAISS distance threshold tuning:** Adjusted FAISS L2 search distance threshold from 1.5 to 1.85 to improve match recall on concise search terms.
- **Inference endpoint standardization:** Migrated inference route from `/chat` to `/ask` with a unified JSON payload structure.
- Version designation updated to v1.3.

### Fixed

- **Conversational history leakage:** Fixed context pollution issues by isolating document retrieval prompts from conversational buffers.
- **Windows file locking ([WinError 32]):** Wrapped file operations in `with fitz.open(...)` context managers and scheduled garbage collection to release OS file locks after ingestion.
- **GPU architecture conflicts:** Confined embedding model execution to CPU resources, avoiding CUDA compilation and compute architecture conflicts on GPU.
- **Benchmark cold start timeouts:** Updated benchmark runners to pass authentication tokens and account for initial model weight loading latencies.
- **Logger compatibility:** Aliased legacy `.record()` calls to `.info()` within `setup_ghost_logger`.

---

## [v1.2.2-beta] - 2026-03-14

**Release Summary:** Empirical Benchmarking and Security Hardening

### Security

- **In-memory ephemeral authentication (CWE-312 mitigation):** Removed plaintext key storage (`auth.token`) in favor of dynamic in-memory key generation stored in `os.environ` and discarded on shutdown.
- **Input validation and sanitization:** Added regex validation filters to intercept command injection and script execution patterns before prompts reach inference.
- **Restricted path traversal rules:** Implemented strict path checks blocking access to system paths (`C:\Windows\System32`, `/etc/`) and sensitive files (`.ssh/id_rsa`, `.env`).
- **Subprocess command allowlist:** Restricted WebSocket commands for Folding@home integration to an explicit list (`pause`, `unpause`, `finish`, `shutdown`).
- **Constant-time authentication comparison:** Integrated `secrets.compare_digest()` in `server.py` to prevent timing attacks during token verification.
- **Local API rate limiting:** Enforced a rate limit of 60 requests per minute per IP to protect local service endpoints.
- **Fail-safe configuration fallback:** Configured `constitution.json` handling to default to restrictive permissions (`allow_file_read: False`) if configuration files are missing or unparseable.

### Added

- **Security test suite:** Added `tests/security_tests.py` to automate testing of containment boundaries and defensive controls against simulated attack payloads.
- **Hardware benchmarking scripts:** Created `benchmarks/vram_test.py` and `benchmarks/inference_test.py` for direct measurement of hardware metrics.
- **Security and benchmarking policies:** Added `SECURITY.md` and `BENCHMARKING.md` guidelines.
- **Structured audit logging:** Deployed `logs/ghost_audit.jsonl` for telemetry events and `logs/security.log` for rejected requests and access violations.

### Performance

- **Empirical hardware benchmarks:** Verified performance on an NVIDIA RTX 5050 Laptop GPU, documenting 6.55ms VRAM swap latency and 45-55 t/s inference speed on Llama-3 8B.

---

## [v1.2.1-beta] - 2026-03-10

**Release Summary:** Security Perimeter, Memory Optimization, and Secured Command Routing

### Security

- **Localhost Bearer authentication:** Introduced local API token validation (`auth.token`) and Bearer token enforcement across all Flask endpoints.
- **Safety boundaries in system prompt:** Updated core system prompts to establish boundaries preventing arbitrary system file deletion or unauthorized data egress, while allowing unrestricted processing of authorized developer tasks.

### Added

- **Direct GPU telemetry:** Integrated `pynvml` (via `nvidia-ml-py`) into the VRAM state machine to monitor GPU memory utilization directly.
- **Health monitoring endpoint:** Added `/health` route in `server.py` to facilitate startup polling.

### Changed

- **WebSocket-based compute orchestration:** Replaced subprocess CLI polling for Folding@home with local WebSocket communication (port 7396), achieving 21ms handoff latency.
- **State machine architecture:** Relocated the background compute state manager into `server.py`, coupling state transitions directly to the inference lifecycle.
- **API-driven command routing:** Overhauled `command_router.py` to dispatch system commands via authenticated HTTP API calls.

### Fixed

- **Unbounded chat history memory leak:** Resolved memory growth in `core.py` by implementing a sliding context window retaining the 10 most recent messages (5 turns).
- **Subprocess module resolution:** Added `sys.path` configuration to `main.py` to prevent import failures when launched from external directories.
- **Startup race conditions:** Replaced fixed `time.sleep()` intervals in `launcher.py` with polling against the `/health` endpoint.
- **Subprocess buffer deadlocks:** Rerouted server stdout and stderr output to `logs/server.log` to prevent pipe buffer saturation from stalling execution.
