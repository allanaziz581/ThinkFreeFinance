import streamlit as st
import json
import pandas as pd
import os
import sys
from typing import Dict, Any, List

# Ensure user_profile is importable
sys.path.append(os.path.abspath("."))
from Profile.user_profile import UserProfile

# Load user profile
def load_profile() -> Dict[str, Any]:
    profile = UserProfile()
    return profile.get_profile()

# Load scraped news data with error handling
def load_articles(path: str = 'UI/news_sentiment.json') -> pd.DataFrame:
    if not os.path.exists(path):
        st.error(f"🚫 File not found: {os.path.abspath(path)}")
        return pd.DataFrame()
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        all_articles: List[Dict[str, Any]] = []
        for keyword, articles in data.items():
            for article in articles:
                article['matched_keyword'] = keyword
                all_articles.append(article)
        df = pd.DataFrame(all_articles)
        df['compound_score'] = df['sentiment'].apply(lambda s: s.get('compound', 0.0))
        return df
    except Exception as e:
        st.error(f"❌ Failed to load articles: {e}")
        return pd.DataFrame()

# Sentiment formatting
def format_sentiment(score: float) -> str:
    if score >= 0.5:
        return f"🟢 Positive ({score:.2f})"
    elif score <= -0.2:
        return f"🔴 Negative ({score:.2f})"
    return f"🟡 Neutral ({score:.2f})"

# --- UI starts here ---
st.set_page_config(page_title="ThinkFree Dashboard", layout="wide")
st.title("📊 ThinkFree Investment Dashboard")

# Sidebar: Profile
st.sidebar.header("👤 User Profile")
profile_data = load_profile()
for k, v in profile_data.items():
    if isinstance(v, dict):
        st.sidebar.markdown(f"**{k.replace('_', ' ').title()}**:")
        for sk, sv in v.items():
            st.sidebar.markdown(f"- {sk.replace('_', ' ').title()}: {sv}")
    else:
        st.sidebar.markdown(f"**{k.replace('_', ' ').title()}**: {v}")

# Main tabs
tabs = st.tabs(["📰 News Feed", "📚 Article History", "🔍 Insights"])

# Tab 1: News Feed
with tabs[0]:
    df = load_articles()
    if not df.empty:
        keyword_options = sorted(df['matched_keyword'].dropna().unique())
        selected_keyword = st.selectbox("Filter by keyword:", keyword_options)
        filtered_df = df[df['matched_keyword'] == selected_keyword].sort_values(by="compound_score", ascending=False)

        for _, row in filtered_df.iterrows():
            title = str(row['title'])
            link = str(row['link'])
            summary = str(row.get('summary', ''))
            source = str(row.get('source', 'unknown'))
            sentiment_score = float(row.get('compound_score', 0.0))
            matched_keyword = str(row.get('matched_keyword', ''))

            st.markdown(f"### [{title}]({link})")
            st.markdown(f"*Source:* {source.title()}  ")
            st.markdown(f"*Keyword:* `{matched_keyword}`")
            st.markdown(format_sentiment(sentiment_score))
            st.markdown(summary, unsafe_allow_html=True)
            st.divider()
    else:
        st.info("No articles available to display.")

# Tab 2: Article History
with tabs[1]:
    if not df.empty:
        grouped = df.groupby("matched_keyword")
        for key, group in grouped:
            st.subheader(f"🔖 {str(key).title()} ({len(group)})")
            for _, row in group.iterrows():
                st.markdown(f"- [{row['title']}]({row['link']}) — {format_sentiment(row['compound_score'])}")
    else:
        st.info("No article history found.")

# Tab 3: Insights
with tabs[2]:
    if not df.empty:
        st.subheader("Top Sentiment Articles")
        top_pos = df.sort_values(by='compound_score', ascending=False).head(3)
        top_neg = df.sort_values(by='compound_score').head(3)

        st.markdown("**🔝 Positive Articles**")
        for _, row in top_pos.iterrows():
            st.markdown(f"- [{row['title']}]({row['link']}) — {format_sentiment(row['compound_score'])}")

        st.markdown("**🔻 Negative Articles**")
        for _, row in top_neg.iterrows():
            st.markdown(f"- [{row['title']}]({row['link']}) — {format_sentiment(row['compound_score'])}")
    else:
        st.info("Sentiment insights not available.")
