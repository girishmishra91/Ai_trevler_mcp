import json
import re
import httpx
from typing import Dict, Any
from datetime import datetime, date


def clean_json_response(text: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM response."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Grab first {...} block (handles extra prose)
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {}


# =========================================================================== #
# Currency helpers                                                              #
# =========================================================================== #

CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹",
    "JPY": "¥", "AUD": "A$", "CAD": "C$", "THB": "฿",
    "SGD": "S$", "AED": "د.إ", "SAR": "ر.س", "MYR": "RM",
    "IDR": "Rp", "VND": "₫", "PHP": "₱", "KRW": "₩",
    "CNY": "¥", "CHF": "CHF", "NZD": "NZ$", "HKD": "HK$",
    "TRY": "₺", "ZAR": "R", "BRL": "R$", "MXN": "MX$",
    "RUB": "₽", "PKR": "₨", "BDT": "৳", "LKR": "₨",
    "NPR": "₨", "MMK": "K", "KHR": "៛",
}

COUNTRY_CURRENCIES = {
    # South Asia
    "india": "INR", "goa": "INR", "delhi": "INR", "mumbai": "INR",
    "bangalore": "INR", "kerala": "INR", "rajasthan": "INR",
    "gorakhpur": "INR", "varanasi": "INR", "agra": "INR",
    "jaipur": "INR", "kolkata": "INR", "chennai": "INR",
    "hyderabad": "INR", "pune": "INR", "ahmedabad": "INR",
    "new delhi": "INR", "lucknow": "INR", "chandigarh": "INR",
    "shimla": "INR", "manali": "INR", "darjeeling": "INR",
    "pakistan": "PKR", "bangladesh": "BDT", "sri lanka": "LKR",
    "nepal": "NPR",
    # Southeast Asia
    "thailand": "THB", "bangkok": "THB", "phuket": "THB", "chiang mai": "THB",
    "singapore": "SGD",
    "malaysia": "MYR", "kuala lumpur": "MYR", "langkawi": "MYR",
    "indonesia": "IDR", "bali": "IDR", "jakarta": "IDR",
    "vietnam": "VND", "hanoi": "VND", "ho chi minh": "VND",
    "philippines": "PHP", "manila": "PHP", "cebu": "PHP",
    "myanmar": "MMK", "cambodia": "KHR",
    # East Asia
    "japan": "JPY", "tokyo": "JPY", "osaka": "JPY", "kyoto": "JPY",
    "china": "CNY", "beijing": "CNY", "shanghai": "CNY",
    "south korea": "KRW", "seoul": "KRW", "busan": "KRW",
    "hong kong": "HKD",
    # Middle East
    "uae": "AED", "dubai": "AED", "abu dhabi": "AED",
    "saudi arabia": "SAR", "riyadh": "SAR",
    "turkey": "TRY", "istanbul": "TRY",
    # Europe
    "france": "EUR", "paris": "EUR",
    "germany": "EUR", "berlin": "EUR", "munich": "EUR",
    "italy": "EUR", "rome": "EUR", "venice": "EUR", "milan": "EUR",
    "spain": "EUR", "barcelona": "EUR", "madrid": "EUR",
    "netherlands": "EUR", "amsterdam": "EUR",
    "greece": "EUR", "athens": "EUR", "santorini": "EUR",
    "portugal": "EUR", "lisbon": "EUR",
    "switzerland": "CHF", "zurich": "CHF", "geneva": "CHF",
    "uk": "GBP", "united kingdom": "GBP", "london": "GBP",
    "russia": "RUB", "moscow": "RUB",
    # Americas
    "usa": "USD", "united states": "USD", "new york": "USD",
    "los angeles": "USD", "las vegas": "USD", "miami": "USD",
    "canada": "CAD", "toronto": "CAD", "vancouver": "CAD",
    "mexico": "MXN", "cancun": "MXN", "mexico city": "MXN",
    "brazil": "BRL", "rio de janeiro": "BRL", "sao paulo": "BRL",
    # Oceania
    "australia": "AUD", "sydney": "AUD", "melbourne": "AUD",
    "new zealand": "NZD", "auckland": "NZD",
    # Africa
    "south africa": "ZAR", "cape town": "ZAR", "johannesburg": "ZAR",
}


def detect_currency(destination: str, origin: str = "") -> str:
    """Auto-detect the best currency for a trip based on destination (and origin as fallback)."""
    dest_lower = destination.lower().strip()
    # Try full destination string first, then each word
    if dest_lower in COUNTRY_CURRENCIES:
        return COUNTRY_CURRENCIES[dest_lower]
    for word in dest_lower.split():
        if word in COUNTRY_CURRENCIES:
            return COUNTRY_CURRENCIES[word]
    # Fallback to origin country currency
    if origin:
        orig_lower = origin.lower().strip()
        if orig_lower in COUNTRY_CURRENCIES:
            return COUNTRY_CURRENCIES[orig_lower]
        for word in orig_lower.split():
            if word in COUNTRY_CURRENCIES:
                return COUNTRY_CURRENCIES[word]
    return "USD"


def get_currency_for_country(country: str) -> str:
    return COUNTRY_CURRENCIES.get(country.lower().strip(), "USD")


def format_currency(amount, currency: str = "USD") -> str:
    """Format amount with the correct currency symbol, safely handling non-numeric values."""
    symbol = CURRENCY_SYMBOLS.get(currency.upper(), "$")
    try:
        val = float(amount)
        # For currencies with large denominations (JPY, KRW, IDR, VND) skip decimals
        if currency.upper() in ("JPY", "KRW", "IDR", "VND", "MMK", "KHR"):
            return f"{symbol}{val:,.0f}"
        return f"{symbol}{val:,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}0.00"

def get_destination_info(destination: str) -> dict:
    """Fetch an image URL and coordinates for a destination using Wikipedia API."""
    import requests
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&prop=pageimages|coordinates&titles={destination}&pithumbsize=800&format=json"
        headers = {"User-Agent": "AI-Travel-Planner-Bot/1.0"}
        resp = requests.get(url, headers=headers, timeout=5).json()
        pages = resp.get("query", {}).get("pages", {})
        for page_id, data in pages.items():
            img_url = data.get("thumbnail", {}).get("source")
            coords = data.get("coordinates", [{}])[0]
            lat = coords.get("lat")
            lon = coords.get("lon")
            return {"image_url": img_url, "lat": lat, "lon": lon}
    except Exception:
        pass
    return {"image_url": None, "lat": None, "lon": None}



def convert_currency(
    amount: float,
    from_currency: str = "USD",
    to_currency: str = "INR",
    api_key: str = "",
) -> float:
    """Convert currency using ExchangeRate API. Returns original amount on failure."""
    if from_currency.upper() == to_currency.upper():
        return amount
    if not api_key or api_key.startswith("your_"):
        fallback_rates = {
            ("USD", "INR"): 83.5, ("INR", "USD"): 0.012,
            ("USD", "EUR"): 0.92, ("EUR", "USD"): 1.09,
            ("USD", "GBP"): 0.79, ("GBP", "USD"): 1.27,
        }
        rate = fallback_rates.get((from_currency.upper(), to_currency.upper()))
        if rate:
            return round(amount * rate, 2)
        return amount
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"https://v6.exchangerate-api.com/v6/{api_key}/pair/"
                f"{from_currency.upper()}/{to_currency.upper()}/{amount}"
            )
            if resp.status_code == 200:
                return resp.json().get("conversion_result", amount)
    except Exception as e:
        print(f"⚠️ Currency conversion error: {e}")
    return amount


# =========================================================================== #
# Date helpers                                                                  #
# =========================================================================== #

def _to_date(value) -> date:
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {value!r}")


def validate_dates(start_date, end_date) -> bool:
    try:
        start = _to_date(start_date)
        end = _to_date(end_date)
        today = datetime.now().date()
        return start < end and start >= today
    except Exception:
        return False


def calculate_days(start_date, end_date) -> int:
    start = _to_date(start_date)
    end = _to_date(end_date)
    return (end - start).days


def categorize_budget(budget: float) -> str:
    if budget < 500:
        return "💚 Budget"
    elif budget < 2000:
        return "💛 Mid-range"
    elif budget < 5000:
        return "🧡 Luxury"
    else:
        return "💎 Ultra-luxury"