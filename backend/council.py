"""3-stage LLM Council orchestration."""

import asyncio
import json
import re
from typing import List, Dict, Any, Tuple, AsyncGenerator
from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL, RESEARCH_MODEL


async def _decompose_query(user_query: str) -> Dict[str, Any]:
    """
    Use Sonar to decompose a user query into 2-3 focused sub-queries.

    Returns:
        Dict with 'needs_research' (bool) and 'sub_queries' (list of strings)
    """
    decompose_prompt = f"""You are a research planning assistant. Given a user question, determine if it references specific products, tools, platforms, companies, frameworks, or niche topics that would benefit from web research.

If the question only involves well-known, general knowledge topics (e.g., Python, Excel, basic business concepts), respond with:
{{"needs_research": false}}

If research would help, break the question into 2-3 focused web search sub-queries, each targeting a DIFFERENT aspect:
- Sub-query 1: What the product/tool/platform IS (factual overview)
- Sub-query 2: Practical use cases, workflows, tutorials, community examples
- Sub-query 3: Context-specific info relevant to the question (e.g., industry-specific, regional)

Rules:
- Maximum 3 sub-queries
- Each sub-query should be concise (under 20 words)
- Each should target a genuinely different angle

Respond in JSON format ONLY, no other text:
{{"needs_research": true, "sub_queries": ["query1", "query2", "query3"]}}

User question: {user_query}"""

    messages = [{"role": "user", "content": decompose_prompt}]
    response = await query_model(RESEARCH_MODEL, messages, timeout=20.0)

    if response is None:
        return {"needs_research": True, "sub_queries": [user_query]}

    content = response.get('content', '').strip()

    # Try to parse JSON from the response
    try:
        # Find JSON in the response (may be wrapped in markdown code blocks)
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            if not parsed.get('needs_research', True):
                return {"needs_research": False, "sub_queries": []}
            sub_queries = parsed.get('sub_queries', [user_query])
            # Cap at 3 sub-queries
            return {"needs_research": True, "sub_queries": sub_queries[:3]}
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: if parsing fails, just research the original query
    return {"needs_research": True, "sub_queries": [user_query]}


async def _research_sub_query(sub_query: str, label: str) -> Dict[str, Any]:
    """
    Research a single sub-query with an enhanced, deep prompt.

    Returns:
        Dict with 'label', 'query', 'response' (or None on failure)
    """
    research_prompt = f"""You are a web research assistant. Search the web and provide thorough, practical information about the following topic.

Research topic: {sub_query}

Provide comprehensive findings including:
- What it is (official description, key features, purpose)
- Practical use cases and real-world examples
- Getting started guides, tutorials, or community resources
- Pricing, licensing, or availability info if applicable
- Notable alternatives or competitors
- Any relevant regional context (especially Singapore/Asia if applicable)

Be factual and cite specific details. If you cannot find information, say so clearly rather than guessing."""

    messages = [{"role": "user", "content": research_prompt}]
    response = await query_model(RESEARCH_MODEL, messages, timeout=30.0)

    if response is None:
        return {"label": label, "query": sub_query, "response": None}

    content = response.get('content', '')
    return {"label": label, "query": sub_query, "response": content if content.strip() else None}


async def stage0_research(user_query: str) -> Dict[str, Any]:
    """
    Enhanced Stage 0: Decompose → Parallel Research → Synthesize.

    1. Decomposes the query into 2-3 focused sub-queries
    2. Researches each sub-query in parallel using Sonar
    3. Concatenates results with clear section headers

    Returns:
        Dict with 'model', 'response', 'has_research', 'sub_queries', 'sub_results'
    """
    # Phase A: Decompose query
    decomposition = await _decompose_query(user_query)

    if not decomposition.get('needs_research', True):
        return {
            "model": RESEARCH_MODEL,
            "response": None,
            "has_research": False,
            "sub_queries": [],
            "sub_results": []
        }

    sub_queries = decomposition['sub_queries']

    # Phase B: Parallel research on all sub-queries
    tasks = [
        _research_sub_query(sq, f"Research {i+1}")
        for i, sq in enumerate(sub_queries)
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out failures
    sub_results = []
    for result in raw_results:
        if isinstance(result, Exception) or result is None:
            continue
        if isinstance(result, dict) and result.get('response'):
            sub_results.append(result)

    if not sub_results:
        return {
            "model": RESEARCH_MODEL,
            "response": None,
            "has_research": False,
            "sub_queries": sub_queries,
            "sub_results": []
        }

    # Phase C: Synthesize — concatenate with section headers
    if len(sub_results) == 1:
        merged = sub_results[0]['response']
    else:
        sections = []
        for sub in sub_results:
            sections.append(f"### {sub['query']}\n\n{sub['response']}")
        merged = "\n\n---\n\n".join(sections)

    return {
        "model": RESEARCH_MODEL,
        "response": merged,
        "has_research": True,
        "sub_queries": sub_queries,
        "sub_results": sub_results
    }


async def stage0_research_stream(user_query: str) -> AsyncGenerator[Tuple[str, Dict], None]:
    """
    Enhanced Stage 0 as an async generator for SSE streaming.
    Yields (event_type, data) tuples for granular progress updates.
    """
    # Phase A: Decompose
    yield ('stage0_decomposing', {})
    decomposition = await _decompose_query(user_query)

    if not decomposition.get('needs_research', True):
        result = {
            "model": RESEARCH_MODEL,
            "response": None,
            "has_research": False,
            "sub_queries": [],
            "sub_results": []
        }
        yield ('stage0_complete', result)
        return

    sub_queries = decomposition['sub_queries']
    yield ('stage0_sub_queries', {"sub_queries": sub_queries})

    # Phase B: Parallel research
    yield ('stage0_researching', {"sub_queries": sub_queries})
    tasks = [
        _research_sub_query(sq, f"Research {i+1}")
        for i, sq in enumerate(sub_queries)
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    sub_results = []
    for i, result in enumerate(raw_results):
        if isinstance(result, Exception) or result is None:
            continue
        if isinstance(result, dict) and result.get('response'):
            sub_results.append(result)
            yield ('stage0_sub_result', {"index": i, "result": result})

    if not sub_results:
        result = {
            "model": RESEARCH_MODEL,
            "response": None,
            "has_research": False,
            "sub_queries": sub_queries,
            "sub_results": []
        }
        yield ('stage0_complete', result)
        return

    # Phase C: Synthesize
    yield ('stage0_synthesizing', {})
    if len(sub_results) == 1:
        merged = sub_results[0]['response']
    else:
        sections = []
        for sub in sub_results:
            sections.append(f"### {sub['query']}\n\n{sub['response']}")
        merged = "\n\n---\n\n".join(sections)

    result = {
        "model": RESEARCH_MODEL,
        "response": merged,
        "has_research": True,
        "sub_queries": sub_queries,
        "sub_results": sub_results
    }
    yield ('stage0_complete', result)


async def stage1_collect_responses(user_query: str, research_context: str = None) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = []
    if research_context:
        messages.append({
            "role": "system",
            "content": f"Background research has been conducted on the topics in the user's query. Use this context to provide an accurate, informed response:\n\n{research_context}"
        })
    messages.append({"role": "user", "content": user_query})

    # Query all models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to model name
    label_to_model = {
        f"Response {label}": result['model']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all council models in parallel
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Format results
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use research model for title generation (Sonar is fast and cheap)
    response = await query_model(RESEARCH_MODEL, messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(user_query: str) -> Tuple[Dict, List, List, Dict, Dict]:
    """
    Run the complete council process (Stage 0 research + 3 deliberation stages).

    Args:
        user_query: The user's question

    Returns:
        Tuple of (stage0_result, stage1_results, stage2_results, stage3_result, metadata)
    """
    # Stage 0: Pre-research with web-search model
    stage0_result = await stage0_research(user_query)
    research_context = stage0_result.get('response')

    # Stage 1: Collect individual responses (with research context if available)
    stage1_results = await stage1_collect_responses(user_query, research_context)

    # If no models responded successfully, return error
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    return stage0_result, stage1_results, stage2_results, stage3_result, metadata
