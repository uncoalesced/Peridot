# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CONVERSATIONAL PROMPT BUILDER
# Copyright (C) 2026 uncoalesced
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

from core_system.prompting.constitution import build_system_prompt

THINK_SEED = "<think>\n"
# Qwen3.x template (preserve_thinking default): past assistant turns carry an
# empty think block.
_PAST_THINK = "<think>\n\n</think>\n\n"


def build_full_context(rag_context, chat_history, current_prompt, model_format, thinking=False,
                       tools_block="", model_name="", capabilities=None):
    """
    Assembles the final string sent to the LLM.
    Order: [System Directive + RAG Context] -> [Chat History] -> [Current Prompt]
    thinking: native-<think> model. ChatML prompts then end with "<think>\\n",
    exactly as the GGUF chat template's generation prompt does; without it the
    1-bit model often closed an empty think and answered an earlier question.
    The generated text therefore starts inside the think block.
    tools_block / model_name / capabilities: passed through to build_system_prompt.
    """
    # 1. Base System Prompt (incorporates RAG Context and cleanly closes the system tag)
    prompt_str = build_system_prompt(context_str=rag_context, model_format=model_format,
                                     thinking=thinking, tools_block=tools_block,
                                     model_name=model_name, capabilities=capabilities)

    # 2. Inject Historical Turns (as distinct conversational role blocks)
    if model_format == "chatml":
        for turn in chat_history:
            past = _PAST_THINK if thinking and turn['role'] == "assistant" else ""
            prompt_str += f"<|im_start|>{turn['role']}\n{past}{turn['content']}<|im_end|>\n"
        prompt_str += f"<|im_start|>user\n{current_prompt}<|im_end|>\n<|im_start|>assistant\n"
        if thinking:
            prompt_str += THINK_SEED
        
    elif model_format == "llama3":
        for turn in chat_history:
            prompt_str += f"<|start_header_id|>{turn['role']}<|end_header_id|>\n\n{turn['content']}<|eot_id|>\n"
        prompt_str += f"<|start_header_id|>user<|end_header_id|>\n\n{current_prompt}<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n"

    elif model_format == "mistral":
        # No per-turn role header: [INST] wraps only the user side, assistant
        # replies are bare text closed with </s>.
        for turn in chat_history:
            if turn['role'] == 'user':
                prompt_str += f"[INST] {turn['content']}[/INST]"
            else:
                prompt_str += f"{turn['content']}</s>"
        prompt_str += f"[INST] {current_prompt}[/INST]"

    return prompt_str