# GlassNote - API Keys Setup Guide

Complete guide to obtaining and configuring API keys for GlassNote.

---

## 📋 Overview

GlassNote integrates with multiple external services. Here's what you need:

| Service | Required? | Purpose | Cost |
|---------|-----------|---------|------|
| **Anthropic** | ✅ Yes | Claude LLM for problem solving | Pay-per-use |
| **OpenAI** | ⚠️ Recommended | Whisper STT, GPT models | Pay-per-use |
| **Deepgram** | ❌ Optional | Alternative STT provider | Pay-per-use |
| **Stripe** | ❌ Optional | Payment processing | Transaction fees |
| **SendGrid** | ❌ Optional | Email notifications | Free tier available |
| **Google OAuth** | ❌ Optional | Social login | Free |

---

## 🔑 Required API Keys

### 1. Anthropic API Key (Required)

**Purpose:** Powers Claude models for interview assistance

**Get your key:**

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to "API Keys"
4. Click "Create Key"
5. Copy the key (starts with `sk-ant-`)

**Pricing:**
- Claude Sonnet: ~$3 per million input tokens, ~$15 per million output tokens
- Claude Opus: ~$15 per million input tokens, ~$75 per million output tokens

**Configure:**

Backend (`backend/.env`):
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

GUI (via Settings or `GUI/config.json`):
```json
{
  "api_keys": {
    "anthropic": "sk-ant-your-key-here"
  }
}
```

---

## 🎤 Speech-to-Text (STT) Keys

### 2. OpenAI API Key (Recommended)

**Purpose:** Whisper STT for audio interview mode, GPT models

**Get your key:**

1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Click "Create new secret key"
4. Name it (e.g., "GlassNote Dev")
5. Copy the key (starts with `sk-`)

**Pricing:**
- Whisper: $0.006 per minute of audio
- GPT-4: ~$10-30 per million tokens (varies by model)

**Configure:**

Backend (`backend/.env`):
```env
OPENAI_API_KEY=sk-your-key-here
```

GUI (via Settings or `GUI/config.json`):
```json
{
  "api_keys": {
    "openai": "sk-your-key-here"
  }
}
```

### 3. Deepgram API Key (Optional Alternative)

**Purpose:** Alternative STT provider with better real-time performance

**Get your key:**

1. Go to https://console.deepgram.com/
2. Sign up or log in
3. Navigate to "API Keys"
4. Create a new key
5. Copy the key

**Pricing:**
- Pay-as-you-go: $0.0043 per minute
- Free tier: $200 credit

**Configure:**

Backend (`backend/.env`):
```env
DEEPGRAM_API_KEY=your-deepgram-key-here
```

---

## 💳 Billing & Payments (Optional)

### 4. Stripe API Keys

**Purpose:** Process payments for subscriptions and PAYG sessions

**Get your keys:**

1. Go to https://dashboard.stripe.com/register
2. Complete account setup
3. Navigate to "Developers" → "API keys"
4. Copy both:
   - **Publishable key** (starts with `pk_test_`)
   - **Secret key** (starts with `sk_test_`)

**For webhooks:**

1. Go to "Developers" → "Webhooks"
2. Click "Add endpoint"
3. URL: `https://your-domain.com/api/billing/webhook`
4. Select events: `checkout.session.completed`, `customer.subscription.updated`, etc.
5. Copy the **Signing secret** (starts with `whsec_`)

**Configure:**

Backend (`backend/.env`):
```env
STRIPE_SECRET_KEY=sk_test_your-key-here
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret-here
```

**Pricing:**
- 2.9% + $0.30 per successful card charge
- No monthly fees

---

## 📧 Email Notifications (Optional)

### 5. SendGrid API Key

**Purpose:** Send email verification codes and notifications

**Get your key:**

1. Go to https://signup.sendgrid.com/
2. Complete account setup
3. Navigate to "Settings" → "API Keys"
4. Click "Create API Key"
5. Choose "Full Access" or "Restricted Access" (with Mail Send permission)
6. Copy the key (starts with `SG.`)

**Configure sender email:**

1. Go to "Settings" → "Sender Authentication"
2. Verify your domain or single sender email
3. Use verified email in configuration

**Configure:**

Backend (`backend/.env`):
```env
SENDGRID_API_KEY=SG.your-key-here
FROM_EMAIL=noreply@yourdomain.com
REPLY_EMAIL=support@yourdomain.com
```

**Pricing:**
- Free tier: 100 emails/day
- Essentials: $19.95/month for 50,000 emails

---

## 🔐 Google OAuth (Optional)

### 6. Google OAuth Credentials

**Purpose:** Enable "Sign in with Google" functionality

**Get your credentials:**

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing
3. Navigate to "APIs & Services" → "Credentials"
4. Click "Create Credentials" → "OAuth client ID"
5. Choose "Web application"
6. Add authorized redirect URIs:
   - `http://localhost:8000/api/auth/google/callback` (dev)
   - `https://your-domain.com/api/auth/google/callback` (prod)
7. Copy:
   - **Client ID** (ends with `.apps.googleusercontent.com`)
   - **Client Secret**

**Configure:**

Backend (`backend/.env`):
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

**Pricing:** Free

---

## 🔒 Security Best Practices

### Development vs Production

**Development:**
- Use test/sandbox keys when available
- Store keys in `.env` file (never commit!)
- Use `DEBUG=true` for verbose logging

**Production:**
- Use production API keys
- Store keys in environment variables or secrets manager
- Use `DEBUG=false`
- Rotate keys regularly
- Monitor usage and set billing alerts

### Key Storage

**❌ Never do this:**
```python
# DON'T hardcode keys in source code
api_key = "sk-ant-1234567890"
```

**✅ Always do this:**
```python
# DO use environment variables
import os
api_key = os.getenv("ANTHROPIC_API_KEY")
```

### .gitignore Protection

The project `.gitignore` already excludes:
```
.env
.env.*
!.env.example
backend/.env
```

Always verify before committing:
```bash
git status
# Ensure .env files are not listed
```

---

## 🧪 Testing Your Keys

### Test Anthropic Key

```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "Hi"}]
  }'
```

### Test OpenAI Key

```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Test via GlassNote Backend

```bash
# Start backend
cd backend
uvicorn app.main:app --reload

# Check health endpoint
curl http://localhost:8000/health

# Check API docs
# Open: http://localhost:8000/docs
```

---

## 💰 Cost Estimation

### Typical Interview Session

**Scenario:** 45-minute coding interview with 3 problems

| Service | Usage | Cost |
|---------|-------|------|
| Claude Sonnet | ~50K input + 20K output tokens | ~$0.45 |
| Whisper STT | 10 minutes of audio | ~$0.06 |
| **Total** | | **~$0.51** |

### Monthly Development Costs

**Light usage** (5 sessions/month):
- ~$2.50/month

**Heavy usage** (20 sessions/month):
- ~$10/month

**Note:** Actual costs vary based on:
- Model selection (Opus costs more than Sonnet)
- Problem complexity (more tokens)
- Audio usage (STT costs)

---

## 🆘 Troubleshooting

### "Invalid API key" Error

**Cause:** Key is incorrect, expired, or not properly configured

**Solution:**
1. Verify key is copied correctly (no extra spaces)
2. Check key hasn't been revoked in provider dashboard
3. Ensure environment variable is loaded:
   ```bash
   # In backend terminal
   echo $ANTHROPIC_API_KEY
   ```
4. Restart the backend server after changing `.env`

### "Rate limit exceeded"

**Cause:** Too many requests to API provider

**Solution:**
1. Check your usage in provider dashboard
2. Upgrade to higher tier if needed
3. Implement request throttling
4. Wait for rate limit to reset (usually 1 minute)

### "Insufficient credits"

**Cause:** API account has no credits/payment method

**Solution:**
1. Add payment method in provider dashboard
2. Purchase credits if using prepaid model
3. Check billing settings

### Keys Not Loading

**Cause:** Environment file not found or not loaded

**Solution:**
```bash
# Verify .env file exists
cd backend
dir .env

# Check file contents (be careful not to expose keys!)
type .env

# Restart server to reload environment
# Press Ctrl+C, then restart
uvicorn app.main:app --reload
```

---

## 📚 Additional Resources

### API Documentation

- **Anthropic:** https://docs.anthropic.com/
- **OpenAI:** https://platform.openai.com/docs/
- **Deepgram:** https://developers.deepgram.com/
- **Stripe:** https://stripe.com/docs/api
- **SendGrid:** https://docs.sendgrid.com/

### Pricing Calculators

- **Anthropic:** https://www.anthropic.com/pricing
- **OpenAI:** https://openai.com/pricing
- **Deepgram:** https://deepgram.com/pricing

---

## ✅ Configuration Checklist

Before running GlassNote, ensure:

- [ ] Anthropic API key configured in backend `.env`
- [ ] Anthropic API key configured in GUI settings
- [ ] OpenAI API key configured (if using audio mode)
- [ ] JWT secret generated and set in backend `.env`
- [ ] Database URL configured correctly
- [ ] Optional services configured as needed
- [ ] All keys tested and working
- [ ] `.env` file not committed to git

---

**Ready to start?** Go back to [QUICK_START.md](QUICK_START.md) to continue setup!
