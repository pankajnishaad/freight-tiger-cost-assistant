from pathlib import Path
import pandas as pd

from src.note_retriever import load_notes, _note_window, _supports_cost_increase, _normalise_route

ROOT = Path(__file__).resolve().parent
RESULTS_PATH = ROOT / "outputs" / "results.csv"
NOTES_PATH = ROOT / "data" / "context_notes.csv"
AUDIT_PATH = ROOT / "outputs" / "audit_issues.csv"


def main():
    results = pd.read_csv(RESULTS_PATH, keep_default_na=False)
    notes = load_notes(NOTES_PATH)
    notes_by_id = {str(row["note_id"]): row for _, row in notes.iterrows()}
    issues = []

    required_columns = [
        "route", "week_of", "cost_per_tonne_km", "vs_own_history",
        "vs_similar_routes", "flagged", "matched_note_id", "reason"
    ]
    if list(results.columns) != required_columns:
        issues.append({
            "route": "", "week_of": "", "issue": "Output columns do not match the required schema",
            "details": f"Found: {list(results.columns)}"
        })

    for _, row in results.iterrows():
        route = str(row["route"])
        week = pd.Timestamp(row["week_of"]).normalize()
        flagged = str(row["flagged"]).strip()
        note_id = str(row["matched_note_id"]).strip()
        reason = str(row["reason"])

        if flagged == "No (justified)":
            if not note_id:
                issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Justified flag has no note ID", "details": reason})
                continue
            note = notes_by_id.get(note_id)
            if note is None:
                issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Note ID does not exist", "details": note_id})
                continue

            applies = str(note["applies_to"]).strip()
            route_ok = applies.casefold() == "all routes" or _normalise_route(applies) == _normalise_route(route)
            start, end = _note_window(note)
            date_ok = start <= week <= end
            impact_ok = _supports_cost_increase(str(note["note"]))

            if not route_ok:
                issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Note route does not match", "details": f"{note_id} applies to {applies}"})
            if not date_ok:
                issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Note date window does not match", "details": f"{note_id} valid from {start.date()} to {end.date()}"})
            if not impact_ok:
                issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Note does not support a cost increase", "details": f"{note_id}: {note['note']}"})
            if note_id not in reason:
                issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Reason does not cite matched note ID", "details": reason})

        elif flagged == "Yes":
            if note_id:
                issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Unjustified flag has a note ID", "details": note_id})
        elif flagged == "No":
            if note_id:
                issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Non anomalous row unexpectedly has a note ID", "details": note_id})
        else:
            issues.append({"route": route, "week_of": str(row["week_of"]), "issue": "Unknown flag value", "details": flagged})

    issues_df = pd.DataFrame(issues, columns=["route", "week_of", "issue", "details"])
    if issues_df.empty:
        if AUDIT_PATH.exists():
            AUDIT_PATH.unlink()
        print(f"AUDIT PASSED: checked {len(results)} rows and found 0 note or flag consistency issues.")
        print("Every justified row has an existing note with a matching route, date window, and cost impact.")
    else:
        issues_df.to_csv(AUDIT_PATH, index=False)
        print(f"AUDIT FOUND {len(issues_df)} issue(s) across {len(results)} rows.")
        print(f"Review the details here: {AUDIT_PATH}")
        print(issues_df["issue"].value_counts().to_string())


if __name__ == "__main__":
    main()
