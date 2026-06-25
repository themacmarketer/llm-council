"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Straico API key
STRAICO_API_KEY = os.getenv("STRAICO_API_KEY")
OPENROUTER_API_KEY = STRAICO_API_KEY

# Council members - list of model identifiers
COUNCIL_MODELS = [
    "openai/gpt-5.2",
    "anthropic/claude-sonnet-4.5",
    "moonshotai/kimi-k2-thinking",
    "google/gemini-3.1-pro-preview",
    "deepseek/deepseek-r1",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "claude-opus-4-5"

# Research model - web-search-capable model for Stage 0 pre-research
RESEARCH_MODEL = "perplexity/sonar3"

# API endpoint (Straico OpenAI-compatible)
OPENROUTER_API_URL = "https://api.straico.com/v0/chat/completions"

# Data directory for conversation storage — /tmp is the only writable path on Vercel
DATA_DIR = "/tmp/conversations" if os.getenv("VERCEL") else "data/conversations"
