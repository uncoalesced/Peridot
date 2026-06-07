# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL | CONVERSATIONAL PROMPT BUILDER
# Copyright (C) 2026 uncoalesced
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

from .constitution import build_system_prompt

def build_full_context(rag_context, chat_history, current_prompt, model_format):
    """
    Assembles the final string sent to the LLM.
    Order: [System Directive + RAG Context] -> [Chat History] -> [Current Prompt]
    """
    # 1. Base System Prompt (incorporates RAG Context and cleanly closes the system tag)
    prompt_str = build_system_prompt(context_str=rag_context, model_format=model_format)
    
    # 2. Inject Historical Turns (as distinct conversational role blocks)
    if model_format == "chatml":
        for turn in chat_history:
            prompt_str += f"<|im_start|>{turn['role']}\n{turn['content']}<|im_end|>\n"
        prompt_str += f"<|im_start|>user\n{current_prompt}<|im_end|>\n<|im_start|>assistant\n"
        
    elif model_format == "llama3":
        for turn in chat_history:
            prompt_str += f"<|start_header_id|>{turn['role']}<|end_header_id|>\n\n{turn['content']}<|eot_id|>\n"
        prompt_str += f"<|start_header_id|>user<|end_header_id|>\n\n{current_prompt}<|eot_id|>\n<|start_header_id|>assistant<|end_header_id|>\n"

    return prompt_str