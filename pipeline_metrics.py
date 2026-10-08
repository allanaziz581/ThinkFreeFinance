"""Evidence from actual extraction runs; never estimates historical throughput.

No article text is stored here. Hashes support deduplication across runs; counts
measure extraction completion, not publication or factual correctness.
"""
import hashlib,json,uuid
from datetime import datetime,timezone
from pathlib import Path

def record_extraction(articles, processed_articles, elapsed_seconds, directory):
    def fingerprint(article):
        identity=article.get('url') or article.get('title') or json.dumps(article,sort_keys=True)
        return hashlib.sha256(str(identity).strip().encode()).hexdigest()
    record={
        'run_id':uuid.uuid4().hex,'completed_at':datetime.now(timezone.utc).isoformat(),
        'stage':'article_extraction','input_records':len(articles),
        'processed_records':len(processed_articles),'elapsed_seconds':round(elapsed_seconds,3),
        'processed_article_hashes':sorted({fingerprint(a) for a in processed_articles}),
        'scope':'extraction completion only; does not establish published outputs or continuous daily operation',
    }
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    path=directory/(record['run_id']+'.json');path.write_text(json.dumps(record,indent=2))
    return record
