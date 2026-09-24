import json
from gemma_service import detect_fake_news

if __name__ == "__main__":
    news = """
    The government announced that the moon will be declared
    the 29th state of the country tomorrow.
    """
    print("Analyzing news with Gemma AI Detection Engine...")
    result = detect_fake_news(news)
    print("\n--- AI Detection Result ---")
    print(json.dumps(result, indent=2))