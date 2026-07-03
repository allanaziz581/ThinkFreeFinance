"""Item 10: numeral set-membership validation must flag numbers a GPT output invented that
are NOT in the source, comparing normalized values with a rounding tolerance (not raw
tokens), while ignoring years and small counts.
"""
import importlib

nv = importlib.import_module("numeral_validation")


def test_extract_handles_currency_commas_percent():
    nums = nv.extract_numerals("GDP fell 3.2% to $1,200.50 in 2022, up from -0.5%")
    assert 3.2 in nums
    assert 1200.5 in nums
    assert 2022.0 in nums
    assert -0.5 in nums


def test_rounding_tolerance_matches_not_raw_tokens():
    # source says 12.34%, output rounds to 12.3% -> must be accepted (normalized, not token)
    res = nv.validate_numerals([12.34], "inflation was 12.3%")
    assert res["ok"] is True
    assert res["hallucinated"] == []


def test_dollar_comma_normalization_matches():
    res = nv.validate_numerals([1200.0], "the contract was worth $1,200")
    assert res["ok"] is True


def test_flags_hallucinated_number():
    res = nv.validate_numerals([5.0, 100.0], "the market surged 47.5% overnight")
    assert res["ok"] is False
    assert 47.5 in res["hallucinated"]
    assert res["hallucinated_count"] == 1


def test_years_and_small_counts_are_ignored():
    # empty source, but the output only has a year and a small count -> nothing to flag
    res = nv.validate_numerals([], "In 2022 the 8 warning signs across 3 sectors were clear")
    assert res["ok"] is True
    assert res["checked"] == 0


def test_collect_numbers_walks_nested_structure():
    src = {"a": "vol 22.5%", "b": [{"c": 4.1}, "spread -0.3"], "d": True}
    nums = nv.collect_numbers(src)
    assert 22.5 in nums and 4.1 in nums and -0.3 in nums
    assert True not in nums   # booleans are not numbers


def test_relative_tolerance_for_large_numbers():
    # 1,000,000 vs 1,005,000 is within 1% relative tolerance -> accepted
    res = nv.validate_numerals([1_000_000.0], "spending hit $1,005,000")
    assert res["ok"] is True
