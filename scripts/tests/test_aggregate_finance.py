"""
Tests for the build_finance() function in aggregate.py.

Verifies:
  - Four boxes render the expected rounded values from a sample statement.
  - Pending state (bad assessment status) renders all boxes with the pending message.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from aggregate import build_finance, Source


# ── Mock source ───────────────────────────────────────────────────────────────

class MockSource(Source):
    """Returns pre-baked dicts instead of hitting disk or the network."""

    def __init__(self, data: dict):
        super().__init__(local_base=None)
        self._data = data  # {site: {rel_path: value}}

    def get(self, site: str, rel: str):
        return self._data.get(site, {}).get(rel)


# ── Sample financial statement ────────────────────────────────────────────────

SAMPLE_STMT = [
    {
        "period_label": "April 2026",
        "fiscal_month": 8,
        "general_fund": {
            "revenue_budget":       762_987_223,
            "revenue_actual":       595_890_119,
            "revenue_pct":          78.10,
            "expenditure_budget":   772_585_769,
            "expenditure_actual":   418_241_769,
            "expenditure_pct":      55.53,
        },
        "yearend_projection": {
            "projected_revenue":    767_606_590,
            "projected_expenditure":764_262_982,
            "other_financing_uses":   8_000_000,
            "projected_net_change":  -4_656_392,
            "projected_fund_balance":159_387_501,
        },
        "bond_2023": {
            "authorized":         1_972_877_000,
            "expended_encumbered":1_476_433_959,
            "pct_expended":       74.8,
        },
    }
]

SAMPLE_META       = {"total_spend": 2_374_334_476.36, "last_updated": "2026-06-11T21:48:03Z"}
SAMPLE_ASSESSMENT_OK     = {"status": "ok"}
SAMPLE_ASSESSMENT_FAILED = {"status": "postcheck_failed"}


def _make_src(assessment=SAMPLE_ASSESSMENT_OK):
    return MockSource({
        "finance": {
            "data/meta.json":                   SAMPLE_META,
            "data/financial_statements.json":   SAMPLE_STMT,
            "data/assessment.json":             assessment,
        }
    })


# ── Tests: normal (ok) state ──────────────────────────────────────────────────

def test_report_not_pending():
    result = build_finance(_make_src())
    assert result["report_pending"] is False
    assert result["report_month"] == "April 2026"


def test_box1_budget_year_progress():
    m = build_finance(_make_src())["metrics"][0]
    assert m["label"] == "Budget Year Progress"
    assert m["value"] == "Month 8 of 12"
    # revenue_pct 78.10 → round → 78; expenditure_pct 55.53 → round → 56
    assert "78%" in m["sub"]
    assert "56%" in m["sub"]
    assert m.get("context") is True


def test_box2_reserves():
    m = build_finance(_make_src())["metrics"][1]
    assert m["label"] == "Reserves"
    # months = 159_387_501 / (764_262_982 / 12) ≈ 2.503 → 2.5
    assert "2.5" in m["value"]
    # projected balance 159_387_501 → $159M (rounded to nearest million)
    assert "$159M" in m["sub"]
    assert "Aug 31" in m["sub"]


def test_box3_year_end_outlook():
    m = build_finance(_make_src())["metrics"][2]
    assert m["label"] == "Year-End Outlook"
    # proj_net = -4_656_392 → "Savings down ~$4.7M"
    assert "Savings down" in m["value"]
    assert "4.7M" in m["value"]
    # budget_net = 762_987_223 - 772_585_769 - 8_000_000 = -17_598_546 → $17.6M
    # proj (-4.7M) > budget (-17.6M), both negative → "Smaller drawdown than budgeted $17.6M"
    assert m["sub"] is not None
    assert "17.6M" in m["sub"]
    assert "Smaller drawdown" in m["sub"]


def test_box4_bond_program():
    m = build_finance(_make_src())["metrics"][3]
    assert m["label"] == "2023 Bond Program"
    # authorized = 1_972_877_000 → $1.97B; pct_expended 74.8 → round → 75
    assert "$1.97B" in m["value"]
    assert "75%" in m["value"]
    # expended = 1_476_433_959 → $1.48B
    assert "$1.48B" in m["sub"]
    assert "$1.97B" in m["sub"]


def test_all_boxes_have_finance_url():
    metrics = build_finance(_make_src())["metrics"]
    for m in metrics:
        assert m.get("link") == "https://cisd-finance.boardmonitor.app"


# ── Tests: pending state ──────────────────────────────────────────────────────

def test_pending_when_assessment_not_ok():
    result = build_finance(_make_src(assessment=SAMPLE_ASSESSMENT_FAILED))
    assert result["report_pending"] is True
    assert result["report_month"] is None


def test_pending_all_boxes_show_message():
    metrics = build_finance(_make_src(assessment=SAMPLE_ASSESSMENT_FAILED))["metrics"]
    assert len(metrics) == 4
    for m in metrics:
        assert m["value"] == "Latest report pending review"


def test_pending_when_no_statement():
    src = MockSource({
        "finance": {
            "data/meta.json":     SAMPLE_META,
            "data/assessment.json": SAMPLE_ASSESSMENT_OK,
            # financial_statements.json intentionally absent
        }
    })
    result = build_finance(src)
    assert result["report_pending"] is True


def test_pending_preserves_four_box_labels():
    metrics = build_finance(_make_src(assessment=SAMPLE_ASSESSMENT_FAILED))["metrics"]
    labels = [m["label"] for m in metrics]
    assert labels == ["Budget Year Progress", "Reserves", "Year-End Outlook", "2023 Bond Program"]
