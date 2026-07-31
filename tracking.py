"""
tracking.py — Live flight & train status tracking.

Flight tracking: AviationStack API (free tier: ~100-500 requests/month,
no credit card required). Sign up: https://aviationstack.com/signup/free

Train tracking: there is no general-purpose free live-status API
(IRCTC has no public API; NTES/Amtrak/Trainline don't offer free public
feeds). Instead of faking data, we surface a live-search-based best-effort
status plus a direct deep link to the correct official tracker so the
user always has a real, working option.
"""

import logging
import re
import httpx

from config import Config

logger = logging.getLogger(__name__)

AVIATIONSTACK_BASE = "http://api.aviationstack.com/v1/flights"

# Friendly labels for AviationStack's raw status strings
FLIGHT_STATUS_LABELS = {
    "scheduled": "🕐 Scheduled",
    "active": "🛫 In the Air",
    "landed": "🛬 Landed",
    "cancelled": "❌ Cancelled",
    "incident": "⚠️ Incident Reported",
    "diverted": "↩️ Diverted",
}


def _clean_flight_number(flight_number: str) -> str:
    """Normalize input like 'AI 202' / 'ai-202' -> 'AI202'."""
    return re.sub(r"[\s\-]", "", (flight_number or "")).upper()


def track_flight(flight_number: str) -> dict:
    """Look up live status for a flight using AviationStack.

    Returns a normalized dict on success:
    {
        "ok": True,
        "flight_number": "AI202",
        "airline": "Air India",
        "status": "active",
        "status_label": "🛫 In the Air",
        "departure": {"airport": "", "iata": "", "terminal": "", "gate": "",
                       "scheduled": "", "estimated": "", "actual": "", "delay_minutes": 0},
        "arrival":   {...same shape...},
        "live": {"latitude": 0, "longitude": 0, "altitude": 0, "speed_kmh": 0} | None,
    }

    On failure / no API key, returns {"ok": False, "reason": "..."} so the
    caller can show a clear, honest message instead of fabricated data.
    """
    api_key = Config.AVIATIONSTACK_API_KEY
    fnum = _clean_flight_number(flight_number)

    if not fnum:
        return {"ok": False, "reason": "No flight number provided."}

    if not api_key or api_key.startswith("your_"):
        return {
            "ok": False,
            "reason": "no_api_key",
            "message": (
                "Live flight tracking isn't configured yet. Get a free AviationStack "
                "API key (no credit card) at https://aviationstack.com/signup/free "
                "and set AVIATIONSTACK_API_KEY in your .env file."
            ),
        }

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                AVIATIONSTACK_BASE,
                params={"access_key": api_key, "flight_iata": fnum},
            )
            if resp.status_code != 200:
                return {"ok": False, "reason": f"AviationStack returned HTTP {resp.status_code}."}

            payload = resp.json()

            if payload.get("error"):
                err = payload["error"]
                if isinstance(err, dict):
                    reason = err.get("info") or err.get("message") or "AviationStack API error."
                else:
                    reason = str(err)
                return {"ok": False, "reason": reason}

            data = payload.get("data", [])
            if not data:
                return {
                    "ok": False,
                    "reason": (
                        f"No live data found for flight {fnum}. It may not be scheduled "
                        f"today, or the flight number format may be wrong (use IATA code, e.g. AI202)."
                    ),
                }

            flight = data[0]
            dep = flight.get("departure", {}) or {}
            arr = flight.get("arrival", {}) or {}
            airline = (flight.get("airline") or {}).get("name", "Unknown Airline")
            live = flight.get("live") or None

            status = flight.get("flight_status", "unknown")

            return {
                "ok": True,
                "flight_number": fnum,
                "airline": airline,
                "status": status,
                "status_label": FLIGHT_STATUS_LABELS.get(status, status.title() if status else "Unknown"),
                "departure": {
                    "airport": dep.get("airport", ""),
                    "iata": dep.get("iata", ""),
                    "terminal": dep.get("terminal") or "—",
                    "gate": dep.get("gate") or "—",
                    "scheduled": dep.get("scheduled", ""),
                    "estimated": dep.get("estimated", ""),
                    "actual": dep.get("actual", ""),
                    "delay_minutes": dep.get("delay") or 0,
                },
                "arrival": {
                    "airport": arr.get("airport", ""),
                    "iata": arr.get("iata", ""),
                    "terminal": arr.get("terminal") or "—",
                    "gate": arr.get("gate") or "—",
                    "scheduled": arr.get("scheduled", ""),
                    "estimated": arr.get("estimated", ""),
                    "actual": arr.get("actual", ""),
                    "delay_minutes": arr.get("delay") or 0,
                },
                "live": (
                    {
                        "latitude": live.get("latitude"),
                        "longitude": live.get("longitude"),
                        "altitude": live.get("altitude"),
                        "speed_kmh": live.get("speed_horizontal"),
                    }
                    if live
                    else None
                ),
            }

    except httpx.TimeoutException:
        return {"ok": False, "reason": "AviationStack request timed out. Try again."}
    except Exception as e:
        logger.warning("Flight tracking error for %r: %s", flight_number, e)
        return {"ok": False, "reason": f"Tracking error: {e}"}


# =========================================================================== #
# Train tracking                                                              #
# =========================================================================== #
# No free general-purpose live train-status API exists (IRCTC has no public
# API; india's NTES, Amtrak, and Trainline don't expose free public feeds).
# We give the user a direct, correct deep link to check live status
# themselves, rather than fabricating positions.

TRAIN_TRACKERS = {
    "india": {
        "name": "NTES (Indian Railways)",
        "url_template": "https://enquiry.indianrail.gov.in/ntes/",
        "note": "Search your train number directly on NTES for live running status.",
    },
    "usa": {
        "name": "Amtrak Status Maps",
        "url_template": "https://www.amtrak.com/track-your-train.html",
        "note": "Enter your train number or route on Amtrak's live status map.",
    },
    "uk": {
        "name": "National Rail Enquiries — Live Departure Boards",
        "url_template": "https://www.nationalrail.co.uk/live-trains/",
        "note": "Search by station for live departure/arrival boards.",
    },
    "europe": {
        "name": "Trainline Live Status",
        "url_template": "https://www.thetrainline.com/",
        "note": "Most EU national rail operators publish live status via Trainline or their own site (e.g. SNCF, Deutsche Bahn, Trenitalia).",
    },
}


def get_train_tracker_info(origin: str, destination: str) -> dict:
    """Return the correct official live-tracking destination for a given route.
    Best-effort region detection from origin/destination strings."""
    text = f"{origin} {destination}".lower()

    if any(k in text for k in ["india", "delhi", "mumbai", "goa", "bangalore", "chennai",
                                "kolkata", "jaipur", "pune", "hyderabad", "agra", "varanasi"]):
        region = "india"
    elif any(k in text for k in ["usa", "united states", "new york", "los angeles",
                                  "chicago", "boston", "washington"]):
        region = "usa"
    elif any(k in text for k in ["uk", "united kingdom", "london", "manchester", "edinburgh"]):
        region = "uk"
    elif any(k in text for k in ["france", "germany", "italy", "spain", "paris", "berlin",
                                  "rome", "madrid", "amsterdam", "netherlands"]):
        region = "europe"
    else:
        region = None

    if region:
        info = TRAIN_TRACKERS[region]
        return {"ok": True, "region": region, **info}

    return {
        "ok": False,
        "reason": "No known official live-train tracker for this route. Check the operator's website directly.",
    }