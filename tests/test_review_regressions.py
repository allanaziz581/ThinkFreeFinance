import importlib.util
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
import numeral_validation as nv
import phase4_clustering as pc
import controller
from agents import security_audit as scan
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('review_news',ROOT/'webapp/build_news_intel.py')
news=importlib.util.module_from_spec(spec);spec.loader.exec_module(news)

@pytest.mark.parametrize('n',[0,1,3,5,10])
def test_clustering_small_batches(n):
 rows=[{'title':str(i)} for i in range(n)]
 out=pc.cluster_with_embeddings(rows,np.random.default_rng(1).random((n,8)))
 assert sorted(i for indices in out.values() for i in indices)==list(range(n))

def test_small_financial_amounts_are_checked():
 assert not nv.validate_numerals([], 'Revenue grew 8%')['ok']
 assert not nv.validate_numerals([], 'The fee was $3')['ok']
 assert not nv.validate_numerals([], 'Founded in 2024',strict=True)['ok']

def test_news_rejects_unsupported_numbers_and_removes_raw_prose():
 out=news.checked_summary('Revenue grew 47.5%', '', [{'headline':'Revenue grew 3.2%'}])
 assert out['source_check']['status']=='withheld'
 assert '47.5%' not in out['summary']

def test_news_accepts_supported_rounding_with_explicit_scope():
 out=news.checked_summary('Revenue grew 12.3%', '', [{'headline':'Revenue grew 12.34%'}],['economic context'])
 assert out['source_check']['status']=='checked'
 assert out['source_check']['missing_sources']==['economic context']
 assert 'attribution' in out['source_check']['scope']

def test_news_missing_ticker_sources_withholds_even_nonnumeric_prose():
 assert news.checked_summary('Strong growth', '', [])['source_check']['status']=='withheld'

def test_scanner_distinguishes_prefixes_from_actual_tokens(tmp_path,monkeypatch):
 p=tmp_path/'example.py';p.write_text('provider_prefix = "sk-proj-"')
 monkeypatch.setattr(scan,'repository_files',lambda root:[p])
 assert scan.scan_repository(tmp_path)==[]
 token='sk-proj-'+('z'*45);p.write_text('value = '+repr(token))
 result=scan.scan_repository(tmp_path)
 assert len(result)==1 and token not in str(result[0].to_dict())

def test_scanner_exits_nonzero_on_scan_errors_and_findings():
 assert scan.exit_code({'verdict':'PASS'})==0
 for result in [{'verdict':'FAIL'},{'verdict':'ERROR'},{}]: assert scan.exit_code(result)==1

@pytest.mark.parametrize('failed_audit',['security','data'])
def test_pipeline_stops_on_audit_failure(monkeypatch,failed_audit):
 args=SimpleNamespace(list=False,audit=False,phase=None,from_phase=None,chef_only=False,skip_scraping=False,skip_audit=False)
 monkeypatch.setattr(controller,'parse_args',lambda:args)
 monkeypatch.setattr(controller,'check_env',lambda:None)
 monkeypatch.setattr(controller,'load_state',lambda:{})
 steps=[{'id':2,'required':True,'audit_checkpoint':'data'}, {'id':3,'required':True,'audit_checkpoint':None}]
 monkeypatch.setattr(controller,'PIPELINE',steps)
 called=[]
 monkeypatch.setattr(controller,'run_phase',lambda step,state:called.append(step['id']) or True)
 monkeypatch.setattr(controller,'run_audit_checkpoint',lambda stage:stage!=failed_audit)
 with pytest.raises(SystemExit) as exc: controller.main()
 assert exc.value.code==1
 assert called==([] if failed_audit=='security' else [2])

def test_throughput_log_deduplicates_actual_processed_records(tmp_path):
 from pipeline_metrics import record_extraction
 from scripts.summarize_extraction_runs import summarize
 docs=[{'url':'https://example.test/a'},{'url':'https://example.test/b'}]
 record_extraction(docs,docs[:1],0.5,tmp_path)
 record_extraction(docs,docs,0.7,tmp_path)
 assert list(summarize(tmp_path).values())==[2]
 # A fresh checkout has no observed historical throughput.
 assert summarize(tmp_path/'missing')=={}

def test_actual_website_generation_withholds_bad_numeric_output(tmp_path,monkeypatch):
 import json
 js=tmp_path/'js';js.mkdir()
 (js/'data.js').write_text('window.TF_DATA = '+json.dumps({'news':[{'symbol':'AAA','headline':'AAA revenue rose 3.2%','sector':'Technology'}]})+';')
 monkeypatch.setattr(news,'JS',js);monkeypatch.setattr(news,'ROOT',tmp_path)
 monkeypatch.setattr(news,'OUT',js/'news_intel.js');monkeypatch.setattr(news,'OPENAI_KEY','synthetic-test-only')
 monkeypatch.setattr(news,'chat_json',lambda *args:{'sector_summary':'Revenue grew 8%','tickers':{'AAA':{'summary':'Revenue rose 47.5%'}}})
 news.main()
 result=json.loads(news.OUT.read_text().split('window.NEWS_INTEL = ',1)[1].strip().rstrip(';'))
 assert result['bySector']['Information Technology']['source_check']['status']=='withheld'
 assert result['byTicker']['AAA']['source_check']['status']=='withheld'
 assert '47.5%' not in result['byTicker']['AAA']['summary']
 assert result['generated_at']

def test_failed_website_generation_preserves_existing_output(tmp_path,monkeypatch):
 js=tmp_path/'js';js.mkdir();out=js/'news_intel.js';out.write_text('existing artifact')
 (js/'data.js').write_text('window.TF_DATA = {"news":[]};')
 monkeypatch.setattr(news,'JS',js);monkeypatch.setattr(news,'ROOT',tmp_path)
 monkeypatch.setattr(news,'OUT',out);monkeypatch.setattr(news,'OPENAI_KEY','synthetic-test-only')
 with pytest.raises(SystemExit,match='No summaries'):news.main()
 assert out.read_text()=='existing artifact'

def test_report_validation_excludes_bookkeeping_but_checks_nested_prose():
 from chef_gpt import report_prose
 text=report_prose({'generated_at':'2026-10-08T18:32:15Z','data_sources_used':['source 99'],
                    'sections':[{'text':'Revenue rose 8%'}]})
 assert text=='Revenue rose 8%'
 assert not nv.validate_numerals([],text,strict=True)['ok']

@pytest.mark.parametrize('mode',['chef_only','phase'])
def test_shortcut_modes_cannot_bypass_security_preflight(monkeypatch,mode):
 args=SimpleNamespace(list=False,audit=False,phase='11' if mode=='phase' else None,
                      from_phase=None,chef_only=mode=='chef_only',skip_scraping=False,skip_audit=False)
 monkeypatch.setattr(controller,'parse_args',lambda:args)
 monkeypatch.setattr(controller,'check_env',lambda:None)
 monkeypatch.setattr(controller,'load_state',lambda:{})
 monkeypatch.setattr(controller,'run_audit_checkpoint',lambda stage:False)
 monkeypatch.setattr(controller,'run_phase',lambda *args:pytest.fail('Generation ran before preflight passed'))
 with pytest.raises(SystemExit) as exc:controller.main()
 assert exc.value.code==1
