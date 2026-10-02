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
import re
from datetime import date
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

# FreeThink registry (v1.6.x): tokenizer.ggml.pre values of models that reason
# natively in <think>...</think> and then answer. Parentheses gets one entry
# here once its GGUF metadata is known -- no new code path.
_THINKING_VOCAB_PRE: frozenset[str] = frozenset({"qwen35"})


def model_supports_thinking(model_path: Path) -> bool:
    """True for models with native <think> reasoning (see _THINKING_VOCAB_PRE)."""
    _arch, vocab_pre = _read_gguf_metadata(model_path)
    return vocab_pre in _THINKING_VOCAB_PRE


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

_QUANT_SUFFIX_RE = re.compile(r"[-._](?:UD[-_])?(?:I?Q\d\w*|BF16|F16|F32)(?:[-_.]imat)?$", re.IGNORECASE)

DEFAULT_IDENTITY = ("You are Peridot, a private AI assistant running entirely on the "
                    "user's own computer.")


def model_display_name(model_name: str) -> str:
    """'Qwen3.8-27B-UD-IQ1_S.gguf' -> 'Qwen3.8-27B' (extension and quant tag dropped)."""
    name = Path(model_name or "").name
    if name.lower().endswith(".gguf"):
        name = name[:-5]
    return _QUANT_SUFFIX_RE.sub("", name)


def _capability_lines(capabilities: Optional[dict], has_documents: bool) -> list[str]:
    caps = capabilities or {}
    names = list(caps.get("tools") or [])
    if names:
        lines = ["Tools available this turn: " + ", ".join(names) + ". Use one only when it "
                 "actually helps answer the user's latest message."]
    else:
        lines = ["You have no tools this turn; you cannot browse the web or read files. "
                 "Say so plainly if the user asks you to."]
    if caps.get("web"):
        lines.append("Web access is on: you can search the web with the web_search tool."
                     if "web_search" in names else
                     "Web search results for this message, if any, are included below.")
    else:
        lines.append("Web access is off. If the user wants something looked up online, tell "
                     "them they can enable web access in Peridot's Settings.")
    if caps.get("documents", has_documents):
        lines.append("Excerpts from the user's own documents are included below; use them "
                     "when they are relevant.")
    return lines


def build_system_prompt(
    context_str: str = "",
    model_format: str = "chatml",
    thinking: bool = False,
    tools_block: str = "",
    model_name: str = "",
    capabilities: Optional[dict] = None,
) -> str:
    """
    The system turn: identity, model and date, what Peridot can actually do
    this turn, behaviour rules from config/constitution.json, the tool
    declarations and any document context.

    model_name: model file name (e.g. MODEL_PATH.name); shown as its display name.
    capabilities: {"tools": [tool names], "web": bool}, computed by the caller.
    Documents count as available iff context_str is non-empty.

    No answer scaffold is mandated for any model: parse_kernel_response()
    accepts a direct answer, and thinking models reason in their own native
    block, which the prompt never names (the model used to quote the tags
    from the instructions inside its reasoning, which leaked into answers).
    """
    constitution = load_constitution()
    perimeter = constitution.get("system_perimeter", {})
    exec_proto = constitution.get("execution_protocol", {})

    identity = perimeter.get("identity") or DEFAULT_IDENTITY
    lang_guard = perimeter.get("language_guardrail", "Reply in the language the user writes in.")
    rules = list(constitution.get("hard_rules", [])) + list(exec_proto.get("behavioral_constraints", []))
    structure = exec_proto.get("structure", "")

    about = identity
    display = model_display_name(model_name)
    if display:
        about += f" The underlying model is {display}, running locally via llama.cpp."
    about += f" Today's date is {date.today().isoformat()}."

    tmpl = get_chat_template(model_format)
    parts = [about]
    directive = perimeter.get("core_directive", "")
    if directive:
        parts.append(directive)
    parts.append("What you can do right now:\n" + "\n".join(
        f"- {line}" for line in _capability_lines(capabilities, bool(context_str))))
    guidelines = [r for r in rules if r] + ([lang_guard] if lang_guard else [])
    if guidelines:
        parts.append("Guidelines:\n" + "\n".join(f"- {g}" for g in guidelines))
    if structure:
        parts.append(structure)
    if tools_block:
        parts.append(tools_block.rstrip("\n"))
    if context_str:
        parts.append(f"Relevant excerpts from the user's documents:\n{context_str}")

    return tmpl["sys_start"] + "\n\n".join(parts) + "\n" + tmpl["sys_end"]

# --- RESPONSE CONTRACT PARSING ---------------------------------------------
# Replies may be a direct answer or the legacy [ANALYSIS] ... [KERNEL_RESPONSE]
# scaffold (still the server's wire format to the UI), optionally preceded by
# native reasoning. Both server.py (empty-answer detection) and core.py (what gets written to
# the chat ledger) route through here, so the two can never disagree about what
# counts as "the answer".

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


def strip_reasoning(text: str) -> str:
    """
    The answer part of raw model output: everything after the LAST </think>.

    The last one, not the first: the model sometimes quotes the tags inside
    its own reasoning, and splitting at the first close leaked the rest of
    the reasoning (plus a literal </think>) into the answer. An unclosed
    <think> means generation stopped mid-reasoning: no answer at all (an
    unclosed tail replayed from the ledger teaches the model empty replies).
    Thinking-model output starts inside the pre-seeded think block, so the
    opening tag may be missing; callers prepend it before parsing.
    """
    text = text or ""
    if _THINK_CLOSE in text:
        return text.rpartition(_THINK_CLOSE)[2].strip()
    if _THINK_OPEN in text:
        return ""
    return text.strip()


def split_reasoning(text: str) -> tuple[str, str]:
    """(reasoning, answer). Reasoning runs from the first <think> (or the start)
    to the last </think>, tags removed; answer is strip_reasoning(text)."""
    text = text or ""
    if _THINK_CLOSE in text:
        reasoning = text.rpartition(_THINK_CLOSE)[0]
    elif _THINK_OPEN in text:
        reasoning = text
    else:
        return "", text.strip()
    if _THINK_OPEN in reasoning:
        reasoning = reasoning.partition(_THINK_OPEN)[2]
    reasoning = reasoning.replace(_THINK_OPEN, "").replace(_THINK_CLOSE, "")
    return reasoning.strip(), strip_reasoning(text)


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


def stream_visible_body(raw: str) -> str:
    """
    The part of a partially streamed completion that is safe to show live.

    Hides reasoning and the [ANALYSIS] preamble: while the latest <think> is
    still open nothing is shown, after it only the text past the last
    </think>. Nothing is visible until [KERNEL_RESPONSE] appears, unless the
    model is answering without the scaffold at all. A half-streamed tag
    ("[ANA", "<thi") also stays hidden. The final text is still rendered from
    parse_kernel_response() once the stream completes.
    """
    text = raw or ""
    if text.rfind(_THINK_OPEN) > text.rfind(_THINK_CLOSE):
        return ""
    text = text.rpartition(_THINK_CLOSE)[2].strip()
    if "[KERNEL_RESPONSE]" in text:
        return text.partition("[KERNEL_RESPONSE]")[2].lstrip()
    head = text.lstrip()
    if head.startswith("[ANALYSIS]") or any(
        tag.startswith(head) for tag in ("[ANALYSIS]", "[KERNEL_RESPONSE]", _THINK_OPEN)
    ):
        return ""
    return text


def format_kernel_response(analysis: str, body: str) -> str:
    """Re-assemble the wire format the UI's dual-phase renderer expects."""
    return f"[ANALYSIS]\n{analysis or 'Direct synthesis.'}\n\n[KERNEL_RESPONSE]\n{body}"


# --- TOOL MARKUP & STORABLE ANSWERS -------------------------------------------
# Here rather than in extensions.tools so the ledger can filter history without
# importing the extension registry. Qwen3.x calls tools in XML
# (<tool_call><function=NAME><parameter=K>V</parameter></function></tool_call>);
# older Qwen wrote JSON inside <tool_call>. A final unclosed block is markup
# too: </tool_call> is a stop string, so llama.cpp leaves it out.
TOOL_CALL_RE = re.compile(r"<tool_call>(.*?)(?:</tool_call>|\Z)", re.DOTALL)
FUNCTION_RE = re.compile(r"<function=([^>\n]+)>(.*?)(?:</function>|\Z)", re.DOTALL)
_TOOL_RESPONSE_RE = re.compile(r"<tool_response>.*?(?:</tool_response>|\Z)", re.DOTALL)
_STRAY_TAG_RE = re.compile(r"</?(?:tool_call|function|parameter[^>]*|tool_response)>")

# Filler the model writes when it means to call a tool but doesn't. Stored as
# an answer it gets imitated on later turns (history poisoning, 2026-10-01).
_STUB_PHRASES = frozenset({
    "let me look that up", "let me look it up", "let me check", "let me check that",
    "let me search", "let me search for that", "let me search for it", "one moment",
    "just a moment", "let me find out", "searching", "looking that up",
})


def strip_tool_markup(text: str) -> str:
    """Remove tool calls (both forms) and tool responses from model text."""
    text = TOOL_CALL_RE.sub("", text or "")
    text = FUNCTION_RE.sub("", text)
    text = _TOOL_RESPONSE_RE.sub("", text)
    return _STRAY_TAG_RE.sub("", text).strip()


def is_bare_tool_json(text: str) -> bool:
    """True for a bare JSON tool call such as {"name": "web_search", "arguments": {...}}."""
    try:
        obj = json.loads((text or "").strip())
    except ValueError:
        return False
    return isinstance(obj, dict) and "name" in obj and ("arguments" in obj or "parameters" in obj)


def is_storable_answer(text: str) -> bool:
    """
    False for replies that must never reach the chat ledger (and so never be
    replayed as history): empty, reasoning/scaffold only, tool markup only, a
    bare tool-call JSON object, or a short stub like "Let me look that up."
    """
    _analysis, body = parse_kernel_response(text or "")
    body = strip_tool_markup(body)
    if not body or is_bare_tool_json(body):
        return False
    if len(body) < 60 and re.sub(r"[^a-z ]", "", body.lower()).strip() in _STUB_PHRASES:
        return False
    return True
