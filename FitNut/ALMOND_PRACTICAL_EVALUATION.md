# Practical multi-turn evaluation

`scripts/practical_almond_comparison.py` compares optional-context methods while holding the Qwen 3.8 writer, pantry, confirmed profile and Python checks fixed. Methods are `bounded_all`, `lexical`, `jev_select`, and `oracle_context`. The last uses fixture-author relevance labels as a reference condition; it is not deployable retrieval.

The practical fixtures contain 20 episodes and 60 turns across creation, substitutions, memory, uncertainty and variety. They use 18 real USDA records, with preparation state, per-100g nutrient basis, source references and retrieval dates. Empty allergen lists describe reviewed food identity, not manufacturing cross-contact certification. Missing/contradictory product evidence stays unresolved.

Run only with private application/database configuration and the same existing evaluation ledger. Do not reset spending or uncertain reservations. A copied checkout on another machine must not receive a fresh $2 allowance: reconcile its cap with the remaining combined budget first. The November 4 run ended at $0.288265922 settled/estimated plus $0.007730000 reserved across all experiments, leaving at most $1.704004078 of the original allowance. These figures are project accounting, not vendor account balances.

Preflight does not make model calls:

```powershell
python -m scripts.practical_almond_comparison --method bounded_all --split dev --output work/practical-dev-check.json --preflight
```

After checking prerequisites, a new run uses a new output path:

```powershell
python -m scripts.practical_almond_comparison --method bounded_all --split dev --output work/new-practical-dev-bounded.json
```

Jev requires the process-only `ALMOND_EVAL_GATEWAY_TOKEN` and the independently verified public certificate at `work/gateway-public.pem`. The client verifies the certificate fingerprint and hostname. Qwen uses the US DashScope endpoint through the local in-process private sidecar. Vendor keys remain private. Never paste credentials into logs, reports or source control.

Only one sequential process may use a method's suspended evaluation identity at a time. All methods share atomic worst-case evaluation reservations. Each turn permits at most two writer calls and one Jev call. A malformed/uncertain gateway outcome stops the run and retains its reservation.

The output journal is written before upstream calls. `--resume` requires no in-flight uncertainty and unchanged prompts, validator, catalog and fixtures. It restores state from recorded turns and skips every recorded turn, including failures. It never automatically repeats a paid request. A `.tmp` snapshot from an interrupted local rename must be inspected against the existing prefix before recovering settled results; do not assume an unlogged request was free.

Scripted confirmation/temporary events administer benchmark state. They do not test NLU extraction or real persistence. `tests/test_almond_meal_scope.py` separately exercises actual authenticated application requests and Profile updates in an isolated test database with model calls mocked. The test verifies revision retention, new-meal expiry and durable/temporary separation.

Keep the metrics separate: restrictions, evidence/reference completeness, appropriate/focused clarification, request following, cooking quality, appeal, repetition/favorite overlap, context selection, cost and latency. Independent subjective review covers predeclared first/final turns; all turns retain objective assertions and raw responses. No weighted formula or this script can qualify a production model. Keep generation disabled until remaining evidence/clarification issues are corrected and fresh qualification passes.
