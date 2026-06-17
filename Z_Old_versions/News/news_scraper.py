import os
import sys
import json
import feedparser
import re

import logging
logging.basicConfig(level=logging.DEBUG)
try:
    import numpy as np
    import pandas as pd
except ImportError as e:
    import traceback
    print("ImportError occurred:")
    traceback.print_exc()
    print("Missing required packages. Please run:")
    print("    pip install numpy pandas")
    sys.exit(1)


from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import PunktSentenceTokenizer, word_tokenize

punkt_tokenizer = PunktSentenceTokenizer()

def clean_and_tokenize(text):
    text = re.sub(r"[^\w\s]", " ", text.lower())  # Clean punctuation
    sentences = punkt_tokenizer.tokenize(text)    # Manually sentence-tokenize
    return [token for sentence in sentences for token in word_tokenize(sentence)]



from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import string
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Profile.user_profile import UserProfile

nltk.download('vader_lexicon')
nltk.download('punkt')
nltk.download('stopwords')

def initialize_nltk():
    """Initialize NLTK resources with robust handling."""
    required_resources = ['vader_lexicon', 'punkt', 'stopwords']
    for resource in required_resources:
        try:
            nltk.download(resource, quiet=False)
        except Exception as e:
            print(f"Error downloading NLTK resource {resource}: {e}")
            sys.exit(1)

    # Force-load punkt tokenizer to make sure it's actually initialized
    try:
        from nltk.tokenize import PunktSentenceTokenizer
        PunktSentenceTokenizer()
    except Exception as e:
        print(f"Error initializing Punkt tokenizer: {e}")
        sys.exit(1)

initialize_nltk()

PROFILE_PATH = os.path.join("..", "Profile", "user_profile.json")
KEYWORDS_PATH = os.path.join("News", "thinkfree_financial_keywords.csv")

OUTPUT_PATH = r"C:\Users\Allan Aziz\ThinkFree\News\enriched_news_sentiment.json" # Ensure this path is correct for your environment...hardcoded for now

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
from pathlib import Path
Path(OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)

RSS_FEEDS = {
    "google": "https://news.google.com/rss/search?q={query}",
    "yahoo": "https://feeds.finance.yahoo.com/rss/2.0/headline?s={query}&region=US&lang=en-US"
}

def load_keywords(csv_path):
    df = pd.read_csv(csv_path)
    keyword_dict = {}
    for strategy in df['strategy'].unique():
        keyword_dict[strategy] = df[df['strategy'] == strategy]['keyword'].dropna().tolist()
    return keyword_dict


def match_keywords(text, keywords, stemmer, stop_words):
    tokens = clean_and_tokenize(text)
    stems = {stemmer.stem(word) for word in tokens if word not in stop_words}
    matched = set()
    for keyword in keywords:
        keyword_tokens = clean_and_tokenize(keyword)
        if all(stemmer.stem(tk) in stems for tk in keyword_tokens):
            matched.add(keyword)
    return list(matched)

def fetch_rss_articles(query):
    articles = []
    for source, url_template in RSS_FEEDS.items():
        try:
            encoded_query = query.replace(" ", "+").strip()
            url = url_template.format(query=encoded_query)
            print(f"Fetching from {source} with URL: {url}")  # Debug URL
            
            feed = feedparser.parse(url)

            # Debug feed parsing status
            if hasattr(feed, 'status'):
                print(f"Feed status for {source}: {feed.status}")
            
            if feed.bozo and not feed.entries:
                print(f"Warning: Feed parsing error for {source}: {feed.bozo_exception}")
                if hasattr(feed, 'debug_message'):
                    print(f"Debug info: {feed.debug_message}")
                continue
            if not feed.entries:
                print(f"No entries found for {source} with query: {query}")
                print(f"Feed headers: {feed.headers if hasattr(feed, 'headers') else 'No headers'}")
                continue
            for entry in feed.entries[:3]:
                title = getattr(entry, 'title', 'No title available')
                summary = getattr(entry, 'summary', getattr(entry, 'description', ''))
                link = getattr(entry, 'link', '')
                
                if not title or not link:
                    print(f"Skipping entry due to missing title or link for {source}")
                    continue
                    
                articles.append({
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": source
                })

            print(f"Successfully fetched {len(feed.entries[:3])} articles from {source}")
        except Exception as e:
            print(f"Error fetching feed from {source}: {str(e)}")
            print(f"Full error details: {repr(e)}")
            continue
    return articles


def analyze_sentiment(text, analyzer):
    """Analyze sentiment of text with input validation."""
    if not text or not isinstance(text, str):
        return {'neg': 0.0, 'neu': 1.0, 'pos': 0.0, 'compound': 0.0}
    try:
        return analyzer.polarity_scores(text)
    except Exception as e:
        print(f"Error analyzing sentiment: {e}")
        return {'neg': 0.0, 'neu': 1.0, 'pos': 0.0, 'compound': 0.0}

def run_scraper():
    profile = UserProfile(PROFILE_PATH)
    user_data = profile.get_profile()
    goal = user_data.get("goal", "Income")
    risk = profile.get_investment_preferences().get("risk_tolerance", "medium")

    print(f"User goal: {goal}")
    print(f"Risk tolerance: {risk}")

    try:
        all_keywords = load_keywords(KEYWORDS_PATH)
        keywords = all_keywords.get(goal, [])
    except Exception as e:
        print(f"❌ Failed to load keywords: {e}")
        keywords = []

    if not keywords:
        print(f"⚠️ No keywords found for goal '{goal}'. Using fallback.")
        keywords = ["dividend stocks", "bond yields", "growth ETFs"]

    print(f"🧠 Using keywords: {keywords}")

    try:
        analyzer = SentimentIntensityAnalyzer()
    except Exception as e:
        print(f"❌ Error initializing sentiment analyzer: {e}")
        sys.exit(1)

    stemmer = PorterStemmer()
    stop_words = set(stopwords.words('english'))

    results = []

    for keyword in keywords:
        articles = fetch_rss_articles(keyword)
        if not articles:
            print(f"⚠️ No articles fetched for keyword: {keyword}")
            continue
        for article in articles:
            full_text = f"{article['title']} {article['summary']}"
            sentiment = analyze_sentiment(full_text, analyzer)
            matched_keywords = match_keywords(full_text, keywords, stemmer, stop_words)
            article.update({
                "sentiment": sentiment,
                "matched_keywords": matched_keywords
            })
            results.append(article)

    print(f"📊 Total articles collected: {len(results)}")

    if results:
        try:
            with open(OUTPUT_PATH, 'w') as f:
                json.dump(results, f, indent=4)
            print(f"✅ News and sentiment saved to {OUTPUT_PATH}")
        except Exception as e:
            print(f"❌ Failed to write JSON file: {e}")
    else:
        print("⚠️ No results to save. JSON file not created.")


if __name__ == "__main__":
    run_scraper()




# TO RUN THE SCRAPER: python News\news_scraper.py
