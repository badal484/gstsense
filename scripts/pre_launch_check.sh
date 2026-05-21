#!/bin/bash
# GSTSense Pre-Launch Checklist
# Run from the repository root: bash scripts/pre_launch_check.sh

set -e

PASS=0
FAIL=0

check() {
    local label="$1"
    local cmd="$2"
    if eval "$cmd" &>/dev/null; then
        echo "  ✓  $label"
        PASS=$((PASS + 1))
    else
        echo "  ✗  $label"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "=== GSTSense Pre-Launch Checklist ==="
echo ""

echo "--- Environment Variables ---"
check "DATABASE_URL is set"         '[ -n "$DATABASE_URL" ]'
check "SECRET_KEY is at least 32 chars"   '[ ${#SECRET_KEY} -ge 32 ]'
check "JWT_SECRET_KEY is at least 32 chars" '[ ${#JWT_SECRET_KEY} -ge 32 ]'
check "SENTRY_DSN is set"           '[ -n "$SENTRY_DSN" ]'
check "RAZORPAY_KEY_ID is set"      '[ -n "$RAZORPAY_KEY_ID" ]'
check "ANTHROPIC_API_KEY is set"    '[ -n "$ANTHROPIC_API_KEY" ]'
check "AWS_REGION is ap-south-1"    '[ "$AWS_REGION" = "ap-south-1" ]'
check "AWS_S3_BUCKET is set"        '[ -n "$AWS_S3_BUCKET" ]'
check "ENVIRONMENT is production"   '[ "$ENVIRONMENT" = "production" ]'
check "DEBUG is False"              '[ "$DEBUG" = "False" ]'
check "FRONTEND_URL is not localhost" '! echo "$FRONTEND_URL" | grep -q localhost'
check "RAZORPAY_PLAN_ID_SMB is set" '[ -n "$RAZORPAY_PLAN_ID_SMB" ]'

echo ""
echo "--- Security ---"
check ".env is not tracked in git"    '! git ls-files --error-unmatch .env 2>/dev/null'
check ".env is not tracked (backend)" '! git ls-files --error-unmatch backend/.env 2>/dev/null'
check "No live API keys in git history" '! git log --all -p --follow --full-diff -- . 2>/dev/null | grep -qE "sk-ant-|rzp_live_" 2>/dev/null'

echo ""
echo "--- Python / Backend ---"
check "requirements.txt exists"     '[ -f backend/requirements.txt ]'
check "alembic.ini exists"          '[ -f backend/alembic.ini ]'
check "No uncommitted Python changes" 'git diff --quiet -- backend/app/ 2>/dev/null'

echo ""
echo "--- Frontend ---"
check "frontend package.json exists"   '[ -f frontend/package.json ]'
check "next.config.mjs exists"         '[ -f frontend/next.config.mjs ]'
check "frontend/.env.local NOT in git" '! git ls-files --error-unmatch frontend/.env.local 2>/dev/null'

echo ""
echo "--- Docker ---"
check "docker-compose.yml exists"      '[ -f docker-compose.yml ]'
check "docker-compose.prod.yml exists" '[ -f docker-compose.prod.yml ]'
check "backend/Dockerfile exists"      '[ -f backend/Dockerfile ]'
check "frontend/Dockerfile exists"     '[ -f frontend/Dockerfile ]'

echo ""
echo "--- Services (requires running stack) ---"
if [ -n "$DATABASE_URL" ]; then
    check "Database is reachable" \
        'cd backend && source venv/bin/activate 2>/dev/null && python3 -c "
import asyncio
from app.core.database import check_database_health
result = asyncio.run(check_database_health())
exit(0 if result else 1)
" 2>/dev/null'
fi
if [ -n "$REDIS_URL" ]; then
    check "Redis is reachable" \
        'redis-cli -u "$REDIS_URL" ping 2>/dev/null | grep -q PONG'
fi

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
echo ""

if [ $FAIL -gt 0 ]; then
    echo "Fix all failures before deploying to production."
    exit 1
else
    echo "All checks passed. Ready to launch."
    exit 0
fi
