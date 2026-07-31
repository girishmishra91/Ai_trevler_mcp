"""
workflow.py — LangGraph multi-agent travel planner workflow.
"""

import json
import logging
from typing import Dict, Any, TypedDict, Annotated, List
import operator

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage

from config import Config
from agents import AGENT_REGISTRY, store_in_knowledge_base
from utils import clean_json_response
from tracking import track_flight, get_train_tracker_info

logger = logging.getLogger(__name__)


# =========================================================================== #
# State                                                                        #
# =========================================================================== #

class TravelState(TypedDict):
    messages:         Annotated[list, operator.add]
    destination:      str
    origin:           str
    departure_date:   str
    return_date:      str
    days:             int
    budget:           float
    base_currency:    str
    interests:        list
    preferences:      str

    # Agent outputs
    research_data:    Dict[str, Any]
    weather_data:     Dict[str, Any]
    flights:          Dict[str, Any]
    trains:           Dict[str, Any]
    cabs:             Dict[str, Any]
    hotels:           Dict[str, Any]
    activities:       Dict[str, Any]
    visa_info:        Dict[str, Any]
    safety_info:      Dict[str, Any]
    budget_breakdown: Dict[str, Any]
    itinerary:        Dict[str, Any]
    booking_info:     Dict[str, Any]

    # Workflow control
    next_agent:       str
    completed_agents: List[str]
    current_agent:    str


# =========================================================================== #
# Execution order & labels                                                     #
# =========================================================================== #

AGENT_ORDER = [
    "research",
    "weather",
    "flight",
    "train",
    "cab",
    "hotel",
    "activity",
    "visa",
    "safety",
    "budget",
    "itinerary",
    "booking",
]

AGENT_LABELS = {
    "research":  "🔍 Research Agent",
    "weather":   "🌤️ Weather Agent",
    "flight":    "✈️ Flight Agent",
    "train":     "🚂 Train Agent",
    "cab":       "🚖 Cab Agent",
    "hotel":     "🏨 Hotel Agent",
    "activity":  "🎯 Activity Agent",
    "visa":      "📋 Visa Agent",
    "safety":    "🛡️ Safety Agent",
    "budget":    "💰 Budget Agent",
    "itinerary": "📅 Itinerary Agent",
    "booking":   "📱 Booking Agent",
}

FIELD_MAP = {
    "research":  "research_data",
    "weather":   "weather_data",
    "flight":    "flights",
    "train":     "trains",
    "cab":       "cabs",
    "hotel":     "hotels",
    "activity":  "activities",
    "visa":      "visa_info",
    "safety":    "safety_info",
    "budget":    "budget_breakdown",
    "itinerary": "itinerary",
    "booking":   "booking_info",
}


# =========================================================================== #
# Workflow                                                                     #
# =========================================================================== #

class TravelPlannerWorkflow:

    def __init__(self):
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(TravelState)

        workflow.add_node("planner",   self._planner_node)
        for key in AGENT_ORDER:
            workflow.add_node(key, self._make_agent_node(key))

        workflow.set_entry_point("planner")

        workflow.add_conditional_edges(
            "planner",
            self._route_agent,
            {**{k: k for k in AGENT_ORDER}, "end": END},
        )

        for key in AGENT_ORDER[:-1]:   # all except booking → back to planner
            workflow.add_edge(key, "planner")

        workflow.add_edge("booking", END)
        return workflow.compile()

    # ------------------------------------------------------------------ #
    # Planner node — returns only the fields it changes                  #
    # ------------------------------------------------------------------ #

    def _planner_node(self, state: TravelState) -> dict:
        completed = state.get("completed_agents") or []
        for agent_key in AGENT_ORDER:
            if agent_key not in completed:
                return {"next_agent": agent_key, "current_agent": agent_key}
        return {"next_agent": "end", "current_agent": ""}

    def _route_agent(self, state: TravelState) -> str:
        return state.get("next_agent", "end")

    # ------------------------------------------------------------------ #
    # Generic agent node factory — returns only the fields it changes    #
    # ------------------------------------------------------------------ #

    def _make_agent_node(self, agent_key: str):
        def node(state: TravelState) -> dict:
            agent = AGENT_REGISTRY[agent_key]
            prompt = self._build_prompt(agent_key, state)

            try:
                result = agent.invoke({"input": prompt})
                output_text = result.get("output", "")
                parsed = clean_json_response(output_text)
            except Exception as e:
                logger.warning("%s agent error: %s", agent_key, e)
                parsed = {"error": str(e)}

            # Store research in vector DB — but only on a clean result.
            # If the agent call failed above, `parsed` is {"error": ...}, which is
            # still a truthy non-empty dict. Without the "error" not in parsed check,
            # that error payload would get embedded and stored as if it were real
            # destination research, and later show up via search_knowledge_base as
            # "prior research" for other agents/runs.
            if agent_key == "research" and parsed and "error" not in parsed:
                try:
                    store_in_knowledge_base.invoke({
                        "text": json.dumps(parsed) if isinstance(parsed, dict) else str(parsed),
                        "agent_name": "ResearchAgent",
                        "destination": state.get("destination", "")
                    })
                except Exception as e:
                    logger.warning("Failed to store research in knowledge base: %s", e)

            completed = list(state.get("completed_agents") or [])
            if agent_key not in completed:
                completed.append(agent_key)

            return {
                FIELD_MAP[agent_key]: parsed,
                "completed_agents": completed,
            }

        node.__name__ = f"_{agent_key}_node"
        return node

    # ------------------------------------------------------------------ #
    # Prompt builder                                                      #
    # ------------------------------------------------------------------ #

    def _build_prompt(self, agent_key: str, state: TravelState) -> str:
        currency = state.get('base_currency', 'USD')
        base = (
            f"Destination: {state.get('destination', '')}\n"
            f"Origin: {state.get('origin', '')}\n"
            f"Dates: {state.get('departure_date', '')} to {state.get('return_date', '')}\n"
            f"Duration: {state.get('days', 3)} days\n"
            f"Budget: {state.get('budget', 0):,.0f} {currency}\n"
            f"Currency: {currency} — ALL prices you return MUST be in {currency}.\n"
            f"Interests: {', '.join(state.get('interests', [])) or 'general travel'}\n"
            f"Preferences: {state.get('preferences', '')}\n"
        )

        extras = {
            "budget": (
                f"\nFlight data: {json.dumps(state.get('flights', {}))}\n"
                f"Hotel data: {json.dumps(state.get('hotels', {}))}\n"
                f"Activity data: {json.dumps(state.get('activities', {}))}\n"
                f"Visa info: {json.dumps(state.get('visa_info', {}))}\n"
            ),
            "itinerary": (
                f"\nActivities: {json.dumps(state.get('activities', {}))}\n"
                f"Hotels: {json.dumps(state.get('hotels', {}))}\n"
                f"Weather: {json.dumps(state.get('weather_data', {}))}\n"
            ),
            "booking": (
                f"\nFlights: {json.dumps(state.get('flights', {}))}\n"
                f"Hotels: {json.dumps(state.get('hotels', {}))}\n"
            ),
        }

        task_map = {
            "research":  "Research the destination thoroughly — find top attractions, tips, transport, and local culture.",
            "weather":   "Get current weather and 5-day forecast. Give packing and clothing advice.",
            "flight":    "Find the best flight options. List top 3 with real prices and booking links.",
            "train":     "Find the best train options between origin and destination. List schedules, classes, and prices.",
            "cab":       "Find cab, taxi and local transport options at the destination. Include airport transfers and ride-hailing apps.",
            "hotel":     "Find top 5 hotels covering budget, mid-range, and luxury options.",
            "activity":  "Recommend the best activities by category (adventure, culture, food, family, etc.).",
            "visa":      "Check visa requirements for this origin/destination pair. Include docs, fees, and processing time.",
            "safety":    "Provide a full safety advisory — ratings, emergency numbers, health tips, scam warnings.",
            "budget":    "Create a complete budget breakdown using the data provided. Flag if over budget.",
            "itinerary": "Create a day-by-day itinerary with morning, afternoon, and evening activities.",
            "booking":   "Provide direct booking links, steps, and tips for flights, hotels, activities, trains, and cabs.",
        }

        return base + extras.get(agent_key, "") + "\n\nTask: " + task_map.get(agent_key, "Complete your assigned travel planning task.")

    # ------------------------------------------------------------------ #
    # Public entry point                                                  #
    # ------------------------------------------------------------------ #

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        state = TravelState(
            messages=[HumanMessage(content=initial_state.get("request", ""))],
            destination=initial_state.get("destination", ""),
            origin=initial_state.get("origin", ""),
            departure_date=initial_state.get("departure_date", ""),
            return_date=initial_state.get("return_date", ""),
            days=initial_state.get("days", 3),
            budget=float(initial_state.get("budget", 0)),
            base_currency=initial_state.get("base_currency", "USD"),
            interests=initial_state.get("interests", []),
            preferences=initial_state.get("preferences", ""),
            research_data={},
            weather_data={},
            flights={},
            trains={},
            cabs={},
            hotels={},
            activities={},
            visa_info={},
            safety_info={},
            budget_breakdown={},
            itinerary={},
            booking_info={},
            next_agent="",
            completed_agents=[],
            current_agent="",
        )
        return self.graph.invoke(state)

    def track_flight_live(self, flight_number: str) -> dict:
        """Direct, non-agent live flight status lookup for the UI."""
        return track_flight(flight_number)

    def get_train_tracking_link(self, origin: str, destination: str) -> dict:
        """Direct, non-agent lookup of the correct official train-tracking site."""
        return get_train_tracker_info(origin, destination)