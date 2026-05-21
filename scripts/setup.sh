#!/usr/bin/env bash
set -euo pipefail

# GSTSense — first-time setup script
# Run from the repo root: bash scripts/setup.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> GSTSense Setup"
echo "    Working directory: $REPO_ROOT"

# ── 1. Backend virtual environment ─────────────────────────────────────────

echo ""
echo "==> [1/5] Setting up Python virtual environment..."
cd "$REPO_ROOT/backend"

if [ ! -d venv ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install -r requirements-dev.txt --quiet

echo "    Python packages installed."
deactivate

# ── 2. Backend .env ────────────────────────────────────────────────────────

if [ ! -f "$REPO_ROOT/backend/.env" ]; then
    echo ""
    echo "==> [2/5] Creating backend/.env from template..."
    cat > "$REPO_ROOT/backend/.env" << 'ENV'
# ── Application ────────────────────────────────────────────────
ENVIRONMENT=development
SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32
JWT_SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32

# ── Database ───────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://gstsense:gstsense_dev_pass@localhost:5432/gstsense

# ── Redis / Celery ────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# ── AWS S3 ────────────────────────────────────────────────────
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_REGION=ap-south-1
S3_BUCKET_NAME=gstsense-dev

# ── Razorpay ─────────────────────────────────────────────────
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
RAZORPAY_WEBHOOK_SECRET=your_razorpay_webhook_secret

# ── AI Providers ─────────────────────────────────────────────
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key

# ── Notifications ─────────────────────────────────────────────
RESEND_API_KEY=re_your_resend_api_key
INTERAKT_API_KEY=your-interakt-api-key
FROM_EMAIL=noreply@gstsense.in

# ── Sentry ────────────────────────────────────────────────────
SENTRY_DSN=
ENV
    echo "    backend/.env created. Fill in real credentials before running."
else
    echo "==> [2/5] backend/.env already exists — skipping."
fi

# ── 3. Frontend .env.local ─────────────────────────────────────────────────

if [ ! -f "$REPO_ROOT/frontend/.env.local" ]; then
    echo ""
    echo "==> [3/5] Creating frontend/.env.local..."
    cat > "$REPO_ROOT/frontend/.env.local" << 'ENV'
NEXT_PUBLIC_API_URL=http://localhost:8000
ENV
    echo "    frontend/.env.local created."
else
    echo "==> [3/5] frontend/.env.local already exists — skipping."
fi

# ── 4. Frontend npm install ────────────────────────────────────────────────

echo ""
echo "==> [4/5] Installing frontend Node packages..."
cd "$REPO_ROOT/frontend"
npm ci --silent
echo "    Frontend packages installed."

# ── 5. Summary ────────────────────────────────────────────────────────────

echo ""
echo "==> [5/5] Setup complete."
echo ""
echo "Next steps:"
echo "  1. Edit backend/.env with your real credentials"
echo "  2. Start services: docker-compose up -d db redis"
echo "  3. Run migrations: cd backend && source venv/bin/activate && alembic upgrade head"
echo "  4. Start backend: uvicorn app.main:app --reload"
echo "  5. Start frontend: cd frontend && npm run dev"
echo ""
echo "Or start everything with Docker:"
echo "  docker-compose up --build"
