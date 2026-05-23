# CSV Stats API

> Enterprise-grade dataset profiling, statistical analysis, and AI-powered insights platform.

[![CI](https://github.com/your-org/csv-stats-api/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/csv-stats-api/actions)

## What It Does

Upload any dataset (CSV, Parquet, Excel, JSON) and get:

- **Statistical profiling** — row counts, distributions, outliers, correlations
- **Data quality analysis** — missing values, duplicates, anomalies
- **Interactive visualizations** — histograms, box plots, correlation heatmaps
- **AI-powered insights** — dataset summaries, ML readiness scores, preprocessing recommendations
- **Conversational assistant** — ask questions about your data in natural language

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Pydantic v2 |
| Database | PostgreSQL + SQLAlchemy 2.0 |
| Queue | Redis + Celery |
| Profiling | Pandas + NumPy + DuckDB + PyArrow |
| AI | OpenAI GPT-4o-mini |
| Frontend | React 18 + TypeScript + Vite + TailwindCSS |
| Observability | Prometheus + Loguru |
| Deployment | Docker + Kubernetes |

## Quick Start

```bash
git clone <repo> && cd csv-stats-api
cp .env.example .env
docker-compose up -d
docker-compose exec api alembic upgrade head
open http://localhost:5173
```

## Project Structure

```
backend/          FastAPI application + Celery workers
frontend/         React/TypeScript SPA
infra/            Docker, Kubernetes, CI/CD configs
docs/             Architecture documentation
docker-compose.yml  Full local development stack
```

See [`docs/README.md`](docs/README.md) for full documentation.

## License

MIT