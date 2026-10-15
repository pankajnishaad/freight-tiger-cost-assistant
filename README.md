# FreightTiger Smart Shipping Cost Assistant

## Overview

This project identifies unusual increases in shipping costs and checks whether the available context notes provide a reasonable explanation.

It analyzes shipment records week by week, compares each route's cost with its own history and similar routes, and generates an explanation for each result. When the available evidence does not explain an unusual increase, the route is flagged for human review.

The solution uses Python, Pandas, and TF IDF based note retrieval. It does not require an external Large Language Model (LLM) API, which keeps the results deterministic and avoids model API costs.

## Setup and Installation

The following steps are for Windows PowerShell.

### 1. Open the project

Open the project folder in VS Code.

### 2. Check the input files

Make sure the following files are present in the `data/` directory:

- `shipment_records.csv`
- `context_notes.csv`
- `sample_output_format.csv`

### 3. Create a virtual environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 4. Run the analysis

```powershell
python run.py
```

The generated results will be saved to `outputs/results.csv`.

### 5. Run the automated tests

```powershell
python -m pytest -q
```

### 6. Check reproducibility

```powershell
python reproducibility_check.py
```

This runs the pipeline three times and checks whether the generated CSV files are identical.

## How the Assistant Works

### 1. Weekly Shipment Analysis

Each shipment is assigned to a week running from Monday to Sunday. The `week_of` field stores the Monday date.

Records are grouped by route, `route_type`, and week. For each group, the assistant calculates cost per tonne kilometre using the total freight cost divided by the total quantity carried in tonnes multiplied by the corresponding distance in kilometres.

Calculating the ratio from aggregated totals avoids treating every shipment as equally weighted.

### 2. Historical Cost Comparison

Each route is compared with its trailing eight week average. The current week is excluded from the calculation to prevent the current observation from influencing its own historical baseline.

If fewer than eight previous weekly observations are available, the assistant uses all available previous observations. It does not fill missing history with estimated values.

### 3. Similar Route Comparison

The assistant compares a route's weekly cost with the average cost of other routes having the same `route_type` in the same week.

The route being evaluated is excluded from its own peer average. If no other route of the same type has a record that week, the peer comparison is unavailable.

### 4. Anomaly Detection

The case study does not prescribe a numerical threshold, so this implementation uses a 10% threshold as an explicit engineering decision.

A route is considered anomalous when its cost is higher than the previous week's cost and at least one available baseline comparison shows an increase of 10% or more.

The threshold can be adjusted as business requirements change.

### 5. Evidence Based Explanations

The assistant searches the context notes using TF IDF lexical similarity. It then checks whether a selected note applies to the route and relevant date and whether its content supports an increase in cost.

A note that says costs were unaffected or reports no relevant disruption cannot justify an increase. If no applicable supporting note is found, the assistant describes the increase as unexplained and flags it for human review.

Explanations are generated using deterministic templates and available note content rather than free form AI generation.

## Context Note Date Policy

When a note contains an explicit date range, that range determines when it can be used as evidence.

When no end date is provided, the implementation treats the note as applicable on its recorded date and for the following six days. This is a conservative assumption intended to avoid extending a note's relevance indefinitely.

Route specific notes must match the evaluated route. Notes marked `All Routes` may apply more broadly, but they must still support an increase in costs and pass the date and cost impact checks.

These rules are implementation choices and can be refined if more precise validity periods become available.

## Output Format

The analysis writes its results to `outputs/results.csv`.

The file follows the eight column schema supplied with the case study:

```text
route,week_of,cost_per_tonne_km,vs_own_history,vs_similar_routes,flagged,matched_note_id,reason
```

Each row represents one route and week.

The `flagged` field has three possible values:

1. `Yes`: The cost increase meets the anomaly rules, but no applicable supporting note was found.
2. `No (justified)`: The cost increase meets the anomaly rules, and a relevant supporting note explains it.
3. `No`: The route does not meet the configured anomaly rules.

The `matched_note_id` field identifies the note used to justify an increase. It remains empty when no supporting note is found.

The `reason` field provides a concise explanation of the verdict.

## Results Summary

The latest successful run processed the supplied shipment records and context notes and produced the following results:

| Metric | Result |
|---|---:|
| Shipment records processed | 2,940 |
| Context notes processed | 10 |
| Route week records generated | 728 |
| Records classified as `No` | 665 |
| Records classified as `Yes` | 60 |
| Records classified as `No (justified)` | 3 |

These results reflect the supplied input data and the configured 10% anomaly threshold. They may change if the input files or detection rules are updated.

## Testing and Validation

The project includes 11 automated tests covering the main calculations, decision rules, and sample outputs.

The tests check:

1. Correct assignment of shipments to Monday based weeks.
2. Cost per tonne kilometre calculation using aggregated shipment values.
3. Historical averages that exclude the current week.
4. Peer averages that exclude the route being evaluated.
5. Rejection of notes that apply to a different route.
6. Rejection of notes that do not support a cost increase.
7. Validation of the required output columns.
8. Consistency of repeated pipeline calculations.
9. Expected results for the Delhi Jaipur sample.
10. Expected results and note ID for the Ahmedabad Mumbai sample.
11. Expected results for the Mumbai Pune sample, where the available note does not justify the increase.

The current test suite passes all 11 tests.

Run the following command to execute the tests:

```powershell
python -m pytest -q
```

The sample tests validate the expected costs, comparison percentages, verdicts, and note identifiers for the three supplied examples.

## Reproducibility and Cost

Run `python reproducibility_check.py` to execute the pipeline three times and compare the generated CSV files.

The script saves the individual outputs as:

- `outputs/run_1.csv`
- `outputs/run_2.csv`
- `outputs/run_3.csv`

Identical SHA256 hashes indicate that the generated CSV files are identical across the three runs.

The file `outputs/token_cost_log.json` records run metadata, including the number of processed records, the configured threshold, input file hashes, and LLM usage information.

The implementation makes no LLM API calls. Therefore, LLM input tokens, LLM output tokens, and estimated LLM API cost are zero. This does not include local processing time or electricity costs.

## Design Decisions and Limitations

The solution prioritizes evidence based explanations, reproducibility, and straightforward validation.

1. **Threshold selection:** The 10% anomaly threshold is an engineering choice because the case study does not specify one.
2. **Note retrieval:** TF IDF provides lightweight lexical retrieval without requiring a vector database or external service. It may miss relevant notes when the wording differs significantly.
3. **Date validity:** Notes without an explicit end date are not assumed to remain valid indefinitely.
4. **No LLM generation:** The current implementation uses deterministic explanation templates. It does not provide a natural language question answering interface or LLM generated explanations.
5. **Human review:** A flagged increase is a signal for investigation, not proof of incorrect billing or deliberate overcharging.
6. **Evaluation scope:** Automated tests cover selected calculations, decision rules, and supplied sample cases. They do not prove that every possible real world scenario is handled correctly.

A future version could improve semantic retrieval, introduce explicit note validity metadata, and add a question answering interface with evidence citations and a separate evaluation set.

## Project Structure

```text
freight-tiger-cost-assistant/
├── data/
│   ├── shipment_records.csv
│   ├── context_notes.csv
│   └── sample_output_format.csv
├── src/
│   ├── __init__.py
│   ├── weekly_metrics.py
│   ├── note_retriever.py
│   └── anomaly_detector.py
├── tests/
│   ├── test_pipeline.py
│   └── test_sample_examples.py
├── outputs/
│   ├── results.csv
│   ├── token_cost_log.json
│   ├── run_1.csv
│   ├── run_2.csv
│   ├── run_3.csv
│   └── reproducibility_report.txt
├── requirements.txt
├── run.py
├── reproducibility_check.py
└── README.md
```
