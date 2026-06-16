#!/usr/bin/env python3
import os
import json
import re
from itertools import islice
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ——— Config ———
BASE_DIR     = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
NEWS_DIR     = os.path.join(BASE_DIR, "news_output")
INPUT_FILE   = os.path.join(NEWS_DIR, "clustered_summaries.json")
OUTPUT_FILE  = os.path.join(NEWS_DIR, "sector_summaries.json")

# ——— API Key & Model ———
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL       = os.getenv("MODEL", "gpt-3.5-turbo")
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.3))
CHUNK_SIZE  = int(os.getenv("CHUNK_SIZE", 50))  # max articles per chunk

# ——— Numeric regex ———
percent_re = re.compile(r"\b\d+(?:\.\d+)?%\b")
dollar_re  = re.compile(r"\$\d{1,3}(?:,\d{3})*(?:\.\d+)?")

# ——— Initialize OpenAI ———
if not API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY environment variable.")
openai = OpenAI(api_key=API_KEY)

# ——— Prompts ———
CHUNK_SYSTEM = (
    "You are a professional financial analyst. Summarize the following article summaries into exactly 4 sentences, "
    "including every percentage and dollar figure."
)
CHUNK_TMPL   = (
    "Chunk of {n} article summaries:\n{entries}\nPlease summarize into 4 sentences, preserving all numeric details."
)
FINAL_SYSTEM = (
    "You are a professional financial analyst. Combine the intermediate summaries into a comprehensive sector overview. "
    "Your response must be at least 12 sentences long and include all percentages and dollar figures."
)
FINAL_TMPL   = (
    "Combine {n} intermediate summaries for the {sector} sector into a cohesive overview of at least 12 sentences, "
    "preserving all numeric data:\n{chunks}\n"
)

# ——— Helper to chunk lists ———
def chunked(seq, size):
    it = iter(seq)
    for first in it:
        yield [first] + list(islice(it, size-1))

# ——— Load clustered summaries ———
with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    raw = json.load(f)
clusters = {'0': raw} if isinstance(raw, list) else raw

# ——— Group by sector ———
sector_articles = {}
for label, arts in clusters.items():
    for art in arts:
        sector = art.get('gics_sector', 'Unknown')
        summary = art.get('summary', '').strip()
        url     = art.get('url', '')
        key = f"- {summary} (URL: {url})"
        sector_articles.setdefault(sector, []).append(key)

# ——— Summarize per sector ———
output = {}
for sector, lines in sector_articles.items():
    # Phase 1: summarize in chunks
    intermediate = []
    for chunk in chunked(lines, CHUNK_SIZE):
        entries = "\n".join(chunk)
        prompt = CHUNK_TMPL.format(n=len(chunk), entries=entries)
        resp = openai.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": CHUNK_SYSTEM},
                {"role": "user",   "content": prompt}
            ],
            temperature=TEMPERATURE
        )
        text = getattr(resp.choices[0].message, 'content', '') or ''
        intermediate.append(text.strip())

    # Phase 2: final overview
    chunks_joined = "\n".join(f"- {s}" for s in intermediate)
    prompt2 = FINAL_TMPL.format(n=len(intermediate), sector=sector, chunks=chunks_joined)
    resp2 = openai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": FINAL_SYSTEM},
            {"role": "user",   "content": prompt2}
        ],
        temperature=TEMPERATURE
    )
    final_text = getattr(resp2.choices[0].message, 'content', '') or ''

    # retention check
    orig_vals  = percent_re.findall(chunks_joined) + dollar_re.findall(chunks_joined)
    found_vals = percent_re.findall(final_text) + dollar_re.findall(final_text)
    if orig_vals and len(found_vals) < len(orig_vals) * 0.8:
        print(f"⚠️ Sector '{sector}' summary may have missed some data.")

    output[sector] = {
        "sector_summary": final_text.strip(),
        "articles_count": len(lines)
    }

# ——— Save results ———
import os as _os
_os.makedirs(NEWS_DIR, exist_ok=True)
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2)
print(f"✔️ Wrote sector summaries (>=12 sentences) to {OUTPUT_FILE}")
