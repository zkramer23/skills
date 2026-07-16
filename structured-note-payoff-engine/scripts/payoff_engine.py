#!/usr/bin/env python3
"""Validate and evaluate canonical structured-note payoff specifications.

Pure standard library. See ../references/payoff-spec.md for the schema.
"""

from __future__ import annotations

import argparse
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence


STRUCTURES = {"single", "worst_of", "best_of", "basket_equal_weight", "basket_defined_weight"}
UPSIDE_KINDS = {"participation", "digital"}
DOWNSIDE_KINDS = {"full", "barrier", "buffer", "principal_protected", "absolute_return"}
CALL_TYPES = {"automatic", "issuer", "none"}


class SpecError(ValueError):
    """Raised when a payoff specification violates the canonical contract."""


def _number(value: object, path: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise SpecError(f"{path} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise SpecError(f"{path} must be finite")
    if minimum is not None and result < minimum:
        raise SpecError(f"{path} must be >= {minimum}")
    return result


def _optional_number(value: object, path: str, *, minimum: float | None = None) -> float | None:
    return None if value is None else _number(value, path, minimum=minimum)


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SpecError(f"{path} must be an object")
    return value


def validate_spec(spec: Mapping[str, Any]) -> list[str]:
    """Validate a canonical spec and return non-fatal informational findings."""
    if spec.get("schema_version") != 1:
        raise SpecError("schema_version must equal 1")
    if not str(spec.get("note_id") or "").strip():
        raise SpecError("note_id must be non-empty")
    if not str(spec.get("product_type") or "").strip():
        raise SpecError("product_type must be non-empty")
    _number(spec.get("notional"), "notional", minimum=0.0000001)

    structure = spec.get("underlier_structure")
    if structure not in STRUCTURES:
        raise SpecError(f"underlier_structure must be one of {sorted(STRUCTURES)}")
    underliers = spec.get("underliers")
    if not isinstance(underliers, list) or not underliers:
        raise SpecError("underliers must be a non-empty array")
    ids: list[str] = []
    weights: list[float | None] = []
    for index, raw in enumerate(underliers):
        item = _mapping(raw, f"underliers[{index}]")
        identifier = str(item.get("id") or "").strip()
        if not identifier:
            raise SpecError(f"underliers[{index}].id must be non-empty")
        ids.append(identifier)
        _number(item.get("initial_level"), f"underliers[{index}].initial_level", minimum=0.0000001)
        weights.append(_optional_number(item.get("weight"), f"underliers[{index}].weight", minimum=0.0))
    if len(ids) != len(set(ids)):
        raise SpecError("underlier ids must be unique")
    is_basket = structure in {"basket_equal_weight", "basket_defined_weight"}
    if is_basket:
        if any(weight is None for weight in weights):
            raise SpecError("basket underliers require weights")
        total = sum(weight for weight in weights if weight is not None)
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise SpecError(f"basket weights sum to {total:.8f}, expected 1.0")
        if structure == "basket_equal_weight" and max(weights) - min(weights) > 1e-6:  # type: ignore[arg-type]
            raise SpecError("basket_equal_weight requires equal weights")
    elif any(weight is not None for weight in weights):
        raise SpecError("non-basket underliers must use null weights")
    if structure == "single" and len(underliers) != 1:
        raise SpecError("single structure requires exactly one underlier")
    if structure != "single" and len(underliers) < 2:
        raise SpecError(f"{structure} requires at least two underliers")

    terminal = _mapping(spec.get("terminal"), "terminal")
    upside = _mapping(terminal.get("upside"), "terminal.upside")
    downside = _mapping(terminal.get("downside"), "terminal.downside")
    upside_kind = upside.get("kind")
    if upside_kind not in UPSIDE_KINDS:
        raise SpecError(f"terminal.upside.kind must be one of {sorted(UPSIDE_KINDS)}")
    participation = _number(
        upside.get("participation_rate", 0.0),
        "terminal.upside.participation_rate",
        minimum=0.0,
    )
    cap = _optional_number(upside.get("cap"), "terminal.upside.cap", minimum=0.0)
    if upside_kind == "digital":
        _number(upside.get("digital_trigger"), "terminal.upside.digital_trigger", minimum=0.0)
        _number(upside.get("digital_return"), "terminal.upside.digital_return", minimum=0.0)
    elif upside.get("digital_trigger") is not None or upside.get("digital_return") is not None:
        raise SpecError("digital fields are only valid for digital upside")

    downside_kind = downside.get("kind")
    if downside_kind not in DOWNSIDE_KINDS:
        raise SpecError(f"terminal.downside.kind must be one of {sorted(DOWNSIDE_KINDS)}")
    gearing = _number(downside.get("gearing", 1.0), "terminal.downside.gearing", minimum=0.0)
    barrier = _optional_number(downside.get("barrier"), "terminal.downside.barrier", minimum=0.0)
    buffer = _optional_number(downside.get("buffer"), "terminal.downside.buffer", minimum=0.0)
    if downside_kind in {"barrier", "absolute_return"} and barrier is None:
        raise SpecError(f"terminal.downside.barrier is required for {downside_kind}")
    if downside_kind == "buffer":
        if buffer is None or buffer > 1.0:
            raise SpecError("terminal.downside.buffer must be between 0 and 1")
    if downside_kind not in {"barrier", "absolute_return"} and barrier is not None:
        raise SpecError(f"terminal.downside.barrier is not valid for {downside_kind}")
    if downside_kind != "buffer" and buffer is not None:
        raise SpecError(f"terminal.downside.buffer is not valid for {downside_kind}")

    income = spec.get("income")
    if income is not None:
        income_map = _mapping(income, "income")
        _number(income_map.get("coupon_barrier"), "income.coupon_barrier", minimum=0.0)
        _number(income_map.get("coupon_per_period"), "income.coupon_per_period", minimum=0.0)
        if not isinstance(income_map.get("memory"), bool):
            raise SpecError("income.memory must be boolean")

    call_map = _mapping(spec.get("call", {"type": "none"}), "call")
    call_type = call_map.get("type")
    if call_type not in CALL_TYPES:
        raise SpecError(f"call.type must be one of {sorted(CALL_TYPES)}")

    schedule = spec.get("schedule", [])
    if not isinstance(schedule, list):
        raise SpecError("schedule must be an array")
    dates: list[str] = []
    trigger_count = 0
    for index, raw in enumerate(schedule):
        row = _mapping(raw, f"schedule[{index}]")
        row_date = str(row.get("date") or "")
        try:
            parsed = __import__("datetime").date.fromisoformat(row_date)
        except ValueError as exc:
            raise SpecError(f"schedule[{index}].date must be ISO YYYY-MM-DD") from exc
        dates.append(parsed.isoformat())
        for key in ("coupon_barrier", "coupon_amount", "call_trigger", "call_premium"):
            _optional_number(row.get(key), f"schedule[{index}].{key}", minimum=0.0)
        if row.get("call_trigger") is not None:
            trigger_count += 1
    if dates != sorted(dates):
        raise SpecError("schedule dates must be sorted ascending")
    if len(dates) != len(set(dates)):
        raise SpecError("schedule dates must be unique")
    if call_type == "automatic" and trigger_count == 0:
        raise SpecError("automatic call requires at least one schedule call_trigger")
    if call_type != "automatic" and trigger_count:
        raise SpecError(f"call triggers are not valid for call.type={call_type}")
    if (income is not None or call_type != "none") and not schedule:
        raise SpecError("income/call features require a non-empty schedule")

    findings: list[str] = []
    if cap is None and participation > 1.0:
        findings.append("uncapped leveraged upside: confirm the document truly has no cap")
    if gearing == 0.0 and downside_kind not in {"principal_protected"}:
        findings.append("zero downside gearing: confirm this is intentional")
    return findings


def aggregate_performance(spec: Mapping[str, Any], levels: Mapping[str, object]) -> float:
    validate_spec(spec)
    performances: list[tuple[float, float | None]] = []
    for index, underlier in enumerate(spec["underliers"]):
        identifier = underlier["id"]
        if identifier not in levels or levels[identifier] is None:
            raise SpecError(f"missing level for underlier {identifier!r}")
        level = _number(levels[identifier], f"levels[{identifier!r}]", minimum=0.0)
        initial = _number(underlier["initial_level"], f"underliers[{index}].initial_level")
        performances.append((level / initial, underlier.get("weight")))
    structure = spec["underlier_structure"]
    values = [performance for performance, _ in performances]
    if structure == "single":
        return values[0]
    if structure == "worst_of":
        return min(values)
    if structure == "best_of":
        return max(values)
    return sum(performance * float(weight) for performance, weight in performances if weight is not None)


def evaluate_terminal_performance(spec: Mapping[str, Any], performance: float) -> dict[str, object]:
    findings = validate_spec(spec)
    performance = _number(performance, "performance", minimum=0.0)
    notional = float(spec["notional"])
    terminal = spec["terminal"]
    upside = terminal["upside"]
    downside = terminal["downside"]
    cap = upside.get("cap")

    def cap_positive(value: float) -> float:
        return min(value, float(cap)) if cap is not None else value

    if upside["kind"] == "digital" and performance >= float(upside["digital_trigger"]):
        note_return = float(upside["digital_return"])
        region = "digital"
    elif performance >= 1.0:
        note_return = cap_positive(float(upside.get("participation_rate", 0.0)) * (performance - 1.0))
        region = "upside"
    else:
        kind = downside["kind"]
        gearing = float(downside.get("gearing", 1.0))
        if kind == "principal_protected":
            note_return = 0.0
            region = "principal_protected"
        elif kind == "barrier":
            if performance >= float(downside["barrier"]):
                note_return = 0.0
                region = "barrier_protected"
            else:
                note_return = gearing * (performance - 1.0)
                region = "barrier_breached"
        elif kind == "buffer":
            excess_decline = max(0.0, (1.0 - performance) - float(downside["buffer"]))
            note_return = -gearing * excess_decline
            region = "buffer" if excess_decline == 0 else "below_buffer"
        elif kind == "absolute_return":
            if performance >= float(downside["barrier"]):
                note_return = cap_positive(float(upside.get("participation_rate", 0.0)) * (1.0 - performance))
                region = "absolute_return"
            else:
                note_return = gearing * (performance - 1.0)
                region = "absolute_barrier_breached"
        else:
            note_return = gearing * (performance - 1.0)
            region = "full_downside"
    note_return = max(-1.0, note_return)
    redemption = notional * (1.0 + note_return)
    return {
        "note_id": spec["note_id"],
        "performance": performance,
        "underlier_return": performance - 1.0,
        "note_return": note_return,
        "redemption": redemption,
        "region": region,
        "findings": findings,
    }


def evaluate_terminal_levels(spec: Mapping[str, Any], levels: Mapping[str, object]) -> dict[str, object]:
    result = evaluate_terminal_performance(spec, aggregate_performance(spec, levels))
    return {**result, "levels": dict(levels)}


def scenario_grid(spec: Mapping[str, Any], start: float, end: float, step: float) -> list[dict[str, object]]:
    start = _number(start, "start", minimum=0.0)
    end = _number(end, "end", minimum=0.0)
    step = _number(step, "step", minimum=0.000000000001)
    if start > end:
        raise SpecError("start must be <= end")
    values: list[dict[str, object]] = []
    current = start
    count = 0
    while current <= end + step * 1e-9:
        values.append(evaluate_terminal_performance(spec, round(current, 12)))
        current += step
        count += 1
        if count > 100_000:
            raise SpecError("scenario grid exceeds 100,000 rows")
    return values


def evaluate_path(
    spec: Mapping[str, Any],
    observations: Sequence[Mapping[str, Any]],
    determinations: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, object]]:
    validate_spec(spec)
    determinations = determinations or {}
    by_date: dict[str, Mapping[str, Any]] = {}
    for index, observation in enumerate(observations):
        if not isinstance(observation, Mapping):
            raise SpecError(f"observations[{index}] must be an object")
        date = str(observation.get("date") or "")
        if date in by_date:
            raise SpecError(f"duplicate observation date {date!r}")
        by_date[date] = observation

    income = spec.get("income")
    call_type = spec.get("call", {"type": "none"})["type"]
    notional = float(spec["notional"])
    missed = 0
    memory_unknown = False
    call_unknown = False
    rows: list[dict[str, object]] = []
    for schedule_row in spec.get("schedule", []):
        date = schedule_row["date"]
        official = determinations.get(date, {})
        if not isinstance(official, Mapping):
            raise SpecError(f"determination for {date} must be an object")
        observation = by_date.get(date)
        performance: float | None = None
        missing_reason: str | None = None
        if observation is None:
            missing_reason = "missing observation date"
        else:
            levels = observation.get("levels")
            if not isinstance(levels, Mapping):
                missing_reason = "levels must be an object"
            else:
                try:
                    performance = aggregate_performance(spec, levels)
                except SpecError as exc:
                    missing_reason = str(exc)

        coupon_status = "NOT_APPLICABLE"
        coupon_payment: float | None = 0.0
        missed_count: int | None = 0
        missed_before = missed
        memory_unknown_before = memory_unknown
        if income is not None:
            memory = bool(income["memory"])
            barrier = schedule_row.get("coupon_barrier")
            if barrier is None:
                barrier = income["coupon_barrier"]
            coupon_amount = schedule_row.get("coupon_amount")
            if coupon_amount is None:
                coupon_amount = income["coupon_per_period"]
            if memory_unknown:
                coupon_status = "UNDETERMINED_PRIOR_MEMORY_STATE"
                coupon_payment = None
                missed_count = None
            elif performance is None:
                coupon_status = "UNDETERMINED_MISSING_LEVEL"
                coupon_payment = None
                missed_count = missed
                memory_unknown = memory
            elif performance >= float(barrier):
                periods = 1 + (missed if memory else 0)
                coupon_status = "PAID"
                coupon_payment = notional * float(coupon_amount) * periods
                missed = 0
                missed_count = 0
            else:
                coupon_status = "MISSED"
                coupon_payment = 0.0
                if memory:
                    missed += 1
                missed_count = missed
            if "coupon_status" in official:
                coupon_status = str(official["coupon_status"])
                if coupon_status not in {"PAID", "MISSED", "NOT_APPLICABLE"}:
                    raise SpecError(
                        f"determinations[{date}].coupon_status must be PAID, MISSED, or NOT_APPLICABLE"
                    )
                if "coupon_payment" in official:
                    coupon_payment = _optional_number(
                        official["coupon_payment"],
                        f"determinations[{date}].coupon_payment",
                        minimum=0.0,
                    )
                if coupon_status == "PAID":
                    missed = 0
                    missed_count = 0
                    memory_unknown = False
                elif coupon_status == "MISSED":
                    official_missed = official.get("missed_count")
                    if official_missed is not None:
                        missed_value = _number(
                            official_missed,
                            f"determinations[{date}].missed_count",
                            minimum=0.0,
                        )
                        if not missed_value.is_integer():
                            raise SpecError(f"determinations[{date}].missed_count must be an integer")
                        missed = int(missed_value)
                        missed_count = missed
                        memory_unknown = False
                    elif memory_unknown_before:
                        missed = missed_before
                        missed_count = None
                        memory_unknown = True
                    else:
                        missed = missed_before + (1 if memory else 0)
                        missed_count = missed
                        memory_unknown = False

        call_status = "NOT_APPLICABLE"
        call_redemption: float | None = None
        trigger = schedule_row.get("call_trigger")
        if call_type == "issuer":
            call_status = "ISSUER_ELECTIVE"
        elif call_type == "automatic":
            if trigger is None:
                call_status = "NOT_CALLABLE"
            elif call_unknown:
                call_status = "UNDETERMINED_PRIOR_CALL_STATE"
            elif performance is None:
                call_status = "UNDETERMINED_MISSING_LEVEL"
                call_unknown = True
            elif performance >= float(trigger):
                call_status = "CALLED"
                call_redemption = notional * (1.0 + float(schedule_row.get("call_premium") or 0.0))
            else:
                call_status = "NOT_CALLED"
        if "call_status" in official:
            call_status = str(official["call_status"])
            if call_status not in {"CALLED", "NOT_CALLED", "NOT_APPLICABLE"}:
                raise SpecError(
                    f"determinations[{date}].call_status must be CALLED, NOT_CALLED, or NOT_APPLICABLE"
                )
            if "call_redemption" in official:
                call_redemption = _optional_number(
                    official["call_redemption"],
                    f"determinations[{date}].call_redemption",
                    minimum=0.0,
                )
            if call_status == "NOT_CALLED":
                call_unknown = False
                call_redemption = None
            elif call_status == "CALLED":
                call_unknown = False

        rows.append({
            "date": date,
            "performance": performance,
            "missing_reason": missing_reason,
            "coupon_status": coupon_status,
            "coupon_payment": coupon_payment,
            "missed_count": missed_count,
            "call_status": call_status,
            "call_redemption": call_redemption,
        })
        if call_status == "CALLED":
            break
    return rows


def _load_object(path: str) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text())
    if not isinstance(value, Mapping):
        raise SpecError(f"{path} must contain a JSON object")
    return value


def _write(value: object, output: str | None) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False)
    if output:
        Path(output).write_text(text + "\n")
    else:
        print(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a canonical payoff spec")
    validate.add_argument("spec")

    terminal = subparsers.add_parser("terminal", help="evaluate one terminal outcome")
    terminal.add_argument("spec")
    inputs = terminal.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--performance", type=float)
    inputs.add_argument("--levels-json")
    terminal.add_argument("--output")

    scenario = subparsers.add_parser("scenario", help="evaluate an aggregate-performance grid")
    scenario.add_argument("spec")
    scenario.add_argument("--start", type=float, required=True)
    scenario.add_argument("--end", type=float, required=True)
    scenario.add_argument("--step", type=float, required=True)
    scenario.add_argument("--output")

    path = subparsers.add_parser("path", help="evaluate schedule observations")
    path.add_argument("spec")
    path.add_argument("observations")
    path.add_argument("--determinations")
    path.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        spec = _load_object(args.spec)
        if args.command == "validate":
            _write({"valid": True, "findings": validate_spec(spec)}, None)
        elif args.command == "terminal":
            if args.levels_json is not None:
                levels = json.loads(args.levels_json)
                if not isinstance(levels, Mapping):
                    raise SpecError("--levels-json must be a JSON object")
                result = evaluate_terminal_levels(spec, levels)
            else:
                result = evaluate_terminal_performance(spec, args.performance)
            _write(result, args.output)
        elif args.command == "scenario":
            _write(scenario_grid(spec, args.start, args.end, args.step), args.output)
        else:
            observations = json.loads(Path(args.observations).read_text())
            if not isinstance(observations, list):
                raise SpecError("observations JSON must contain an array")
            determinations: dict[str, Mapping[str, Any]] = {}
            if args.determinations:
                raw_determinations = json.loads(Path(args.determinations).read_text())
                if not isinstance(raw_determinations, list):
                    raise SpecError("determinations JSON must contain an array")
                for index, determination in enumerate(raw_determinations):
                    if not isinstance(determination, Mapping):
                        raise SpecError(f"determinations[{index}] must be an object")
                    determination_date = str(determination.get("date") or "")
                    if not determination_date:
                        raise SpecError(f"determinations[{index}].date must be non-empty")
                    if determination_date in determinations:
                        raise SpecError(f"duplicate determination date {determination_date}")
                    determinations[determination_date] = determination
            _write(evaluate_path(spec, observations, determinations), args.output)
    except (OSError, json.JSONDecodeError, SpecError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
