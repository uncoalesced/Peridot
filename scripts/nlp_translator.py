# scripts/nlp_translator.py

# --- FIXED IMPORT ---
from core_system.enhancedlogger import logger


def summarize_text(text):
    """
    Summarizes long text using basic heuristic splitting.
    (In the future, this can be routed to the local LLM).
    """
    if not text:
        return "No text provided to summarize."

    logger.info("Summarizing text...", source="NLP")

    # Simple heuristic: Take the first 3 sentences
    sentences = text.split(".")
    summary = ". ".join(sentences[:3]) + "."

    return f"[Summary]: {summary}"
