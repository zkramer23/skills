from __future__ import annotations

from datetime import date

import pytest

from note_monitor import MonitorError, compile_ledger


def payoff_spec(*, call_type: str = "automatic", memory: bool = False) -> dict[str, object]:
    triggers = [1.10, 1.00, 0.95] if call_type == "automatic" else [None, None, None]
    return {
        "schema_version": 1,
        "note_id": "note-1",
        "product_type": "phoenix_autocall" if call_type == "automatic" else "contingent_yield_note",
        "notional": 1000.0,
        "underlier_structure": "single",
        "underliers": [{"id": "A", "initial_level": 100.0, "weight": None}],
        "terminal": {
            "upside": {
                "kind": "participation", "participation_rate": 0.0, "cap": None,
                "digital_trigger": None, "digital_return": None,
            },
            "downside": {"kind": "barrier", "barrier": 0.70, "buffer": None, "gearing": 1.0},
        },
        "income": {"coupon_barrier": 0.70, "coupon_per_period": 0.02, "memory": memory},
        "call": {"type": call_type},
        "schedule": [
            {"date": event_date, "coupon_barrier": 0.70, "coupon_amount": 0.02,
             "call_trigger": trigger, "call_premium": premium}
            for event_date, trigger, premium in zip(
                ["2026-01-15", "2026-02-15", "2026-03-15"],
                triggers,
                [0.0, 0.01, 0.02],
            )
        ],
    }


def inventory(spec: dict[str, object], **overrides: object) -> dict[str, object]:
    note = {
        "note_id": "note-1",
        "position_notional": 2000.0,
        "currency": "USD",
        "maturity_date": "2027-01-15",
        "spec": spec,
        "official_determinations": [],
        "official_notices": [],
        **overrides,
    }
    return {"portfolio_id": "portfolio", "notes": [note]}


def observation(event_date: str, level: float) -> dict[str, object]:
    return {
        "note_id": "note-1",
        "date": event_date,
        "levels": {"A": level},
        "source": "fixture",
        "retrieved_at": "2026-02-16T08:00:00-05:00",
    }


def test_indicative_call_scales_position_and_cancels_later_events() -> None:
    result = compile_ledger(
        inventory(payoff_spec()),
        [observation("2026-01-15", 80.0), observation("2026-02-15", 105.0)],
        as_of=date(2026, 2, 20),
        horizon_days=45,
    )

    assert result["notes"][0]["state"] == "INDICATIVELY_CALLED"
    called = next(event for event in result["events"] if event["call_status"] == "CALLED")
    assert called["position_call_redemption"] == pytest.approx(2020.0)
    assert result["events"][-1]["event_state"] == "CANCELLED_BY_CALL"


def test_missing_prior_call_propagates_but_future_event_stays_scheduled() -> None:
    result = compile_ledger(
        inventory(payoff_spec(memory=True)),
        [observation("2026-02-15", 105.0)],
        as_of=date(2026, 2, 20),
        horizon_days=45,
    )

    states = [event["event_state"] for event in result["events"]]
    assert states == ["UNRESOLVED", "UNRESOLVED", "SCHEDULED"]
    assert result["notes"][0]["state"] == "ACTIVE_WITH_UNRESOLVED_EVENTS"
    assert result["summary"]["overdue_events"] == 2


def test_issuer_call_requires_notice_then_official_notice_terminates() -> None:
    no_notice = compile_ledger(
        inventory(payoff_spec(call_type="issuer")),
        [observation("2026-01-15", 120.0)],
        as_of=date(2026, 1, 20),
    )
    assert no_notice["events"][0]["event_state"] == "NOTICE_REQUIRED"
    assert no_notice["notes"][0]["state"] == "ACTIVE_WITH_UNRESOLVED_EVENTS"

    with_notice = compile_ledger(
        inventory(
            payoff_spec(call_type="issuer"),
            official_notices=[{
                "type": "issuer_call",
                "effective_date": "2026-01-15",
                "source": "issuer notice",
            }],
        ),
        [observation("2026-01-15", 50.0)],
        as_of=date(2026, 1, 20),
    )
    assert with_notice["notes"][0]["state"] == "OFFICIALLY_CALLED"
    observation_event = next(
        event for event in with_notice["events"] if event["event_type"] == "OBSERVATION"
    )
    assert observation_event["event_state"] == "OFFICIAL"
    assert observation_event["call_status"] == "CALLED"
    assert not any(
        finding["code"] == "ISSUER_NOTICE_REQUIRED" for finding in with_notice["findings"]
    )
    assert any(event["event_state"] == "OFFICIAL_NOTICE" for event in with_notice["events"])
    assert with_notice["events"][-1]["event_state"] == "CANCELLED_BY_CALL"


def test_official_determination_overrides_and_records_conflict() -> None:
    result = compile_ledger(
        inventory(
            payoff_spec(),
            official_determinations=[{
                "date": "2026-01-15",
                "coupon_status": "MISSED",
                "coupon_payment": 0.0,
                "call_status": "NOT_CALLED",
                "source": "calculation agent",
            }],
        ),
        [observation("2026-01-15", 80.0)],
        as_of=date(2026, 1, 20),
    )

    assert result["events"][0]["event_state"] == "OFFICIAL"
    assert result["events"][0]["coupon_status"] == "MISSED"
    assert any(finding["code"] == "OFFICIAL_INDICATIVE_CONFLICT" for finding in result["findings"])


def test_official_prior_state_allows_later_memory_coupon_and_call() -> None:
    result = compile_ledger(
        inventory(
            payoff_spec(memory=True),
            official_determinations=[{
                "date": "2026-01-15",
                "coupon_status": "MISSED",
                "coupon_payment": 0.0,
                "missed_count": 1,
                "call_status": "NOT_CALLED",
                "source": "calculation agent",
            }],
        ),
        [observation("2026-02-15", 105.0)],
        as_of=date(2026, 2, 20),
    )

    second = next(event for event in result["events"] if event["date"] == "2026-02-15")
    assert second["coupon_status"] == "PAID"
    assert second["position_coupon_payment"] == pytest.approx(80.0)
    assert second["call_status"] == "CALLED"
    assert result["notes"][0]["state"] == "INDICATIVELY_CALLED"


def test_duplicate_observations_fail_before_batch_processing() -> None:
    row = observation("2026-01-15", 80.0)
    with pytest.raises(MonitorError, match="duplicate observation"):
        compile_ledger(inventory(payoff_spec()), [row, row], as_of=date(2026, 1, 20))
