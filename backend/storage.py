"""Conversation storage: Upstash Redis (Vercel) or local JSON files (dev)."""

import json
import os
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from .config import DATA_DIR

# Upstash Redis REST API — set when KV_REST_API_URL env var is present
_KV_URL = os.getenv("KV_REST_API_URL")
_KV_TOKEN = os.getenv("KV_REST_API_TOKEN")
USE_REDIS = bool(_KV_URL and _KV_TOKEN)

_CONV_LIST_KEY = "llm_council:conversations"


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

def _redis(*args):
    """Execute a Redis command via Upstash REST API (POST / with JSON array body)."""
    resp = httpx.post(
        _KV_URL,
        headers={"Authorization": f"Bearer {_KV_TOKEN}"},
        json=list(args),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("result")


def _conv_key(conversation_id: str) -> str:
    return f"llm_council:conv:{conversation_id}"


# ---------------------------------------------------------------------------
# File helpers (local dev)
# ---------------------------------------------------------------------------

def _ensure_data_dir():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def _conv_path(conversation_id: str) -> str:
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


# ---------------------------------------------------------------------------
# Public API — same interface as before
# ---------------------------------------------------------------------------

def create_conversation(conversation_id: str) -> Dict[str, Any]:
    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "messages": [],
    }
    if USE_REDIS:
        _redis("SET", _conv_key(conversation_id), json.dumps(conversation))
        _redis("SADD", _CONV_LIST_KEY, conversation_id)
    else:
        _ensure_data_dir()
        with open(_conv_path(conversation_id), "w") as f:
            json.dump(conversation, f, indent=2)
    return conversation


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    if USE_REDIS:
        raw = _redis("GET", _conv_key(conversation_id))
        return json.loads(raw) if raw else None
    path = _conv_path(conversation_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_conversation(conversation: Dict[str, Any]):
    if USE_REDIS:
        _redis("SET", _conv_key(conversation["id"]), json.dumps(conversation))
    else:
        _ensure_data_dir()
        with open(_conv_path(conversation["id"]), "w") as f:
            json.dump(conversation, f, indent=2)


def list_conversations() -> List[Dict[str, Any]]:
    if USE_REDIS:
        ids = _redis("SMEMBERS", _CONV_LIST_KEY) or []
        conversations = []
        for cid in ids:
            conv = get_conversation(cid)
            if conv:
                conversations.append({
                    "id": conv["id"],
                    "created_at": conv["created_at"],
                    "title": conv.get("title", "New Conversation"),
                    "message_count": len(conv["messages"]),
                })
        conversations.sort(key=lambda x: x["created_at"], reverse=True)
        return conversations
    # local file fallback
    _ensure_data_dir()
    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            with open(os.path.join(DATA_DIR, filename)) as f:
                data = json.load(f)
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "message_count": len(data["messages"]),
                })
    conversations.sort(key=lambda x: x["created_at"], reverse=True)
    return conversations


def add_user_message(conversation_id: str, content: str):
    conv = get_conversation(conversation_id)
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    conv["messages"].append({"role": "user", "content": content})
    save_conversation(conv)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    stage0: Dict[str, Any] = None,
):
    conv = get_conversation(conversation_id)
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    message = {"role": "assistant", "stage1": stage1, "stage2": stage2, "stage3": stage3}
    if stage0 is not None:
        message["stage0"] = stage0
    conv["messages"].append(message)
    save_conversation(conv)


def update_conversation_title(conversation_id: str, title: str):
    conv = get_conversation(conversation_id)
    if conv is None:
        raise ValueError(f"Conversation {conversation_id} not found")
    conv["title"] = title
    save_conversation(conv)


def delete_conversation(conversation_id: str) -> bool:
    if USE_REDIS:
        deleted = _redis("DEL", _conv_key(conversation_id))
        _redis("SREM", _CONV_LIST_KEY, conversation_id)
        if not deleted:
            raise ValueError(f"Conversation {conversation_id} not found")
        return True
    path = _conv_path(conversation_id)
    if not os.path.exists(path):
        raise ValueError(f"Conversation {conversation_id} not found")
    os.remove(path)
    return True
