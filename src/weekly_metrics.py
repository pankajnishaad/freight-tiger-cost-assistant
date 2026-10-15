from __future__ import annotations
import pandas as pd

ROUTE_COLUMNS = ["origin", "destination", "route_type"]
REQUIRED_COLUMNS = [
    "origin", "destination", "route_type", "quantity_tonnes",
    "distance_km", "freight_cost_inr", "shipment_date"
]

def load_shipments(path):
    """Load and validate shipment records without modifying the input file."""
    df = pd.read_csv(path)
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Shipment CSV is missing required columns: {missing}")

    df["shipment_date"] = pd.to_datetime(df["shipment_date"], errors="raise")
    for col in ["quantity_tonnes", "distance_km", "freight_cost_inr"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    if (df["quantity_tonnes"] <= 0).any():
        raise ValueError("quantity_tonnes must be greater than zero.")
    if (df["distance_km"] <= 0).any():
        raise ValueError("distance_km must be greater than zero.")
    if (df["freight_cost_inr"] < 0).any():
        raise ValueError("freight_cost_inr cannot be negative.")
    if df[ROUTE_COLUMNS].isna().any().any():
        raise ValueError("Route columns cannot contain missing values.")

    # Monday is the start of each Monday-to-Sunday week.
    df["week_of"] = (
        df["shipment_date"].dt.to_period("W-SUN").dt.start_time
    )
    df["route"] = df["origin"].astype(str) + "-" + df["destination"].astype(str)
    df["tonne_km"] = df["quantity_tonnes"] * df["distance_km"]
    return df

def build_weekly_metrics(shipments):
    """Aggregate shipment rows first, then divide totals for a weighted rate."""
    weekly = (
        shipments.groupby(
            ["route", "origin", "destination", "route_type", "week_of"],
            as_index=False,
            sort=True,
        )
        .agg(
            total_freight_cost=("freight_cost_inr", "sum"),
            total_tonne_km=("tonne_km", "sum"),
            shipment_count=("shipment_id", "count")
            if "shipment_id" in shipments.columns
            else ("freight_cost_inr", "size"),
        )
    )
    weekly["cost_per_tonne_km"] = (
        weekly["total_freight_cost"] / weekly["total_tonne_km"]
    )
    weekly = weekly.sort_values(
        ["route", "route_type", "week_of"], kind="mergesort"
    ).reset_index(drop=True)

    # Prior 8 route-week observations only; shift(1) prevents look-ahead.
    weekly["vs_own_history"] = (
        weekly.groupby(["route", "route_type"], sort=False)["cost_per_tonne_km"]
        .transform(lambda s: s.shift(1).rolling(window=8, min_periods=1).mean())
    )
    weekly["history_weeks_used"] = (
        weekly.groupby(["route", "route_type"], sort=False)["cost_per_tonne_km"]
        .transform(lambda s: s.shift(1).rolling(window=8, min_periods=1).count())
        .fillna(0)
        .astype(int)
    )

    # Same week and route_type, average across OTHER routes only.
    type_week_total = weekly.groupby(["route_type", "week_of"])["cost_per_tonne_km"].transform("sum")
    type_week_count = weekly.groupby(["route_type", "week_of"])["cost_per_tonne_km"].transform("count")
    weekly["vs_similar_routes"] = (type_week_total - weekly["cost_per_tonne_km"]) / (type_week_count - 1)
    weekly.loc[type_week_count <= 1, "vs_similar_routes"] = float("nan")

    weekly["history_change_pct"] = (
        (weekly["cost_per_tonne_km"] / weekly["vs_own_history"] - 1) * 100
    )
    weekly["peer_change_pct"] = (
        (weekly["cost_per_tonne_km"] / weekly["vs_similar_routes"] - 1) * 100
    )
    weekly["previous_week_cost"] = (
        weekly.groupby(["route", "route_type"], sort=False)["cost_per_tonne_km"].shift(1)
    )
    weekly["is_rising"] = weekly["cost_per_tonne_km"] > weekly["previous_week_cost"]
    return weekly
