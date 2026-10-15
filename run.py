from pathlib import Path
import hashlib
import json
import pandas as pd
from src.weekly_metrics import load_shipments, build_weekly_metrics
from src.note_retriever import load_notes
from src.anomaly_detector import build_output

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
THRESHOLD_PCT = 10.0


def sha256(path):
    # Create a hash so we can check whether an input file has changed.
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def main():
    # Create the output folder if it does not exist yet.
    OUT.mkdir(exist_ok=True)

    # Read the shipment data and the notes provided with the case study.
    shipments = load_shipments(DATA / "shipment_records.csv")
    notes = load_notes(DATA / "context_notes.csv")

    # Calculate weekly costs for each route.
    weekly = build_weekly_metrics(shipments)

    # Check for unusual cost increases and look for notes that explain them.
    output = build_output(weekly, notes, threshold_pct=THRESHOLD_PCT)

    # Keep the output columns in the exact order required by the case study.
    required_columns = [
        "route",
        "week_of",
        "cost_per_tonne_km",
        "vs_own_history",
        "vs_similar_routes",
        "flagged",
        "matched_note_id",
        "reason",
    ]
    output = output[required_columns]

    # Save the final results as a CSV file.
    output.to_csv(OUT / "results.csv", index=False, encoding="utf-8")

    # Record the run details and hashes of the input files.
    # This implementation uses local retrieval, so no LLM API is called.
    log = {
        "shipment_rows": int(len(shipments)),
        "route_week_rows": int(len(weekly)),
        "context_note_rows": int(len(notes)),
        "llm_model": None,
        "llm_calls": 0,
        "llm_input_tokens": 0,
        "llm_output_tokens": 0,
        "llm_estimated_cost_usd": 0.0,
        "note": "No LLM was called. TF-IDF retrieval and deterministic templates run locally, with no API token cost.",
        "threshold_pct": THRESHOLD_PCT,
        "input_sha256": {
            "shipment_records.csv": sha256(DATA / "shipment_records.csv"),
            "context_notes.csv": sha256(DATA / "context_notes.csv"),
        },
    }

    # Save the log so the run can be checked later.
    (OUT / "token_cost_log.json").write_text(
        json.dumps(log, indent=2),
        encoding="utf-8",
    )

    # Print a short summary after the analysis finishes.
    print(f"Loaded {len(shipments)} shipments, {len(notes)} notes.")
    print(f"Created {len(output)} route-week rows: {OUT / 'results.csv'}")
    print("Flag counts:")
    print(output["flagged"].value_counts(dropna=False).to_string())
    print(f"Token/cost log: {OUT / 'token_cost_log.json'}")


if __name__ == "__main__":
    main()