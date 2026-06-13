"""
bot.py — Conversation state machine for the LagosGo WhatsApp bot.

States: NEW → AWAITING_NAME → AWAITING_ORIGIN → AWAITING_DESTINATION → AWAITING_ARRIVE_BY → READY

Commands (always available):
  CHECK / GO   — run optimizer now
  ROUTES       — list saved routes
  ADD          — start adding a new route
  DELETE label — remove a route
  PAUSE/RESUME — toggle morning alerts
  UPGRADE      — premium info
  HELP         — command list
"""

import re
from typing import Optional
from app import db, traffic, ads

_sessions: dict[str, dict] = {}


def _session(phone: str) -> dict:
    if phone not in _sessions:
        _sessions[phone] = {"state": "IDLE", "temp": {}}
    return _sessions[phone]


def _set_state(phone: str, state: str, **temp_data) -> None:
    s = _session(phone)
    s["state"] = state
    s["temp"].update(temp_data)


def _clear_temp(phone: str) -> None:
    _sessions[phone]["temp"] = {}


HELP_TEXT = """\
🚦 *LagosGo Commands*

*CHECK* — Optimal departure time for your route
*ADD* — Save a new route
*ROUTES* — List your saved routes
*DELETE [name]* — Remove a route (e.g. DELETE Work)
*PAUSE* — Stop morning alerts
*RESUME* — Turn morning alerts back on
*UPGRADE* — Go ad-free with LagosGo Premium
*HELP* — Show this menu

Reply with a command or just say *GO* when you need to leave."""


async def handle_message(phone: str, body: str) -> str:
    text = body.strip()
    cmd = text.upper().split()[0] if text else ""
    user = db.get_user(phone)
    session = _session(phone)
    state = session["state"]

    # ── Global commands ──────────────────────────────────────────────────────────────────
    if cmd in ("HELP", "MENU", "HI", "HELLO", "START"):
        if not user:
            db.upsert_user(phone)
            _set_state(phone, "AWAITING_NAME")
            return (
                "👋 Welcome to *LagosGo* — your Lagos commute optimizer!\n\n"
                "I'll tell you the *exact minute to leave* based on live traffic.\n\n"
                "First, what's your name?"
            )
        return HELP_TEXT

    if cmd == "UPGRADE":
        return (
            "💎 *LagosGo Premium — ₦1,500/month*\n\n"
            "✅ No ads in messages\n"
            "✅ Up to 5 saved routes\n"
            "✅ Alerts 30, 15 & 5 mins before optimal window\n"
            "✅ Weekend traffic patterns\n\n"
            "To subscribe, send your payment to:\n"
            "*Bank:* Opay · *Acc:* 8012345678 · *Name:* LagosGo Ltd\n\n"
            "Then reply *PAID* with your payment screenshot. We verify within 1 hour."
        )

    # ── State machine ────────────────────────────────────────────────────────────────────
    if state == "AWAITING_NAME":
        name = text.strip().title()
        db.upsert_user(phone, name=name)
        _set_state(phone, "AWAITING_ORIGIN", name=name)
        return (
            f"Nice to meet you, *{name}*! 🙌\n\n"
            "Let's set up your first route.\n\n"
            "📍 What's your *home address or area*?\n"
            "_e.g. Lekki Phase 1, Ikeja GRA, Surulere_"
        )

    if state == "AWAITING_ORIGIN":
        _set_state(phone, "AWAITING_DESTINATION", origin=text)
        return (
            f"Got it — *{text}*\n\n"
            "🏢 Now, what's your *destination / workplace*?\n"
            "_e.g. Victoria Island, Oshodi, Ikeja City Mall_"
        )

    if state == "AWAITING_DESTINATION":
        _set_state(phone, "AWAITING_ARRIVE_BY", destination=text)
        return (
            f"Got it — *{text}*\n\n"
            "⏰ What time do you need to *arrive*? (Lagos time, 24h)\n"
            "_e.g. 08:30 for 8:30 AM, 17:00 for 5 PM_"
        )

    if state == "AWAITING_ARRIVE_BY":
        match = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if not match:
            return "⚠️ Please use HH:MM format, e.g. *08:30* or *17:00*"
        hour, minute = int(match.group(1)), int(match.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return "⚠️ That doesn't look like a valid time. Try again, e.g. *08:30*"

        temp = session["temp"]
        label = _next_route_label(phone)
        db.upsert_route(
            phone=phone, label=label,
            origin=temp.get("origin", ""),
            destination=temp.get("destination", ""),
            arrive_by=text, alert_enabled=True,
        )
        _set_state(phone, "IDLE")
        _clear_temp(phone)
        return (
            f"✅ Route *{label}* saved!\n\n"
            f"📍 {temp.get('origin')} → {temp.get('destination')}\n"
            f"⏰ Arrive by: {text}\n\n"
            "I'll send you a morning alert before your commute.\n\n"
            "Reply *CHECK* to get your optimal departure time right now, or *HELP* for all commands."
        )

    if state == "AWAITING_LABEL_FOR_ADD":
        label = text.title()
        _set_state(phone, "AWAITING_ORIGIN", route_label=label)
        return f"Great — new route *{label}*.\n\n📍 What's the *origin* for this route?"

    # ── ADD ──────────────────────────────────────────────────────────────────────────
    if cmd == "ADD":
        if user and not user.get("is_premium"):
            routes = db.get_routes(phone)
            if len(routes) >= 1:
                return (
                    "🔒 Free tier supports 1 route.\n\n"
                    "Reply *UPGRADE* to save up to 5 routes with Premium."
                )
        _set_state(phone, "AWAITING_LABEL_FOR_ADD")
        return "What do you want to name this route? _(e.g. Work, School, Gym)_"

    # ── ROUTES ──────────────────────────────────────────────────────────────────────
    if cmd == "ROUTES":
        routes = db.get_routes(phone)
        if not routes:
            return "You have no saved routes. Reply *ADD* to set one up."
        lines = ["📋 *Your routes:*", ""]
        for r in routes:
            icon = "🔔" if r["alert_enabled"] else "🔕"
            lines.append(f"{icon} *{r['label']}* — {r['origin']} → {r['destination']} (arrive {r['arrive_by']})")
        return "\n".join(lines)

    # ── DELETE ──────────────────────────────────────────────────────────────────────
    if cmd == "DELETE":
        parts = text.split(maxsplit=1)
        label = parts[1].title() if len(parts) > 1 else ""
        if not label:
            return "Please specify a route to delete, e.g. *DELETE Work*"
        route = db.get_route(phone, label)
        if not route:
            return f"No route named *{label}* found. Reply *ROUTES* to see your list."
        db.delete_route(phone, label)
        return f"✅ Route *{label}* deleted."

    # ── PAUSE / RESUME ────────────────────────────────────────────────────────────────
    if cmd in ("PAUSE", "STOP"):
        for r in db.get_routes(phone):
            db.toggle_alert(phone, r["label"], False)
        return "🔕 Morning alerts paused. Reply *RESUME* to turn them back on."

    if cmd == "RESUME":
        for r in db.get_routes(phone):
            db.toggle_alert(phone, r["label"], True)
        return "🔔 Morning alerts are back on!"

    # ── CHECK / GO ────────────────────────────────────────────────────────────────────
    if cmd in ("CHECK", "GO", "NOW", "COMMUTE"):
        if not user:
            return "Reply *HI* to get started with LagosGo! 🚦"
        routes = db.get_routes(phone)
        if not routes:
            return "You have no saved routes. Reply *ADD* to set one up first."
        route = routes[0]
        arrive_h, arrive_m = map(int, route["arrive_by"].split(":"))
        result = await traffic.find_optimal_departure(
            origin=route["origin"],
            destination=route["destination"],
            arrive_by_hour=arrive_h,
            arrive_by_minute=arrive_m,
        )
        message = traffic.format_recommendation(result, user_name=user.get("name", ""))
        return ads.append_ad(message, phone, is_premium=user.get("is_premium", False))

    # ── PAID ─────────────────────────────────────────────────────────────────────────
    if cmd == "PAID":
        return "✅ Payment received! We'll verify and activate your Premium within 1 hour.\n\nThank you 🙏"

    # ── Fallback ───────────────────────────────────────────────────────────────────
    if not user:
        db.upsert_user(phone)
        _set_state(phone, "AWAITING_NAME")
        return (
            "👋 Welcome to *LagosGo*!\n\n"
            "I'll tell you the *exact minute to leave* to beat Lagos traffic.\n\n"
            "What's your name?"
        )

    return "🤔 I didn't catch that. Reply *HELP* for commands, or *GO* for your commute update."


def _next_route_label(phone: str) -> str:
    routes = db.get_routes(phone)
    if not routes:
        return "Home→Work"
    return f"Route {len(routes) + 1}"
