# W68 D6 Phase 2 Dry-run Report (Auto-generated)

- Mode: **dry-fallback**
- Concurrency: **5**
- Started: 2026-07-24T04:51:14.401446+00:00
- Finished: 2026-07-24T04:51:14.408445+00:00
- Total questions: **1000**
- Rounds per question: **3**
- Pass rate (consensus): **0.0%**
- Gate threshold: **90%**
- Gate verdict: **FAIL**

## Verdict counts

| Verdict | Count |
|---|---|
| unknown | 1000 |

## Latency

- min: **0.0s**
- mean: **0.0s**
- median: **0.0s**
- p95: **0.0s**
- max: **0.0s**

## Per-intent breakdown

| Intent | Pass rate | Counts |
|---|---|---|
| action | 0.0% | unknown=136 |
| casual | 0.0% | unknown=118 |
| data | 0.0% | unknown=316 |
| deep | 0.0% | unknown=129 |
| explain_concept | 0.0% | unknown=161 |
| none | 0.0% | unknown=15 |
| search_info | 0.0% | unknown=125 |

## Per-intent latency

| Intent | Mean (s) | Median (s) | p95 (s) | Max (s) | Samples |
|---|---|---|---|---|---|
| action | 0.0 | 0.0 | 0.0 | 0.0 | 136 |
| casual | 0.0 | 0.0 | 0.0 | 0.0 | 118 |
| data | 0.0 | 0.0 | 0.0 | 0.0 | 316 |
| deep | 0.0 | 0.0 | 0.0 | 0.0 | 129 |
| explain_concept | 0.0 | 0.0 | 0.0 | 0.0 | 161 |
| none | 0.0 | 0.0 | 0.0 | 0.0 | 15 |
| search_info | 0.0 | 0.0 | 0.0 | 0.0 | 125 |

## Notes

- Phase 2 corpus: 1000 questions (questions_780 + questions_d4_extra_300)
- Concurrency: 5 workers (Phase 1 was 3, Phase 2 elevates to 5)
- Gate threshold: 90% (Phase 2 baseline 80%, target 90%)
- MIMO_API_KEY not present -> skipped live run
- DATABASE_URL / QA_BENCH_DB_URL not present -> skipped live run
- --dry-run flag set -> skipped live run on purpose
- Action: main orchestrator must SSH onto the runner host with MIMO_API_KEY + DATABASE_URL exported and rerun this script verbatim.