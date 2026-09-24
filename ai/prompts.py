from typing import Any, Dict, List, Optional


SYSTEM_PROMPT = """You are an expert AI Misinformation and Fact-Checking Analyst.

Your task is to analyze news articles, headlines, and claims to evaluate whether they are real news, fake/misinformation, or uncertain.

Evaluation Guidelines:
1. Examine factual plausibility, internal consistency, and alignment with verifiable reality.
2. Check for deceptive manipulation tactics: sensationalism, out-of-context claims, fabricated quotes, pseudo-science, or conspiracy narratives.
3. Consider linguistic cues provided in the context (such as sensationalism score, shouting words, and clickbait triggers).
4. Do not assert absolute factual certainty without conclusive grounds. If a claim is ambiguous, developing, or unverifiable, categorize it as UNCERTAIN.

You MUST respond strictly with a valid JSON object matching this schema:
{
  "verdict": "LIKELY_REAL" | "LIKELY_FAKE" | "UNCERTAIN",
  "confidence": <integer between 0 and 100>,
  "explanation": "<2-4 sentences explaining the reasoning, evidence indicators, and source plausibility>",
  "key_signals": ["<signal 1>", "<signal 2>"],
  "manipulation_tactics": ["<tactic 1 if fake/misleading, else empty list>"]
}

Output ONLY the JSON object. Do not include markdown code block syntax or conversational filler outside the JSON.
"""


def build_detection_prompt(
    news_text: str,
    nlp_features: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Constructs the chat messages array for Gemma AI with enriched NLP context.
    """
    context_lines = []
    if nlp_features:
        sensationalism = nlp_features.get("sensationalism", {})
        readability = nlp_features.get("readability", {})
        stats = nlp_features.get("statistics", {})

        score = sensationalism.get("sensationalism_score", 0.0)
        triggers = sensationalism.get("trigger_words_found", [])
        caps_ratio = sensationalism.get("caps_ratio", 0.0)
        grade_level = readability.get("grade_level", "N/A")
        reading_level = readability.get("reading_level", "N/A")
        word_count = stats.get("word_count", "N/A")

        context_lines.append("--- PRE-PROCESSED NLP LINGUISTIC SIGNALS ---")
        context_lines.append(f"- Sensationalism Index: {score:.2f} (Scale: 0.0 to 1.0)")
        if triggers:
            context_lines.append(f"- Sensational / Clickbait Triggers Found: {', '.join(triggers)}")
        context_lines.append(f"- ALL-CAPS Shouting Ratio: {caps_ratio:.1%}")
        context_lines.append(f"- Readability: {reading_level} (Flesch-Kincaid Grade: {grade_level})")
        context_lines.append(f"- Word Count: {word_count}")
        context_lines.append("---------------------------------------------\n")

    user_content = ""
    if context_lines:
        user_content += "\n".join(context_lines) + "\n"

    user_content += f"Analyze this news claim / article:\n\n{news_text.strip()}"

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

