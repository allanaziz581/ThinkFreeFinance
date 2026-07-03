"""Item 3: the look-ahead-contaminated backtest must not reach the Chef GPT briefing.

assemble_inputs() must not surface a backtest key, build_prompt() must not emit the
Strategy Validation section or any CAGR/Sharpe backtest wording, and the archived metrics
file must live under archived_contaminated/ (not where the runner used to read it).
"""
import importlib
from pathlib import Path

chef = importlib.import_module("chef_gpt")

BASE = Path(chef.__file__).parent


def test_assemble_inputs_has_no_backtest_key():
    inputs = chef.assemble_inputs()
    assert "backtest_metrics" not in inputs


def test_prompt_omits_backtest_section():
    # Minimal inputs: every source empty. The prompt must still build and must not carry
    # a strategy-validation / backtest block.
    inputs = {
        "user_profile": {}, "economic_reasoning": {}, "sector_summaries": {},
        "technical_signals": [], "recession_data": {}, "political_trades": {},
        "historical_parallels": {}, "opportunity_scores": {}, "quantlib_metrics": {},
    }
    prompt = chef.build_prompt(inputs)
    lowered = prompt.lower()
    assert "strategy validation" not in lowered
    assert "backtest" not in lowered
    assert "cagr" not in lowered


def test_contaminated_metrics_archived_not_live():
    live = BASE / "Module_2_Technical_Analysis" / "results_run" / "summary_metrics.json"
    archived = (BASE / "Module_2_Technical_Analysis" / "results_run"
                / "archived_contaminated" / "summary_metrics.CONTAMINATED.json")
    assert not live.exists(), "contaminated summary_metrics.json is still in the live path"
    assert archived.exists(), "archived contaminated metrics file is missing"
