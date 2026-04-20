# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install all dependencies (backend venv + frontend npm)
make install

# Initialize database + seed baseline stats
make data

# Start both services (backend + frontend)
./start.sh

# Manual start
cd backend && source venv/bin/activate && uvicorn app.main:app --port 8001 --reload
cd frontend && npm run dev

# Production: build frontend then serve everything from backend on one port
cd frontend && npm run build
cd backend && source venv/bin/activate && uvicorn app.main:app --port 8001

# Run backend tests
make test
# or: cd backend && source venv/bin/activate && python -m pytest tests/ -v

# Frontend type check + build
cd frontend && npx tsc --noEmit && npx vite build

# Full CI
make ci
```

## Architecture

Insta-Advisor is an AI-powered Instagram post diagnosis platform targeting Korean content creators, small business owners, and freelance SNS managers. Users submit a post (text/screenshot/images/video), and 4 AI agents analyze it through a multi-round debate.

### Multi-Agent Flow (backend/app/agents/orchestrator.py)

```
Input → TextAnalyzer + ImageAnalyzer
     → BaselineComparator (SQLite, 8 Instagram categories)
     → Model A pre-score (deterministic, no LLM)
     → Round 1: 4 agents diagnose in parallel (asyncio.gather)
        ContentAgent | VisualAgent | GrowthAgent | UserSimAgent
     → Round 2: Each agent debates others' opinions
     → Round 3: JudgeAgent synthesizes final report
     → Response assembly (stable_scores + LLM opinions merged)
```

### Model Tiers (configured in backend/.env)

Three models via OpenAI-compatible API (Claude, GPT-4o, Gemini, or MiMo):
- `LLM_MODEL_PRO` (default: gpt-4o) — used for agent diagnosis, debate, judging
- `LLM_MODEL_OMNI` (default: gpt-4o) — multimodal, used for image/video analysis
- `LLM_MODEL_FAST` (default: gpt-4o-mini) — used for quick tasks (debate round, comments)

`base_agent.py` handles provider detection and gateway quirks:
- `LLM_PROVIDER=openai|anthropic|gemini` selects the provider
- `OPENAI_COMPAT=mimo` forces MiMo gateway quirks (max_completion_tokens, etc.)
- Rate limit retry with backoff via `LLM_RATE_LIMIT_RETRIES`

### Instagram Categories (8개)

| Key | 한국어 | Description |
|-----|--------|-------------|
| `food` | 맛집/카페 | Food, cafes, recipes |
| `fashion` | 패션/뷰티 | OOTD, makeup, nails |
| `fitness` | 운동/건강 | Fitness, yoga, diet |
| `business` | 사업/마케팅 | Small biz, sellers, brands |
| `lifestyle` | 일상/육아 | Daily vlog, parenting |
| `travel` | 여행 | Domestic/overseas travel |
| `education` | 정보/교육 | Study tips, finance, how-tos |
| `shop` | 쇼핑/리뷰 | Product reviews, hauls |

### Content Formats

- `single_image` — single image post
- `carousel` — carousel (2–20 slides)
- `reels` — short-form video

### Frontend-Backend Connection

- **Dev mode**: Vite proxy forwards `/api/*` to backend:8001 (configured in `frontend/vite.config.ts`)
- **Production**: FastAPI serves the built SPA via `SPAMiddleware` — all non-`/api` routes fall through to `index.html`
- Both modes use the same `/api` prefix

### Database

SQLite at `backend/data/baseline.db`.
- **Baseline data**: stats per category (engagement rates, optimal caption length, tag counts, format ER). Used by `BaselineComparator`.
- **Diagnosis history**: `diagnosis_history` table (auto-created on startup).
- **Usage log**: `usage_log` table for token tracking and analytics.

### Key API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/diagnose` | Main diagnosis (multipart form, non-streaming) |
| POST | `/api/diagnose-stream` | SSE streaming diagnosis with real-time progress |
| POST | `/api/pre-score` | Instant Model A pre-score (no LLM, <50ms) |
| POST | `/api/generate-comments` | Generate more simulated comments |
| GET | `/api/baseline/{category}` | Category baseline stats |
| POST | `/api/screenshot` | Screenshot OCR parse |
| GET | `/api/health` | Health check with DB status |

### Frontend Stack

React 19 + TypeScript + MUI v9 + Vite. Framer Motion for page transitions. ECharts for radar chart. html2canvas for export card.

Pages: Home (input) → Diagnosing (SSE progress) → Report (score, radar, dimension bars, baseline comparison, agent debate, simulated comments, export card).

Theme: Instagram gradient (`#feda75 → #d62976 → #4f5bd5`). Font: Pretendard / Noto Sans KR.

## Configuration

Copy `.env.example` to `backend/.env`. Key vars:
- `OPENAI_API_KEY` — API key (also used as fallback for Anthropic/Gemini)
- `ANTHROPIC_API_KEY` — Anthropic-specific key (when `LLM_PROVIDER=anthropic`)
- `GEMINI_API_KEY` — Google AI Studio key (when `LLM_PROVIDER=gemini`)
- `OPENAI_BASE_URL` — Gateway URL (leave empty for official OpenAI)
- `LLM_PROVIDER` — `openai` (default) | `anthropic` | `gemini`
- `LLM_MODEL_FAST` / `LLM_MODEL_PRO` / `LLM_MODEL_OMNI` — model names per tier
- `ALLOWED_ORIGINS` — comma-separated CORS origins for production (default: localhost only)
- `LLM_FREE_TIER_MODE` — `1` to skip debate round (reduces API calls for free-tier quotas)
