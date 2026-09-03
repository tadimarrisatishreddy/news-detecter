from ollama import chat


def analyze_news(news_text: str):

    response = chat(
        model="gemma3:4b",
        messages=[
            {
                "role": "system",
                "content": """
You are an AI assistant for a Fake News and Misinformation Detector.

Analyze the news text carefully.

Return your analysis in this format:

VERDICT: LIKELY_REAL, LIKELY_FAKE, or UNCERTAIN
CONFIDENCE: 0-100
EXPLANATION: Short explanation

Do not claim absolute factual certainty without evidence.
"""
            },
            {
                "role": "user",
                "content": f"Analyze this news claim:\n\n{news_text}"
            }
        ]
    )

    return response.message.content