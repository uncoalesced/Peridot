# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CONSTITUTION & PROMPT ENGINEERING
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Constitution Loader & Prompt Assembly.
Handles sovereign constitution parsing and multi-model prompt compilation.
Supports ChatML (Qwen), Llama-3, and Mistral chat templates with strict
dual-phase formatting.
"""

import json
from pathlib import Path
from typing import Optional

# Dynamically resolve to the project root directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONSTITUTION_PATH = _PROJECT_ROOT / "config" / "constitution.json"
_CONSTITUTION_CACHE: Optional[dict] = None

# ponytail: model_format used to be guessed from the filename ("llama" in
# name -> llama3, else chatml). That silently mis-templated Mistral-Nemo-
# Instruct-2407.gguf -- its filename matches neither substring, so it fell
# through to chatml even though it's a Mistral/Tekken model and needs
# [INST]/[/INST]. Filenames are operator-chosen and arbitrary; the GGUF
# header's own tokenizer.ggml.pre field is authoritative and already sitting
# in every model file. Reading it via the gguf-py reader vendored at
# llama.cpp/gguf-py means new models get the right template automatically
# instead of needing a new elif every time one gets downloaded.
_VOCAB_PRE_TO_FORMAT: dict[str, str] = {
    "llama-bpe": "llama3",
    "tekken": "mistral",
    "qwen2": "chatml",
    "qwen35": "chatml",
}
_GGUF_METADATA_CACHE: dict[Path, tuple] = {}


def _read_gguf_metadata(model_path: Path) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (general.architecture, tokenizer.ggml.pre) read straight from the
    GGUF header, or (None, None) if the vendored reader is unavailable or the
    read fails for any reason -- callers must fall back to the filename
    heuristic rather than let a missing/broken reader block boot.
    """
    if model_path in _GGUF_METADATA_CACHE:
        return _GGUF_METADATA_CACHE[model_path]

    result = (None, None)
    try:
        import sys
        gguf_py_path = str(_PROJECT_ROOT / "llama.cpp" / "gguf-py")
        if gguf_py_path not in sys.path:
            sys.path.insert(0, gguf_py_path)
        import gguf

        reader = gguf.GGUFReader(str(model_path), mode="r")

        def _get_str(key: str) -> Optional[str]:
            field = reader.fields.get(key)
            if field is None:
                return None
            return bytes(field.parts[field.data[0]]).decode("utf-8", errors="ignore")

        result = (_get_str("general.architecture"), _get_str("tokenizer.ggml.pre"))
    except Exception:
        result = (None, None)

    _GGUF_METADATA_CACHE[model_path] = result
    return result

def load_constitution() -> dict:
    """Load and cache the sovereign constitution from disk."""
    global _CONSTITUTION_CACHE
    if _CONSTITUTION_CACHE is not None:
        return _CONSTITUTION_CACHE

    if CONSTITUTION_PATH.exists():
        try:
            with open(CONSTITUTION_PATH, "r", encoding="utf-8") as f:
                _CONSTITUTION_CACHE = json.load(f)
        except Exception:
            _CONSTITUTION_CACHE = {}
    else:
        _CONSTITUTION_CACHE = {}

    return _CONSTITUTION_CACHE

def get_model_format(model_path: Path) -> str:
    """
    Detect model chat template format from the GGUF header's
    tokenizer.ggml.pre field (authoritative). Falls back to the old
    filename heuristic only if the header can't be read.
    """
    _arch, vocab_pre = _read_gguf_metadata(model_path)
    if vocab_pre in _VOCAB_PRE_TO_FORMAT:
        return _VOCAB_PRE_TO_FORMAT[vocab_pre]

    model_name = model_path.name.lower()
    if "llama" in model_name:
        return "llama3"
    elif "mistral" in model_name:
        return "mistral"
    return "chatml"

def get_chat_template(model_format: str) -> dict:
    """Return correct chat template tokens for the given model format."""
    if model_format == "llama3":
        return {
            "sys_start": "<|start_header_id|>system<|end_header_id|>\n\n",
            "sys_end": "<|eot_id|>\n",
            "user_start": "<|start_header_id|>user<|end_header_id|>\n\n",
            "assistant_start": "<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n",
            "stop_tokens": ["<|eot_id|>", "<|start_header_id|>", "<|im_end|>"],
        }
    elif model_format == "mistral":
        # Mistral V3-Tekken format (Mistral-Nemo and later): no per-turn role
        # header, [INST]/[/INST] wraps only the user turn, assistant text is
        # bare and closed with </s>. Untested against real hardware -- see
        # the ponytail note in server.py's target_stops selection.
        return {
            "sys_start": "<s>[SYSTEM_PROMPT] ",
            "sys_end": "[/SYSTEM_PROMPT]",
            "user_start": "[INST] ",
            "assistant_start": "[/INST]",
            "stop_tokens": ["</s>", "[INST]"],
        }
    else:
        # Default to standard ChatML tokens (Qwen/Coder)
        return {
            "sys_start": "<|im_start|>system\n",
            "sys_end": "<|im_end|>\n",
            "user_start": "<|im_start|>user\n",
            "assistant_start": "<|im_end|>\n<|im_start|>assistant\n",
            "stop_tokens": ["<|im_end|>", "<|im_start|>"],
        }

def build_system_prompt(
    context_str: str = "",
    model_format: str = "chatml",
) -> str:
    """
    Surgically compiles the hard constitution boundaries with live RAG vectors.
    Forces dual-phase reasoning loop, preventing language bleed.
    """
    constitution = load_constitution()
    perimeter = constitution.get("system_perimeter", {})
    exec_proto = constitution.get("execution_protocol", {})
    rules = constitution.get("hard_rules", [])

    identity = perimeter.get("identity", "Peridot Sovereign Kernel v1.5.4")
    lang_guard = perimeter.get("language_guardrail", "Output must be 100% English only.")
    protocol = exec_proto.get("structure", "Output must follow [ANALYSIS] and [KERNEL_RESPONSE] blocks strictly.")
    constraints = exec_proto.get("behavioral_constraints", [])

    tmpl = get_chat_template(model_format)

    sys_prompt = tmpl["sys_start"]
    sys_prompt += f"CORE IDENTITY: {identity}\n"
    sys_prompt += f"LANGUAGE CONSTRAINT: {lang_guard}\n\n"
    sys_prompt += f"STRUCTURAL PARSE MANDATE:\n{protocol}\n\n"

    if rules or constraints:
        sys_prompt += "BEHAVIORAL CONSTRAINTS & HARD RULES:\n"
        for rule in rules:
            sys_prompt += f"- {rule}\n"
        for constraint in constraints:
            sys_prompt += f"- {constraint}\n"
        sys_prompt += "\n"

    sys_prompt += (
        "ANTI-PATTERN WARNING: You are forbidden from stating 'The term X does not appear in the context'. "
        "Evaluate context silently. If empty, pivot to a sharp, minimal objective summary.\n\n"
    )

    if context_str:
        sys_prompt += f"[SECURED KERNEL VAULT CONTEXT]:\n{context_str}\n"
    else:
        sys_prompt += "[SECURED KERNEL VAULT CONTEXT]: VRAM Vault empty/unmapped for this node.\n"

    sys_prompt += tmpl["sys_end"]
    return sys_prompt

def get_assistant_start(model_format: str) -> str:
    """Get the assistant start token for the model format."""
    return get_chat_template(model_format)["assistant_start"]

def get_stop_tokens(model_format: str) -> list:
    """Get stop tokens for the model format."""
    return get_chat_template(model_format)["stop_tokens"]

# --- RESPONSE CONTRACT PARSING ---------------------------------------------
# The constitution mandates that every reply is [ANALYSIS] ... [KERNEL_RESPONSE]
# ... , so the parser for that contract lives next to the mandate that creates
# it. Both server.py (empty-answer detection) and core.py (what gets written to
# the chat ledger) route through here, so the two can never disagree about what
# counts as "the answer".

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


def strip_reasoning(text: str) -> str:
    """
    Remove Qwen3-style <think> reasoning blocks from raw model output.

    Handles the unclosed case too: if generation stopped inside a think block,
    everything from <think> onward is reasoning, not answer. That case is the
    whole reason this exists -- an unclosed <think> tail used to survive into
    the chat ledger and then get replayed as an assistant turn, teaching the
    model in-context that an empty reply is the house style.
    """
    while _THINK_OPEN in text:
        head, _, tail = text.partition(_THINK_OPEN)
        if _THINK_CLOSE in tail:
            text = head + tail.split(_THINK_CLOSE, 1)[1]
        else:
            text = head
            break
    return text.strip()


def parse_kernel_response(raw: str) -> tuple[str, str]:
    """
    Split raw model output into (analysis, answer_body).

    Reasoning blocks are dropped. If the model emitted the [KERNEL_RESPONSE]
    header and then stopped, the body comes back empty -- callers must treat
    empty as failure rather than as a valid reply.
    """
    text = strip_reasoning(raw or "")

    if "[KERNEL_RESPONSE]" in text:
        analysis, _, body = text.partition("[KERNEL_RESPONSE]")
        analysis = analysis.replace("[ANALYSIS]", "").strip()
        return analysis, strip_reasoning(body)

    return "", text


def format_kernel_response(analysis: str, body: str) -> str:
    """Re-assemble the wire format the UI's dual-phase renderer expects."""
    return f"[ANALYSIS]\n{analysis or 'Direct synthesis.'}\n\n[KERNEL_RESPONSE]\n{body}"
