"""Flatten prospectus extraction JSON into tidy CSV tables.

Usage: python3 extraction_to_tables.py <out_dir> <file.extraction.json> [more.json ...]

Pure stdlib — no installs. Writes relational, long-format tables keyed by
document_id so any number of prospectuses land in ONE set of files that load
straight into Excel, SQLite (`sqlite3 db ".import --csv fields.csv fields"`),
pandas, or a warehouse:

  documents.csv             one row per prospectus (type, classification, cusip)
  fields.csv                one row per scalar field — extracted AND derived
                            (source column tells them apart; derived rows have
                            no evidence by construction)
  underliers.csv            one row per reference asset
  observation_schedule.csv  one row per observation/call date
  off_schema_terms.csv      stated features outside the schema
  findings.csv              validation warnings/blockers

Evidence is kept: page + first quote per row (all evidence pages joined in
evidence_pages). Values stay in their normalized units (percents as decimals,
ISO dates) so downstream math needs no cleanup.
"""

import csv
import json
import sys
from pathlib import Path

UNDERLIER_COLS = ["symbol", "name", "initialLevel", "couponBarrierLevel", "knockInLevel", "protectionLevel", "weight"]
SCHEDULE_COLS = ["observationDate", "autocallLevel", "couponBarrierLevel", "couponAmount", "callPremium", "paymentDate"]


def first_evidence(ev: list) -> tuple:
    if not ev:
        return None, None, ""
    pages = ";".join(str(e.get("page", "")) for e in ev)
    return ev[0].get("page"), ev[0].get("quote"), pages


def snake(name: str) -> str:
    out = []
    for ch in name:
        if ch.isupper():
            out.append("_" + ch.lower())
        else:
            out.append(ch)
    return "".join(out)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    docs, fields, unders, sched, off_schema, findings = [], [], [], [], [], []

    for path in sys.argv[2:]:
        p = Path(path)
        data = json.loads(p.read_text())
        doc_id = p.name.removesuffix(".json").removesuffix(".extraction")
        f = data.get("fields", {})
        cusip = (f.get("cusip") or {}).get("normalizedValue")
        docs.append({
            "document_id": doc_id,
            "source_file": str(p),
            "document_type": data.get("documentType"),
            "product_type": data.get("productType"),
            "classification_confidence": (data.get("classification") or {}).get("confidence"),
            "cusip": cusip,
        })

        for name, v in f.items():
            page, quote, pages = first_evidence(v.get("evidence", []))
            fields.append({
                "document_id": doc_id, "field": snake(name), "source": "extracted",
                "normalized_value": v.get("normalizedValue"), "unit": v.get("unit"),
                "raw_text": v.get("rawText"), "confidence": v.get("confidence"),
                "page": page, "quote": quote, "evidence_pages": pages,
                "warnings": " | ".join(v.get("warnings", [])),
            })
        for name, d in (data.get("derived") or {}).items():
            fields.append({
                "document_id": doc_id, "field": snake(name), "source": "derived",
                "normalized_value": d.get("value"), "unit": d.get("unit"),
                "raw_text": None, "confidence": None,
                "page": None, "quote": None, "evidence_pages": "",
                "warnings": f"derived from: {d.get('from', '')}",
            })

        tables = data.get("tables") or {}
        for row in tables.get("underliers", []):
            page, quote, pages = first_evidence(row.get("evidence", []))
            rec = {"document_id": doc_id}
            rec.update({snake(c): row.get("values", {}).get(c) for c in UNDERLIER_COLS})
            rec.update({"page": page, "quote": quote, "evidence_pages": pages})
            unders.append(rec)
        for row in tables.get("observationSchedule", []):
            page, quote, pages = first_evidence(row.get("evidence", []))
            rec = {"document_id": doc_id}
            rec.update({snake(c): row.get("values", {}).get(c) for c in SCHEDULE_COLS})
            rec.update({"page": page, "quote": quote, "evidence_pages": pages})
            sched.append(rec)

        for t in data.get("offSchemaTerms") or []:
            page, quote, pages = first_evidence(t.get("evidence", []))
            off_schema.append({
                "document_id": doc_id, "name": snake(t.get("name", "")),
                "value": t.get("value"), "unit": t.get("unit"),
                "description": t.get("description"), "page": page, "quote": quote,
            })
        for fi in data.get("findings") or []:
            findings.append({
                "document_id": doc_id, "severity": fi.get("severity"),
                "field": fi.get("field"), "message": fi.get("message"),
            })

    def write(name: str, rows: list):
        if not rows:
            return
        cols = list(rows[0].keys())
        with open(out_dir / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"{name}: {len(rows)} rows")

    write("documents.csv", docs)
    write("fields.csv", fields)
    write("underliers.csv", unders)
    write("observation_schedule.csv", sched)
    write("off_schema_terms.csv", off_schema)
    write("findings.csv", findings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
