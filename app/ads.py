"""
ads.py — Ad injection for free-tier users.

Ads are rotated deterministically per user so they don't see the
same ad twice in a row. Premium users (is_premium=True) skip ads entirely.
"""

import hashlib
from datetime import date
from typing import Optional

AD_INVENTORY = [
    {
        "id": "ad_001",
        "text": "📦 *Need fast delivery in Lagos?* Try Kwik — same-day logistics for businesses.\nkwikdelivery.com",
    },
    {
        "id": "ad_002",
        "text": "⚡ *Cut your fuel costs.* Switch to CNG with GreenMobility Lagos — ask us how.\ngreenmo.ng",
    },
    {
        "id": "ad_003",
        "text": "🏦 *Send money instantly across Africa.* Chipper Cash — zero fees on first transfer.\nchippercash.com",
    },
    {
        "id": "ad_004",
        "text": "🛡️ *Renew your vehicle insurance in 2 mins.* Leadway Assurance — from ₦15,000/year.\nleadway.com",
    },
    {
        "id": "ad_005",
        "text": "☕ *Start your morning right.* Ozone Coffee Lagos — ₦500 off your first order with code LAGOSGO.\nozonelagos.com",
    },
    {
        "id": "ad_006",
        "text": "🚗 *Ride smarter, not harder.* InDrive Lagos — set your own price. Download now.\nindrive.com",
    },
    {
        "id": "ad_007",
        "text": "📱 *Affordable data bundles for Lagos hustlers.* Airtel SmartConnect — 10GB for ₦1,500.\nairtelnigeria.com",
    },
    {
        "id": "ad_008",
        "text": "🏠 *Looking for a home close to work?* PropertyPro — filter by commute time on the map.\npropertypro.ng",
    },
]

PREMIUM_CTA = (
    "\n\n─\n💎 _Go ad-free + get multi-route alerts._ Reply *UPGRADE* to learn more."
)


def get_ad_for_user(user_phone: str, is_premium: bool = False) -> Optional[str]:
    if is_premium:
        return None
    seed = f"{user_phone}:{date.today().isoformat()}"
    h = int(hashlib.md5(seed.encode()).hexdigest(), 16)
    ad = AD_INVENTORY[h % len(AD_INVENTORY)]
    return f"\n\n─\n_Sponsored_\n{ad['text']}"


def append_ad(message: str, user_phone: str, is_premium: bool = False) -> str:
    """Append an ad (and upgrade CTA for free users) to a message."""
    ad = get_ad_for_user(user_phone, is_premium)
    if ad:
        return message + ad + PREMIUM_CTA
    return message
