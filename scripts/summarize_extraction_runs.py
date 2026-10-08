"""Print observed UTC daily extraction totals, deduplicated across logged runs."""
import argparse,json
from collections import defaultdict
from pathlib import Path

def summarize(directory):
    daily=defaultdict(set)
    for p in Path(directory).glob('*.json'):
        doc=json.loads(p.read_text())
        if doc.get('stage')=='article_extraction':
            daily[doc['completed_at'][:10]].update(doc['processed_article_hashes'])
    return {day:len(ids) for day,ids in sorted(daily.items())}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',nargs='?',default='run_metrics')
    totals=summarize(parser.parse_args().directory)
    print(json.dumps({'utc_daily_unique_extractions':totals,
                     'scope':'Only observed logged runs; no historical volume inferred.'},indent=2))
