import pandas as pd
import os

CSV_PATH = "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/qlib_data/formatted/ta_analysis_detailed.csv"
QLIB_OUTPUT_DIR = "/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/qlib_data/formatted"
OUTPUT_FILE = os.path.join(QLIB_OUTPUT_DIR, "data.pkl")

def convert_to_qlib_format():
    print("🔹 Reading your CSV...")
    df = pd.read_csv(CSV_PATH)

    # Drop completely empty rows
    df.dropna(how="all", inplace=True)

    # Ensure 'date' or 'datetime' exists
    if 'date' not in df.columns and 'datetime' not in df.columns:
        if 'Date' in df.columns:
            df.rename(columns={'Date': 'date'}, inplace=True)
        else:
            raise ValueError("❌ The CSV must include a 'date' or 'datetime' column.")

    # Rename 'ticker' to 'instrument' for Qlib
    if "ticker" in df.columns:
        df.rename(columns={"ticker": "instrument"}, inplace=True)

    # Standardize date column
    if "date" in df.columns:
        df.rename(columns={"date": "datetime"}, inplace=True)

    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index(["datetime", "instrument"]).sort_index()

    os.makedirs(QLIB_OUTPUT_DIR, exist_ok=True)
    df.to_pickle(OUTPUT_FILE)

    print(f"✅ Data saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    convert_to_qlib_format()
