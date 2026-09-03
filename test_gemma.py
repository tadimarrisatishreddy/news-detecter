from gemma_client import analyze_news


news = """
The government announced that the moon will be declared
the 29th state of the country tomorrow.
"""

result = analyze_news(news)

print(result)