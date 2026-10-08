import numpy as np
import pytest
from retrieval_index import ReferenceIndex

def test_faiss_round_trip_returns_correct_source_not_wrong_row(tmp_path):
 docs=[{'title':'Inflation','text':'Synthetic price example'}, {'title':'Employment','text':'Synthetic jobs example'}]
 idx=ReferenceIndex.build(docs,[[1.,0.],[0.,1.]])
 idx.save(tmp_path)
 loaded=ReferenceIndex.load(tmp_path)
 assert loaded.search([0.,1.],k=1)==[docs[1]]
 assert len(loaded.search([0.,1.],k=99))==2

def test_reference_assets_are_required(tmp_path):
 with pytest.raises(FileNotFoundError,match='Reference assets missing'): ReferenceIndex.load(tmp_path)

def test_mismatched_documents_and_embeddings_rejected():
 with pytest.raises(ValueError): ReferenceIndex.build([{'text':'one'}],np.zeros((2,3)))
