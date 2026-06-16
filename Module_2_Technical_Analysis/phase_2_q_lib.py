# phase_2_q_lib.py
# Step 1: Convert TA Analysis JSON into Qlib-compatible format

import pandas as pd
import json
import os
from datetime import datetime, timedelta

# Load TA Analysis Output
with open("/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/news_output/ta_analysis_results.json", "r") as f:
    ta_data = json.load(f)

# Combine bullish and bearish results
combined = ta_data["bullish_analysis"] + ta_data["bearish_analysis"]

# Generate synthetic datetime index for 1-year span (required by Qlib)
today = datetime.today()
dates = [today - timedelta(days=i) for i in range(365)]
dates = sorted(dates)

rows = []
for stock in combined:
    ticker = stock["ticker"].upper()
    for i, date in enumerate(dates[-1:]):  # Only use the latest day for now (will expand)
        row = {
            "datetime": date.strftime("%Y-%m-%d"),
            "instrument": ticker,
            "rsi": stock["rsi"],
            "macd": stock["macd"],
            "sma_50": stock["sma_50"],
            "sma_200": stock["sma_200"],
            "close": stock["close"],
            "rsi_signal": 1 if stock["rsi_signal"] == "oversold" else -1 if stock["rsi_signal"] == "overbought" else 0,
            "macd_signal": 1 if stock["macd_signal"] == "bullish" else -1,
            "trend_signal": 1 if stock["trend_signal"] == "bullish" else -1,
            "label": None  # Placeholder for future return
        }
        rows.append(row)

# Create DataFrame
df = pd.DataFrame(rows)

# Save CSV for Qlib
output_dir = "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/qlib_data"
os.makedirs(output_dir, exist_ok=True)
df.to_csv(os.path.join(output_dir, "qlib_feature_data.csv"), index=False)
print("✅ Exported Qlib-compatible dataset with", len(df), "rows")
