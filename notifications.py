import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config


# =========================================================================== #
# Formatters                                                                   #
# =========================================================================== #

def format_itinerary_summary(state_data: dict) -> str:
    dest   = state_data.get("destination", "Unknown Destination")
    dates  = f"{state_data.get('departure_date', '?')} to {state_data.get('return_date', '?')}"
    budget = state_data.get("budget", 0)
    curr   = state_data.get("base_currency", "USD")

    itin_data = state_data.get("itinerary", {})
    if isinstance(itin_data, str):
        try:
            itin_data = json.loads(itin_data)
        except Exception:
            itin_data = {}

    summary  = f"✈️ *Your AI Travel Itinerary is Ready!*\n"
    summary += f"📍 Destination: {dest}\n"
    summary += f"📅 Dates: {dates}\n"
    summary += f"💰 Budget: {budget:,} {curr}\n\n"

    # Try day-list format first
    days_list = None
    if isinstance(itin_data, dict):
        if "days" in itin_data:
            days_list = itin_data["days"]
        else:
            # Keys like "day_1", "day_2"...
            days_list = [v for k, v in itin_data.items() if k.startswith("day_")]

    if days_list:
        summary += "*Highlights:*\n"
        for i, day in enumerate(days_list[:3]):
            if isinstance(day, dict):
                summary += f"Day {day.get('day', i+1)}: {day.get('theme', 'Exploration')}\n"
        if len(days_list) > 3:
            summary += "...and more! Check your email for full details.\n"
    else:
        summary += "Your trip has been planned! Check your email for full details.\n"

    summary += "\nSafe Travels! 🌍\n_Sent by AI Autonomous Travel Planner_"
    return summary


def format_email_html(state_data: dict) -> str:
    dest   = state_data.get("destination", "Unknown")
    origin = state_data.get("origin", "")
    dep    = state_data.get("departure_date", "")
    ret    = state_data.get("return_date", "")
    budget = state_data.get("budget", 0)
    curr   = state_data.get("base_currency", "USD")

    section_keys = [
        "research_data", "weather_data", "flights", "trains", "cabs",
        "hotels", "activities", "visa_info", "safety_info",
        "budget_breakdown", "itinerary", "booking_info",
    ]

    html = f"""
<html>
<head>
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; color: #333; margin: 0; padding: 0; }}
    .container {{ max-width: 680px; margin: 30px auto; background: #fff; border-radius: 12px;
                  box-shadow: 0 4px 24px rgba(0,0,0,0.10); overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #0f3460, #16213e); color: #fff;
               padding: 32px 28px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 2rem; }}
    .header p  {{ margin: 6px 0 0; opacity: .75; font-size: .95rem; }}
    .trip-meta {{ display: flex; justify-content: space-around; background: #eef2ff;
                  padding: 18px; flex-wrap: wrap; gap: 12px; }}
    .meta-item {{ text-align: center; }}
    .meta-label {{ font-size: .75rem; color: #888; text-transform: uppercase; }}
    .meta-value {{ font-size: 1.1rem; font-weight: 700; color: #0f3460; }}
    .section {{ padding: 20px 28px; border-bottom: 1px solid #eee; }}
    .section h3 {{ color: #0f3460; margin-bottom: 10px; }}
    pre {{ background: #f8f9fa; padding: 14px; border-radius: 8px; font-size: .82rem;
           overflow-x: auto; white-space: pre-wrap; word-break: break-word; }}
    .footer {{ background: #f8f9fa; padding: 18px 28px; text-align: center;
               font-size: .8rem; color: #888; }}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>✈️ Your AI Travel Plan to {dest}</h1>
    <p>Powered by 12 AI Agents • LangGraph • Groq AI</p>
  </div>
  <div class="trip-meta">
    <div class="meta-item"><div class="meta-label">From</div><div class="meta-value">{origin}</div></div>
    <div class="meta-item"><div class="meta-label">To</div><div class="meta-value">{dest}</div></div>
    <div class="meta-item"><div class="meta-label">Depart</div><div class="meta-value">{dep}</div></div>
    <div class="meta-item"><div class="meta-label">Return</div><div class="meta-value">{ret}</div></div>
    <div class="meta-item"><div class="meta-label">Budget</div><div class="meta-value">{budget:,} {curr}</div></div>
  </div>
"""

    section_icons = {
        "research_data": "🔍", "weather_data": "🌤️", "flights": "✈️",
        "trains": "🚂", "cabs": "🚖", "hotels": "🏨", "activities": "🎯",
        "visa_info": "📋", "safety_info": "🛡️", "budget_breakdown": "💰",
        "itinerary": "📅", "booking_info": "📱",
    }

    def json_to_html(obj):
        if isinstance(obj, dict):
            if "error" in obj and len(obj) == 1:
                return "<span style='color: #ff5252;'>⚠️ Agent failed due to API rate limits. Please try again later.</span>"
            res = "<ul style='list-style-type: none; padding-left: 0; margin-top: 5px;'>"
            for k, v in obj.items():
                clean_k = k.replace('_', ' ').title()
                res += f"<li style='margin-bottom: 8px;'><strong style='color:#0f3460;'>{clean_k}:</strong> {json_to_html(v)}</li>"
            res += "</ul>"
            return res
        elif isinstance(obj, list):
            if not obj:
                return "None"
            res = "<ul style='padding-left: 20px; margin-top: 5px;'>"
            for item in obj:
                res += f"<li style='margin-bottom: 4px;'>{json_to_html(item)}</li>"
            res += "</ul>"
            return res
        else:
            return str(obj)

    for key in section_keys:
        data = state_data.get(key)
        if data:
            icon  = section_icons.get(key, "📌")
            title = key.replace("_", " ").title()
            body  = json_to_html(data) if isinstance(data, (dict, list)) else str(data)
            html += f"""
  <div class="section">
    <h3>{icon} {title}</h3>
    <div style="font-size: 0.9rem; line-height: 1.5;">{body}</div>
  </div>"""

    html += """
  <div class="footer">
    Safe Travels! 🌍<br>
    <strong>AI Autonomous Travel Planner</strong> — Powered by Groq AI &amp; LangGraph
  </div>
</div>
</body>
</html>"""
    return html


# =========================================================================== #
# WhatsApp via Twilio                                                           #
# =========================================================================== #

def send_whatsapp_itinerary(state_data: dict) -> tuple[bool, str]:
    """Send WhatsApp summary via Twilio. Returns (success, message)."""
    sid   = Config.TWILIO_ACCOUNT_SID
    token = Config.TWILIO_AUTH_TOKEN

    if not sid or not token or sid.startswith("your_") or token.startswith("your_"):
        return False, "Twilio credentials not configured in .env"

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        body   = format_itinerary_summary(state_data)

        # Recipient — prefer EMERGENCY_PHONE, then EMERGENCY_CONTACTS (legacy)
        to_number = Config.EMERGENCY_PHONE or getattr(Config, "EMERGENCY_CONTACTS", "")
        if not to_number:
            return False, "No recipient phone number set (EMERGENCY_PHONE in .env)"

        # Normalise: must start with +
        to_number = to_number.strip()
        if not to_number.startswith("+"):
            to_number = "+" + to_number

        from_wa = f"whatsapp:{Config.TWILIO_WHATSAPP_NUMBER}"
        to_wa   = f"whatsapp:{to_number}"

        msg = client.messages.create(body=body, from_=from_wa, to=to_wa)
        return True, f"WhatsApp sent! SID: {msg.sid}"

    except ImportError:
        return False, "twilio package not installed — run: pip install twilio"
    except Exception as e:
        return False, f"Twilio error: {e}"


# =========================================================================== #
# Email via SMTP                                                                #
# =========================================================================== #

def send_email_itinerary(state_data: dict, recipient_email: str = None) -> tuple[bool, str]:
    """Send detailed HTML email. Returns (success, message)."""
    sender    = Config.EMAIL_ADDRESS
    password  = Config.EMAIL_PASSWORD
    recipient = recipient_email if recipient_email else Config.EMERGENCY_EMAIL

    if not sender or not password:
        return False, "Email credentials not set in .env (EMAIL_ADDRESS / EMAIL_PASSWORD)"
    if not recipient or recipient == "recipient@gmail.com":
        return False, "Recipient email not configured (provide in UI or set EMERGENCY_EMAIL in .env)"

    try:
        msg = MIMEMultipart("alternative")
        dest = state_data.get("destination", "Unknown")
        msg["Subject"] = f"✈️ Your AI Trip to {dest} is Ready!"
        msg["From"]    = sender
        msg["To"]      = recipient

        html_content = format_email_html(state_data)
        msg.attach(MIMEText(html_content, "html"))

        # Try Gmail TLS (port 587) first, fall back to SSL (port 465)
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
            server.ehlo()
            server.starttls()
            server.login(sender, password)
        except Exception:
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15)
            server.login(sender, password)

        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        return True, f"Email sent to {recipient}!"

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail login failed. Make sure you're using an App Password "
            "(not your regular Gmail password). "
            "Enable at: myaccount.google.com → Security → App Passwords"
        )
    except Exception as e:
        return False, f"Email error: {e}"
