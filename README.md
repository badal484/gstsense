# GSTSense

Production-grade GST compliance SaaS for Indian SMBs and CA firms. Automates GSTR-2A/2B vs purchase register reconciliation, surfaces mismatches, generates AI-powered explanations, and delivers actionable compliance reports.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, Shadcn/ui |
| State | Zustand, TanStack Query |
| Backend | FastAPI, Python 3.11 |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Database | PostgreSQL 15 (AWS RDS, ap-south-1) |
| Cache / Queue | Redis (AWS ElastiCache) + Celery |
| Storage | AWS S3 (ap-south-1) |
| AI | Anthropic Claude, OpenAI, LangChain |
| Payments | Razorpay |
| Notifications | Resend (email), Interakt (WhatsApp) |
| Monitoring | Sentry, Structlog |
| Infra | Docker, Nginx, GitHub Actions |

---

## Local Setup

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 15 (or use Docker)
- Redis (or use Docker)

### 1. Clone the repository

```bash
git clone <repo-url>
cd gstsense
```

### 2. Start infrastructure with Docker

```bash
docker compose up -d postgres redis
```

### 3. Backend setup

```bash
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in your values

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local and fill in your values

# Start the dev server
npm run dev
```

The app will be available at `http://localhost:3000`.

---

## Running Tests

```bash
cd backend
source venv/bin/activate

# Run all tests with coverage
pytest --cov=app --cov-report=html

# Run a specific test file
pytest tests/test_reconciler.py -v

# Type checking
mypy app/

# Linting
flake8 app/
black --check app/
isort --check-only app/
```

---

## Running with Docker (full stack)

```bash
# Development
docker compose up --build

# Production
docker compose -f docker-compose.prod.yml up --build -d
```

---

## Deployment

### Infrastructure

All infrastructure runs in AWS `ap-south-1` (Mumbai) for data residency compliance.

- **Compute**: ECS Fargate (backend) + Vercel (frontend)
- **Database**: AWS RDS PostgreSQL 15 (Multi-AZ)
- **Cache**: AWS ElastiCache Redis 7
- **Storage**: AWS S3 (server-side encryption enabled)
- **CDN**: CloudFront

### CI/CD

GitHub Actions workflows handle:
- `test.yml` — runs on every PR: lint, type-check, pytest, coverage gate
- `deploy.yml` — runs on merge to `main`: builds Docker image, pushes to ECR, deploys to ECS

### Environment variables

Copy `.env.example` to `.env` (backend) and `.env.example` to `.env.local` (frontend) and populate all values before deploying. Never commit `.env` files.

---

## Project Structure

```
gstsense/
├── backend/          # FastAPI application
├── frontend/         # Next.js application
├── nginx/            # Reverse proxy config
├── scripts/          # Dev and ops scripts
└── .github/          # CI/CD workflows
```

---

## License

Proprietary — all rights reserved.
