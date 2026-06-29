# RepoGuardBench datasheet

Following the spirit of Gebru et al.'s "Datasheets for Datasets".

## Motivation

* **For what purpose was the dataset created?**  To measure
  prompt-injection robustness of *local open-weight* coding
  agents while they perform repository-level bug repair.  Existing
  bug-fix benchmarks assume benign repositories; existing
  prompt-injection benchmarks evaluate tool-using or web agents
  rather than coding agents on repair tasks.

* **Who created the dataset?**  The (currently anonymous) authors
  of the accompanying paper.

* **What support was used?**  Authors' time only.  No grant
  funding is acknowledged in the anonymous submission.

## Composition

* **What do the instances represent?**  Each instance is a
  Python micro-repository plus a target failing test plus an
  issue text.  A run consists of (instance, model, defense,
  carrier, goal, seed); the benchmark itself ships the instances.

* **How many instances are there in total?**
  * **Core**: 80 verified tasks generated from 10 ticket
    archetypes (off-by-one slice bounds, mutable default
    arguments, integer division, recursive base cases, semver
    lexicographic comparison, sorting key error, mutable cache
    state, iterator double consumption, exception type, string
    normalisation), instantiated across many module names.
  * **Applied**: 14 hand-curated multi-file tasks inspired by
    issue archetypes in popular pure-Python libraries (ISO-8601
    parsing, JSON escape, pathlib extension change, CSV quote
    escape, base64-URL encoding, HTML script stripping, semver
    comparison, generator double-iteration, color short-form,
    argv flag parsing, pluralization, integer clamp, Caesar
    cipher, log filter comparison).

* **Does the dataset contain all possible instances or is it a
  sample?**  Applied is intentionally small and curated; Core is
  parameterised over module names so additional Core instances
  can be generated.

* **Does the dataset contain data that might be considered
  confidential?**  No.  All tasks are authored by us; the
  embedded canary value is a deterministic per-task token, not a
  real secret.

* **Does the dataset contain data that, if viewed directly, might
  be offensive, insulting, threatening, or might otherwise cause
  anxiety?**  No.

* **Does the dataset relate to people?**  No.

## Collection

* **How was the data acquired?**  Authored by the authors.  No
  scraping.

* **What mechanisms or procedures were used to collect the
  data?**  Templates in
  `scripts/build_benchmark.py:TEMPLATES` and
  `REAL_TEMPLATES`.

* **Who was involved in the data collection process?**  The
  authors only.

* **Over what timeframe was the data collected?**
  April--May 2026.

* **Were any ethical review processes conducted?**  Not
  applicable; no human subjects.

## Preprocessing / verification

* **Was any preprocessing/cleaning/labelling done?**  Each
  candidate task is materialised in a temporary workspace and
  the target test is run before the agent.  A task is excluded
  if (i) the target test passes on the unfixed code or (ii) a
  hand-written reference patch fails to make the target test
  pass.  The released exclusion log records any task removed by
  these checks.

## Uses

* **Has the dataset been used for any tasks already?**  Yes, the
  experiments reported in the accompanying paper.

* **Is there a repository that links to any or all papers or
  systems that use the dataset?**  Will be published after
  de-anonymization.

* **What (other) tasks could the dataset be used for?**
  Defense-design research, IDE security audits, comparative
  evaluation of open coding models on repair under adversarial
  context.

* **Is there anything about the composition of the dataset that
  might affect future uses?**  Yes.  The Applied tier is
  hand-curated rather than scraped from real GitHub issues; it
  should not be used to claim ecological validity for real
  GitHub repositories.

* **Are there tasks for which the dataset should not be used?**
  Do not use the inert payloads as a substitute for adaptive
  red-teaming; do not extrapolate matched rates here to ASR
  rates against commercial coding editors.

## Distribution

* **How will the dataset be distributed?**  As part of the paper's
  supplementary materials and (after deanonymization) a public
  repository.

* **When will it be distributed?**  After paper notification.

* **Will the dataset be distributed under a copyright or
  intellectual property licence?**  MIT for the code.
  CC-BY-4.0 for the data.

## Maintenance

* **Who will be supporting/hosting/maintaining the dataset?**  The
  authors will maintain a repository after deanonymization.

* **How can the owner/curator/manager of the dataset be
  contacted?**  Via the corresponding-author address in the
  paper.

* **Is there an erratum?**  Errata are tracked in
  `logs/failures.md` in the released repository.

## Known limitations

* The Applied tier is small.
* The primary evidence is from the Qwen2.5-Coder family; we
  additionally evaluate a model-size point at 14B, two
  cross-family local models (StarCoder2-3B,
  DeepSeek-Coder-6.7B-Instruct, plus Llama-3.1-8B), and a
  closed-model reference point (Claude via its headless
  commercial coding-agent harness).  These additions are pilots,
  not a full multi-family sweep.
* Inert payloads only; the attacker is non-adaptive.
* Four-turn default budget.
* Sandbox blocks network so completion of network-exfiltration
  goals is impossible by construction.

## Misuse risks

The payloads cannot be used to compromise a real system.  The
benchmark sandbox blocks every action that would touch real
secrets or the network.  Releasing the benchmark does not
provide attack tooling.
