from __future__ import annotations
import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

REQUIRED_NOTE_COLUMNS = ["note_id", "date", "applies_to", "note"]

def load_notes(path):
    notes = pd.read_csv(path)
    missing = sorted(set(REQUIRED_NOTE_COLUMNS) - set(notes.columns))
    if missing:
        raise ValueError(f"Context notes CSV is missing required columns: {missing}")
    notes["date"] = pd.to_datetime(notes["date"], errors="raise")
    notes["applies_to"] = notes["applies_to"].fillna("").astype(str).str.strip()
    notes["note"] = notes["note"].fillna("").astype(str)
    return notes.sort_values(["date", "note_id"], kind="mergesort").reset_index(drop=True)

def _normalise_route(text):
    return re.sub(r"\s+", "", str(text).casefold()).replace("–", "-").replace("—", "-")

def _note_window(note):
    """Conservative date window: explicit ranges are honoured; otherwise one week."""
    start = pd.Timestamp(note["date"]).normalize()
    text = note["note"].casefold()

    # N001-like explicit month/day range: "from Feb 24 to Mar 8".
    match = re.search(
        r"from\s+([a-z]{3,9})\s+(\d{1,2})\s+to\s+([a-z]{3,9})\s+(\d{1,2})",
        text,
    )
    if match:
        sm, sd, em, ed = match.groups()
        year = start.year
        start = pd.Timestamp(f"{sm} {sd} {year}")
        end = pd.Timestamp(f"{em} {ed} {year}")
        if end < start:
            end = end.replace(year=end.year + 1)
        return start, end

    # Without an explicit end date, do not extrapolate indefinitely.
    return start, start + pd.Timedelta(days=6)

def _supports_cost_increase(note_text):
    t = note_text.casefold()
    # Notes that explicitly deny impact cannot justify a price rise.
    negative = [
        "costs were not significantly affected",
        "no significant disruptions",
        "no major disruptions",
        "no rate change",
        "costs were not affected",
        "no cost impact",
        "costs remained stable",
    ]
    if any(x in t for x in negative):
        return False
    positive = [
        "higher trip costs", "surcharge", "pushing up transportation costs",
        "increased costs", "increased transportation costs", "rate increase",
        "costs increased", "higher costs",
    ]
    return any(x in t for x in positive)

def retrieve_justifying_note(route, week_of, notes):
    """
    TF-IDF ranks the small set of notes; deterministic metadata and impact checks
    decide whether any note can justify the anomaly. No LLM is used.
    """
    week = pd.Timestamp(week_of).normalize()
    route_norm = _normalise_route(route)
    if notes.empty:
        return None

    # Retrieval query provides route and cost-change context.
    corpus = notes["applies_to"].astype(str) + " " + notes["note"].astype(str)
    query = f"{route} freight cost increase route disruption surcharge fuel toll"
    try:
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), lowercase=True)
        matrix = vectorizer.fit_transform(corpus.tolist() + [query])
        similarities = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    except ValueError:
        similarities = [0.0] * len(notes)

    candidates = []
    for idx, note in notes.iterrows():
        applies = str(note["applies_to"]).strip()
        applies_norm = _normalise_route(applies)
        route_match = applies.casefold() == "all routes" or applies_norm == route_norm
        if not route_match:
            continue

        start, end = _note_window(note)
        if not (start <= week <= end):
            continue
        if not _supports_cost_increase(str(note["note"])):
            continue

        # Similarity is only used for stable ranking after hard evidence gates.
        candidates.append((float(similarities[idx]), str(note["note_id"]), note))

    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][2]
