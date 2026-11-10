# Ask Almond

Almond is integrated into Overview, Food, and Activity. It uses the existing account/session/CSRF system and the charcoal/almond theme. Chats, editable personal preferences, recipe revisions, favorite snapshots, food-log drafts, and budget records persist in MySQL. Confirm lasting restrictions in Profile; temporary meal constraints stay with the current recipe conversation.

## Current release gate

Generation is disabled by default. Both `ALMOND_ENABLED=true` and the database admin switch are required, plus a qualifying evaluation for the exact current prompt and writer from the last 30 days. No writer has been qualified and no paid calls were made during local implementation. The original 80 fixtures are regression cases used while fixing the validator; they cannot qualify a writer as held-out evidence.

## Server deployment

Keep the current Caddy proxy, Waitress listener on 5055, database on 3307, and `FitNut Web` task. The supplied sidecar listens on **127.0.0.1:8001 only**, uses a separate strong token, routes the four allowed writers directly and pinned Jev through OpenRouter, and leaves the older public gateway unchanged. The server operator must inspect the existing gateway's public `/api/chat` authorization separately; this checkout does not contain that gateway's source.

Extract the release separately from `C:\ProgramData\FitNut\app`. Inspect `service\serve_fitnut.py` and `service\app.env`; confirm the Python executable and mysqldump location, database environment names, and scheduled-task principal. Then run `scripts\deploy_almond.ps1 -PythonPath <server-python.exe> -MySqlDumpPath <mysqldump.exe> -MigrationCredential (Get-Credential)` with a database account allowed to create/alter tables. Keep the runtime app account restricted. The script backs up the app/environment/database before copying code and applying additive schema updates, keeps generation off, and registers a startup task for the sidecar. Verify both tasks restart after reboot. The script is prepared but has not been run on the remote server.

The sidecar reads `ALMOND_VENDOR_ENV` (default `C:/broll-api/geography/.env`) and expects `DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`, `ZAI_API_KEY`, and `OPENROUTER_API_KEY`. Confirm the actual variable names without printing values. Neither vendor keys nor the private token belong in browser code, Git, or this release. See `.env.almond.example` for configuration names.

Check public HTTPS with normal certificate verification. Keep the IP URL if its certificate is trusted and covers that IP. If it is not, configure the existing Caddy with `fitnut.192-236-176-111.sslip.io` as a hostname pointing at the same server; no hosting migration or idle sleep is involved. Do not configure clients to skip TLS checks.

## Food evidence

USDA lookup stores nutrients and observed ingredient data. Retrieved records are **not automatically trusted as allergen-absence evidence**. `python -m scripts.review_almond_food reviewed-food.json` imports human-reviewed composition evidence for an existing `food_catalog` ID. Include `ingredients` (all subingredients), canonical `allergens`, verified `dietary_tags`, `restriction_coverage` for custom restrictions, an exact HTTPS `source_url`, stable `evidence_id`, and `reviewer_notes`. Observed USDA records are in `almond_food_observations`; reviewed metadata is separate. Reviews expire from generation after 30 days.

The restriction vocabulary is conservative and incomplete; a missing custom mapping causes abstention. Text matching and Jev review cannot certify clinical allergy safety or actual preparation cross-contact. Source links alone do not establish facts. Do not load synthetic test fixtures into production as reviewed food data.

## Evaluation and operations

1. Update/verify the allowed model versions, provider-specific non-thinking settings, and conservative rate cards against direct provider catalogs before spending.
2. Run `python -m scripts.evaluate_almond --dry-run`. The current estimate for all four writers is $0.2495 for 20 cases each and $0.7485 for 60 each at reserved maxima, before Jev/review experiments. The shared evaluation budget stops new calls at $2.
3. The default `almond_writer_benchmark.json` is a separately frozen, independently authored set of 80 cases (20 development / 60 held-out). Run development then held-out evaluation on the server with `--user-id <active-admin-id> --output work/report.json`. Keep held-out labels and grading feedback out of writer context and prompt development. The fixture tests supplied evidence and synthetic portions, not clinical outcomes.
4. Two independent Luna graders assess anonymized answers against the supplied references. Review schema and CLI examples are in `scripts/evaluate_almond.py`. Resolve disagreements by source review; do not treat model agreement as medical authority. Finalize only a complete reviewed held-out report. No qualifying result means generation stays off.
5. Set `ALMOND_WRITER_MODEL` to the qualifying winner, restart FitNut with `ALMOND_ENABLED=true`, then use an authenticated admin session to POST `{"enabled":true}` to `/almond/admin`. Set false for the kill switch.

`GET /almond/admin` reports separate evaluation/team balances and uncertain calls. The budgets are $2 evaluation and $3 team use for this project, not monthly resets. Calls reserve worst-case cost under a row lock, then settle reported usage; unknown outcomes stay reserved. Inspect and reconcile upstream usage before releasing a reservation. Do not blindly retry timeouts. Configured rates must be maintained; a provider charging above its published ceiling cannot be undone by accounting.

## Verification

Run `scripts/test.ps1` against its temporary database. It checks the 80 evidence cases, text escapes, profile/memory bounds, tenant isolation, CSRF, idempotency, gateway boundaries, and concurrent spending. `tests/browser_smoke.cjs` checks existing logging/profile flows; `tests/browser_almond.cjs` checks the Almond interface at desktop/mobile sizes without paid inference. All browser results are local verification, not proof of live model capability.

## Other approved OpenRouter writers

`ALMOND_OPENROUTER_MODELS` optionally contains a server-controlled JSON object mapping an exact OpenRouter `provider/model` ID to `[input_ceiling, output_ceiling]` in USD per million uncached tokens. Register only after verifying current endpoint availability and pricing; Gemini/Google and automatic routers are rejected. Use `openrouter/provider/model` as the Almond writer ID. The sidecar imposes OpenRouter `provider.max_price` ceilings and requires parameter support. Unregistered IDs and invented aliases such as `openrouter/qwen3.7-flash` are rejected. Additional writers must pass the same qualification gate before use. Load this configuration identically into FitNut and the sidecar, then restart both.

## Companion and goal confirmation API

Almond handles simple greetings locally. The normal route uses Jev to distinguish
general companion chat from meal requests. General chat uses one bounded call
with the approved model selected by `ALMOND_COMPANION_MODEL` (default
`qwen3.7-flash`). The loopback preview uses local intent rules and reserves
companion usage against the evaluation budget.

A goal statement can return a `goal_proposal` from `POST /almond/messages`.
The object contains `request_id`, `current`, `proposed`, `label`, and
`scope` (`profile`). Render it as a pending action. To save it, send
`{"request_id":"<proposal request ID>","confirmed":true}` to
`POST /almond/goals/confirm` with the existing session and CSRF token. On success
the response contains `saved: true`, `fitness_goal`, and `label`.
A superseded proposal or changed profile goal can return 409. The authenticated
conversation history exposes `goal_actions` including saved status. The save
changes only the profile goal. Apply migration 005 before saving Gain weight.
