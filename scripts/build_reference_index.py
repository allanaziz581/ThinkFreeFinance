"""Build the economic-reference index from authorized JSON documents.

Explicitly calls the configured embedding API and can incur charges. Expected
input: [{"title": "...", "text": "..."}, ...]. Not invoked by offline tests.
"""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from openai import OpenAI
from retrieval_index import ReferenceIndex

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('documents',type=Path)
    p.add_argument('--output',type=Path,default=Path('Economic_Books/FAISS_Store'))
    args=p.parse_args();documents=json.loads(args.documents.read_text())
    if not isinstance(documents,list) or not documents or any(not isinstance(d,dict) or not isinstance(d.get('text'),str) or not d['text'].strip() for d in documents):
        p.error('Input must be a nonempty JSON array of documents with text')
    load_dotenv();client=OpenAI();vectors=[]
    for start in range(0,len(documents),32):
        batch=documents[start:start+32]
        response=client.embeddings.create(model='text-embedding-ada-002',input=[d['text'] for d in batch])
        vectors.extend(item.embedding for item in sorted(response.data,key=lambda item:item.index))
    ReferenceIndex.build(documents,vectors).save(args.output)
    print(f'Saved {len(documents)} reference documents to {args.output}')
if __name__=='__main__':main()
