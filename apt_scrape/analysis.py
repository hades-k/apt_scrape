"""apt_scrape.analysis — LangGraph agent for per-listing AI scoring.

Scores each listing dict against a plain-text preferences file using a
single-node LangGraph StateGraph backed by OpenRouter. The graph is
designed with a single node now but structured for future extension
(e.g. retry-on-low-confidence, web-lookup nodes).

Required env vars:
    OPENROUTER_API_KEY  — OpenRouter API key
    OPENROUTER_MODEL    — OpenRouter model slug (default: google/gemini-3.1-flash-lite-preview)
    ANALYSIS_CONCURRENCY — max parallel LLM calls (default: 5)
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import TypedDict

import click
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Structured output model
# ---------------------------------------------------------------------------


class AnalysisResult(BaseModel):
    score: int      # 0–100
    verdict: str    # e.g. "Strong match", "Skip", "Potential"
    reason: str     # 1–2 sentence explanation


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------


class AnalysisState(TypedDict):
    listing: dict
    preferences: str
    result: AnalysisResult | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def score_to_stars(score: int) -> str:
    """Map a 0–100 integer score to a star-emoji string."""
    if score < 20:
        return "⭐"
    if score < 40:
        return "⭐⭐"
    if score < 60:
        return "⭐⭐⭐"
    if score < 80:
        return "⭐⭐⭐⭐"
    return "⭐⭐⭐⭐⭐"


def load_preferences(path: str | None = None) -> str:
    """Load preferences from *path* (or PREFERENCES_FILE env var, or preferences.txt).

    Raises:
        FileNotFoundError: if the resolved path does not exist.
    """
    resolved = path or os.environ.get("PREFERENCES_FILE") or "preferences.txt"
    p = Path(resolved)
    if not p.exists():
        raise FileNotFoundError(f"Preferences file not found: {resolved}")
    return p.read_text(encoding="utf-8").strip()


def _format_listing_context(listing: dict) -> str:
    """Format key listing fields into a structured prompt context string."""
    detail = listing.get("detail") or {}
    title = detail.get("title") or listing.get("title", "")
    size = detail.get("size") or listing.get("sqm", "")
    floor = detail.get("floor", "")
    price = listing.get("price", "")
    rooms = listing.get("rooms", "")
    address = listing.get("detail_address") or listing.get("address", "")
    description = listing.get("detail_description", "")
    features = listing.get("detail_features") or {}
    costs = listing.get("detail_costs") or {}
    energy = listing.get("detail_energy_class", "")

    features_str = "\n".join(f"  {k}: {v}" for k, v in features.items()) if features else "  (none)"
    costs_str = "\n".join(f"  {k}: {v}" for k, v in costs.items()) if costs else "  (none)"

    return f"""Apartment: {title}
Price: {price}
Size: {size}
Rooms: {rooms}
Floor: {floor}
Address: {address}
Energy class: {energy}

Description:
{description}

Features:
{features_str}

Costs:
{costs_str}"""


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------


def _make_llm() -> ChatOpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("OPENROUTER_MODEL", "google/gemini-3.1-flash-lite-preview")
    return ChatOpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        model=model,
    )


# Module-level LLM instance (created lazily on first use via _get_llm())
_llm_instance: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    """Return a shared LLM instance, creating it on first call."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = _make_llm()
    return _llm_instance


async def _analyse_node(state: AnalysisState) -> AnalysisState:
    """Single graph node: score a listing against preferences."""
    llm = _get_llm()
    structured_llm = llm.with_structured_output(AnalysisResult)

    system_prompt = (
        "You are an apartment-hunting assistant. "
        "Given a user's preferences and an apartment listing, score the listing "
        "from 0 (terrible fit) to 100 (perfect fit) and give a short verdict and reason.\n\n"
        f"USER PREFERENCES:\n{state['preferences']}"
    )
    human_prompt = f"LISTING:\n{_format_listing_context(state['listing'])}"

    try:
        result: AnalysisResult = await structured_llm.ainvoke(
            [{"role": "system", "content": system_prompt},
             {"role": "user", "content": human_prompt}]
        )
    except Exception:
        # Fallback: ask for raw JSON block
        fallback_prompt = (
            system_prompt
            + "\n\nRespond ONLY with a JSON object: "
              '{"score": <int 0-100>, "verdict": "<short label>", "reason": "<1-2 sentences>"}'
        )
        try:
            raw_response = await _get_llm().ainvoke(
                [{"role": "system", "content": fallback_prompt},
                 {"role": "user", "content": human_prompt}]
            )
            text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
            start = text.find("{")
            end = text.rfind("}") + 1
            data = json.loads(text[start:end])
            result = AnalysisResult(**data)
        except Exception as e2:
            result = AnalysisResult(score=0, verdict="Error", reason=str(e2))

    return {**state, "result": result}


# ---------------------------------------------------------------------------
# Compiled graph (cached singleton)
# ---------------------------------------------------------------------------

_graph_instance = None


def _get_graph():
    global _graph_instance
    if _graph_instance is None:
        builder = StateGraph(AnalysisState)
        builder.add_node("analyse_listing", _analyse_node)
        builder.add_edge(START, "analyse_listing")
        builder.add_edge("analyse_listing", END)
        _graph_instance = builder.compile()
    return _graph_instance


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def analyse_listings(listings: list[dict], preferences: str) -> None:
    """Score each listing in-place against *preferences*.

    Adds ai_score, ai_stars, ai_verdict, ai_reason to each listing dict.
    Runs with bounded concurrency (ANALYSIS_CONCURRENCY env var, default 5).
    """
    concurrency = int(os.environ.get("ANALYSIS_CONCURRENCY", "5"))
    semaphore = asyncio.Semaphore(concurrency)
    graph = _get_graph()

    async def _score_one(listing: dict) -> None:
        async with semaphore:
            try:
                output = await graph.ainvoke(
                    {"listing": listing, "preferences": preferences, "result": None}
                )
                result: AnalysisResult = output["result"]
            except Exception as e:
                result = AnalysisResult(score=0, verdict="Error", reason=str(e))

            listing["ai_score"] = result.score
            listing["ai_stars"] = score_to_stars(result.score)
            listing["ai_verdict"] = result.verdict
            listing["ai_reason"] = result.reason

    total = len(listings)
    click.echo(f"Analysing {total} listings with AI...", err=True)
    await asyncio.gather(*(_score_one(l) for l in listings))
    click.echo(f"Analysis complete.", err=True)
