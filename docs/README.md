# CSV Stats API

Enterprise-grade dataset profiling and AI-powered analysis platform.

## Quick Start

```bash
cp .env.example .env
docker-compose up -d
docker-compose exec api alembic upgrade head
```

Services: API (8000), Frontend (5173), Flower (5555), Prometheus (9090), Grafana (3001)

## Architecture

- **Backend**: FastAPI + SQLAlchemy 2.0 + Celery + Redis + PostgreSQL
- **Profiling**: Streaming engine with Welford algorithm + reservoir sampling
- **AI**: OpenAI GPT grounded in real dataset statistics
- **Frontend**: React 18 + TypeScript + Vite + TanStack Query + Zustand
- **Infra**: Docker Compose + Kubernetes manifests + GitHub Actions CI/CD

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/datasets/upload` | Upload dataset |
| GET | `/api/v1/datasets/{id}/preview` | Paginated preview |
| GET | `/api/v1/datasets/{id}/profiling` | Statistical profile |
| GET | `/api/v1/datasets/{id}/charts/histogram` | Histogram |
| GET | `/api/v1/datasets/{id}/charts/correlation` | Correlation matrix |
| GET | `/api/v1/datasets/{id}/ai/summary` | AI summary |
| POST | `/api/v1/datasets/{id}/ai/chat` | AI chat |
| GET | `/api/v1/jobs/{id}` | Job status |

## Supported Formats

CSV, TSV, XLSX, XLS, JSON, JSONL, Parquet (up to 500 MB)

## Key Design Decisions

- **Streaming profiling**: Welford online algorithm + reservoir sampling for O(1) memory
- **Async workers**: Celery (not BackgroundTasks) for retries, cancellation, timeouts
- **DuckDB preview**: Server-side SQL queries without loading full dataset
- **AI grounding**: Prompts built from real statistics, never hallucinated columns
- **Storage abstraction**: Local or S3-compatible via `StorageBackend` interface
- **Path safety**: All storage keys validated against traversal attacks

## Running Tests

```bash
cd backend
pytest tests/ -v --cov=backend --cov-report=term-missing
```

## Production Deployment

```bash
kubectl create namespace csv-stats
kubectl apply -f infra/k8s/deployment.yaml