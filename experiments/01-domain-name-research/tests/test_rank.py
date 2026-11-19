from domain_research.pipeline import parse_report, rank
from domain_research.schemas import Candidate, CandidateList, Quote, Verdict, VerdictList


def candidates(*domains):
    return CandidateList(candidates=[Candidate(domain=d, guideline="g", reasoning="r") for d in domains])


def quote(domain, provider, status, price=None):
    return Quote(domain=domain, provider=provider, status=status, price=price)


def test_orders_by_cheapest_price_and_keeps_other_prices():
    final = rank(
        candidates("b.com", "a.com"),
        [
            quote("b.com", "godaddy", "available", 20.0),
            quote("b.com", "porkbun", "available", 9.0),
            quote("a.com", "godaddy", "available", 12.0),
        ],
        None,
    )
    assert [(r.domain, r.provider, r.price) for r in final.ranked] == [
        ("b.com", "porkbun", 9.0),
        ("a.com", "godaddy", 12.0),
    ]
    assert final.ranked[0].other_prices == {"godaddy": 20.0}


def test_taken_anywhere_is_dropped_even_if_the_judge_keeps_it():
    final = rank(
        candidates("a.com"),
        [quote("a.com", "godaddy", "available", 5.0), quote("a.com", "registry", "taken")],
        VerdictList(verdicts=[Verdict(domain="a.com", keep=True, reason="nice")]),
    )
    assert final.ranked == []
    assert "registry" in final.dropped[0].reason


def test_judge_can_drop_and_unknown_only_is_dropped():
    final = rank(
        candidates("a.com", "b.com"),
        [quote("a.com", "godaddy", "available", 5.0), quote("b.com", "godaddy", "unknown")],
        VerdictList(verdicts=[Verdict(domain="a.com", keep=False, reason="brand clash")]),
    )
    assert final.ranked == []
    assert {d.domain: d.reason for d in final.dropped} == {
        "a.com": "judge: brand clash",
        "b.com": "no provider confirmed availability",
    }


def test_unpriced_available_domain_is_listed_last_with_a_flag():
    final = rank(
        candidates("a.com", "b.com"),
        [quote("a.com", "registry", "available"), quote("b.com", "porkbun", "available", 30.0)],
        None,
    )
    assert [r.domain for r in final.ranked] == ["b.com", "a.com"]
    assert any("no provider returned a price" in f for f in final.ranked[1].flags)


def test_parse_report_ignores_text_that_is_not_a_report():
    assert parse_report("Lookup finished.") is None
    assert parse_report('{"provider": "x", "quotes": []}').provider == "x"
