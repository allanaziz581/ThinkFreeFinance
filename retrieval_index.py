"""FAISS reference retrieval shared by the economic pipeline and offline tests.

Embeddings must come from the same model for both documents and queries. Stored
assets are local, trusted data; no pickle deserialization is used.
"""
from pathlib import Path
import json
import faiss
import numpy as np

class ReferenceIndex:
    def __init__(self, index, documents):
        if index.ntotal != len(documents):
            raise ValueError('Index/document count mismatch')
        self.index, self.documents = index, documents

    @classmethod
    def build(cls, documents, embeddings):
        vectors=np.asarray(embeddings,dtype='float32')
        if vectors.ndim != 2 or not len(documents) or len(vectors)!=len(documents):
            raise ValueError('Provide one embedding for each nonempty reference document')
        if not np.isfinite(vectors).all(): raise ValueError('Embeddings must be finite')
        index=faiss.IndexFlatL2(vectors.shape[1]);index.add(vectors)
        return cls(index,documents)

    @classmethod
    def load(cls, directory):
        directory=Path(directory)
        index_path=directory/'economic_knowledge_index.faiss'
        metadata_path=directory/'economic_knowledge_metadata.json'
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError('Reference assets missing. See README: build_reference_index.py; API-backed generation needs your own authorized source documents.')
        return cls(faiss.read_index(str(index_path)),json.loads(metadata_path.read_text()))

    def save(self,directory):
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        faiss.write_index(self.index,str(directory/'economic_knowledge_index.faiss'))
        (directory/'economic_knowledge_metadata.json').write_text(json.dumps(self.documents,indent=2))

    def search(self,embedding,k=6):
        query=np.asarray(embedding,dtype='float32').reshape(1,-1)
        if query.shape[1]!=self.index.d or not np.isfinite(query).all():
            raise ValueError('Query embedding must match index dimensions and be finite')
        if k<1: raise ValueError('k must be positive')
        _,indices=self.index.search(query,min(k,len(self.documents)))
        return [self.documents[int(i)] for i in indices[0] if i>=0]
