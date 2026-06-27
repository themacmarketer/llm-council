# CLAUDE.md — LLM Council

## What This Is

A 4-stage deliberation system where multiple LLMs collaboratively answer questions. Stage 0 does web research, Stage 1 collects parallel responses, Stage 2 does anonymized peer review + ranking, Stage 3 is chairman synthesis.

## Commands

```bash
# Backend (FastAPI on port 8001)
cd backend && python -m backend.main

# Frontend (Vite on port 5173)
cd frontend && npm run dev

# Test API connectivity
python test_openrouter.py
```

## Architecture

```
backend/
├── config.py       # Model config (council, chairman, research)
├── openrouter.py   # Async model queries (OpenRouter + Straico)
├── council.py      # Core 4-stage deliberation logic
├── storage.py      # JSON conversation storage (data/conversations/)
└── main.py         # FastAPI app with SSE streaming

frontend/src/
├── api.js          # API client (localhost:8001)
├── App.jsx         # Main orchestration + SSE streaming
├── components/
│   ├── Sidebar.jsx       # Conversation list + rename/delete
│   ├── ChatInterface.jsx # Message input + stage loading
│   ├── Stage0-3.jsx      # Stage-specific display components
│   └── CopyButton.jsx    # Shared clipboard component
```

## Key Patterns

- All backend modules use **relative imports** (`from .config import ...`). Run as `python -m backend.main` from project root.
- Metadata (label_to_model, aggregate_rankings) is **ephemeral** — returned via API but not persisted to JSON.
- De-anonymization happens **client-side** only (models receive "Response A, B, C").
- All ReactMarkdown must be wrapped in `<div className="markdown-content">`.
- Async generator pattern: `stage0_research_stream()` yields `(event_type, data)` tuples for SSE.

## Common Gotchas

1. **Module imports**: Always run from project root as `python -m backend.main`, not from backend/
2. **CORS**: Frontend must match allowed origins in `main.py`
3. **Ranking parse failures**: Fallback regex extracts "Response X" patterns if strict format fails
4. **Straico model availability**: Some models return 422. Use `RESEARCH_MODEL` for utility tasks.
5. **Port conflict**: Backend is 8001 (not 8000). Update both `main.py` and `api.js` if changing.

## Environment

Requires `.env` with: `OPENROUTER_API_KEY`, `STRAICO_API_KEY`

## Detailed Architecture

@.claude/rules/architecture.md
