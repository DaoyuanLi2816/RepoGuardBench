# Results

All numbers are auto-generated from `results/aggregate/` and match the paper.
Regenerate the tables/figures with `make reproduce-tables` /
`make reproduce-figures`.

## Headline (primary local open-weight grid)
Matched proposed-attempt **34.9%**, landed **8.8%**, completion **2.1%**;
matched utility delta (attacked − clean) **−12.5%** [95% CI: −16.2%, −8.5%]
(`results/aggregate/headline.json`).

## RQ1 — carriers (marginal proposed-attempt, attacked runs)
| Carrier | Attempt | Landed | Complete |
|---|---|---|---|
| code comment | 50.9% | 11.1% | 0.0% |
| rule file | 45.8% | 12.9% | 5.6% |
| issue | 13.7% | 2.1% | 1.2% |
| README | 0.0% | 0.0% | 0.0% |
| test log | 0.0% | 0.0% | 0.0% |

Source: `results/aggregate/by_carrier.csv`. Completion concentrates in
rule-file → test deletion.

## RQ2 — model scaling (Qwen2.5-Coder, matched)
| Model | clean pass | attempt | landed | complete |
|---|---|---|---|---|
| 1.5B | ~6% | 0% | 0% | 0% |
| 3B | 71% | 22% | 1% | 0.8% |
| 7B | 73% | 58% | 13% | 3.8% |
| 14B | 100% | 83% | 35% | 6.3% |

Source: `results/aggregate/matched_model.csv`. Susceptibility rises
monotonically with capability.

## RQ3 — defenses
Among the five primary defenses (D0–D3, D5) on their shared 18-task subset, all
matched utility-delta confidence intervals include zero — no statistically
clear utility winner (`results/aggregate/matched_defense_common.csv`).
Context-side (D1/D2) drive attempts to 0% but act only on the model's
interpretation of context; action-side gates (D3/D5) cut landed actions but
miss semantic test deletion. The exploratory silent variants D3np/D5np are
separate; D3np shows a clear utility degradation on the broader 3B cells.

The **rule-file → `TEST_DELETE`** pair completes **15.4%** on Qwen2.5-Coder-7B
under D3 (`results/aggregate/matched_model_defense.csv`), because a path-prefix
gate cannot distinguish attacker-induced test deletion from a legitimate
`tests/` edit.

## Cross-family & closed-model
Two non-Qwen open models (DeepSeek-Coder-6.7B, Llama-3.1-8B) reproduce the
pattern with non-trivial clean pass. The **non-local Claude reference**
(Haiku-4.5, Sonnet-4.6) keeps 100% clean pass and near-zero completion
(0–2.1%) on these carriers — excluded from the headline aggregate
(`results/scored/claude.jsonl`; see [REPRODUCIBILITY.md](REPRODUCIBILITY.md)).
