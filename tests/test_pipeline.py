from pathlib import Path
import pandas as pd
from src.weekly_metrics import load_shipments, build_weekly_metrics
from src.note_retriever import load_notes, retrieve_justifying_note
from src.anomaly_detector import build_output

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def test_week_starts_monday():
    df = load_shipments(DATA / "shipment_records.csv")
    assert (df["week_of"].dt.dayofweek == 0).all()
    assert str(df.loc[df["shipment_date"] == pd.Timestamp("2024-01-01"), "week_of"].iloc[0].date()) == "2024-01-01"

def test_weighted_cost_aggregation():
    raw = pd.DataFrame({
        "shipment_id": ["a", "b"],
        "origin": ["A", "A"], "destination": ["B", "B"], "route_type": ["Short", "Short"],
        "quantity_tonnes": [10.0, 20.0], "distance_km": [100.0, 100.0],
        "freight_cost_inr": [1000.0, 6000.0],
        "shipment_date": ["2024-01-01", "2024-01-02"],
    })
    raw["shipment_date"] = pd.to_datetime(raw["shipment_date"])
    raw["week_of"] = raw["shipment_date"].dt.to_period("W-SUN").dt.start_time
    raw["route"] = "A-B"
    raw["tonne_km"] = raw["quantity_tonnes"] * raw["distance_km"]
    result = build_weekly_metrics(raw)
    assert abs(result.iloc[0]["cost_per_tonne_km"] - (7000 / 3000)) < 1e-9

def test_history_excludes_current_week_and_uses_max_eight():
    df = load_shipments(DATA / "shipment_records.csv")
    weekly = build_weekly_metrics(df)
    row = weekly[(weekly["route"] == "Mumbai-Pune") & (weekly["week_of"] == pd.Timestamp("2024-01-15"))].iloc[0]
    prior = weekly[(weekly["route"] == "Mumbai-Pune") & (weekly["week_of"] < pd.Timestamp("2024-01-15"))].tail(8)
    assert row["history_weeks_used"] == len(prior)
    assert abs(row["vs_own_history"] - prior["cost_per_tonne_km"].mean()) < 1e-9

def test_peer_baseline_excludes_current_route():
    df = load_shipments(DATA / "shipment_records.csv")
    weekly = build_weekly_metrics(df)
    row = weekly[(weekly["route"] == "Mumbai-Pune") & (weekly["week_of"] == pd.Timestamp("2024-01-15"))].iloc[0]
    peers = weekly[(weekly["route_type"] == row["route_type"]) & (weekly["week_of"] == row["week_of"]) & (weekly["route"] != row["route"])]
    assert abs(row["vs_similar_routes"] - peers["cost_per_tonne_km"].mean()) < 1e-9

def test_wrong_route_note_does_not_justify():
    notes = load_notes(DATA / "context_notes.csv")
    assert retrieve_justifying_note("Mumbai-Pune", "2025-02-24", notes) is None

def test_nonimpact_note_does_not_justify():
    notes = load_notes(DATA / "context_notes.csv")
    assert retrieve_justifying_note("Mumbai-Delhi", "2024-07-29", notes) is None

def test_output_schema_exact():
    df = load_shipments(DATA / "shipment_records.csv")
    notes = load_notes(DATA / "context_notes.csv")
    out = build_output(build_weekly_metrics(df), notes)
    assert out.columns.tolist() == [
        "route", "week_of", "cost_per_tonne_km", "vs_own_history",
        "vs_similar_routes", "flagged", "matched_note_id", "reason"
    ]

def test_reproducible_output():
    df = load_shipments(DATA / "shipment_records.csv")
    notes = load_notes(DATA / "context_notes.csv")
    weekly = build_weekly_metrics(df)
    one = build_output(weekly, notes).to_csv(index=False)
    two = build_output(weekly, notes).to_csv(index=False)
    assert one == two
