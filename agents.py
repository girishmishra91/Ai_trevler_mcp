"""
agents.py — LangGraph multi-agent travel planner using create_agent + @tool
All 12 travel agents built with the functional paradigm.
"""

import logging
import uuid
import json
import httpx
import chromadb
from typing import Optional
from sentence_transformers import SentenceTransformer

from langchain.tools import tool
from langchain_groq import ChatGroq
from langchain.agents import create_agent         # canonical import (LangChain >=0.3)
from langchain_core.messages import HumanMessage, SystemMessage


from config import Config
from utils import clean_json_response, format_currency
from mcp_client import BrowserMCP, DDGSSearchClient
from tracking import track_flight, get_train_tracker_info

logger = logging.getLogger(__name__)


# =========================================================================== #
# Groq LLM factory                                                             #
# =========================================================================== #

def _make_llm():
    return ChatGroq(
        api_key=Config.GROQ_API_KEY,
        model_name=Config.MODEL_NAME,
        temperature=Config.TEMPERATURE,
    )


# =========================================================================== #
# ChromaDB singleton for RAG                                                   #
# =========================================================================== #

_chroma_client = None
_chroma_collection = None
_embedder = None


def _get_rag_store():
    global _chroma_client, _chroma_collection, _embedder
    if _chroma_client is None:
        try:
            _chroma_client = chromadb.PersistentClient(path=Config.CHROMA_PERSIST_DIR)
        except AttributeError:
            from chromadb.config import Settings
            _chroma_client = chromadb.Client(
                Settings(persist_directory=Config.CHROMA_PERSIST_DIR, anonymized_telemetry=False)
            )
        try:
            _chroma_collection = _chroma_client.get_collection("travel_knowledge")
        except Exception:
            _chroma_collection = _chroma_client.create_collection("travel_knowledge")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _chroma_collection, _embedder


# =========================================================================== #
# @tool definitions                                                            #
# =========================================================================== #

@tool
def search_web(query: str) -> str:
    """Search the web for travel information using Browser MCP (or DuckDuckGo fallback).
    Use for destination guides, flight info, hotel listings, and travel tips."""
    # Try Browser MCP first, fall back to DDGS
    try:
        browser = BrowserMCP()
        browser.connect()
        result = browser.search(query)
        browser.disconnect()
        if result and not result.get("error"):
            return json.dumps(result)
    except Exception as e:
        logger.warning("Browser MCP search failed for query=%r: %s", query, e)

    # DDGS fallback
    try:
        client = DDGSSearchClient()
        results = client.search(query, max_results=5)
        if isinstance(results, list) and results:
            return json.dumps({"results": results})
    except Exception as e:
        logger.warning("DDGS fallback search failed for query=%r: %s", query, e)

    return f"Search temporarily unavailable. Use your own knowledge about '{query}'."


@tool
def fetch_weather(destination: str) -> str:
    """Fetch real-time weather data for a destination from OpenWeatherMap.
    Returns current conditions and 5-day forecast in JSON format."""
    api_key = Config.OPENWEATHER_API_KEY
    if not api_key or api_key.startswith("your_"):
        return "No OpenWeatherMap API key configured. Use your knowledge of the destination's typical weather."

    try:
        with httpx.Client(timeout=10.0) as client:
            current_resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": destination, "appid": api_key, "units": "metric"},
            )
            forecast_resp = client.get(
                "https://api.openweathermap.org/data/2.5/forecast",
                params={"q": destination, "appid": api_key, "units": "metric"},
            )
            data = {}
            if current_resp.status_code == 200:
                data["current"] = current_resp.json()
            if forecast_resp.status_code == 200:
                data["forecast"] = forecast_resp.json()
            if not data:
                return f"Weather API returned {current_resp.status_code}. Use your knowledge."
            return json.dumps(data)
    except Exception as e:
        logger.warning("Weather API error for destination=%r: %s", destination, e)
        return f"Weather API error: {e}. Use your knowledge of the destination's typical weather."


@tool
def search_knowledge_base(query: str) -> str:
    """Search the local travel knowledge base (ChromaDB) for previously researched information."""
    try:
        collection, embedder = _get_rag_store()
        if collection.count() == 0:
            return "Knowledge base is empty — no prior research found."
        embedding = embedder.encode([query]).tolist()
        results = collection.query(
            query_embeddings=embedding,
            n_results=min(3, collection.count()),
        )
        docs = results.get("documents", [[]])[0]
        if not docs:
            return "No relevant results found in knowledge base."
        return "\n\n".join(docs)
    except Exception as e:
        logger.warning("Knowledge base search failed for query=%r: %s", query, e)
        return f"Knowledge base search failed: {e}"


@tool
def store_in_knowledge_base(text: str, agent_name: str, destination: str) -> str:
    """Store research results in the ChromaDB knowledge base for reuse by later agents/runs.
    Call this after you've gathered useful destination research via search_web."""
    try:
        collection, embedder = _get_rag_store()
        embedding = embedder.encode([text]).tolist()
        collection.add(
            embeddings=embedding,
            documents=[text],
            metadatas=[{"agent": agent_name, "destination": destination}],
            ids=[str(uuid.uuid4())],
        )
        return "Stored successfully."
    except Exception as e:
        logger.warning("Failed to store in knowledge base: %s", e)
        return f"Failed to store in knowledge base: {e}"

@tool
def track_flight_status(flight_number: str) -> str:
    """Get LIVE real-time status for a specific flight using its IATA flight number
    (e.g. 'AI202', 'UA100', '6E2341'). Returns scheduled/active/landed/cancelled/diverted
    status, departure & arrival gate/terminal/delay info, and live position if airborne.
    Use this ONLY when the user gives you an actual flight number to track post-booking —
    NOT for searching/comparing flight options (use search_web for that)."""
    result = track_flight(flight_number)
    return json.dumps(result)


@tool
def track_train_status(origin: str, destination: str) -> str:
    """Get the correct official live train-tracking website for a given route/region
    (e.g. NTES for India, Amtrak for USA, National Rail for UK). There is no universal
    free live train-status API, so this returns a direct link to check real-time running
    status rather than approximate data. Use when the user wants to track a booked train."""
    result = get_train_tracker_info(origin, destination)
    return json.dumps(result)


# =========================================================================== #
# Agent factory                                                                #
# =========================================================================== #

class _AgentWrapper:
    """Thin wrapper around the new create_agent graph to keep the .invoke({'input':...})
    interface that workflow.py expects."""

    def __init__(self, graph):
        self._graph = graph

    def invoke(self, inputs: dict) -> dict:
        """Accept {'input': str} and return {'output': str} for compatibility."""
        user_text = inputs.get("input", "")
        result = self._graph.invoke({"messages": [HumanMessage(content=user_text)]})
        messages = result.get("messages", [])
        # Last message should be the AI's final answer
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                return {"output": msg.content}
        return {"output": str(result)}


def _build_agent(system_prompt: str, tools: list, agent_name: str) -> _AgentWrapper:
    """Build a LangChain agent using the canonical create_agent factory."""
    llm = _make_llm()
    graph = create_agent(
        model=llm,
        tools=tools if tools else [],   # never pass None
        system_prompt=system_prompt,
    )
    return _AgentWrapper(graph)


# =========================================================================== #
# All 12 Agents                                                                #
# =========================================================================== #

research_agent = _build_agent(
    system_prompt="""You are a Travel Research Agent.
You have three tools available: search_web, search_knowledge_base, and store_in_knowledge_base.
Do NOT call any other tool. Do NOT invent tool names.
Steps:
1. Call search_knowledge_base to check for prior research.
2. Call search_web to find current information about the destination.
3. Call store_in_knowledge_base with a concise summary of what you found (pass the destination name and agent_name="ResearchAgent") so future runs can reuse it.
4. After gathering information, respond with ONLY a raw JSON object (no markdown, no code fences):
{"attractions": [], "local_tips": [], "transportation": "", "weather_overview": "", "cultural_notes": ""}""",
    tools=[search_web, search_knowledge_base, store_in_knowledge_base],
    agent_name="ResearchAgent",
)

weather_agent = _build_agent(
    system_prompt="""You are a Weather Analysis Agent for travel planning.
You have one tool: fetch_weather. Do NOT call any other tool.
Step 1: Call fetch_weather with the destination city name.
Step 2: After receiving the data, respond with ONLY a raw JSON object (no markdown, no code fences, no extra text):
{"current": {"temperature_celsius": 0, "condition": "", "humidity": 0, "wind_speed_kmh": 0}, "forecast_summary": "", "best_time_to_visit": "", "packing_suggestions": [], "weather_warnings": [], "clothing_recommendations": []}""",
    tools=[fetch_weather],
    agent_name="WeatherAgent",
)

flight_agent = _build_agent(
    system_prompt="""You are a Flight Search Agent.
You have one tool: search_web. Do NOT call any other tool or invent tool names.
Step 1: Call search_web to find flight options between the origin and destination.
Step 2: Respond with ONLY a raw JSON object (no markdown, no code fences):
{"options": [{"airline": "", "price": 0, "currency": "USD", "duration": "", "layovers": 0, "departure_time": "", "arrival_time": "", "class": "economy", "booking_url": ""}], "cheapest": "", "fastest": "", "recommended": ""}""",
    tools=[search_web],
    agent_name="FlightAgent",
)

hotel_agent = _build_agent(
    system_prompt="""You are a Hotel Search Agent.
You have one tool: search_web. Do NOT call any other tool or invent tool names.
Step 1: Call search_web to find hotel listings at the destination.
Step 2: Respond with ONLY a raw JSON object (no markdown, no code fences):
{"options": [{"name": "", "type": "hotel", "price_per_night": 0, "total_price": 0, "currency": "USD", "rating": 0, "stars": 0, "amenities": [], "location": "", "distance_to_center": "", "booking_url": ""}], "budget_pick": "", "luxury_pick": "", "best_value": ""}""",
    tools=[search_web],
    agent_name="HotelAgent",
)

activity_agent = _build_agent(
    system_prompt="""You are an Activity Recommendation Agent.
Tools: search_web.
Do NOT invent or call tools not listed. After using tools, return ONLY a raw JSON object (no markdown, no code fences):
{"adventure": [{"name": "", "description": "", "duration": "", "price": 0, "rating": 0, "best_time": "", "location": ""}], "relaxation": [], "family": [], "culture": [], "food": [], "nightlife": []}""",
    tools=[search_web],
    agent_name="ActivityAgent",
)

visa_agent = _build_agent(
    system_prompt="""You are a Visa Requirements Expert Agent.
You have one tool: search_web. Do NOT call any other tool or invent tool names.
Step 1: Call search_web to look up current official visa policies for the origin/destination pair.
Step 2: Respond with ONLY a raw JSON object (no markdown, no code fences):
{"visa_required": true, "visa_type": "", "visa_on_arrival": false, "e_visa_available": false, "documents_required": [], "processing_time": "", "visa_fee": "", "validity_period": "", "max_stay": "", "embassy_info": {"website": "", "notes": ""}, "tips": [], "warnings": []}""",
    tools=[search_web],
    agent_name="VisaAgent",
)

safety_agent = _build_agent(
    system_prompt="""You are a Travel Safety Agent.
You have one tool: search_web. Do NOT call any other tool or invent tool names.
Step 1: Call search_web to check the latest travel advisories and safety info for the destination.
Step 2: Respond with ONLY a raw JSON object (no markdown, no code fences):
{"safety_rating": "", "overall_assessment": "", "travel_advisories": [], "health_tips": {"vaccinations_recommended": [], "health_risks": [], "water_safety": "", "food_safety_tips": []}, "emergency_numbers": {"police": "", "ambulance": "", "fire": "", "tourist_helpline": ""}, "local_laws": [], "scam_warnings": [], "safe_areas": [], "areas_to_avoid": [], "women_safety_tips": [], "general_tips": []}""",
    tools=[search_web],
    agent_name="SafetyAgent",
)

budget_agent = _build_agent(
    system_prompt=(
        "You are a Budget Planning Agent.\n"
        "You have NO tools. Do NOT attempt to call any tool or function.\n"
        "Calculate all travel expenses from the data in the prompt. Include a 10% miscellaneous buffer.\n"
        "Respond with ONLY a raw JSON object (no markdown, no code fences):\n"
        '{"flights": 0, "accommodation": 0, "food": 0, "transportation": 0, "activities": 0, '
        '"visa_fees": 0, "travel_insurance": 0, "miscellaneous": 0, "total": 0, "remaining": 0, '
        '"daily_budget": 0, "budget_status": "within_budget", "savings_tips": [], "warnings": []}\n'
        "budget_status must be one of: within_budget, tight, or over_budget"
    ),
    tools=[],
    agent_name="BudgetAgent",
)

itinerary_agent = _build_agent(
    system_prompt="""You are an Itinerary Planning Agent.
You have one tool: search_knowledge_base. Do NOT call any other tool or invent tool names.
Step 1: Optionally call search_knowledge_base for prior research on this destination.
Step 2: Create a detailed day-by-day plan and respond with ONLY a raw JSON object (no markdown, no code fences):
{"day_1": {"theme": "Arrival & Exploration", "morning": [{"time": "", "activity_name": "", "duration": "", "location": "", "cost": 0, "notes": ""}], "afternoon": [], "evening": []}, "day_2": {"theme": "", "morning": [], "afternoon": [], "evening": []}}""",
    tools=[search_knowledge_base],
    agent_name="ItineraryAgent",
)

booking_agent = _build_agent(
    system_prompt="""You are a Booking Assistant Agent.
You have one tool: search_web. Do NOT call any other tool or invent tool names. NEVER make actual payments.
Step 1: Call search_web to find the best booking platforms for flights, hotels, and activities.
Step 2: Respond with ONLY a raw JSON object (no markdown, no code fences):
{"booking_steps": [], "important_notes": [], "links": {"flights": "", "hotels": "", "activities": "", "trains": "", "cabs": ""}, "tips": [], "best_booking_time": "", "cancellation_advice": ""}""",
    tools=[search_web],
    agent_name="BookingAgent",
)

train_agent = _build_agent(
    system_prompt="""You are a Train Search Agent specializing in rail travel.
You have one tool: search_web. Do NOT call any other tool or invent tool names.
Step 1: Call search_web to find real train options between origin and destination (IRCTC for India, Eurail/Amtrak for international).
Step 2: Respond with ONLY a raw JSON object (no markdown, no code fences):
{"available": true, "trains": [{"train_name": "", "train_number": "", "departure_time": "", "arrival_time": "", "duration": "", "class_options": ["Sleeper", "3AC", "2AC", "1AC"], "price_sleeper": 0, "price_3ac": 0, "price_2ac": 0, "price_1ac": 0, "currency": "INR", "days_of_run": [], "availability": "Available", "booking_url": "https://www.irctc.co.in"}], "tips": ["Book in advance on IRCTC"], "booking_url": "https://www.irctc.co.in", "note": ""}""",
    tools=[search_web],
    agent_name="TrainAgent",
)

cab_agent = _build_agent(
    system_prompt="""You are a Cab & Local Transport Agent.
You have one tool: search_web. Do NOT call any other tool or invent tool names.
Step 1: Call search_web to find cab, taxi, and local transport options at the destination (Ola/Uber for India, Uber/Lyft/Grab for international).
Step 2: Respond with ONLY a raw JSON object (no markdown, no code fences):
{"airport_transfer": {"options": [{"provider": "Ola/Uber", "type": "Sedan", "estimated_cost": 0, "currency": "INR", "booking_url": ""}], "tip": ""}, "local_transport": [{"type": "Auto-Rickshaw", "avg_cost_per_km": 0, "currency": "INR", "tip": ""}, {"type": "Cab (Ola/Uber)", "avg_cost_per_km": 0, "currency": "INR", "tip": ""}], "intercity_cab": {"available": true, "providers": [{"name": "", "approx_cost": 0, "currency": "INR", "booking_url": ""}], "tip": ""}, "tips": []}""",
    tools=[search_web],
    agent_name="CabAgent",
)

tracking_agent = _build_agent(
    system_prompt="""You are a Live Trip Tracking Agent.
You have two tools: track_flight_status and track_train_status. Do NOT call any other tool or invent tool names.
- If the user gives a flight number, call track_flight_status with it.
- If the user gives a train route (origin/destination) or train number, call track_train_status with origin and destination.
- If a tool returns ok:false, report the reason/message honestly — do NOT invent flight status, gates, or delays.
Respond with ONLY a raw JSON object (no markdown, no code fences):
{"flight_status": null, "train_tracker": null, "summary": ""}
Put the raw tool result (parsed JSON) into the matching key, leave the other null if not applicable.
"summary" is one short plain-English sentence about what you found.""",
    tools=[track_flight_status, track_train_status],
    agent_name="TrackingAgent",
)

# =========================================================================== #
# Registry                                                                     #
# =========================================================================== #

AGENT_REGISTRY = {
    "research":  research_agent,
    "weather":   weather_agent,
    "flight":    flight_agent,
    "train":     train_agent,
    "cab":       cab_agent,
    "hotel":     hotel_agent,
    "activity":  activity_agent,
    "visa":      visa_agent,
    "safety":    safety_agent,
    "budget":    budget_agent,
    "itinerary": itinerary_agent,
    "booking":   booking_agent,
    "tracking":  tracking_agent,
}

"""
agents_tracking_addition.py

This is the code to ADD to your existing agents.py.
It does NOT replace anything — it's purely additive:
  1. one new import
  2. one new @tool: track_flight_status
  3. one new agent: tracking_agent
  4. one new registry entry: "tracking"

────────────────────────────────────────────────────────────────────────
STEP 1 — add this import near your other local imports at the top of agents.py
────────────────────────────────────────────────────────────────────────

from tracking import track_flight, get_train_tracker_info


────────────────────────────────────────────────────────────────────────
STEP 2 — add this @tool next to your other @tool definitions
(after store_in_knowledge_base, before "Agent factory" section)
────────────────────────────────────────────────────────────────────────
"""

from langchain.tools import tool
import json


@tool
def track_flight_status(flight_number: str) -> str:
    """Get LIVE real-time status for a specific flight using its IATA flight number
    (e.g. 'AI202', 'UA100', '6E2341'). Returns scheduled/active/landed/cancelled/diverted
    status, departure & arrival gate/terminal/delay info, and live position if airborne.
    Use this ONLY when the user gives you an actual flight number to track post-booking —
    NOT for searching/comparing flight options (use search_web for that)."""
    result = track_flight(flight_number)
    return json.dumps(result)


@tool
def track_train_status(origin: str, destination: str) -> str:
    """Get the correct official live train-tracking website for a given route/region
    (e.g. NTES for India, Amtrak for USA, National Rail for UK). There is no universal
    free live train-status API, so this returns a direct link to check real-time running
    status rather than approximate data. Use when the user wants to track a booked train."""
    result = get_train_tracker_info(origin, destination)
    return json.dumps(result)


"""
────────────────────────────────────────────────────────────────────────
STEP 3 — add this agent definition in the "All 12 Agents" section
(rename that section header to "All 13 Agents" if you like)
────────────────────────────────────────────────────────────────────────
"""

# tracking_agent = _build_agent(
#     system_prompt="""You are a Live Trip Tracking Agent.
# You have two tools: track_flight_status and track_train_status. Do NOT call any other tool or invent tool names.
# - If the user gives a flight number, call track_flight_status with it.
# - If the user gives a train route (origin/destination) or train number, call track_train_status with origin and destination.
# - If a tool returns ok:false, report the reason/message honestly — do NOT invent flight status, gates, or delays.
# Respond with ONLY a raw JSON object (no markdown, no code fences):
# {"flight_status": null, "train_tracker": null, "summary": ""}
# Put the raw tool result (parsed JSON) into the matching key, leave the other null if not applicable.
# "summary" is one short plain-English sentence about what you found.""",
#     tools=[track_flight_status, track_train_status],
#     agent_name="TrackingAgent",
# )


"""
────────────────────────────────────────────────────────────────────────
STEP 4 — add to AGENT_REGISTRY at the bottom of agents.py
────────────────────────────────────────────────────────────────────────

AGENT_REGISTRY = {
    "research":  research_agent,
    "weather":   weather_agent,
    "flight":    flight_agent,
    "train":     train_agent,
    "cab":       cab_agent,
    "hotel":     hotel_agent,
    "activity":  activity_agent,
    "visa":      visa_agent,
    "safety":    safety_agent,
    "budget":    budget_agent,
    "itinerary": itinerary_agent,
    "booking":   booking_agent,
    "tracking":  tracking_agent,   # <-- ADD THIS LINE
}

Note: "tracking" is intentionally NOT added to AGENT_ORDER in workflow.py.
It's an on-demand agent the user triggers themselves (post-booking, when they
have a real flight number) — not part of the automatic 12-step planning
pipeline. See workflow_tracking_addition.py for how it's wired into the UI
as a standalone call instead.
"""