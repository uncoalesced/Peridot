# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CONSTITUTION & PROMPT ENGINEERING
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Constitution Loader & Prompt Assembly.
Handles sovereign constitution parsing and multi-model prompt compilation.
Supports ChatML (Qwen) and Llama-3 chat templates with strict dual-phase formatting.
"""

import json
from pathlib import Path
from typing import Optional

# Dynamically resolve to the project root directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONSTITUTION_PATH = _PROJECT_ROOT / "config" / "constitution.json"
_CONSTITUTION_CACHE: Optional[dict] = None

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
    """Detect model chat template format from filename."""
    model_name = model_path.name.lower()
    if "llama" in model_name:
        return "llama3"
    elif "qwen" in model_name:
        return "chatml"
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

    identity = perimeter.get("identity", "Peridot Sovereign Kernel v1.5.3")
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