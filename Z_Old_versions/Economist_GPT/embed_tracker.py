# embed_tracker.py

import os
import numpy as np
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from Module_2_Technical_Analysis.book_metadata import book_metadata

# Use HuggingFaceEmbeddings for compatibility with FAISS
EMBEDDING_MODEL = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2')
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
VECTOR_DB_ROOT = os.path.join(os.path.dirname(__file__), "economist_gpt", "vector_db")

def count_tokens(text):
    return len(text.split())  # Rough fallback

def track_and_embed():
    os.makedirs(VECTOR_DB_ROOT, exist_ok=True)
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    total_tokens = 0

    for meta in book_metadata:
        file_path = meta.get("filepath")
        book_id = meta["id"]
        db_path = os.path.join(VECTOR_DB_ROOT, book_id)

        if not file_path or not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            continue

        try:
            print(f"📚 Embedding {meta['title']}...")
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            chunks = splitter.split_documents(docs)
            
            for chunk in chunks:
                chunk.metadata["source"] = meta["title"]

            texts = [chunk.page_content for chunk in chunks]
            metadatas = [chunk.metadata for chunk in chunks]

            db = FAISS.from_texts(texts=texts, embedding=EMBEDDING_MODEL, metadatas=metadatas)

            if not chunks:
                print(f"⚠️ No content found in {meta['title']}. Skipping.")
                continue

            token_count = sum([count_tokens(chunk.page_content) for chunk in chunks])
            total_tokens += token_count

            print(f"    → Tokens: {token_count:,}")

            texts = [chunk.page_content for chunk in chunks]
            metadatas = [meta for _ in chunks]

            db = FAISS.from_texts(texts=texts, embedding=EMBEDDING_MODEL, metadatas=metadatas)
            db.save_local(db_path)
            print(f"✅ Saved vector DB for {meta['title']} at {db_path}\n")

        except Exception as e:
            print(f"❌ Error processing {meta['title']}: {e}\n")

    print("============================")
    print(f"📊 TOTAL: {total_tokens:,} tokens")
    print("============================")

if __name__ == "__main__":
    track_and_embed()
