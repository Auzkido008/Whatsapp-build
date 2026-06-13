"""
db.py — User & route storage via Supabase.

Schema (run schema.sql to set up):
  users(phone TEXT PK, name TEXT, is_premium BOOL, created_at TIMESTAMPTZ)
  routes(id SERIAL PK, phone TEXT, label TEXT, origin TEXT, destination TEXT,
         arrive_by TEXT, alert_enabled BOOL, created_at TIMESTAMPTZ)
"""

import os
from typing import Optional
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ── Users ────────────────────────────────────────────────────────────────────────

def get_user(phone: str) -> Optional[dict]:
    result = get_client().table("users").select("*").eq("phone", phone).execute()
    return result.data[0] if result.data else None


def upsert_user(phone: str, name: str = "", is_premium: bool = False) -> dict:
    data = {"phone": phone, "name": name, "is_premium": is_premium}
    result = get_client().table("users").upsert(data, on_conflict="phone").execute()
    return result.data[0]


def set_premium(phone: str, is_premium: bool) -> None:
    get_client().table("users").update({"is_premium": is_premium}).eq("phone", phone).execute()


# ── Routes ──────────────────────────────────────────────────────────────────────

def get_routes(phone: str) -> list[dict]:
    result = (
        get_client()
        .table("routes")
        .select("*")
        .eq("phone", phone)
        .order("created_at", desc=False)
        .execute()
    )
    return result.data or []


def get_route(phone: str, label: str) -> Optional[dict]:
    result = (
        get_client()
        .table("routes")
        .select("*")
        .eq("phone", phone)
        .eq("label", label)
        .execute()
    )
    return result.data[0] if result.data else None


def upsert_route(phone: str, label: str, origin: str, destination: str,
                 arrive_by: str, alert_enabled: bool = True) -> dict:
    existing = get_route(phone, label)
    data = {
        "phone": phone,
        "label": label,
        "origin": origin,
        "destination": destination,
        "arrive_by": arrive_by,
        "alert_enabled": alert_enabled,
    }
    if existing:
        result = get_client().table("routes").update(data).eq("id", existing["id"]).execute()
    else:
        result = get_client().table("routes").insert(data).execute()
    return result.data[0]


def delete_route(phone: str, label: str) -> None:
    get_client().table("routes").delete().eq("phone", phone).eq("label", label).execute()


def toggle_alert(phone: str, label: str, enabled: bool) -> None:
    get_client().table("routes").update({"alert_enabled": enabled}).eq("phone", phone).eq("label", label).execute()


def get_all_alert_routes() -> list[dict]:
    result = (
        get_client()
        .table("routes")
        .select("*, users(name, is_premium)")
        .eq("alert_enabled", True)
        .execute()
    )
    return result.data or []
