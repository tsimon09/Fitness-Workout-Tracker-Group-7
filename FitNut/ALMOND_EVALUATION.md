# Exploratory pipeline comparison

`scripts/intensive_almond_comparison.py` compares Qwen 3.8 plus Python checks, the same with a Qwen review, the same with a Jev review, and Jev context selection plus final review. It never qualifies a model or enables generation.

Use the existing private database configuration and the local evaluation ledger; do not reset the $2 cap or outstanding reservations. Qwen calls use the US DashScope endpoint with the existing server-side/in-process sidecar. Remote Jev calls require `ALMOND_EVAL_GATEWAY_TOKEN` in the process environment and the independently verified public gateway certificate at `work/gateway-public.pem`. No vendor key should be pasted into chat or bundled in results. The remote credential is not the sidecar's private listener token.

Example after configuring those private prerequisites:

```powershell
python -m scripts.intensive_almond_comparison --split dev --output work/intensive-dev.json
```

The four methods use every current hard restriction and mandatory food record. They permit one Python-directed writer repair and at most two Jev calls. The final judge can withhold an answer; it cannot bypass Python validation. Optional context is dropped before hard restrictions. A private `in_flight` journal entry records the case and reservation before upstream calls. After interruption, inspect that journal and the ledger; do not automatically retry an uncertain call. Failed HTTP requests retain reservations.

The new dietary/memory fixtures contain 60 synthetic scenarios, split 20 development and 40 held out. Their official references support general relationships, not real product certification. The November 4 exploratory matrix has known limitations: exclude EDGE-024 from label accuracy because its supposedly foreign evidence ID actually matches; the injected note on food 302 appears in 29 dietary catalogs; EDGE-026's actual missing food ID requires rejection, but its spice-blend rationale is incorrect. Keep frozen fixtures intact when reproducing those recorded results. Fix fixture quality in a separately versioned future set.

Static snapshots do not prove live profile persistence or account isolation. Validator acceptance is distinct from useful preparation. Cooking-water records, preparation state and missing package directions materially affect strict usefulness grading. No writer or judge combination is production-qualified from this matrix. Keep `ALMOND_ENABLED=false` until a fresh, fully frozen reference-backed qualification passes all required thresholds.

For parallel evaluation, give each method its own suspended test identity using `--account-label` with the same method name; each process remains sequential. Do not run two processes under the same identity. The shared ledger atomically reserves their combined worst-case spending. Account provisioning creates only suspended ordinary users.
