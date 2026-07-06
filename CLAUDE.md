# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AetherFrame is a lightweight personal image processing tool for anime-style content. It provides three main modules: Material Processing (素材加工), Art Creation (美图创作), and Image Repair (图片修补). The app calls external AI APIs (Gemini via yibuapi.com) for LLM inference and image generation. Image beautify (图片美化) is documented in `claude_docs/feature_beautify/`.

## Development Commands

### Frontend (page/)

```bash
cd page
npm install
npm run dev          # Dev server on port 3000, proxies /api to localhost:8000
npm run build        # Outputs to ../app/static/
npm run lint         # ESLint
npm run type-check   # TypeScript check (tsconfig.app.json)
```

### Backend

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker compose up -d --build
```

### Tests

```bash
pytest
```

## Architecture

### Backend (app/)

- **Framework**: FastAPI with SQLAlchemy ORM, SQLite database (WAL mode) stored at `data/db/aetherframe.db`
- **Entry point**: `app/main.py` — registers routers, runs lifespan init (directory setup, DB migrations, prompt template seeding)
- **Route modules**: `app/routes/` — `repair.py`, `material.py`, `creation.py`, `api.py`, `pages.py`
- **Service layer**: `app/services/` — business logic organized by module (repair_service/, material_service/, creation_service/)
- **Repository layer**: `app/repositories/` — generic `BaseRepository[T]` with CRUD; module-specific repos extend it
- **Schemas**: `app/schemas/` — Pydantic models for request/response validation
- **Models**: `app/models/` — SQLAlchemy models; `database.py` contains engine setup and lightweight migrations (no Alembic — uses ALTER TABLE checks)
- **LLM tools**: `app/tools/llm/` — `yibu_llm_infer.py` (Gemini text inference), `nano_banana_pro.py` (Gemini image generation). Config in `config.py` (gitignored)
- **Prompts**: `app/prompts/` — prompt templates for creation and material modules
- **Background tasks**: Long-running image generation and LLM calls use FastAPI `BackgroundTasks`. A dedicated `BackgroundSessionLocal` (NullPool) avoids exhausting the main connection pool.

### Frontend (page/)

- **Stack**: React 19 + TypeScript + Vite + Tailwind CSS + react-router-dom v7
- **Auto-imports**: `unplugin-auto-import` provides React hooks, router hooks, and i18n hooks as globals (no manual imports needed). ESLint config declares matching globals.
- **Pages**: `page/src/pages/` — `home/`, `material/`, `repair/`, `creation/` (each has `page.tsx` + `components/`)
- **Services**: `page/src/services/` — API client modules (`api.ts` is the base HTTP wrapper for `/api/repair`; `materialApi.ts`, `creationApi.ts` for other modules)
- **i18n**: react-i18next with browser language detection, English default
- **Build output**: Production build goes to `app/static/` and is served by FastAPI's StaticFiles mount. Dev mode uses Vite proxy to backend.
- **Path alias**: `@` maps to `page/src/`

### Data Directory (data/)

All user data lives under `data/` (gitignored, mounted as volume in Docker):
- `db/` — SQLite database
- `repair/tasks/`, `repair/templates/` — repair module files
- `material/characters/` — character assets
- `beautify/` — creation module (prompt_precreation/, quick_create/ with history)
- `temp/` — auto-cleaned on startup (>24h files)

## Key Patterns

- **DB migrations**: Done inline in `app/models/database.py` via `migrate_*` functions that check column existence before ALTER TABLE. No migration framework.
- **API convention**: All API responses wrap in `ApiResponse(success, data, message)`. Routes are prefixed `/api/repair`, `/api/material`, `/api/creation`.
- **Polling**: Frontend polls task status endpoints; backend suppresses these from uvicorn access logs via `_SuppressPollAccessLog` filter.
- **LLM config**: `app/tools/llm/config.py` holds API keys and is gitignored. Must be created locally.
- **Image generation timeout**: Both frontend and backend have timeout utilities for long-running image generation tasks.
