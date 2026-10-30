# GlassNote AI <img width="40" height="40" alt="image" src="https://github.com/sshivasai/GlassNoteAI/blob/main/logo.jpg" />


<div align="center">
  

  www.glassnoteai.com


  
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)

Real-time transcription and contextual AI assistance for desktop workflows.

GlassNote combines a Python desktop application with speech-to-text and language-model integrations. It is intended for permitted meeting assistance, personal note-taking, and reviewing on-screen information.

[Website](https://glassnoteai.com) · [Setup](SETUP.md) · [Issues](https://github.com/sshivasai/GlassNoteAI/issues)

## Capabilities

- Capture supported audio sources and send audio to a configured transcription provider.
- Stream responses from supported language-model providers.
- Use screen context to inform responses when screen capture is enabled.
- Display assistance through a PyQt6 desktop interface.
- Configure provider credentials and application preferences.

Features and provider availability depend on the installed version and configuration. AI-generated transcripts and responses can contain errors; review outputs before relying on them.

## Architecture

| Component | Technology | Responsibility |
| --- | --- | --- |
| Desktop client | Python, PyQt6 | Audio capture, interface, screen context, session controls |
| Backend | FastAPI, PostgreSQL, SQLAlchemy | Application APIs and account workflows |
| Website | Next.js, React, Tailwind CSS | Web interface and application access |
| External providers | Configured STT and LLM APIs | Transcription and response generation |

See the source and configuration for the routing used by your deployment. Local execution of the client does not mean all processing remains on your device.

## Setup

The existing project setup documentation specifies Python 3.11+, Node.js 18+, PostgreSQL 15+, and Windows 10/11 for the desktop client. Consult [SETUP.md](SETUP.md) and package manifests for version-specific requirements.

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Configure your database and provider credentials.
alembic upgrade head
uvicorn app.main:app --reload
```

### Website

```bash
cd website
npm install
npm run dev
```

### Desktop client

```bash
cd GUI
pip install -r requirements.txt
python main.py
```

Keep credentials out of source control. Use development credentials when evaluating the application.

## Data handling

Depending on enabled features and configuration, audio, transcript text, prompts, or screen-derived context may be transmitted to external providers for processing. Bring-your-own-key configuration does not by itself guarantee local processing, zero retention, or end-to-end privacy.

Review your provider's policies and inspect your deployment's routing, logging, session storage, and deletion behavior before using sensitive information. This project does not claim certified compliance or suitability for regulated data.

## Responsible use

Use audio and screen capture only when you have the necessary permission and when the activity is allowed by your organization or meeting rules. Do not use the application to bypass assessment rules or conceal prohibited assistance.

An overlay's visibility during screen sharing depends on the operating system, capture method, and application. Do not rely on capture exclusion to protect confidential information.

## Performance

Latency varies with provider, model, network, hardware, prompt length, and service load. This README does not assert a universal latency guarantee.

Reproducible performance reports should include:
- Commit, OS, hardware, provider, model, and region.
- Input size, concurrency, request count, and warm/cold conditions.
- Separate audio-capture delay, transcription delay, time to first token, and full-response latency.
- Median and P95 latency, failure rate, measurement script, and raw results.

## Limitations

Transcription quality varies with noise, accents, and overlapping speech. Generated answers may be inaccurate. Third-party services can impose costs, rate limits, or outages. Cross-platform behavior and capture compatibility require separate testing.

## Contributing

Open an issue with reproduction steps, application version, and redacted logs. Never include API keys, private transcripts, or confidential screenshots.

See the repository license file for licensing terms.

## Repository guide

| Path | Purpose |
| --- | --- |
| `GUI/` | Windows desktop application and audio/interface workflows |
| `GUI/main.py` | Documented desktop entry point |
| `GUI/settings/config.py` | Settings referenced by the setup guide |
| `backend/` | FastAPI application and database integration |
| `website/` | Next.js web application |
| `SETUP.md` | Component installation instructions |

The setup steps below follow the repository's existing setup guide. They are development instructions, not evidence of a tested production deployment.

## Detailed local installation

### 1. Get the source

```bash
git clone https://github.com/sshivasai/GlassNoteAI.git
cd GlassNoteAI
```

Use separate terminals for the backend, website, and desktop client. Run each component from its own directory. Use the Python requirements and JavaScript package manifests in your checkout as the authoritative dependency definitions.

### 2. Prepare the backend

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the environment:

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create a dedicated PostgreSQL database and account with permissions to apply the application's migrations. Use a development database for your first run. Configure its connection string in the backend environment.

Copy the supplied environment template:

macOS or Linux:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Generate a random application secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Generate independent values for separate secret settings. Do not reuse the example placeholders.

### Backend configuration reference

These names are documented in the existing setup guide. Check the configuration loader in your checkout for required fields, defaults, and accepted formats.

| Variable | Purpose | Configuration guidance |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection | Use the documented asyncpg URL format with a dedicated database account |
| `SECRET_KEY` | Application secret | Generate a random value and keep it private |
| `JWT_SECRET_KEY` | Token-signing secret | Generate separately; avoid shared development credentials |
| `JWT_ALGORITHM` | Token-signing algorithm | Match the backend's supported configuration |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime | Set according to your session requirements |
| `ENVIRONMENT` | Runtime environment | Use development settings for local evaluation |
| `CORS_ORIGINS` | Browser origins allowed by the API | Match the web application's exact origin and loader format |
| `FRONTEND_URL` | Web application address | Use your local website URL during development |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in integration | Configure only when enabling that integration |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Billing integration | Start with test credentials |
| `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL` | Transactional email | Configure for email-dependent workflows |

Example database URL shape:

```dotenv
DATABASE_URL=postgresql+asyncpg://glassnote_user:REPLACE_WITH_PASSWORD@localhost:5432/glassnote
ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
```

This example is not a complete environment file. Use the repository template and supply all fields required by your version. Encode reserved characters in URL credentials correctly.

Apply migrations and start the development server:

```bash
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [local API documentation](http://127.0.0.1:8000/docs). Binding to loopback keeps this development server accessible on the local machine. A development server with reload enabled is not a production deployment.

### 3. Prepare the website

In a new terminal, from the repository root:

```bash
cd website
npm install
```

When the repository includes a compatible lockfile, use `npm ci` for a reproducible installation.

Create `website/.env.local` using the variables documented in the setup guide:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_ENV=development
```

Optional integrations may also use `NEXT_PUBLIC_GOOGLE_CLIENT_ID` and `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY`.

Variables prefixed with `NEXT_PUBLIC_` are intended for browser exposure. Never place provider API secrets, private Stripe keys, database passwords, or token-signing secrets in them.

Start the website:

```bash
npm run dev
```

Open [the local website](http://localhost:3000). Restart the development process after environment changes. Ensure the backend allows the exact origin used in your browser; `localhost` and `127.0.0.1` are different hostnames.

### 4. Prepare the desktop client

In another terminal on Windows, from the repository root:

```powershell
cd GUI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

The existing setup guide describes a tray-based startup flow. If the main window does not appear, check the system tray and the launching terminal for errors.

Use application settings to configure the backend address and the providers you intend to use. Do not add real credentials to tracked configuration files.

### Desktop settings reference

| Setting | Meaning |
| --- | --- |
| `glassnote_api_url` | Backend address used by the client |
| `hotkey_trigger` | Shortcut for triggering the configured action |
| `theme` | Interface appearance |
| `byok_mode` | Selects the documented bring-your-own-key mode |
| `api_keys.anthropic` | Anthropic credentials when using that integration |
| `api_keys.openai` | OpenAI credentials when using that integration |
| `api_keys.deepgram` | Deepgram credentials when using that integration |

The settings table documents names, not a promise that credentials are stored securely. Inspect the installed version's credential persistence before adding sensitive keys.

## First session walkthrough

1. Start the services required by your chosen configuration.
2. Select an available transcription provider and a supported response model.
3. Configure credentials for those providers; you do not need every provider to evaluate a single workflow.
4. Select the intended audio input.
5. Test with non-sensitive audio and confirm the transcript reflects that source.
6. Trigger a response and confirm that it streams into the desktop interface.
7. If using screen context, test on a non-sensitive window and inspect what context is included.
8. Stop the session and confirm capture has ended.
9. Review any local session files and provider usage associated with your test.

Do not assume session export, recording, or retention behavior from the presence of a UI control. Check what your installed version actually writes and sends.

## Audio routing

Microphone input and system-playback capture are different sources. Select the source that matches your intended workflow.

The existing Windows setup guide describes Stereo Mix and virtual audio routing. Availability varies by sound hardware and drivers. Enable or configure a supported recording source, then select it in the application where supported. Avoid changing the system-wide default device unless necessary.

The guide documents this diagnostic command from `GUI/`:

```bash
python audio/stereo_mix_checker.py
```

If that script is absent in your checkout, use the application's available device selection and Windows sound settings to inspect the input.

When debugging, first test the microphone independently, then test system audio. Prevent feedback loops by ensuring that generated playback is not repeatedly routed into the transcription input.

## Provider modes and costs

### Bring your own keys

BYOK uses credentials supplied by the user. Provider charges, quotas, model access, and rate limits still apply. BYOK is not a guarantee of unlimited usage, offline processing, or zero data retention.

Confirm the request route for each integration. Different providers or features may use different paths through the application.

### Backend-managed integrations

The repository documents backend account, billing, proxy, and usage-tracking components. Their presence in source does not establish availability of a hosted subscription service. Check the actual deployed offering before relying on managed access or a pricing plan.

No fixed provider prices are reproduced here because they can change. Estimate costs using your provider's current pricing, selected models, audio duration, token usage, and retry volume.

## Data lifecycle review

The following table identifies data that can be involved in each workflow. It is a review guide, not a claim that every listed storage destination is used.

| Data | Why it may be processed | What to verify |
| --- | --- | --- |
| Audio | Speech recognition | Destination, buffering, recording, provider retention |
| Transcript text | Context for AI responses | Prompt inclusion, session storage, logging, deletion |
| Screen images or extracted text | Contextual assistance | Capture trigger, selected region, destination, persistence |
| Prompts and responses | Language-model inference | Routing, provider policies, local history |
| Account information | Authentication and account management | Database fields, access restrictions, removal |
| Usage metadata | Quotas, analytics, or billing | Fields collected and retention period |
| API keys and tokens | Provider and service authentication | Storage mechanism, access control, rotation |

Self-hosting the backend gives you control over that backend's operation. It does not automatically keep requests to external transcription or language-model providers local.

## Performance measurement guide

Measure each stage separately so the results describe the user experience accurately.

| Metric | Start | End |
| --- | --- | --- |
| Transcription finalization delay | End of the spoken segment | Final transcript received |
| Time to first token | Model request submitted | First response token received |
| Full response latency | Model request submitted | Final response token received |
| UI display delay | Response data received by client | Corresponding content displayed |
| End-to-end response delay | Defined user trigger or end of speech | First useful response displayed |

Document the exact timing boundaries used. For a benchmark, include request count, median, P95, errors, timeouts, model identifier, prompt sizes, concurrency, network location, hardware, application commit, and warm versus cold conditions. Include failed requests instead of silently excluding them.

Do not present one provider's best-case first-token measurement as total speech-to-answer latency.

## Troubleshooting reference

| Symptom | Checks |
| --- | --- |
| Database connection fails | Confirm PostgreSQL is running, credentials are valid, host and port match, and the database exists |
| Migration fails | Inspect the first error, current migration revision, and database permissions; back up data before changing schema |
| Website cannot reach API | Verify the backend URL, service availability, browser network errors, and exact CORS origin |
| Authentication fails | Check environment secrets, callback configuration where applicable, and token expiration |
| Provider rejects requests | Check key validity, account balance, model access, request limits, and the returned error |
| No transcript appears | Verify selected audio source, input levels, capture permissions, and transcription credentials |
| Transcript repeats or echoes | Inspect virtual routing and whether speaker playback feeds the selected input |
| Response is slow | Separate transcription, provider inference, network, and UI delays before changing settings |
| Desktop window appears missing | Check tray state, monitor placement, opacity settings, and startup errors |
| Python import fails | Verify the active environment and install requirements with that environment's Python |
| Website build fails | Inspect the first build error and dependency versions; distinguish configuration errors from code errors |

Do not reset the database as a routine migration fix. Do not assume administrator privileges are required to resolve a desktop display issue.

When reporting a problem, include the component, commit or version, OS, reproduction steps, expected behavior, actual behavior, and redacted error output.

## Deployment considerations

Local development and production operation have different requirements. Before exposing the application beyond your machine:

- Configure HTTPS and verify authentication and authorization on sensitive routes.
- Restrict allowed origins and keep the database on a private network.
- Separate development and production credentials.
- Define session, transcript, screenshot, and log retention.
- Apply migrations through a controlled process with tested backups.
- Set resource limits, timeouts, and provider spending limits.
- Monitor request failures without logging sensitive content unnecessarily.
- Verify OAuth redirects and billing webhook handling if those integrations are enabled.

The setup guide contains Docker examples. Validate them against the current repository and your deployment environment before use. Containerizing the backend does not provide Windows desktop capture functionality.

## Development and validation

Use a dedicated branch and keep changes focused. Follow the test and build commands present in the relevant component's configuration; this README does not claim an existing passing test suite or coverage percentage.

For changes involving audio or model integrations, validate:
- Startup and shutdown.
- Provider errors, rate limits, and network interruption.
- Empty audio, long pauses, and overlapping speech.
- Session cancellation during a streaming response.
- Handling of missing credentials.
- Whether logs expose private content.
- Compatibility with the documented operating system.

For website changes, the setup guide documents:

```bash
npm run build
```

A successful frontend build does not validate backend authorization, audio correctness, or provider behavior.

## FAQ

**Does GlassNote run entirely offline?**  
The documented workflow uses external transcription and language-model APIs. Do not assume offline support.

**Do I need accounts with every provider?**  
Configure credentials for the integrations you choose. Additional requirements depend on your version and selected mode.

**Does BYOK prevent providers from receiving my data?**  
No. The selected provider must receive the inputs required for the requested processing.

**Is the desktop client supported on macOS or Linux?**  
The current setup guide specifies Windows for the GUI. Backend or website portability does not establish desktop capture support on other platforms.

**Is the overlay guaranteed to stay out of recordings?**  
No universal guarantee is made. Test the exact operating system, capture application, and sharing mode, and avoid relying on this behavior for confidentiality.

**Can I use it with sensitive business or clinical information?**  
Only after your organization has evaluated the actual deployment, provider arrangements, permissions, and data handling. This README does not establish compliance.

**Are performance numbers guaranteed?**  
No. Publish reproducible measurements for the configuration being evaluated.

## Support and licensing

Report reproducible issues at [GitHub Issues](https://github.com/sshivasai/GlassNoteAI/issu
