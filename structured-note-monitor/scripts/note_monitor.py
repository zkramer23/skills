#!/usr/bin/env python3
"""Build an as-of structured-note event ledger from inventory and observations.

Depends on the sibling structured-note-payoff-engine skill for deterministic
coupon/autocall calculations. Pure standard library otherwise.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence


_SKILLS_ROOT = Path(__file__).resolve().parents[2]
_PAYOFF_SCRIPTS = _SKILLS_ROOT / "structured-note-payoff-engine" / "scripts"
if str(_PAYOFF_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_PAYOFF_SCRIPTS))

try:
    from payoff_engine import SpecError, evaluate_path, validate_spec
except ImportError as exc:  # pragma: no cover - installation failure path
    raise RuntimeError(
        "structured-note-payoff-engine must be installed beside structured-note-monitor"
    ) from exc


class MonitorError(ValueError):
    """Raised when monitor-level inputs violate the inventory contract."""


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MonitorError(f"{path} must be an object")
    return value


def _number(value: object, path: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MonitorError(f"{path} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise MonitorError(f"{path} must be finite")
    if minimum is not None and result < minimum:
        raise MonitorError(f"{path} must be >= {minimum}")
    return result


def _date(value: object, path: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise MonitorError(f"{path} must be ISO YYYY-MM-DD") from exc


def _finding(
    severity: str,
    code: str,
    message: str,
    *,
    note_id: str | None = None,
    event_date: str | None = None,
) -> dict[str, object]:
    return {
        "severity": severity,
        "code": code,
        "note_id": note_id,
        "date": event_date,
        "message": message,
    }


def _load_spec(note: Mapping[str, Any], inventory_dir: Path) -> Mapping[str, Any]:
    inline = note.get("spec")
    path_value = note.get("payoff_spec")
    if (inline is None) == (path_value is None):
        raise MonitorError("provide exactly one of spec or payoff_spec")
    if inline is not None:
        return _mapping(inline, "spec")
    path = Path(str(path_value))
    if not path.is_absolute():
        path = inventory_dir / path
    value = json.loads(path.read_text())
    return _mapping(value, str(path))


def _normalize_observations(
    observations: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Mapping[str, Any]]], list[dict[str, object]]]:
    grouped: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    findings: list[dict[str, object]] = []
    for index, raw in enumerate(observations):
        row = _mapping(raw, f"observations[{index}]")
        note_id = str(row.get("note_id") or "").strip()
        if not note_id:
            raise MonitorError(f"observations[{index}].note_id must be non-empty")
        event_date = _date(row.get("date"), f"observations[{index}].date").isoformat()
        if event_date in grouped[note_id]:
            raise MonitorError(f"duplicate observation ({note_id!r}, {event_date!r})")
        if not isinstance(row.get("levels"), Mapping):
            raise MonitorError(f"observations[{index}].levels must be an object")
        grouped[note_id][event_date] = row
        if not str(row.get("source") or "").strip():
            findings.append(_finding(
                "warning",
                "MISSING_OBSERVATION_SOURCE",
                "market observation has no source",
                note_id=note_id,
                event_date=event_date,
            ))
        if not str(row.get("retrieved_at") or "").strip():
            findings.append(_finding(
                "warning",
                "MISSING_RETRIEVAL_TIME",
                "market observation has no retrieval timestamp",
                note_id=note_id,
                event_date=event_date,
            ))
    return grouped, findings


def _official_map(note: Mapping[str, Any], note_id: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    values = note.get("official_determinations", [])
    if not isinstance(values, list):
        raise MonitorError("official_determinations must be an array")
    for index, raw in enumerate(values):
        item = _mapping(raw, f"official_determinations[{index}]")
        event_date = _date(item.get("date"), f"official_determinations[{index}].date").isoformat()
        if event_date in result:
            raise MonitorError(f"duplicate official determination ({note_id!r}, {event_date!r})")
        if not str(item.get("source") or "").strip():
            raise MonitorError(f"official determination {event_date} requires source")
        if not any(key in item for key in ("coupon_status", "coupon_payment", "call_status", "call_redemption")):
            raise MonitorError(f"official determination {event_date} states no determination fields")
        result[event_date] = item
    return result


def _issuer_notices(note: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    values = note.get("official_notices", [])
    if not isinstance(values, list):
        raise MonitorError("official_notices must be an array")
    result: list[Mapping[str, Any]] = []
    for index, raw in enumerate(values):
        item = _mapping(raw, f"official_notices[{index}]")
        if item.get("type") != "issuer_call":
            raise MonitorError(f"unsupported official_notices[{index}].type")
        _date(item.get("effective_date"), f"official_notices[{index}].effective_date")
        if not str(item.get("source") or "").strip():
            raise MonitorError(f"official_notices[{index}] requires source")
        result.append(item)
    return result


def _different(indicative: object, official: object) -> bool:
    if indicative is None or official is None:
        return False
    if str(indicative).startswith("UNDETERMINED") or indicative in {
        "ISSUER_ELECTIVE",
        "NOT_APPLICABLE",
    }:
        return False
    if isinstance(indicative, (int, float)) and isinstance(official, (int, float)):
        return not math.isclose(float(indicative), float(official), rel_tol=1e-9, abs_tol=1e-9)
    return indicative != official


def _timing(event_date: date, as_of: date, horizon_end: date, state: str) -> str:
    if state == "CANCELLED_BY_CALL":
        return "CANCELLED"
    if event_date < as_of:
        return "OVERDUE" if state in {"UNRESOLVED", "NOTICE_REQUIRED"} else "COMPLETED"
    if event_date == as_of:
        return "TODAY"
    if event_date <= horizon_end:
        return "UPCOMING"
    return "FUTURE"


def compile_ledger(
    inventory: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
    horizon_days: int = 45,
    inventory_dir: Path | None = None,
) -> dict[str, object]:
    if horizon_days < 0:
        raise MonitorError("horizon_days must be >= 0")
    inventory_dir = inventory_dir or Path.cwd()
    notes_raw = inventory.get("notes")
    if not isinstance(notes_raw, list):
        raise MonitorError("inventory.notes must be an array")
    note_ids = [str(_mapping(note, f"notes[{index}]").get("note_id") or "").strip()
                for index, note in enumerate(notes_raw)]
    if any(not note_id for note_id in note_ids):
        raise MonitorError("every note_id must be non-empty")
    if len(note_ids) != len(set(note_ids)):
        raise MonitorError("note_id values must be unique")

    grouped_observations, findings = _normalize_observations(observations)
    known_notes = set(note_ids)
    for unknown in sorted(set(grouped_observations).difference(known_notes)):
        findings.append(_finding(
            "warning", "UNKNOWN_OBSERVATION_NOTE", "observation does not match inventory", note_id=unknown
        ))

    horizon_end = as_of + timedelta(days=horizon_days)
    note_results: list[dict[str, object]] = []
    events: list[dict[str, object]] = []
    for index, raw_note in enumerate(notes_raw):
        note = _mapping(raw_note, f"notes[{index}]")
        note_id = str(note["note_id"]).strip()
        try:
            spec = _load_spec(note, inventory_dir)
            spec_findings = validate_spec(spec)
            if spec["note_id"] != note_id:
                raise MonitorError(
                    f"inventory note_id {note_id!r} does not match spec note_id {spec['note_id']!r}"
                )
            position_notional = _number(
                note.get("position_notional", spec["notional"]),
                "position_notional",
                minimum=0.0,
            )
            currency = str(note.get("currency") or "").strip()
            if not currency:
                raise MonitorError("currency must be non-empty")
            multiplier = position_notional / float(spec["notional"])
            official = _official_map(note, note_id)
            notices = _issuer_notices(note)
            note_observations = grouped_observations.get(note_id, {})
            engine_observations = [
                {"date": event_date, "levels": row["levels"]}
                for event_date, row in sorted(note_observations.items())
            ]
            raw_indicative_rows = evaluate_path(spec, engine_observations)
            indicative_rows = evaluate_path(spec, engine_observations, official)
            raw_indicative = {str(row["date"]): row for row in raw_indicative_rows}
            indicative = {str(row["date"]): row for row in indicative_rows}

            indicative_call_dates = [
                _date(row["date"], "call date")
                for row in indicative_rows
                if row.get("call_status") == "CALLED" and _date(row["date"], "call date") <= as_of
            ]
            official_call_dates = [
                _date(event_date, "official call date")
                for event_date, row in official.items()
                if row.get("call_status") == "CALLED" and _date(event_date, "official call date") <= as_of
            ]
            active_notices = [
                item for item in notices
                if _date(item["effective_date"], "notice effective_date") <= as_of
            ]
            issuer_call_dates = [
                _date(item["effective_date"], "notice effective_date") for item in active_notices
            ]
            notices_by_date = {
                str(item["effective_date"]): item for item in active_notices
            }
            termination_dates = official_call_dates + issuer_call_dates + indicative_call_dates
            termination_date = min(termination_dates) if termination_dates else None
            officially_called = bool(official_call_dates or issuer_call_dates)
            indicatively_called = bool(indicative_call_dates)

            for message in spec_findings:
                findings.append(_finding("warning", "PAYOFF_SPEC_FINDING", message, note_id=note_id))

            note_events: list[dict[str, object]] = []
            for schedule_row in spec.get("schedule", []):
                event_date_text = str(schedule_row["date"])
                event_date = _date(event_date_text, "schedule date")
                row = indicative.get(event_date_text)
                raw_row = raw_indicative.get(event_date_text)
                determination = official.get(event_date_text)
                observation = note_observations.get(event_date_text)
                notice = notices_by_date.get(event_date_text)
                has_official_basis = event_date <= as_of and (
                    determination is not None or notice is not None
                )
                basis = "official" if has_official_basis else "indicative"

                final_values = {
                    "coupon_status": row.get("coupon_status") if row else None,
                    "coupon_payment": row.get("coupon_payment") if row else None,
                    "call_status": row.get("call_status") if row else None,
                    "call_redemption": row.get("call_redemption") if row else None,
                }
                if determination is not None and event_date <= as_of:
                    for key in final_values:
                        if key in determination:
                            raw_value = raw_row.get(key) if raw_row else None
                            if _different(raw_value, determination[key]):
                                findings.append(_finding(
                                    "warning",
                                    "OFFICIAL_INDICATIVE_CONFLICT",
                                    f"{key}: indicative={raw_value!r}, official={determination[key]!r}",
                                    note_id=note_id,
                                    event_date=event_date_text,
                                ))
                            final_values[key] = determination[key]
                if notice is not None and event_date <= as_of:
                    final_values["call_status"] = "CALLED"

                if termination_date is not None and event_date > termination_date:
                    state = "CANCELLED_BY_CALL"
                elif event_date > as_of:
                    state = "SCHEDULED"
                elif row is None and not has_official_basis:
                    state = "UNRESOLVED"
                else:
                    unresolved = any(
                        str(final_values[key] or "").startswith("UNDETERMINED")
                        for key in ("coupon_status", "call_status")
                    )
                    if unresolved:
                        state = "UNRESOLVED"
                    elif final_values["call_status"] == "ISSUER_ELECTIVE":
                        state = "NOTICE_REQUIRED"
                    elif has_official_basis:
                        state = "OFFICIAL"
                    else:
                        state = "INDICATIVE"
                if state in {"UNRESOLVED", "NOTICE_REQUIRED"} and event_date <= as_of:
                    findings.append(_finding(
                        "blocker" if state == "UNRESOLVED" else "warning",
                        "PAST_EVENT_UNRESOLVED" if state == "UNRESOLVED" else "ISSUER_NOTICE_REQUIRED",
                        "past event requires resolution" if state == "UNRESOLVED" else "issuer-election outcome requires notice",
                        note_id=note_id,
                        event_date=event_date_text,
                    ))

                coupon_payment = final_values["coupon_payment"]
                call_redemption = final_values["call_redemption"]
                event = {
                    "portfolio_id": inventory.get("portfolio_id"),
                    "note_id": note_id,
                    "event_type": "OBSERVATION",
                    "date": event_date_text,
                    "payment_date": schedule_row.get("payment_date"),
                    "event_state": state,
                    "timing": _timing(event_date, as_of, horizon_end, state),
                    "basis": basis,
                    "performance": row.get("performance") if row else None,
                    "missing_reason": row.get("missing_reason") if row else None,
                    **final_values,
                    "position_coupon_payment": (
                        float(coupon_payment) * multiplier if coupon_payment is not None else None
                    ),
                    "position_call_redemption": (
                        float(call_redemption) * multiplier if call_redemption is not None else None
                    ),
                    "currency": currency,
                    "source": determination.get("source") if determination else (
                        notice.get("source") if notice else (
                            observation.get("source") if observation else None
                        )
                    ),
                    "retrieved_at": observation.get("retrieved_at") if observation else None,
                }
                note_events.append(event)
                events.append(event)

            for notice in active_notices:
                notice_date = _date(notice["effective_date"], "notice effective_date")
                notice_event = {
                    "portfolio_id": inventory.get("portfolio_id"),
                    "note_id": note_id,
                    "event_type": "ISSUER_CALL_NOTICE",
                    "date": notice_date.isoformat(),
                    "payment_date": None,
                    "event_state": "OFFICIAL_NOTICE",
                    "timing": _timing(notice_date, as_of, horizon_end, "OFFICIAL_NOTICE"),
                    "basis": "official",
                    "performance": None,
                    "coupon_status": None,
                    "coupon_payment": None,
                    "call_status": "CALLED",
                    "call_redemption": None,
                    "position_coupon_payment": None,
                    "position_call_redemption": None,
                    "currency": currency,
                    "source": notice["source"],
                    "retrieved_at": None,
                }
                note_events.append(notice_event)
                events.append(notice_event)

            unresolved = any(
                event["event_state"] in {"UNRESOLVED", "NOTICE_REQUIRED"}
                and _date(event["date"], "event date") <= as_of
                for event in note_events
            )
            maturity_raw = note.get("maturity_date")
            maturity = _date(maturity_raw, "maturity_date") if maturity_raw is not None else None
            if officially_called:
                note_state = "OFFICIALLY_CALLED"
            elif indicatively_called:
                note_state = "INDICATIVELY_CALLED"
            elif maturity is not None and maturity <= as_of:
                note_state = "MATURED_WITH_UNRESOLVED_EVENTS" if unresolved else "MATURED"
            elif unresolved:
                note_state = "ACTIVE_WITH_UNRESOLVED_EVENTS"
            else:
                note_state = "ACTIVE"
            note_results.append({
                "note_id": note_id,
                "state": note_state,
                "position_notional": position_notional,
                "currency": currency,
                "maturity_date": maturity.isoformat() if maturity else None,
                "termination_date": termination_date.isoformat() if termination_date else None,
                "event_count": len(note_events),
                "unresolved_event_count": sum(
                    event["event_state"] in {"UNRESOLVED", "NOTICE_REQUIRED"}
                    for event in note_events
                ),
            })
        except (OSError, json.JSONDecodeError, SpecError, MonitorError) as exc:
            findings.append(_finding("blocker", "INVALID_NOTE", str(exc), note_id=note_id))
            note_results.append({
                "note_id": note_id,
                "state": "INVALID",
                "position_notional": note.get("position_notional"),
                "currency": note.get("currency"),
                "maturity_date": note.get("maturity_date"),
                "termination_date": None,
                "event_count": 0,
                "unresolved_event_count": 0,
            })

    events.sort(key=lambda row: (str(row["date"]), str(row["note_id"]), str(row["event_type"])))
    findings.sort(key=lambda row: (
        {"blocker": 0, "warning": 1, "info": 2}.get(str(row["severity"]), 3),
        str(row.get("date") or ""),
        str(row.get("note_id") or ""),
        str(row["code"]),
    ))
    state_counts = Counter(str(note["state"]) for note in note_results)
    event_state_counts = Counter(str(event["event_state"]) for event in events)
    return {
        "portfolio_id": inventory.get("portfolio_id"),
        "as_of": as_of.isoformat(),
        "horizon_days": horizon_days,
        "horizon_end": horizon_end.isoformat(),
        "summary": {
            "notes": len(note_results),
            "note_states": dict(sorted(state_counts.items())),
            "event_states": dict(sorted(event_state_counts.items())),
            "upcoming_events": sum(event["timing"] in {"TODAY", "UPCOMING"} for event in events),
            "overdue_events": sum(event["timing"] == "OVERDUE" for event in events),
            "blockers": sum(finding["severity"] == "blocker" for finding in findings),
            "warnings": sum(finding["severity"] == "warning" for finding in findings),
        },
        "notes": note_results,
        "events": events,
        "findings": findings,
        "disclaimer": "Indicative market-derived results are subject to official determination.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory")
    parser.add_argument("observations")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--horizon-days", type=int, default=45)
    parser.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        inventory_path = Path(args.inventory)
        inventory = _mapping(json.loads(inventory_path.read_text()), args.inventory)
        observations = json.loads(Path(args.observations).read_text())
        if not isinstance(observations, list):
            raise MonitorError("observations must contain a JSON array")
        result = compile_ledger(
            inventory,
            observations,
            as_of=_date(args.as_of, "as_of"),
            horizon_days=args.horizon_days,
            inventory_dir=inventory_path.parent,
        )
        text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False)
        if args.output:
            Path(args.output).write_text(text + "\n")
        else:
            print(text)
    except (OSError, json.JSONDecodeError, MonitorError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
