# GlassNote — Cheapest Production Deployment Plan (GCP $300 Credits)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Users / GUI Desktop App                                        │
└────────────┬────────────────────────────┬───────────────────────┘
             │                            │
             ▼                            ▼
  ┌─────────────────────┐     ┌─────────────────────────┐
  │  glassnote.com      │     │  api.glassnote.com       │
  │  Next.js Frontend   │     │  FastAPI Backend          │
  │  Vercel FREE tier   │     │  GCP Cloud Run            │
  └─────────────────────┘     └──────────┬──────────────┘
                                          │
                               ┌──────────▼──────────────┐
                               │  Cloud SQL               │
                               │  PostgreSQL 15           │
                               │  db-f1-micro ~7/mo       │
                               └─────────────────────────┘
```

## Cost Breakdown (Monthly Estimate)

| Service | Tier | Est. Monthly Cost |
|---|---|---|
| **Domain** | Hostinger .com | ~$9/yr = ~$0.75/mo |
| **Cloud Run** backend | Pay-per-request, 1 vCPU / 512 MB | ~$0–5/mo (free tier: 2M req/mo) |
| **Cloud SQL** PostgreSQL | db-f1-micro, 10 GB SSD | ~$7–10/mo |
| **Artifact Registry** | Docker image storage | ~$0 (first 0.5 GB free) |
| **Cloud Run Egress** | Outbound to LLM APIs | ~$1–3/mo |
| **Vercel** frontend | Hobby free | $0 |
| **SSL Certificates** | Managed by Cloud Run + Vercel | $0 |
| **Total** | | **~$9–19/mo** |

> Your $300 GCP credits cover **15–30 months** of backend + database costs at this scale.

---

## Step 1 — Purchase Domain via Hostinger

1. Go to [hostinger.com](https://hostinger.com) → search for your domain (e.g. `glassnote.com`)
2. Purchase for ~$9/year
3. After purchase, go to **hPanel → Domains → DNS / Nameservers**
4. You will add DNS records here in Step 9 — keep this tab handy

> Hostinger's DNS is free and included. No need to move nameservers anywhere else.

---

## Step 2 — Set Up GCP Project

```bash
# Install gcloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Login and create project
gcloud auth login
gcloud projects create glassnote-prod --name="GlassNote Production"
gcloud config set project glassnote-prod

# Link billing account (required to activate your $300 credits)
gcloud billing accounts list
gcloud billing projects link glassnote-prod --billing-account=YOUR_BILLING_ACCOUNT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com
```

---

## Step 3 — Create Cloud SQL (PostgreSQL)

Use the **smallest possible instance** — `db-f1-micro` is sufficient for early-stage traffic.

```bash
# Create PostgreSQL 15 instance
gcloud sql instances create glassnote-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-size=10GB \
  --storage-type=SSD \
  --no-backup \
  --authorized-networks=0.0.0.0/0

# Create database and user
gcloud sql databases create glassnote --instance=glassnote-db
gcloud sql users create glassnote \
  --instance=glassnote-db \
  --password=STRONG_PASSWORD_HERE

# Note the connection name for later
gcloud sql instances describe glassnote-db --format="value(connectionName)"
# Example output: glassnote-prod:us-central1:glassnote-db
```

> **Cost tip:** `--no-backup` saves ~$1.50/mo. Enable backups once you have real users.

---

## Step 4 — Build and Push Backend Docker Image

```bash
# Create Artifact Registry repository
gcloud artifacts repositories create glassnote-backend \
  --repository-format=docker \
  --location=us-central1 \
  --description="GlassNote backend images"

# Configure Docker auth
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push from backend/ directory
cd backend
docker build -t us-central1-docker.pkg.dev/glassnote-prod/glassnote-backend/api:latest .
docker push us-central1-docker.pkg.dev/glassnote-prod/glassnote-backend/api:latest
```

---

## Step 5 — Store Secrets in Secret Manager

Never put secrets directly in Cloud Run env var config (they are visible in the GCP console). Use Secret Manager instead:

```bash
# Database URL uses Cloud SQL Unix socket path (no public IP needed)
echo -n "postgresql+asyncpg://glassnote:STRONG_PASSWORD_HERE@/glassnote?host=/cloudsql/glassnote-prod:us-central1:glassnote-db" \
  | gcloud secrets create DATABASE_URL --data-file=-

echo -n "$(openssl rand -hex 32)" \
  | gcloud secrets create JWT_SECRET --data-file=-

echo -n "YOUR_ANTHROPIC_KEY"       | gcloud secrets create ANTHROPIC_API_KEY --data-file=-
echo -n "YOUR_OPENAI_KEY"          | gcloud secrets create OPENAI_API_KEY --data-file=-
echo -n "YOUR_DEEPGRAM_KEY"        | gcloud secrets create DEEPGRAM_API_KEY --data-file=-
echo -n "YOUR_CEREBRAS_KEY"        | gcloud secrets create CEREBRAS_API_KEY --data-file=-
echo -n "YOUR_STRIPE_SECRET"       | gcloud secrets create STRIPE_SECRET_KEY --data-file=-
echo -n "YOUR_STRIPE_WEBHOOK_SEC"  | gcloud secrets create STRIPE_WEBHOOK_SECRET --data-file=-
echo -n "YOUR_SENDGRID_KEY"        | gcloud secrets create SENDGRID_API_KEY --data-file=-
echo -n "YOUR_GOOGLE_CLIENT_ID"    | gcloud secrets create GOOGLE_CLIENT_ID --data-file=-
echo -n "YOUR_GOOGLE_CLIENT_SEC"   | gcloud secrets create GOOGLE_CLIENT_SECRET --data-file=-
echo -n "https://glassnote.com,https://www.glassnote.com" \
  | gcloud secrets create CORS_ORIGINS --data-file=-
```

---

## Step 6 — Deploy Backend to Cloud Run

```bash
# Create a dedicated service account for Cloud Run
gcloud iam service-accounts create glassnote-run \
  --display-name="GlassNote Cloud Run SA"

# Grant access to read secrets
gcloud projects add-iam-policy-binding glassnote-prod \
  --member="serviceAccount:glassnote-run@glassnote-prod.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Grant Cloud SQL client access
gcloud projects add-iam-policy-binding glassnote-prod \
  --member="serviceAccount:glassnote-run@glassnote-prod.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

# Deploy
gcloud run deploy glassnote-api \
  --image=us-central1-docker.pkg.dev/glassnote-prod/glassnote-backend/api:latest \
  --region=us-central1 \
  --platform=managed \
  --allow-unauthenticated \
  --service-account=glassnote-run@glassnote-prod.iam.gserviceaccount.com \
  --add-cloudsql-instances=glassnote-prod:us-central1:glassnote-db \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,JWT_SECRET=JWT_SECRET:latest,ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,DEEPGRAM_API_KEY=DEEPGRAM_API_KEY:latest,CEREBRAS_API_KEY=CEREBRAS_API_KEY:latest,STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:latest,STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:latest,SENDGRID_API_KEY=SENDGRID_API_KEY:latest,GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest,GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest,CORS_ORIGINS=CORS_ORIGINS:latest \
  --set-env-vars=FROM_EMAIL=noreply@glassnote.com,REPLY_EMAIL=support@glassnote.com \
  --min-instances=0 \
  --max-instances=10 \
  --memory=512Mi \
  --cpu=1 \
  --concurrency=80 \
  --timeout=300
```

> **Cost tip:** `--min-instances=0` scales to zero when idle — you pay $0 during quiet periods. Cold start is ~1–2 seconds for this Python image.

---

## Step 7 — Run Alembic Migrations

Run as a one-off Cloud Run Job (charged only for execution time, essentially free):

```bash
# Create migration job
gcloud run jobs create glassnote-migrate \
  --image=us-central1-docker.pkg.dev/glassnote-prod/glassnote-backend/api:latest \
  --region=us-central1 \
  --service-account=glassnote-run@glassnote-prod.iam.gserviceaccount.com \
  --add-cloudsql-instances=glassnote-prod:us-central1:glassnote-db \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest \
  --command="python" \
  --args="run_migrations.py"

# Run it
gcloud run jobs execute glassnote-migrate --region=us-central1 --wait
```

---

## Step 8 — Deploy Frontend to Vercel (Free)

1. Push your repo to GitHub (if not already)
2. Go to [vercel.com](https://vercel.com) → **Add New Project** → Import your repo
3. Set **Root Directory** to `website`
4. Framework preset: **Next.js** (auto-detected)
5. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL = https://api.glassnote.com
   ```
6. Click **Deploy** — Vercel provisions SSL and global CDN automatically

---

## Step 9 — Configure DNS in Hostinger hPanel

After deploying you will have:
- Cloud Run URL: `https://glassnote-api-XXXX-uc.a.run.app`
- Vercel URL: `https://glassnote-XXXX.vercel.app`

### In Hostinger hPanel → Domains → DNS Records:

| Type | Name | Value | Notes |
|---|---|---|---|
| `A` | `@` | `76.76.21.21` | Vercel's IP for root domain |
| `CNAME` | `www` | `cname.vercel-dns.com` | Vercel www redirect |
| `CNAME` | `api` | `glassnote-api-XXXX-uc.a.run.app` | Cloud Run backend |

> The `api` CNAME points directly to Cloud Run — SSL is handled by Cloud Run's managed certificate.

### Map custom domain to Cloud Run:

```bash
gcloud run domain-mappings create \
  --service=glassnote-api \
  --domain=api.glassnote.com \
  --region=us-central1
```

GCP will show you a CNAME record to add — use the value it gives you for the `api` record above.

### Map custom domain in Vercel:
- Vercel Dashboard → Project → **Settings → Domains**
- Add `glassnote.com` and `www.glassnote.com`
- Vercel will confirm once DNS propagates (usually 5–30 minutes)

---

## Step 10 — Configure Stripe Webhook

1. Go to [Stripe Dashboard → Developers → Webhooks](https://dashboard.stripe.com/webhooks)
2. Click **Add endpoint**
3. URL: `https://api.glassnote.com/api/billing/webhook`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Copy the **Signing Secret** → update `STRIPE_WEBHOOK_SECRET` in Secret Manager:
   ```bash
   echo -n "whsec_XXXX" | gcloud secrets versions add STRIPE_WEBHOOK_SECRET --data-file=-
   ```

---

## Step 11 — Verify End-to-End

```bash
# Backend health
curl https://api.glassnote.com/health
# Expected: {"status": "ok"}

# API docs
open https://api.glassnote.com/docs

# Frontend
open https://glassnote.com
```

Manual checklist:
- [ ] `GET /health` returns `{"status":"ok"}`
- [ ] User registration and email verification works
- [ ] Google OAuth login works
- [ ] Stripe checkout completes and plan updates in DB
- [ ] LLM proxy streams responses (test from GUI desktop app)
- [ ] Session start/end records correctly in DB

---

## Optional: CI/CD with GitHub Actions

Auto-deploy backend on every push to `main`:

```yaml
# .github/workflows/deploy-backend.yml
name: Deploy Backend
on:
  push:
    branches: [main]
    paths: [backend/**]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v2
      - run: |
          gcloud auth configure-docker us-central1-docker.pkg.dev
          docker build -t us-central1-docker.pkg.dev/glassnote-prod/glassnote-backend/api:$GITHUB_SHA backend/
          docker push us-central1-docker.pkg.dev/glassnote-prod/glassnote-backend/api:$GITHUB_SHA
          gcloud run deploy glassnote-api \
            --image=us-central1-docker.pkg.dev/glassnote-prod/glassnote-backend/api:$GITHUB_SHA \
            --region=us-central1
```

Vercel auto-deploys the frontend on every push — no extra config needed.

---

## Summary: Why This Stack

| Decision | Reason |
|---|---|
| **Cloud Run** for backend | Serverless, scales to zero, no idle cost, handles SSE streaming natively, Docker-native |
| **Cloud SQL db-f1-micro** | Cheapest managed Postgres, ~$7/mo, persistent, no ops overhead |
| **Vercel Hobby** for frontend | Free forever for Next.js, global CDN, auto SSL, zero config |
| **Hostinger** for domain | $9/yr, includes DNS management, no extra cost |
| **Secret Manager** for secrets | Secure, auditable, secrets never exposed in GCP console UI |
| **$300 GCP credits** | Covers ~15–30 months of Cloud Run + Cloud SQL at this scale |
