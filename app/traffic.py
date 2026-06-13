"""
traffic.py — Google Maps traffic optimizer for Lagos routes.

Core logic: query the Directions API at 5-minute departure intervals
over the next 2 hours, find the slot with the shortest travel time,
and return a human-readable recommendation.
"""

import os
import time
import math
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional


GMAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"

# Lagos is UTC+1 year-round (no DST)
LAGOS_TZ_OFFSET = 1  # hours ahead of UTC


def _lagos_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=LAGOS_TZ_OFFSET)


def _unix(dt: datetime) -> int:
    """Convert a datetime to Unix timestamp (int)."""
    return int(dt.replace(tzinfo=timezone.utc).timestamp() - LAGOS_TZ_OFFSET * 3600)


async def query_travel_time(origin: str, destination: str, departure_unix: int) -> Optional[int]:
    """
    Returns travel time in seconds for a given departure Unix timestamp.
    Returns None on API error or no route found.
    """
    params = {
        "origin": origin,
        "destination": destination,
        "departure_time": departure_unix,
        "traffic_model": "best_guess",
        "key": GMAPS_API_KEY,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(DIRECTIONS_URL, params=params)
        data = resp.json()

    if data.get("status") != "OK":
        return None

    try:
        leg = data["routes"][0]["legs"][0]
        # duration_in_traffic is the traffic-aware duration
        return leg.get("duration_in_traffic", leg["duration"])["value"]
    except (KeyError, IndexError):
        return None


async def find_optimal_departure(
    origin: str,
    destination: str,
    arrive_by_hour: int,
    arrive_by_minute: int,
    window_minutes: int = 120,
    step_minutes: int = 5,
) -> dict:
    """
    Scans departure times from now → arrive_by time in `step_minutes` steps.
    Returns the slot with the shortest in-traffic travel time.
    """
    now = _lagos_now()

    target = now.replace(hour=arrive_by_hour, minute=arrive_by_minute, second=0, microsecond=0)
    if target < now:
        target += timedelta(days=1)

    earliest = target - timedelta(minutes=window_minutes)
    if earliest < now:
        earliest = now

    slots = []
    cursor = earliest
    while cursor <= target:
        dep_unix = int(cursor.timestamp())
        duration = await query_travel_time(origin, destination, dep_unix)
        if duration is not None:
            slots.append((cursor, duration))
        cursor += timedelta(minutes=step_minutes)

    if not slots:
        return {"error": "Could not fetch traffic data. Check your API key or try again."}

    optimal_dt, optimal_secs = min(slots, key=lambda x: x[1])
    current_secs = slots[0][1]
    savings = max(0, current_secs - optimal_secs)

    return {
        "optimal_departure": optimal_dt,
        "optimal_duration_mins": math.ceil(optimal_secs / 60),
        "current_duration_mins": math.ceil(current_secs / 60),
        "savings_mins": math.ceil(savings / 60),
        "slots": slots,
        "origin": origin,
        "destination": destination,
    }


def format_recommendation(result: dict, user_name: str = "") -> str:
    """Turn the optimizer result into a WhatsApp-ready message."""
    if "error" in result:
        return f"❌ {result['error']}"

    dep = result["optimal_departure"]
    dep_str = dep.strftime("%-I:%M %p")
    dur = result["optimal_duration_mins"]
    cur = result["current_duration_mins"]
    sav = result["savings_mins"]
    greeting = f"Hey {user_name}! " if user_name else ""

    lines = [
        f"🚦 *LagosGo Commute Update*",
        "",
        f"{greeting}Leave at *{dep_str}* for your best window.",
        f"⏱ Travel time: ~{dur} mins",
    ]

    if sav >= 3:
        lines.append(f"✅ Saves you {sav} mins vs leaving now ({cur} mins)")
    else:
        lines.append(f"ℹ️ Leaving now is also fine (~{cur} mins)")

    if dur <= 25:
        lines.append("🟢 Roads look clear — smooth ride ahead!")
    elif dur <= 45:
        lines.append("🟡 Moderate traffic — leave on time.")
    else:
        lines.append("🔴 Heavy traffic. Leave exactly at this time for best results.")

    return "\n".join(lines)
