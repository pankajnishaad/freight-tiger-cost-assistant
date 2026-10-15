from __future__ import annotations
import pandas as pd
from .note_retriever import retrieve_justifying_note

def _pct(value):
    if pd.isna(value):
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1f}%"

def classify_week(row, notes, threshold_pct=10.0):
    """Return stable output values for a single route-week row."""
    history_pct = row["history_change_pct"]
    peer_pct = row["peer_change_pct"]

    # A rise is anomalous if it is rising week-over-week and >= threshold
    # versus at least one available baseline.
    exceeds_history = pd.notna(history_pct) and history_pct >= threshold_pct
    exceeds_peers = pd.notna(peer_pct) and peer_pct >= threshold_pct
    anomalous = bool(row["is_rising"]) and bool(exceeds_history or exceeds_peers)

    note = retrieve_justifying_note(row["route"], row["week_of"], notes) if anomalous else None
    note_id = ""
    if not anomalous:
        flagged = "No"
        reason = "No material rise detected by the configured comparison rules."
    elif note is not None:
        flagged = "No (justified)"
        note_id = str(note["note_id"])
        reason = (
            f"Justified by note {note_id} dated {pd.Timestamp(note['date']).date()}: "
            f"{str(note['note']).strip()}"
        )
    else:
        flagged = "Yes"
        reason = (
            "No applicable note with evidence of a cost increase was found for this route "
            "and week. Cost rise is unexplained and should be reviewed."
        )

    return {
        "route": row["route"],
        "week_of": pd.Timestamp(row["week_of"]).strftime("%Y-%m-%d"),
        "cost_per_tonne_km": round(float(row["cost_per_tonne_km"]), 2),
        "vs_own_history": f"{_pct(history_pct)} vs this route's past average"
            if pd.notna(history_pct) else "N/A (no prior weeks)",
        "vs_similar_routes": f"{_pct(peer_pct)} vs similar-length routes this week"
            if pd.notna(peer_pct) else "N/A (no eligible peer routes)",
        "flagged": flagged,
        "matched_note_id": note_id,
        "reason": reason,
    }

def build_output(weekly, notes, threshold_pct=10.0):
    rows = [classify_week(row, notes, threshold_pct) for _, row in weekly.iterrows()]
    columns = [
        "route", "week_of", "cost_per_tonne_km", "vs_own_history",
        "vs_similar_routes", "flagged", "matched_note_id", "reason"
    ]
    return pd.DataFrame(rows, columns=columns)
