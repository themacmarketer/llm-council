# CLAUDE.md - Technical Notes for LLM Council

This file contains technical details, architectural decisions, and important implementation notes for future development sessions.

## Project Overview

LLM Council is a 4-stage deliberation system where multiple LLMs collaboratively answer user questions. Stage 0 performs web research for factual grounding, followed by individual responses, anonymized peer review (preventing models from playing favorites), and chairman synthesis.

## Architecture

### Backend Structure (`backend/`)

**`config.py`**
- Contains `COUNCIL_MODELS` (list of OpenRouter model identifiers)
- Contains `CHAIRMAN_MODEL` (model that synthesizes final answer)
- Contains `RESEARCH_MODEL` (Perplexity Sonar via Straico for Stage 0)
- Contains `STRAICO_API_BASE` and `STRAICO_API_KEY` for Stage 0 web research
- Uses environment variables `OPENROUTER_API_KEY` and `STRAICO_API_KEY` from `.env`
- Backend runs on **port 8001** (NOT 8000 - user had another app on 8000)

**`openrouter.py`**
- `query_model()`: Single async model query (supports both OpenRouter and Straico endpoints)
- `query_models_parallel()`: Parallel queries using `asyncio.gather()`
- Returns dict with 'content' and optional 'reasoning_details'
- Graceful degradation: returns None on failure, continues with successful responses

**`council.py`** - The Core Logic

*Stage 0 (Pre-research):*
- `_decompose_query(user_query)`: Asks Sonar to break query into 2-3 focused sub-queries (factual, practical, contextual). Returns `{needs_research, sub_queries}`. Timeout: 20s. Falls back to original query on parse failure.
- `_research_sub_query(sub_query, label)`: Researches one sub-query with enhanced prompt (use cases, tutorials, pricing, alternatives, community resources). Timeout: 30s.
- `stage0_research(user_query)`: Orchestrates decompose → parallel gather → concatenate. Returns `{model, response, has_research, sub_queries, sub_results}`.
- `stage0_research_stream(user_query)`: Async generator yielding `(event_type, data)` tuples for granular SSE progress events.

*Stages 1-3 (Deliberation):*
- `stage1_collect_responses(user_query, research_context)`: Parallel queries to all council models, with optional Stage 0 context
- `stage2_collect_rankings()`:
  - Anonymizes responses as "Response A, B, C, etc."
  - Creates `label_to_model` mapping for de-anonymization
  - Prompts models to evaluate and rank (with strict format requirements)
  - Returns tuple: (rankings_list, label_to_model_dict)
  - Each ranking includes both raw text and `parsed_ranking` list
- `stage3_synthesize_final()`: Chairman synthesizes from all responses + rankings
- `parse_ranking_from_text()`: Extracts "FINAL RANKING:" section, handles both numbered lists and plain format
- `calculate_aggregate_rankings()`: Computes average rank position across all peer evaluations

*Utilities:*
- `generate_conversation_title(user_query)`: Uses `RESEARCH_MODEL` to generate 3-5 word title on first message
- `run_full_council(user_query)`: Orchestrates all stages, returns `(stage0, stage1, stage2, stage3, metadata)`

**`storage.py`**
- JSON-based conversation storage in `data/conversations/`
- Each conversation: `{id, created_at, title, messages[]}`
- Assistant messages contain: `{role, stage0, stage1, stage2, stage3}`
- Note: metadata (label_to_model, aggregate_rankings) is NOT persisted to storage, only returned via API
- Key functions:
  - `create_conversation()`, `get_conversation()`, `save_conversation()`, `list_conversations()`
  - `add_user_message()`, `add_assistant_message()`
  - `update_conversation_title()`: Updates title field
  - `delete_conversation()`: Removes conversation JSON file from disk

**`main.py`**
- FastAPI app with CORS enabled for localhost:5173 and localhost:3000
- API endpoints:
  - `GET /api/conversations` — List all conversations (metadata only)
  - `POST /api/conversations` — Create new conversation
  - `GET /api/conversations/{id}` — Get conversation with messages
  - `DELETE /api/conversations/{id}` — Delete a conversation
  - `PATCH /api/conversations/{id}` — Rename a conversation (UpdateConversationRequest with `title` field)
  - `POST /api/conversations/{id}/message` — Send message (non-streaming)
  - `POST /api/conversations/{id}/message/stream` — Send message with SSE streaming
- SSE streaming events: `stage0_start`, `stage0_decomposing`, `stage0_sub_queries`, `stage0_researching`, `stage0_sub_result`, `stage0_synthesizing`, `stage0_complete`, `stage1_start/complete`, `stage2_start/complete`, `stage3_start/complete`, `title_complete`, `complete`, `error`

### Frontend Structure (`frontend/src/`)

**`api.js`**
- Base URL: `http://localhost:8001`
- Methods: `listConversations()`, `createConversation()`, `getConversation()`, `sendMessage()`, `sendMessageStream()`, `deleteConversation()`, `renameConversation()`

**`App.jsx`**
- Main orchestration: manages conversations list and current conversation
- Handles message sending with progressive SSE streaming updates
- Stage 0 streaming: tracks `stage0Phase` and `stage0SubQueries` in loading state
- `handleDeleteConversation(id)`: Calls API, filters from state, clears view if active
- `handleRenameConversation(id, newTitle)`: Calls API, updates state optimistically
- Important: metadata is stored in the UI state for display but not persisted to backend JSON

**`components/Sidebar.jsx`**
- Conversation list with hover-reveal action buttons (✏️ rename, 🗑️ delete)
- Inline title editing: click pencil → input field → Enter/blur saves, Escape cancels
- Delete: click trash → browser confirm → API call
- Local state: `editingId`, `editTitle` for rename mode

**`components/ChatInterface.jsx`**
- Multiline textarea (3 rows, resizable)
- Enter to send, Shift+Enter for new line
- Phase-specific loading display for Stage 0: "Analyzing query..." → "Researching N topics" (with sub-query chips) → "Compiling research findings..."
- User messages wrapped in markdown-content class for padding

**`components/Stage0.jsx`**
- Shows synthesized research result with CopyButton
- Collapsible "Show individual research (N queries)" toggle reveals sub-results
- Each sub-result shows query label and has its own CopyButton

**`components/Stage1.jsx`**
- Tab view of individual model responses with CopyButton per tab
- ReactMarkdown rendering with markdown-content wrapper

**`components/Stage2.jsx`**
- **Critical Feature**: Tab view showing RAW evaluation text from each model
- De-anonymization happens CLIENT-SIDE for display (models receive anonymous labels)
- Shows "Extracted Ranking" below each evaluation so users can validate parsing
- Aggregate rankings shown with average position and vote count
- CopyButton on each tab

**`components/Stage3.jsx`**
- Final synthesized answer from chairman with CopyButton
- Green-tinted background (#f0fff0) to highlight conclusion

**`components/CopyButton.jsx`**
- Shared component used across all stages
- Copies markdown content to clipboard via `navigator.clipboard.writeText()`
- Visual feedback: copy icon → green checkmark with "Copied!" for 2 seconds

**Styling (`*.css`)**
- Light mode theme (not dark mode)
- Primary color: #4a90e2 (blue)
- Global markdown styling in `index.css` with `.markdown-content` class
- 12px padding on all markdown content to prevent cluttered appearance
- Sidebar: 260px fixed width, hover-reveal action buttons, inline rename input

## Key Design Decisions

### Stage 0 Multi-Query Research
- Query decomposition uses Sonar itself (not a separate utility model) to avoid Straico model availability issues
- Sub-queries run in parallel via `asyncio.gather()` — no added latency vs single query
- Results concatenated with markdown headers (no separate LLM synthesis call needed)
- Graceful degradation: decomposition fails → single query; some sub-queries fail → use successful ones

### Stage 2 Prompt Format
The Stage 2 prompt is very specific to ensure parseable output:
```
1. Evaluate each response individually first
2. Provide "FINAL RANKING:" header
3. Numbered list format: "1. Response C", "2. Response A", etc.
4. No additional text after ranking section
```

This strict format allows reliable parsing while still getting thoughtful evaluations.

### De-anonymization Strategy
- Models receive: "Response A", "Response B", etc.
- Backend creates mapping: `{"Response A": "openai/gpt-5.1", ...}`
- Frontend displays model names in **bold** for readability
- Users see explanation that original evaluation used anonymous labels
- This prevents bias while maintaining transparency

### Error Handling Philosophy
- Continue with successful responses if some models fail (graceful degradation)
- Never fail the entire request due to single model failure
- Log errors but don't expose to user unless all models fail

### UI/UX Transparency
- All raw outputs are inspectable via tabs
- Parsed rankings shown below raw text for validation
- Users can verify system's interpretation of model outputs
- Copy buttons on every output for easy markdown export
- This builds trust and allows debugging of edge cases

## Important Implementation Details

### Relative Imports
All backend modules use relative imports (e.g., `from .config import ...`) not absolute imports. This is critical for Python's module system to work correctly when running as `python -m backend.main`.

### Port Configuration
- Backend: 8001 (changed from 8000 to avoid conflict)
- Frontend: 5173 (Vite default)
- Update both `backend/main.py` and `frontend/src/api.js` if changing

### Markdown Rendering
All ReactMarkdown components must be wrapped in `<div className="markdown-content">` for proper spacing. This class is defined globally in `index.css`.

### Model Configuration
- Council models and chairman are hardcoded in `backend/config.py`
- Research model (`RESEARCH_MODEL`): `perplexity/sonar` via Straico API
- Chairman can be same or different from council members
- Title generation uses `RESEARCH_MODEL` (not a separate model)

### Async Generator Pattern (Stage 0 Streaming)
`stage0_research_stream()` is an async generator that yields `(event_type, data)` tuples. `main.py` iterates over it with `async for` in the SSE event generator. This pattern allows granular progress updates without callbacks.

## Common Gotchas

1. **Module Import Errors**: Always run backend as `python -m backend.main` from project root, not from backend directory
2. **CORS Issues**: Frontend must match allowed origins in `main.py` CORS middleware
3. **Ranking Parse Failures**: If models don't follow format, fallback regex extracts any "Response X" patterns in order
4. **Missing Metadata**: Metadata is ephemeral (not persisted), only available in API responses
5. **Straico Model Availability**: Some models (e.g., `google/gemini-2.5-flash`) return 422 on Straico. Use `RESEARCH_MODEL` for utility tasks.
6. **Worktree Development**: Changes developed on `claude/laughing-galileo` branch in `.claude/worktrees/laughing-galileo/`, merged to master via fast-forward

## Future Enhancement Ideas

- Configurable council/chairman via UI instead of config file
- Export conversations to markdown/PDF
- Model performance analytics over time
- Custom ranking criteria (not just accuracy/insight)
- Support for reasoning models (o1, etc.) with special handling
- Conversation search/filter in sidebar

## Testing Notes

Use `test_openrouter.py` to verify API connectivity and test different model identifiers before adding to council. The script tests both streaming and non-streaming modes.

## Data Flow Summary

```
User Query
    ↓
Stage 0: Decompose query → Parallel sub-query research → Synthesize context
    ↓
Stage 1: Parallel queries (with research context) → [individual responses]
    ↓
Stage 2: Anonymize → Parallel ranking queries → [evaluations + parsed rankings]
    ↓
Aggregate Rankings Calculation → [sorted by avg position]
    ↓
Stage 3: Chairman synthesis with full context
    ↓
Return: {stage0, stage1, stage2, stage3, metadata}
    ↓
Frontend: Display with tabs + validation UI + copy buttons
```

The entire flow is async/parallel where possible to minimize latency.
