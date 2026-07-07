# BoC Economics dbt Project

End-to-end analytics engineering portfolio project: Bank of Canada Valet API to BigQuery to dbt to Looker Studio. This file is the single source of truth for the project. Read it fully before making changes.

---

## 1. What this is and why it exists

A public, reviewable portfolio repo that demonstrates a complete modern-data-stack pipeline. Its specific job is to prove dbt competence (the one gap in an otherwise strong Databricks / BigQuery / SQL / Python profile) and to show stack versatility across two warehouse ecosystems.

The narrative is deliberately Canadian macroeconomic data, because the primary job targets are the Big Five banks and major insurers, and this dataset lets the project be discussed fluently in a financial-services interview.

**What a reviewer should be able to see in under two minutes:** a clean staging to intermediate to mart dbt structure, real tests (including a custom one), schema YAML docs on every model, a GitHub Actions CI run on PRs, and a live Looker Studio dashboard linked from the README.

---

## 2. Guiding principle: build small and ship

This is the most important rule in this file. The project is scoped to about one week of evening work. The complete pipeline is the signal, not any one polished component.

- Do NOT add more models, series, or tests than the plan below specifies.
- Do NOT over-engineer ingestion. Truncate-and-reload is correct here. No incremental logic, no orchestration tool.
- If a single task balloons, ship the simplest working version and move on.
- Application cadence (5 to 8 tailored job applications per week) runs in parallel and takes priority over gold-plating this repo.

Decisions in sections 4 to 8 are already made. Do not relitigate them; execute them.

---

## 3. Current state (Day 0 complete)

Done:
- GCP project created. Project ID: `boc-dbt-portfolio-project`.
- BigQuery enabled, billing linked. Free tier (1TB queries, 10GB storage/month) makes cost effectively zero.
- Service account `dbt-runner` created with `roles/bigquery.dataEditor` and `roles/bigquery.jobUser`.
- Service account key JSON generated and stored OUTSIDE the repo at `~/.gcp/dbt-runner-key.json` (Windows: `C:\Users\sayee\.gcp\dbt-runner-key.json`).
- dbt project scaffolded (dbt 1.11.x, dbt-bigquery adapter). Repo root IS the dbt project (`dbt_project.yml` at root).
- `profiles.yml` configured. `dbt debug` passes including the connection test.
- Repo pushed: https://github.com/xprsayeem/boc-economics-dbt (branch: `main`).

Confirm at the start of Day 1:
- That the `boc_raw` BigQuery dataset exists (location `northamerica-northeast2`). Create it if missing: `bq --location=northamerica-northeast2 mk --dataset boc-dbt-portfolio-project:boc_raw`.
- That the venv folder (`dbt-venv/`, which lives INSIDE the repo) is gitignored. It must never be committed. Add `dbt-venv/` to `.gitignore` if it is not already there.
- That the service account key path is not tracked. `.gitignore` includes `*-key.json` and `.env`.

---

## 4. Environment

- OS: Windows 11, shell is PowerShell. Use PowerShell syntax, not bash.
- Repo root: `C:\Users\sayee\Desktop\Projects\BOC-portfolio-project`
- venv: `dbt-venv\` inside the repo. Activate with `.\dbt-venv\Scripts\Activate.ps1`.
- dbt profiles: `C:\Users\sayee\.dbt\profiles.yml`, profile name `boc_economics` (must match `profile:` in `dbt_project.yml`).
- Auth: `profiles.yml` reads the keyfile path from the `DBT_KEYFILE` environment variable. This keeps CI a drop-in swap.

Setting the env var in PowerShell (session only):
```powershell
$env:DBT_KEYFILE = "$HOME\.gcp\dbt-runner-key.json"
```
For persistence across sessions, set it via a PowerShell profile or Windows System Environment Variables rather than re-exporting each time. Confirm `profiles.yml` uses `env_var('DBT_KEYFILE')` and not a hardcoded path before relying on this.

Target profiles.yml block (reference):
```yaml
boc_economics:
  target: dev
  outputs:
    dev:
      type: bigquery
      method: service-account
      keyfile: "{{ env_var('DBT_KEYFILE') }}"
      project: boc-dbt-portfolio-project
      dataset: boc_analytics
      location: northamerica-northeast2
      threads: 4
      priority: interactive
```

---

## 5. Tech stack

| Layer | Tool |
|---|---|
| Warehouse | BigQuery (location `northamerica-northeast2`) |
| Transformation | dbt Core, dbt-bigquery adapter |
| Ingestion | Python (`requests`), lands raw tables in `boc_raw` |
| CI/CD | GitHub Actions, runs `dbt build` on PR |
| Visualization | Looker Studio on the mart |

BigQuery datasets:
- `boc_raw`: raw ingested series (created by hand / by the Python script).
- `boc_analytics`: dbt target. dbt auto-creates it on first run. Staging, intermediate, and mart models all materialize here (or into schema suffixes if configured).

---

## 6. Data source: Bank of Canada Valet API

- Base URL: `https://www.bankofcanada.ca/valet/`
- No registration, no API key, free. Be polite: cache responses, ramp request rate gradually.
- Formats available: JSON, CSV, XML. Use JSON.

Key endpoints:
- `GET /lists/series/json` and `GET /lists/groups/json`: discover and confirm exact series names.
- `GET /observations/{seriesNames}/json`: observations for one or more comma-separated series. Supports `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` and `?recent=N`.
- `GET /series/{seriesName}/json`: metadata for a single series.

**Four series to ingest (one concept each):**
1. Policy interest rate (target for the overnight rate)
2. CPI (total, all-items) or the headline inflation rate
3. CAD/USD daily exchange rate
4. A Government of Canada benchmark bond yield (e.g. 5-year)

Known-good anchor: `FXUSDCAD` is the daily USD-to-CAD exchange rate series (`FXCADUSD` is the inverse). 

**First Day 1 task:** hit `/lists/series/json` (or the relevant group via `/lists/groups/json`) and confirm the exact series name for each of the four concepts. Do not hardcode series codes from memory or from third-party blogs; some older CANSIM-style codes are deprecated. Store the four confirmed series names in a small config (a Python dict or a list at the top of the ingestion script) so they are easy to see and change.

Note on frequency: exchange rates, interest rates, and bond yields are daily; CPI is monthly. The intermediate/mart layer standardizes these onto a common grain (see section 7). Decide the grain deliberately; monthly is the cleaner story for a dashboard, so daily series can be aggregated (e.g. month-end or monthly average) in the intermediate layer.

---

## 7. Target architecture and modeling

Three dbt layers. Keep model counts minimal.

**Staging (`models/staging/`, prefix `stg_`):** one model per source series. Rename columns, cast types, standardize the date column and grain. Thin, no business logic. Add `_sources.yml` pointing at the `boc_raw` tables.

**Intermediate (`models/intermediate/`, prefix `int_`):** union the four staging models into a single long/tidy table with the shape:

```
date | indicator_code | value
```

This is where daily series get aligned to the chosen common grain (recommended: monthly).

**Mart (`models/marts/`):**
- `fct_economic_indicators`: the fact table built off the intermediate model. One row per (date, indicator_code) with the value. This feeds Looker Studio.
- `dim_indicator`: a small dimension seeded from a CSV (`seeds/dim_indicator.csv`) with columns like `indicator_code`, `indicator_name`, `unit`, `frequency`, `source`. Loaded via `dbt seed`.

This shape intentionally demonstrates: a seed, a union across sources, and a clean star (fact joined to a dimension). That range is what interviewers want to see.

---

## 8. Testing, docs, and CI

**Tests (target 5 to 8 total):**
- Built-in: `not_null` and `unique` on keys, `relationships` from `fct_economic_indicators.indicator_code` to `dim_indicator.indicator_code`, `accepted_values` on `indicator_code`.
- One custom test: a generic "no missing months" (no date gaps) test per series. This is the showcase test. It signals real data-quality thinking, so make it the one you can explain in an interview.

**Docs:** every model gets a schema YAML (`_models.yml` per folder) with model and column descriptions. Document as you build each layer so the docs step is not a big lift at the end.

**CI/CD (Day 5, the differentiator):**
- GitHub Actions workflow triggered on pull requests.
- Runs `dbt deps` (if any packages) then `dbt build` (build = run + test).
- Auth: store the service account key JSON as a GitHub repo secret (e.g. `GCP_SA_KEY`). In the workflow, write the secret to a file at runtime and point `DBT_KEYFILE` at it.
- Writes to a SEPARATE CI dataset (e.g. `boc_analytics_ci`) via a `ci` target in `profiles.yml`, so CI never touches the main `boc_analytics`.
- Because auth already uses the `DBT_KEYFILE` env var, this is a config swap, not a rewrite.
- Expect this to be the fiddliest day. If the workflow YAML fights you, that is the one place worth stopping to get the exact file right rather than grinding.

---

## 9. Remaining plan (evenings)

**Day 1, ingestion.** Confirm the four Valet series names via `/lists/series/json`. Write one Python script that pulls each series and loads it into a raw table in `boc_raw`. Idempotent, truncate-and-reload, no incremental logic. Put the script in `ingestion/`. This is plumbing, not the showpiece; do not polish it.

**Day 2, staging.** One `stg_` model per series (rename, cast, standardize grain). Add `_sources.yml` for the `boc_raw` tables. Start the schema YAML docs here.

**Day 3, intermediate and mart.** Build the `int_` union model (long format). Build `fct_economic_indicators` and the `dim_indicator` seed. Run `dbt seed` then `dbt build`. Confirm the star joins cleanly.

**Day 4, tests and docs.** Add the built-in tests and the custom no-date-gaps test. Finish schema YAML on every model. `dbt build` should be green with tests passing.

**Day 5, CI/CD.** GitHub Actions workflow running `dbt build` on PR against a separate CI dataset, authed via the `GCP_SA_KEY` secret. Open a test PR and confirm the check runs and passes.

**Day 6, dashboard and README.** One Looker Studio dashboard on `fct_economic_indicators` (the four indicators over time; nothing fancy). Then flesh out the README: a short architecture description, the staging to intermediate to mart flow, how to run it locally, and a link to the live dashboard. The README matters as much as the code because it is what a reviewer actually reads.

---

## 10. Conventions

- Model names: `stg_boc__<series>`, `int_<description>`, `fct_<noun>`, `dim_<noun>`.
- One `_sources.yml` and one `_models.yml` per model folder.
- SQL: lowercase keywords, leading commas or trailing commas consistently, CTEs over nested subqueries.
- Commit messages: short and factual, prefixed by day (e.g. `Day 2: staging models + sources`).
- Keep secrets out of git: `*-key.json`, `.env`, and `dbt-venv/` are gitignored. Verify before every push that no key file is staged.

---

## 11. Quick reference

```powershell
# activate venv
.\dbt-venv\Scripts\Activate.ps1

# set auth (session)
$env:DBT_KEYFILE = "$HOME\.gcp\dbt-runner-key.json"

# core dbt loop
dbt debug        # verify connection + project
dbt seed         # load dim_indicator.csv
dbt run          # build models
dbt test         # run tests
dbt build        # run + test in dependency order
```

- Project ID: `boc-dbt-portfolio-project`
- Datasets: `boc_raw` (ingestion), `boc_analytics` (dbt), `boc_analytics_ci` (CI, Day 5)
- Location: `northamerica-northeast2` (must be identical everywhere)
- Repo: https://github.com/xprsayeem/boc-economics-dbt (branch `main`)
