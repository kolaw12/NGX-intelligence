# dbt project — NGX warehouse quality + (future) transforms

## Local usage

Run from `ai-stock-broker-backend/` (the repo root — **not** from inside `dbt/`),
with the venv active (`source venv/Scripts/activate`).

```bash
# Load the two env vars dbt needs from .env
export GCP_PROJECT_ID="$(grep -E '^GCP_PROJECT_ID=' .env | cut -d= -f2-)"
export GCP_CREDENTIALS_PATH="$(grep -E '^GCP_CREDENTIALS_PATH=' .env | cut -d= -f2-)"
export BIGQUERY_MARKET_DATASET=ngx_market_data

dbt deps   --project-dir dbt --profiles-dir dbt   # downloads dbt_utils into dbt/dbt_packages/
dbt parse  --project-dir dbt --profiles-dir dbt   # offline sanity: project parses, no warnings
dbt build  --project-dir dbt --profiles-dir dbt   # creates stg_price view + runs all tests
```

Both flags matter:

- `--project-dir dbt` tells dbt where `dbt_project.yml` lives (otherwise it
  looks in the current working directory and fails with
  `No dbt_project.yml found at expected path`).
- `--profiles-dir dbt` tells dbt where `profiles.yml` lives.

`dbt build` creates the view `ngx_market_data.stg_price` and runs every test
defined in `models/staging/schema.yml`. A failing test fails the whole command
(exit non-zero), which is what CI picks up.

To inspect failing-test rows in BigQuery later, re-run with:

```bash
dbt build --project-dir dbt --profiles-dir dbt --store-failures
```

That materializes each failure as `dbt_test_failures.<test_name>` in BQ.

## Layout

```
dbt/
├── dbt_project.yml          project config
├── profiles.yml             env-var-driven; no creds in this file
├── packages.yml             dbt_utils pin
└── models/staging/
    ├── sources.yml          declares the raw price table as a source
    ├── stg_price.sql        thin pass-through view (downstream tests run here)
    └── schema.yml           quality tests
```
