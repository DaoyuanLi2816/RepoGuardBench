# Paper-to-artifact map

The committed scored streams and aggregates are the source of truth for the
camera-ready numbers. `python scripts/verify_paper_claims.py` checks every
headline below without rerunning a model.

| Paper evidence | Released source | Regeneration or verification |
|---|---|---|
| 80 Core + 14 Applied tasks | `data/repoguardbench_core.jsonl`, `data/repoguardbench_real.jsonl` | `scripts/build_benchmark.py`; verifier |
| 2,340-run local grid and matched headline | `results/scored/main.jsonl`, `results/aggregate/headline.json` | `scripts/aggregate_results.py`; verifier |
| Carrier table | `results/aggregate/by_carrier.csv` | `scripts/make_tables.py`; verifier |
| Qwen capability scaling | `results/aggregate/matched_model.csv` | `scripts/make_tables.py`; verifier |
| Defense table and shared 18-task subset | `matched_model_defense.csv`, `matched_defense_common.csv` | aggregator; verifier |
| D3 rule-file/test-deletion gap | `matched_model_defense.csv`, per-carrier aggregates | verifier |
| Cross-family local models | `results/scored/main.jsonl`, `matched_model.csv` | aggregator |
| Claude reference, excluded from headline | `results/scored/claude.jsonl` | verifier |
| Paper tables | `results/aggregate/` | `make reproduce-tables` |
| Paper figures | `results/aggregate/` | `make reproduce-figures` |
| Final accepted paper | `paper/main.pdf` | `paper/SHA256SUMS`; verifier |

Model reruns create new observations and need not be byte-identical. If a
rerun changes a published aggregate, preserve both scored streams and document
the Ollama build, quantization, model digest, seed, and affected matched cells.
