import streamlit as st
from datetime import datetime, timedelta
from workflow import TravelPlannerWorkflow, AGENT_ORDER, AGENT_LABELS
from utils import validate_dates, calculate_days, categorize_budget, format_currency, detect_currency, get_destination_info

from notifications import send_whatsapp_itinerary, send_email_itinerary
import json
import os
import hashlib
import pandas as pd
import plotly.express as px

# ================================================================== #
# Page Config                                                          #
# ================================================================== #

st.set_page_config(
    page_title="AI Travel Planner | Multi-Agent System",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================================================== #
# Premium CSS Theme — Dark Gradient + Glassmorphism                    #
# ================================================================== #

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ---- Global ---- */
.stApp {
    background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 30%, #16213e 60%, #0f3460 100%);
    font-family: 'Inter', sans-serif;
}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.05);
}
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #e0e0ff !important;
}

/* ---- Glass Cards ---- */
.glass-card {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 1.5rem;
    margin: 0.75rem 0;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.glass-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(79,172,254,0.15);
}

/* ---- Hero Header ---- */
.hero-header {
    text-align: center;
    padding: 2rem 0 1rem;
}
.hero-title {
    font-size: 3.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 50%, #43e97b 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.3rem;
    letter-spacing: -1px;
}
.hero-subtitle {
    font-size: 1.1rem;
    color: rgba(255,255,255,0.5);
    font-weight: 300;
    letter-spacing: 2px;
}

/* ---- Section Headers ---- */
.section-header {
    font-size: 1.6rem;
    font-weight: 700;
    color: #e0e0ff;
    margin-top: 2.5rem;
    margin-bottom: 1rem;
    padding-bottom: 0.6rem;
    border-bottom: 2px solid rgba(79,172,254,0.3);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* ---- Metric Cards ---- */
.metric-card {
    background: linear-gradient(135deg, rgba(79,172,254,0.1), rgba(0,242,254,0.05));
    border: 1px solid rgba(79,172,254,0.15);
    border-radius: 12px;
    padding: 1.2rem;
    text-align: center;
}
.metric-label {
    font-size: 0.8rem;
    color: rgba(255,255,255,0.5);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 0.3rem;
}
.metric-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: #4facfe;
}

/* ---- Agent Progress ---- */
.agent-step {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.75rem;
    margin: 0.25rem 0;
    border-radius: 8px;
    font-size: 0.9rem;
    transition: all 0.3s ease;
}
.agent-step.completed {
    background: rgba(67,233,123,0.08);
    color: #43e97b;
}
.agent-step.active {
    background: rgba(79,172,254,0.12);
    color: #4facfe;
    animation: pulse-glow 1.5s ease-in-out infinite;
}
.agent-step.pending {
    color: rgba(255,255,255,0.25);
}
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 0 rgba(79,172,254,0); }
    50% { box-shadow: 0 0 15px rgba(79,172,254,0.2); }
}

/* ---- Flight / Hotel Cards ---- */
.result-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 1rem 1.2rem;
    margin: 0.5rem 0;
    transition: all 0.2s ease;
}
.result-card:hover {
    background: rgba(255,255,255,0.07);
    border-color: rgba(79,172,254,0.2);
}

/* ---- Budget Bar ---- */
.budget-item {
    background: rgba(255,255,255,0.04);
    padding: 0.7rem 1rem;
    margin: 0.3rem 0;
    border-radius: 8px;
    border-left: 3px solid #4facfe;
    display: flex;
    justify-content: space-between;
    color: #e0e0ff;
}

/* ---- Safety Badges ---- */
.safety-badge {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
}
.badge-safe { background: rgba(67,233,123,0.15); color: #43e97b; }
.badge-caution { background: rgba(255,193,7,0.15); color: #ffc107; }
.badge-warning { background: rgba(255,82,82,0.15); color: #ff5252; }

/* ---- Footer ---- */
.footer {
    text-align: center;
    padding: 2rem 0;
    color: rgba(255,255,255,0.25);
    font-size: 0.85rem;
    border-top: 1px solid rgba(255,255,255,0.05);
    margin-top: 3rem;
}
.footer a { color: #4facfe; text-decoration: none; }

/* ---- Streamlit overrides ---- */
.stMetric label { color: rgba(255,255,255,0.6) !important; }
.stMetric [data-testid="stMetricValue"] { color: #4facfe !important; }
.stExpander { border: 1px solid rgba(255,255,255,0.06) !important; border-radius: 12px !important; }
div[data-testid="stExpander"] details summary p { color: #e0e0ff !important; }
.stDownloadButton > button {
    background: linear-gradient(135deg, #4facfe, #00f2fe) !important;
    color: #0f0c29 !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# ================================================================== #
# Session State                                                        #
# ================================================================== #

if "workflow" not in st.session_state:
    st.session_state.workflow = TravelPlannerWorkflow()
if "result" not in st.session_state:
    st.session_state.result = None

# ================================================================== #
# Hero Header                                                          #
# ================================================================== #

st.markdown("""
<div class="hero-header">
    <div class="hero-title">🌍 AI Travel Planner</div>
    <div class="hero-subtitle">MULTI-AGENT SYSTEM • POWERED BY GROQ AI & LANGGRAPH</div>
</div>
""", unsafe_allow_html=True)

# ================================================================== #
# Sidebar — Trip Input Form                                            #
# ================================================================== #

with st.sidebar:
    st.markdown("## ✈️ Plan Your Trip")
    st.markdown("---")

    with st.form("travel_form"):
        destination = st.text_input("🎯 Destination", placeholder="e.g., Paris, Tokyo, Goa")
        origin = st.text_input("🏠 Departing From", placeholder="e.g., New Delhi, London")

        col1, col2 = st.columns(2)
        with col1:
            departure_date = st.date_input(
                "📅 Departure",
                min_value=datetime.now().date(),
                value=(datetime.now() + timedelta(days=30)).date(),
            )
        with col2:
            return_date = st.date_input(
                "📅 Return",
                min_value=(datetime.now() + timedelta(days=1)).date(),
                value=(datetime.now() + timedelta(days=37)).date(),
            )

        col_curr, col_budg = st.columns([1, 2])
        with col_curr:
            # Auto-detect currency but allow override
            base_currency = st.selectbox(
                "💱 Currency",
                ["INR", "USD", "EUR", "GBP", "AUD", "CAD", "JPY", "SGD", "AED", "THB"],
                help="Auto-detected from destination. You can change it."
            )
        with col_budg:
            budget = st.number_input(
                f"💰 Budget ({base_currency})",
                min_value=100,
                value=50000 if base_currency == "INR" else (200000 if base_currency in ("JPY", "KRW") else 2000),
                step=500 if base_currency == "INR" else 100
            )

        interests = st.multiselect(
            "🎨 Interests",
            ["Adventure", "Relaxation", "Culture", "Food", "Nightlife", "Family", "Nature", "Shopping"],
        )
        preferences = st.text_area(
            "📝 Additional Preferences",
            placeholder="e.g., vegetarian food, near beach, budget-friendly",
        )
        user_email = st.text_input(
            "📧 Email for Itinerary",
            placeholder="e.g., you@example.com (optional)",
        )
        submit = st.form_submit_button("🚀 Create My Trip", use_container_width=True)



# ================================================================== #
# Live Trip Tracking Panel — works any time, independent of planning  #
# ================================================================== #

st.markdown('<div class="section-header">📡 Track My Trip (Live)</div>', unsafe_allow_html=True)

track_tab1, track_tab2 = st.tabs(["✈️ Flight Status", "🚂 Train Status"])

with track_tab1:
    tcol1, tcol2 = st.columns([3, 1])
    with tcol1:
        flight_number_input = st.text_input(
            "Flight number (IATA format)",
            placeholder="e.g. AI202, UA100, 6E2341",
            key="flight_tracker_input",
        )
    with tcol2:
        st.markdown("<div style='height: 1.7rem;'></div>", unsafe_allow_html=True)
        track_flight_btn = st.button("🔍 Track Flight", use_container_width=True, key="track_flight_btn")

    if track_flight_btn:
        if not flight_number_input.strip():
            st.warning("Enter a flight number first.")
        else:
            with st.spinner("Fetching live status…"):
                status = st.session_state.workflow.track_flight_live(flight_number_input)

            if not status.get("ok"):
                reason = status.get("message") or status.get("reason", "Could not fetch live status.")
                st.info(f"ℹ️ {reason}")
            else:
                dep, arr = status["departure"], status["arrival"]
                st.markdown(f"""
                <div class="glass-card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                        <div style="font-size:1.3rem; font-weight:700; color:#e0e0ff;">
                            ✈️ {status['flight_number']} — {status['airline']}
                        </div>
                        <div class="safety-badge badge-safe" style="font-size:0.9rem;">
                            {status['status_label']}
                        </div>
                    </div>
                    <div style="display:flex; gap:2rem; flex-wrap:wrap;">
                        <div style="flex:1; min-width:220px;">
                            <div style="color:#4facfe; font-weight:600; margin-bottom:0.4rem;">🛫 Departure</div>
                            <div style="color:rgba(255,255,255,0.8);">{dep['airport']} ({dep['iata']})</div>
                            <div style="color:rgba(255,255,255,0.5); font-size:0.85rem; margin-top:0.3rem;">
                                Terminal {dep['terminal']} · Gate {dep['gate']}
                            </div>
                            <div style="color:rgba(255,255,255,0.5); font-size:0.85rem;">
                                Scheduled: {dep['scheduled'] or '—'}
                            </div>
                            {f'<div style="color:#ffc107; font-size:0.85rem;">⏱️ Delay: {dep["delay_minutes"]} min</div>' if dep['delay_minutes'] else ''}
                        </div>
                        <div style="flex:1; min-width:220px;">
                            <div style="color:#43e97b; font-weight:600; margin-bottom:0.4rem;">🛬 Arrival</div>
                            <div style="color:rgba(255,255,255,0.8);">{arr['airport']} ({arr['iata']})</div>
                            <div style="color:rgba(255,255,255,0.5); font-size:0.85rem; margin-top:0.3rem;">
                                Terminal {arr['terminal']} · Gate {arr['gate']}
                            </div>
                            <div style="color:rgba(255,255,255,0.5); font-size:0.85rem;">
                                Scheduled: {arr['scheduled'] or '—'}
                            </div>
                            {f'<div style="color:#ffc107; font-size:0.85rem;">⏱️ Delay: {arr["delay_minutes"]} min</div>' if arr['delay_minutes'] else ''}
                        </div>
                    </div>
                </div>""", unsafe_allow_html=True)

                if status.get("live"):
                    live = status["live"]
                    st.markdown(f"""
                    <div class="glass-card" style="margin-top:0.5rem;">
                        <div style="font-weight:600; color:#e0e0ff; margin-bottom:0.5rem;">📍 Live Position</div>
                        <div style="display:flex; gap:2rem; color:rgba(255,255,255,0.7); font-size:0.9rem;">
                            <span>Lat: {live.get('latitude', 'N/A')}</span>
                            <span>Lon: {live.get('longitude', 'N/A')}</span>
                            <span>Altitude: {live.get('altitude', 'N/A')} m</span>
                            <span>Speed: {live.get('speed_kmh', 'N/A')} km/h</span>
                        </div>
                    </div>""", unsafe_allow_html=True)

                st.caption("Live data via AviationStack · updates every 30–60s · refresh to get the latest")

with track_tab2:
    tr_col1, tr_col2 = st.columns(2)
    with tr_col1:
        train_origin_input = st.text_input("Origin", placeholder="e.g. New Delhi", key="train_origin_input")
    with tr_col2:
        train_dest_input = st.text_input("Destination", placeholder="e.g. Mumbai", key="train_dest_input")

    track_train_btn = st.button("🔍 Find Live Tracker", key="track_train_btn")

    if track_train_btn:
        if not train_origin_input.strip() or not train_dest_input.strip():
            st.warning("Enter both origin and destination.")
        else:
            tracker_info = st.session_state.workflow.get_train_tracking_link(
                train_origin_input, train_dest_input
            )
            if not tracker_info.get("ok"):
                st.info(f"ℹ️ {tracker_info.get('reason', 'No tracker found for this route.')}")
            else:
                st.markdown(f"""
                <div class="glass-card">
                    <div style="font-weight:600; color:#e0e0ff; font-size:1.1rem; margin-bottom:0.5rem;">
                        🚂 {tracker_info['name']}
                    </div>
                    <div style="color:rgba(255,255,255,0.6); margin-bottom:0.8rem;">
                        {tracker_info['note']}
                    </div>
                    <a href="{tracker_info['url_template']}" target="_blank" style="
                        display:inline-block; background:linear-gradient(135deg,#4facfe,#00f2fe);
                        color:#0f0c29; font-weight:600; padding:0.5rem 1.2rem; border-radius:8px;
                        text-decoration:none;">
                        Open Live Tracker →
                    </a>
                </div>""", unsafe_allow_html=True)
            st.caption(
                "No single free API covers live train status worldwide, so this links "
                "you straight to the correct official tracker instead of guessing."
            )

# ================================================================== #
# Main Content                                                         #
# ================================================================== #

if submit:
    if not destination or not origin:
        st.error("❌ Please provide both destination and origin")
    elif not validate_dates(departure_date, return_date):
        st.error("❌ Invalid dates — departure must be today or later and before return date")
    else:
        days = calculate_days(departure_date, return_date)
        budget_category = categorize_budget(budget)
        # Auto-detect currency from destination; use it only when user left the
        # selectbox at its default "INR" value AND the destination maps to a
        # different currency — otherwise always respect the user's explicit pick.
        auto_currency = detect_currency(destination, origin)
        effective_currency = auto_currency if (base_currency == "INR" and auto_currency != "INR") else base_currency

        dest_info = get_destination_info(destination)

        # ---- Destination Preview & Live Map ---- #
        col_img, col_map = st.columns([1, 1])
        with col_img:
            st.markdown('<div class="section-header">📸 Destination Preview</div>', unsafe_allow_html=True)
            if dest_info.get("image_url"):
                st.image(dest_info["image_url"], use_container_width=True)
            else:
                st.info("No picture available.")
        
        with col_map:
            st.markdown('<div class="section-header">🗺️ Live Map Location</div>', unsafe_allow_html=True)
            map_html = f'''
                <iframe 
                    width="100%" 
                    height="300" 
                    frameborder="0" 
                    scrolling="no" 
                    marginheight="0" 
                    marginwidth="0" 
                    src="https://maps.google.com/maps?q={destination}&t=&z=10&ie=UTF8&iwloc=&output=embed"
                    style="border-radius: 12px; border: 1px solid rgba(79,172,254,0.15);">
                </iframe>
            '''
            st.components.v1.html(map_html, height=310)

        # ---- Trip Overview Metrics ---- #
        st.markdown('<div class="section-header">📋 Trip Overview</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Destination</div>
            <div class="metric-value">{destination}</div>
        </div>""", unsafe_allow_html=True)
        c2.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Duration</div>
            <div class="metric-value">{days} days</div>
        </div>""", unsafe_allow_html=True)
        c3.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Budget</div>
            <div class="metric-value">{format_currency(budget, effective_currency)}</div>
        </div>""", unsafe_allow_html=True)
        c4.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Category</div>
            <div class="metric-value">{budget_category}</div>
        </div>""", unsafe_allow_html=True)

        # ---- Agent Progress ---- #
        st.markdown('<div class="section-header">🤖 Agent Pipeline</div>', unsafe_allow_html=True)
        progress_placeholder = st.empty()

        def render_progress(completed_agents):
            html = '''
            <div class="glass-card" style="
                display: flex; 
                flex-wrap: nowrap; 
                gap: 0.5rem; 
                justify-content: flex-start; 
                align-items: center; 
                overflow-x: auto; 
                padding-bottom: 0.5rem;
            ">
            '''
            for idx, agent_key in enumerate(AGENT_ORDER):
                label = AGENT_LABELS.get(agent_key, agent_key)
                if agent_key in completed_agents:
                    html += f'<div class="agent-step completed" style="margin:0; flex-shrink:0; white-space:nowrap;">✅ {label}</div>'
                else:
                    html += f'<div class="agent-step pending" style="margin:0; flex-shrink:0; white-space:nowrap;">⬜ {label}</div>'
                
                if idx < len(AGENT_ORDER) - 1:
                    html += '<div style="color:rgba(255,255,255,0.3); font-size:0.8rem; flex-shrink:0;">➔</div>'
            html += '</div>'
            progress_placeholder.markdown(html, unsafe_allow_html=True)

        render_progress([])

        # ---- Run Workflow ---- #
        with st.spinner("🤖 10 AI agents are collaborating on your trip plan..."):
            try:
                initial_state = {
                    "request": f"Plan a trip to {destination}",
                    "destination": destination,
                    "origin": origin,
                    "departure_date": str(departure_date),
                    "return_date": str(return_date),
                    "days": days,
                    "budget": budget,
                    "base_currency": effective_currency,
                    "interests": interests,
                    "preferences": preferences,
                }
                # Smart Caching System
                cache_dir = "trip_cache"
                os.makedirs(cache_dir, exist_ok=True)
                key_str = f"{destination}_{origin}_{str(departure_date)}_{str(return_date)}_{days}_{budget}_{effective_currency}_{'_'.join(sorted(interests))}"
                cache_key = hashlib.md5(key_str.encode('utf-8')).hexdigest()
                cache_path = os.path.join(cache_dir, f"{cache_key}.json")

                if os.path.exists(cache_path):
                    st.toast("Loading instantly from Smart Cache! ⚡", icon="💾")
                    with open(cache_path, "r", encoding="utf-8") as f:
                        result = json.load(f)
                else:
                    result = st.session_state.workflow.run(initial_state)
                    # Remove non-serializable LangChain message objects
                    cacheable_result = {k: v for k, v in result.items() if k != "messages"}
                    try:
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(cacheable_result, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        pass # Silently fail cache save instead of breaking the app
                
                st.session_state.result = result
                
                # Send notifications
                st.toast("Sending WhatsApp & Email notifications...", icon="📨")
                wa_success, wa_msg = send_whatsapp_itinerary(result)
                em_success, em_msg = send_email_itinerary(result, recipient_email=user_email)
                
                if wa_success:
                    st.toast("WhatsApp notification sent!", icon="✅")
                else:
                    st.warning(f"WhatsApp skipped: {wa_msg}")
                    
                if em_success:
                    st.toast("Email notification sent!", icon="✅")
                else:
                    st.warning(f"Email skipped: {em_msg}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                import traceback
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())
                st.stop()

        result = st.session_state.result
        completed = result.get("completed_agents", [])
        render_progress(completed)

        # ============================================================ #
        # RESULTS                                                        #
        # ============================================================ #

        # ---- Research ---- #
        if result.get("research_data"):
            st.markdown('<div class="section-header">🔍 Research Insights</div>', unsafe_allow_html=True)
            with st.expander("View Research Data", expanded=False):
                research = result["research_data"]
                
                def render_json_ui(obj):
                    if isinstance(obj, dict):
                        if "error" in obj and len(obj) == 1:
                            return "<span style='color: #ff5252;'>⚠️ Agent failed due to API rate limits. Please try again later.</span>"
                        res = "<ul style='list-style-type: none; padding-left: 0;'>"
                        for k, v in obj.items():
                            clean_k = k.replace('_', ' ').title()
                            res += f"<li style='margin-bottom: 8px;'><strong style='color:#e0e0ff;'>{clean_k}:</strong> {render_json_ui(v)}</li>"
                        res += "</ul>"
                        return res
                    elif isinstance(obj, list):
                        if not obj:
                            return "None"
                        res = "<ul style='padding-left: 20px;'>"
                        for item in obj:
                            res += f"<li style='margin-bottom: 4px; color:rgba(255,255,255,0.7);'>{render_json_ui(item)}</li>"
                        res += "</ul>"
                        return res
                    else:
                        return f"<span style='color:rgba(255,255,255,0.7);'>{str(obj)}</span>"

                if isinstance(research, (dict, list)):
                    st.markdown(f'<div style="font-size: 0.9rem;">{render_json_ui(research)}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(str(research))

        # ---- Weather ---- #
        if result.get("weather_data"):
            st.markdown('<div class="section-header">🌤️ Weather Forecast</div>', unsafe_allow_html=True)
            weather = result["weather_data"]
            has_live = isinstance(weather, dict) and "current" in weather and "temperature_celsius" in weather.get("current", {})

            if isinstance(weather, dict):
                w1, w2, w3 = st.columns(3)
                current = weather.get("current", {})
                with w1:
                    st.markdown(f"""
                    <div class="glass-card" style="text-align:center;">
                        <div style="font-size:2.5rem;">🌡️</div>
                        <div style="font-size:1.8rem; font-weight:700; color:#4facfe;">
                            {current.get('temperature_celsius', 'N/A')}°C
                        </div>
                        <div style="color:rgba(255,255,255,0.5);">{current.get('condition', 'N/A')}</div>
                        {'<div style="color:#43e97b; font-size:0.7rem; margin-top:0.5rem;">🟢 LIVE DATA</div>' if has_live else '<div style="color:rgba(255,255,255,0.3); font-size:0.7rem; margin-top:0.5rem;">📊 ESTIMATED</div>'}
                    </div>""", unsafe_allow_html=True)
                with w2:
                    st.markdown(f"""
                    <div class="glass-card">
                        <div style="font-weight:600; color:#e0e0ff; margin-bottom:0.5rem;">🧳 Packing List</div>
                        {"".join(f'<div style="color:rgba(255,255,255,0.7); padding:0.2rem 0;">• {item}</div>' for item in weather.get('packing_suggestions', ['Check weather closer to trip'])[:5])}
                    </div>""", unsafe_allow_html=True)
                with w3:
                    st.markdown(f"""
                    <div class="glass-card">
                        <div style="font-weight:600; color:#e0e0ff; margin-bottom:0.5rem;">👕 What to Wear</div>
                        {"".join(f'<div style="color:rgba(255,255,255,0.7); padding:0.2rem 0;">• {item}</div>' for item in weather.get('clothing_recommendations', ['Comfortable clothing'])[:5])}
                    </div>""", unsafe_allow_html=True)

                if weather.get("weather_warnings"):
                    for warning in weather["weather_warnings"]:
                        st.warning(f"⚠️ {warning}")

        # ---- Flights ---- #
        if result.get("flights"):
            st.markdown('<div class="section-header">✈️ Recommended Flights</div>', unsafe_allow_html=True)
            flights_data = result["flights"] if isinstance(result["flights"], dict) else {}
            flights_options = flights_data.get("options", [])
            if flights_options:
                for i, flight in enumerate(flights_options[:3], 1):
                    rec = ""
                    airline = flight.get("airline", "N/A")
                    if airline == flights_data.get("recommended"):
                        rec = '<span style="background:#43e97b; color:#0f0c29; padding:2px 8px; border-radius:10px; font-size:0.7rem; font-weight:600; margin-left:8px;">RECOMMENDED</span>'
                    st.markdown(f"""
                    <div class="result-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-size:1.1rem; font-weight:600; color:#e0e0ff;">
                                    ✈️ {airline}
                                </span>{rec}
                            </div>
                            <div style="font-size:1.3rem; font-weight:700; color:#4facfe;">
                                {format_currency(flight.get('price', 0), result.get('base_currency', effective_currency))}
                            </div>
                        </div>
                        <div style="display:flex; gap:2rem; margin-top:0.5rem; color:rgba(255,255,255,0.5); font-size:0.85rem;">
                            <span>⏱️ {flight.get('duration', 'N/A')}</span>
                            <span>🔄 {flight.get('layovers', 0)} stops</span>
                            <span>🛫 {flight.get('departure_time', 'N/A')}</span>
                            <span>🛬 {flight.get('arrival_time', 'N/A')}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info("Flight data is being processed…")

        # ---- Trains ---- #
        if result.get("trains"):
            st.markdown('<div class="section-header">🚂 Recommended Trains</div>', unsafe_allow_html=True)
            train_data = result["trains"] if isinstance(result["trains"], dict) else {}
            train_options = train_data.get("trains", [])
            
            if train_options:
                for train in train_options[:3]:
                    st.markdown(f"""
                    <div class="glass-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-size:1.1rem; font-weight:600;">
                                🚂 {train.get('train_name', 'Train')} ({train.get('train_number', '')})
                            </div>
                            <div style="font-size:1.3rem; font-weight:700; color:#4facfe;">
                                {format_currency(train.get('price_sleeper', train.get('price_3ac', 0)), result.get('base_currency', effective_currency))}
                            </div>
                        </div>
                        <div style="display:flex; gap:2rem; margin-top:0.5rem; color:rgba(255,255,255,0.5); font-size:0.85rem;">
                            <span>⏱️ {train.get('duration', 'N/A')}</span>
                            <span>🛫 {train.get('departure_time', 'N/A')}</span>
                            <span>🛬 {train.get('arrival_time', 'N/A')}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info("No train options found.")

        # ---- Cabs / Local Transport ---- #
        if result.get("cabs"):
            st.markdown('<div class="section-header">🚖 Local Transport & Cabs</div>', unsafe_allow_html=True)
            cab_data = result["cabs"] if isinstance(result["cabs"], dict) else {}
            
            local_trans = cab_data.get("local_transport", [])
            if local_trans:
                for cab in local_trans[:3]:
                    st.markdown(f"""
                    <div class="glass-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div style="font-size:1.1rem; font-weight:600;">
                                🚖 {cab.get('type', 'Cab')}
                            </div>
                            <div style="font-size:1.3rem; font-weight:700; color:#4facfe;">
                                {format_currency(cab.get('avg_cost_per_km', 0), result.get('base_currency', effective_currency))}<span style="font-size:0.8rem;">/km</span>
                            </div>
                        </div>
                        <div style="margin-top:0.5rem; color:rgba(255,255,255,0.5); font-size:0.85rem;">
                            💡 {cab.get('tip', '')}
                        </div>
                    </div>""", unsafe_allow_html=True)

        # ---- Hotels ---- #
        if result.get("hotels"):
            st.markdown('<div class="section-header">🏨 Recommended Hotels</div>', unsafe_allow_html=True)
            hotel_data = result["hotels"] if isinstance(result["hotels"], dict) else {}
            hotel_options = hotel_data.get("options", [])
            if hotel_options:
                for i, hotel in enumerate(hotel_options[:5], 1):
                    stars = "⭐" * int(hotel.get("stars", 0))
                    best_val = ""
                    if hotel.get("name") == hotel_data.get("best_value"):
                        best_val = '<span style="background:#ffc107; color:#0f0c29; padding:2px 8px; border-radius:10px; font-size:0.7rem; font-weight:600; margin-left:8px;">BEST VALUE</span>'
                    st.markdown(f"""
                    <div class="result-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-size:1.05rem; font-weight:600; color:#e0e0ff;">
                                    🏨 {hotel.get('name', 'N/A')}
                                </span>{best_val}
                                <div style="font-size:0.8rem; margin-top:2px;">{stars}</div>
                            </div>
                            <div style="text-align:right;">
                                <div style="font-size:1.2rem; font-weight:700; color:#4facfe;">
                                    {format_currency(hotel.get('price_per_night', 0), result.get('base_currency', effective_currency))}<span style="font-size:0.8rem; color:rgba(255,255,255,0.4);">/night</span>
                                </div>
                                <div style="font-size:0.8rem; color:rgba(255,255,255,0.4);">
                                    ⭐ {hotel.get('rating', 'N/A')} • 📍 {hotel.get('location', 'N/A')}
                                </div>
                            </div>
                        </div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info("Hotel data is being processed…")

        # ---- Activities ---- #
        if result.get("activities"):
            st.markdown('<div class="section-header">🎯 Top Activities</div>', unsafe_allow_html=True)
            activities_data = result["activities"] if isinstance(result["activities"], dict) else {}
            if isinstance(activities_data, dict):
                # Show only categories that have data
                active_categories = {k: v for k, v in activities_data.items() if v and isinstance(v, list)}
                if active_categories:
                    tabs = st.tabs([f"{'🏔️' if k=='adventure' else '🧘' if k=='relaxation' else '👨‍👩‍👧' if k=='family' else '🏛️' if k=='culture' else '🍽️' if k=='food' else '🌙'} {k.title()}" for k in active_categories.keys()])
                    for tab, (category, items) in zip(tabs, active_categories.items()):
                        with tab:
                            for act in items[:4]:
                                if isinstance(act, dict):
                                    st.markdown(f"""
                                    <div class="result-card">
                                        <div style="font-weight:600; color:#e0e0ff;">{act.get('name', 'N/A')}</div>
                                        <div style="color:rgba(255,255,255,0.6); font-size:0.85rem; margin-top:0.3rem;">
                                            {act.get('description', '')}
                                        </div>
                                        <div style="display:flex; gap:1.5rem; margin-top:0.5rem; color:rgba(255,255,255,0.4); font-size:0.8rem;">
                                            <span>⏱️ {act.get('duration', 'N/A')}</span>
                                            <span>💵 {format_currency(act.get('price', 0), result.get('base_currency', effective_currency))}</span>
                                            <span>⭐ {act.get('rating', 'N/A')}</span>
                                        </div>
                                    </div>""", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"- {act}")
            else:
                st.info("Activity data is being processed…")

        # ---- Visa Requirements ---- #
        if result.get("visa_info"):
            st.markdown('<div class="section-header">📋 Visa Requirements</div>', unsafe_allow_html=True)
            visa = result["visa_info"] if isinstance(result["visa_info"], dict) else {}
            if isinstance(visa, dict):
                visa_required = visa.get("visa_required", True)
                badge_class = "badge-warning" if visa_required else "badge-safe"
                badge_text = "VISA REQUIRED" if visa_required else "VISA FREE"

                v1, v2 = st.columns([1, 2])
                with v1:
                    st.markdown(f"""
                    <div class="glass-card" style="text-align:center;">
                        <div style="font-size:3rem;">📋</div>
                        <div class="safety-badge {badge_class}" style="margin-top:0.5rem;">{badge_text}</div>
                        <div style="color:rgba(255,255,255,0.6); margin-top:0.5rem; font-size:0.85rem;">
                            Type: {visa.get('visa_type', 'N/A')}
                        </div>
                        <div style="color:rgba(255,255,255,0.5); font-size:0.8rem;">
                            Fee: {visa.get('visa_fee', 'N/A')}
                        </div>
                        <div style="color:rgba(255,255,255,0.5); font-size:0.8rem;">
                            Processing: {visa.get('processing_time', 'N/A')}
                        </div>
                    </div>""", unsafe_allow_html=True)
                with v2:
                    docs = visa.get("documents_required", [])
                    if docs:
                        html_docs = '<div class="glass-card"><div style="font-weight:600; color:#e0e0ff; margin-bottom:0.5rem;">📄 Required Documents</div><ul style="margin-bottom:0;">'
                        for doc in docs:
                            html_docs += f'<li style="margin-bottom:0.3rem;">{doc}</li>'
                        html_docs += '</ul></div>'
                        st.markdown(html_docs, unsafe_allow_html=True)

                    tips = visa.get("tips", [])
                    if tips:
                        for tip in tips[:3]:
                            st.info(f"💡 {tip}")

        # ---- Safety Advisory ---- #
        if result.get("safety_info"):
            st.markdown('<div class="section-header">🛡️ Safety Advisory</div>', unsafe_allow_html=True)
            safety = result["safety_info"] if isinstance(result["safety_info"], dict) else {}
            if isinstance(safety, dict):
                rating = safety.get("safety_rating", "").lower()
                if "safe" in rating or "low" in rating:
                    badge_cls, badge_txt = "badge-safe", "SAFE"
                elif "moderate" in rating or "medium" in rating:
                    badge_cls, badge_txt = "badge-caution", "MODERATE"
                else:
                    badge_cls, badge_txt = "badge-warning", "CAUTION"

                s1, s2, s3 = st.columns(3)
                with s1:
                    st.markdown(f"""
                    <div class="glass-card" style="text-align:center;">
                        <div style="font-size:2.5rem;">🛡️</div>
                        <div class="safety-badge {badge_cls}" style="margin-top:0.5rem;">{badge_txt}</div>
                        <div style="color:rgba(255,255,255,0.6); margin-top:0.5rem; font-size:0.85rem;">
                            {safety.get('overall_assessment', 'N/A')}
                        </div>
                    </div>""", unsafe_allow_html=True)
                with s2:
                    emergency = safety.get("emergency_numbers", {})
                    st.markdown(f"""
                    <div class="glass-card">
                        <div style="font-weight:600; color:#e0e0ff; margin-bottom:0.5rem;">🚨 Emergency Numbers</div>
                        <div style="color:rgba(255,255,255,0.7); padding:0.2rem 0;">🚔 Police: {emergency.get('police', 'N/A')}</div>
                        <div style="color:rgba(255,255,255,0.7); padding:0.2rem 0;">🚑 Ambulance: {emergency.get('ambulance', 'N/A')}</div>
                        <div style="color:rgba(255,255,255,0.7); padding:0.2rem 0;">🚒 Fire: {emergency.get('fire', 'N/A')}</div>
                        <div style="color:rgba(255,255,255,0.7); padding:0.2rem 0;">📞 Tourist: {emergency.get('tourist_helpline', 'N/A')}</div>
                    </div>""", unsafe_allow_html=True)
                with s3:
                    health = safety.get("health_tips", {})
                    vaccines = health.get("vaccinations_recommended", [])
                    st.markdown(f"""
                    <div class="glass-card">
                        <div style="font-weight:600; color:#e0e0ff; margin-bottom:0.5rem;">💊 Health Tips</div>
                        <div style="color:rgba(255,255,255,0.7); padding:0.2rem 0;">💧 Water: {health.get('water_safety', 'N/A')}</div>
                        {"".join(f'<div style="color:rgba(255,255,255,0.6); padding:0.1rem 0;">💉 {v}</div>' for v in vaccines[:3])}
                    </div>""", unsafe_allow_html=True)

                scams = safety.get("scam_warnings", [])
                if scams:
                    with st.expander("⚠️ Common Scams to Watch For"):
                        for scam in scams:
                            st.warning(scam)

        # ---- Budget Breakdown ---- #
        if result.get("budget_breakdown"):
            st.markdown('<div class="section-header">💰 Budget Breakdown</div>', unsafe_allow_html=True)
            budget_data = result["budget_breakdown"] if isinstance(result["budget_breakdown"], dict) else {}
            if isinstance(budget_data, dict):
                b1, b2 = st.columns([3, 2])

                skip_keys = {"total", "remaining", "daily_budget", "warnings", "budget_status", "savings_tips"}
                expense_items = {k: v for k, v in budget_data.items() if k not in skip_keys and isinstance(v, (int, float))}

                with b1:
                    st.markdown("#### 📊 Expense Breakdown")
                    for key, value in expense_items.items():
                        st.markdown(f"""
                        <div class="budget-item">
                            <span>{key.replace('_', ' ').title()}</span>
                            <span style="font-weight:600; color:#4facfe;">{format_currency(value, result.get('base_currency', effective_currency))}</span>
                        </div>""", unsafe_allow_html=True)

                    # Interactive 3D Donut Chart using Plotly
                    if expense_items:
                        chart_df = pd.DataFrame({
                            "Category": [k.replace("_", " ").title() for k in expense_items.keys()],
                            "Amount": list(expense_items.values()),
                        })
                        fig = px.pie(
                            chart_df, 
                            values="Amount", 
                            names="Category", 
                            hole=0.6,
                            color_discrete_sequence=px.colors.sequential.Tealgrn
                        )
                        fig.update_layout(
                            showlegend=False,
                            margin=dict(t=0, b=0, l=0, r=0),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)"
                        )
                        fig.update_traces(
                            textposition='inside', 
                            textinfo='percent+label',
                            hoverinfo='label+value',
                            marker=dict(line=dict(color='#0f0c29', width=2))
                        )
                        st.plotly_chart(fig, use_container_width=True)

                with b2:
                    st.markdown("#### 📋 Summary")
                    total = budget_data.get("total", 0)
                    remaining = budget_data.get("remaining", 0)
                    daily = budget_data.get("daily_budget", 0)
                    status = budget_data.get("budget_status", "")

                    status_color = "#43e97b" if status == "within_budget" else "#ffc107" if status == "tight" else "#ff5252"
                    st.markdown(f"""
                    <div class="glass-card">
                        <div style="margin-bottom:1rem;">
                            <div class="metric-label">Total Cost</div>
                            <div style="font-size:1.8rem; font-weight:700; color:#4facfe;">{format_currency(total, result.get('base_currency', effective_currency))}</div>
                        </div>
                        <div style="margin-bottom:1rem;">
                            <div class="metric-label">Remaining</div>
                            <div style="font-size:1.4rem; font-weight:600; color:{status_color};">{format_currency(remaining, result.get('base_currency', effective_currency))}</div>
                        </div>
                        <div style="margin-bottom:1rem;">
                            <div class="metric-label">Daily Budget</div>
                            <div style="font-size:1.2rem; font-weight:500; color:#e0e0ff;">{format_currency(daily, result.get('base_currency', effective_currency))}</div>
                        </div>
                        <div class="metric-label">Status</div>
                        <div style="color:{status_color}; font-weight:600; text-transform:uppercase;">
                            {status.replace('_', ' ')}
                        </div>
                    </div>""", unsafe_allow_html=True)

                    warnings = budget_data.get("warnings", [])
                    for w in warnings:
                        st.warning(w)

                    tips = budget_data.get("savings_tips", [])
                    if tips:
                        with st.expander("💡 Savings Tips"):
                            for tip in tips:
                                st.info(tip)

        # ---- Itinerary ---- #
        if result.get("itinerary"):
            st.markdown('<div class="section-header">📅 Day-by-Day Itinerary</div>', unsafe_allow_html=True)
            itinerary_data = result["itinerary"] if isinstance(result["itinerary"], dict) else {}
            if isinstance(itinerary_data, dict):
                if "error" in itinerary_data:
                    st.error(f"⚠️ Could not generate itinerary: {itinerary_data['error']}")
                else:
                    for day, schedule in itinerary_data.items():
                        day_label = day.replace("_", " ").title()
                        theme = ""
                        if isinstance(schedule, dict) and schedule.get("theme"):
                            theme = f" — {schedule['theme']}"
                        with st.expander(f"📆 {day_label}{theme}", expanded=False):
                            if isinstance(schedule, dict):
                                for period in ["morning", "afternoon", "evening"]:
                                    acts = schedule.get(period, [])
                                    if not acts:
                                        continue
                                    period_emoji = "🌅" if period == "morning" else "☀️" if period == "afternoon" else "🌙"
                                    st.markdown(f"**{period_emoji} {period.title()}**")
                                    items = acts if isinstance(acts, list) else [acts]
                                    for item in items:
                                        if isinstance(item, dict):
                                            time = item.get("time", "")
                                            name = item.get("activity_name", item.get("name", ""))
                                            loc = item.get("location", "")
                                            cost = item.get("cost", "")
                                            notes = item.get("notes", "")
                                            st.markdown(f"""
                                            <div class="result-card">
                                                <div style="display:flex; justify-content:space-between;">
                                                    <span style="font-weight:600; color:#e0e0ff;">
                                                        🕐 {time} — {name}
                                                    </span>{f' <span style="color:#4facfe;">{format_currency(cost, result.get("base_currency", effective_currency))}</span>' if cost else ''}
                                                </div>
                                                {f'<div style="color:rgba(255,255,255,0.5); font-size:0.8rem;">📍 {loc}</div>' if loc else ''}
                                                {f'<div style="color:rgba(255,255,255,0.4); font-size:0.8rem; margin-top:0.2rem;">💡 {notes}</div>' if notes else ''}
                                            </div>""", unsafe_allow_html=True)
                                        else:
                                            st.write(f"  - {item}")
            else:
                st.info("Itinerary is being generated…")

        # ---- Booking ---- #
        if result.get("booking_info"):
            st.markdown('<div class="section-header">📱 Booking Information</div>', unsafe_allow_html=True)
            booking_data = result["booking_info"] if isinstance(result["booking_info"], dict) else {}
            if isinstance(booking_data, dict):
                st.warning("⚠️ This is for information only. We do not process actual payments or bookings.")

                bk1, bk2 = st.columns(2)
                with bk1:
                    steps = booking_data.get("booking_steps", [])
                    if steps:
                        st.markdown("#### 📝 Steps to Book")
                        for i, step in enumerate(steps, 1):
                            st.markdown(f"**{i}.** {step}")

                with bk2:
                    links = booking_data.get("links", {})
                    tips = booking_data.get("tips", [])
                    best_time = booking_data.get("best_booking_time", "")

                    st.markdown("#### 🔗 Quick Links & Tips")
                    if links.get("flights"):
                        st.markdown(f"✈️ [Book Flights]({links['flights']})")
                    if links.get("hotels"):
                        st.markdown(f"🏨 [Book Hotels]({links['hotels']})")
                    if links.get("activities"):
                        st.markdown(f"🎯 [Book Activities]({links['activities']})")
                    if best_time:
                        st.info(f"⏰ Best time to book: {best_time}")
                    for tip in tips[:3]:
                        st.success(f"💡 {tip}")

        # ---- Export ---- #
        st.markdown('<div class="section-header">📥 Export Your Trip</div>', unsafe_allow_html=True)
        export_data = {
            "trip": {
                "destination": destination,
                "origin": origin,
                "dates": {"departure": str(departure_date), "return": str(return_date)},
                "duration_days": days,
                "base_currency": base_currency,
                "interests": interests,
            },
            "results": {k: v for k, v in result.items() if k not in ("messages", "completed_agents", "next_agent", "current_agent")},
        }

        e1, e2 = st.columns(2)
        with e1:
            st.download_button(
                label="📄 Download Trip Plan (JSON)",
                data=json.dumps(export_data, indent=2, default=str),
                file_name=f"trip_to_{destination.replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True,
            )
        with e2:
            # Markdown export
            md_content = f"# Trip to {destination}\n\n"
            md_content += f"**From:** {origin} | **Dates:** {departure_date} → {return_date} | **Budget:** {format_currency(budget, effective_currency)}\n\n"

            md_content += f"---\n\n{json.dumps(export_data['results'], indent=2, default=str)}"
            st.download_button(
                label="📝 Download as Markdown",
                data=md_content,
                file_name=f"trip_to_{destination.replace(' ', '_')}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        # Calendar ICS Export
        if export_data['results'].get("itinerary"):
            def generate_ics(dest, start_str, itin_dict):
                ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//AI Travel Planner//EN\n"
                try:
                    curr_date = pd.to_datetime(start_str)
                    for day, sched in itin_dict.items():
                        if isinstance(sched, dict):
                            theme = sched.get("theme", "Exploration")
                            dt_str = curr_date.strftime("%Y%m%d")
                            end_str = (curr_date + pd.Timedelta(days=1)).strftime("%Y%m%d")
                            ics += "BEGIN:VEVENT\n"
                            ics += f"DTSTART;VALUE=DATE:{dt_str}\n"
                            ics += f"DTEND;VALUE=DATE:{end_str}\n"
                            ics += f"SUMMARY:Day in {dest} - {theme}\n"
                            ics += "END:VEVENT\n"
                        curr_date += pd.Timedelta(days=1)
                except Exception:
                    pass
                ics += "END:VCALENDAR"
                return ics

            ics_content = generate_ics(
                destination, 
                departure_date, 
                export_data['results']["itinerary"]
            )
            st.download_button(
                label="📅 Export to Apple/Google Calendar (.ics)",
                data=ics_content,
                file_name=f"{destination.replace(' ', '_')}_Trip.ics",
                mime="text/calendar",
                use_container_width=True,
            )

# ================================================================== #
# Footer                                                               #
# ================================================================== #
