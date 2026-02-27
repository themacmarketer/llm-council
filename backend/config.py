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
    "x-ai/grok-4",
    "google/gemini-3-pro-preview",
    "deepseek/deepseek-r1",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "claude-opus-4-5"

# Research model - web-search-capable model for Stage 0 pre-research
RESEARCH_MODEL = "perplexity/sonar"

# API endpoint (Straico OpenAI-compatible)
OPENROUTER_API_URL = "https://api.straico.com/v0/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
