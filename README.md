# SocialPulse AI

Explainable social media intelligence and emerging trend forecasting for an
academic Big Data Analytics project. The primary experience is a React + Vite
dashboard that automatically loads a clearly labeled synthetic demo dataset.
An optional Streamlit client and separate Hadoop Streaming/Hive examples are
also included.

> **Important:** local dashboard analytics run on one machine with Pandas and
> scikit-learn. Only a configured Hadoop cluster can execute the distributed
> workflow. No live social-media API is required or included.

## Architecture

- `backend/` — FastAPI endpoints, validation, analytics, and SQLite aggregate history.
- `frontend/web/` — primary React, TypeScript, Vite, Tailwind, Recharts, and
  Lucide dashboard, connected to the API over HTTP.
- `frontend/app.py` — optional Streamlit client using the same API.
- `data/sample/` — explicitly synthetic test/demo CSV.
- `bigdata/` — Hadoop Streaming mapper/reducer, local smoke runner, and Hive SQL.
- `docs/ACADEMIC_REPORT.md` — methodology, diagrams, report scaffold, viva Q&A.

Python 3.12 is the workspace runtime used for initial implementation. Python
3.10+ is recommended. Java, Hadoop, Hive, a live API, and pretrained model
downloads are not required for local dashboard use.

## Install and run on Windows PowerShell

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Start the API in one terminal:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn backend.app.main:app --reload
```

In another terminal, install and start the React dashboard:

```powershell
Push-Location frontend\web
npm install
npm run dev
Pop-Location
```

Open the Vite URL shown in the terminal (usually `http://localhost:5173`).
The API and interactive OpenAPI documentation are at
`http://127.0.0.1:8000` and `http://127.0.0.1:8000/docs`.

Copy `frontend/web/.env.example` to `frontend/web/.env.local` and change
`VITE_API_URL` if the backend runs elsewhere.
The API allows the local Vite origin by default. Other backend settings are
documented in `.env.example`.

## Quick start demo

1. Start the API and Vite development server.
2. Open the dashboard. It automatically requests `/demo/dashboard`, which
   generates synthetic records locally and derives the displayed analytics.
3. Explore the 13 pages: Executive Overview, Live Intelligence, Sentiment
   Analysis, Topic Discovery, Emerging Trends, Trend Forecasting, Brand
   Intelligence, Conversation Explorer, AI Insights, Big Data Pipeline, Model
   Evaluation, Data Sources, and Settings & Project.
4. Import CSV/JSON from Data Sources, or filter records, manually regenerate
   the demo, export a JSON report or filtered conversation CSV, and optionally
   upload labeled data on the Model Evaluation page.
5. Demo records are synthetic—not evidence about real brands or current public
   opinion. No live feed or background refresh is active.

The optional Streamlit application can still be run with
`streamlit run frontend/app.py`; it is not the primary frontend.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Service status and honest processing mode |
| GET | `/demo/dashboard` | Generate synthetic demo records and calculated analytics |
| GET | `/demo/sources` | Report demo, external API, and Hadoop configuration status |
| POST | `/predict/sentiment` | Rule-based sentiment baseline for a text |
| POST | `/analyze/dataset` | Validate and analyze uploaded CSV |
| POST | `/analyze/import` | Analyze an uploaded CSV or JSON object/array |
| POST | `/analyze/topics` | TF-IDF/NMF topics with assigned-post evidence |
| POST | `/analyze/trends` | Configurable calendar-window keyword comparison |
| POST | `/evaluate/sentiment` | Evaluate baseline against supplied labeled CSV |
| POST | `/forecast` | Daily model comparison and chronological holdout metrics |
| GET | `/analytics/summary` | Aggregate analysis metadata |
| GET | `/analytics/history` | Recent metadata records |

Uploads are bounded by default to 5 MiB and 5,000 rows. The selected CSV filename
is never used as a filesystem path. SQLite stores aggregate counts only, not
the uploaded post text. Configure `SOCIALPULSE_DATABASE_PATH` to change its
location. SQLAlchemy 2.x manages the local SQLite metadata schema.

## Big Data demonstration

`bigdata/mapreduce/mapper.py` and `reducer.py` implement word frequency;
`hashtag_mapper.py` counts hashtags; `sentiment_mapper.py` and
`sentiment_reducer.py` aggregate pre-labeled records by day, topic, and
sentiment.
`bigdata/hadoop/README.md` documents HDFS upload, execution, inspection, and safe
cleanup. `bigdata/hive/schema.sql` contains Hive DDL and aggregation examples.
`bigdata/spark/socialpulse_spark.py` implements PySpark word/hashtag counts and
lexicon sentiment aggregation. PySpark is optional:

```powershell
python -m pip install -r bigdata/spark/requirements.txt
spark-submit --master "local[*]" bigdata/spark/socialpulse_spark.py `
  data/sample/socialpulse_sample.csv data/spark-output
```

`local[*]` executes Spark on one machine; it is not a cluster run.

The local smoke test uses the same mapper/reducer but is explicitly not
distributed:

```powershell
python bigdata/mapreduce/local_wordcount.py data/sample/socialpulse_sample.csv
```

For actual MapReduce, install/configure Java and Hadoop in a supported Linux or
WSL2 environment, set the Hadoop Streaming JAR path, and follow the
HDFS/Hadoop/Hive guide. No successful cluster execution is claimed for this
workspace.

## Testing

```powershell
python -m pytest
```

Tests cover preprocessing, dataset validation and duplicates, sentiment
response shape, NMF topic evidence, guarded trend scoring, forecast model
comparison, CSV/JSON API imports, Streaming word/hashtag/sentiment jobs, and
metadata-only history.

Build the React/TypeScript application with:

```powershell
Push-Location frontend\web
npm run build
npm run lint
Pop-Location
```

## Analytics and limitations

- Sentiment uses a small transparent lexicon; it is not a trained transformer
  and its scores are not calibrated probabilities.
- Topics use TF-IDF and seeded NMF, with assigned representative records,
  sentiment breakdown, and UMass top-term coherence. Labels and coherence are
  exploratory, not verified subjects or ground-truth quality.
- Trend analysis compares adjacent calendar windows and counts each keyword at
  most once per post. A documented volume/growth score ranks results; a spike
  is not a durable trend, and growth is withheld for a small prior baseline.
- Daily forecasting requires at least 14 calendar days, fills missing dates
  within the observed span with zero, compares a last-value baseline with Holt
  damped-trend smoothing, selects using an earlier chronological split inside
  the training data, and reports outer-holdout MAE/RMSE. Empirical error bands
  appear only with enough holdout errors and are not calibrated.
- Brand matching is text search, not verified entity resolution.
- No genuine social-media posts, labeled evaluation scores, live API integration,
  or cluster results are bundled.
- CSV/JSON imports are available. Authorized social-platform connectors still
  require a provider-specific adapter, credentials, and verified access; this
  application does not scrape platforms or treat unconfigured sources as live.

Review [docs/ACADEMIC_REPORT.md](docs/ACADEMIC_REPORT.md) for the academic
report scaffold, methodology, dataset sourcing cautions, demonstration guide,
and likely viva questions. Synthetic data is explicitly identified.
See [docs/DATASETS.md](docs/DATASETS.md) for source links and a use/license
verification checklist; external dataset terms and exact release sizes are
intentionally not guessed.

## Troubleshooting

- **Dashboard cannot connect:** ensure Uvicorn is running at the configured
  `SOCIALPULSE_API_URL`; open `/health`.
- **CSV rejected:** save as UTF-8 CSV, check delimiter/quoting, ensure the text
  column is mapped correctly, and stay within the file/row limits.
- **No trend results:** trends need valid timestamps and at least the minimum
  mentions inside the latest window.
- **Forecast rejected:** provide at least 14 consecutive daily periods within
  the supplied date range; missing days inside that range count as zero.
- **PowerShell blocks activation:** use the current Python executable to run
  `.venv\Scripts\python.exe -m pip ...`, or follow your organization's
  PowerShell policy. Do not weaken machine policy just for this project.
- **Hadoop command unavailable:** Hadoop/Hive/Java are external prerequisites;
  use the local word-count command only for a non-distributed smoke test.

## Completion checklist

- Implemented: auto-loaded synthetic demo, React dashboard, dataset
  ingestion/cleaning, baseline sentiment, topic suggestions, trend comparison,
  linear forecast baseline, metadata database, API, exports, and Hadoop
  Streaming/Hive assets.
- Testable locally: API, analytics, upload validation, SQLite history, React
  production build, dashboard HTTP integration, local MapReduce-script smoke
  run, and label-based baseline evaluation on user data.
- Requires external resources: real licensed datasets and any optional live
  platform API; no live API connector is implemented. Demo refresh is manual and
  regenerates local synthetic data.
- Requires separate installation: actual Hadoop/HDFS/MapReduce/Hive execution.
- Evaluation metrics for sentiment require an independent labeled test set;
  none are fabricated or reported.
