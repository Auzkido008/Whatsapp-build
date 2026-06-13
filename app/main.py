"""
main.py — FastAPI app. Twilio WhatsApp webhook + morning alert cron trigger.

Endpoints:
  POST /webhook/whatsapp  — Twilio inbound message webhook
  POST /cron/morning      — Morning alerts (protected by CRON_SECRET header)
  GET  /health            — Health check
"""

import os
import hmac
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Form, Request, HTTPException, Header
from fastapi.responses import PlainTextResponse
from twilio.rest import Client as TwilioClient
from twilio.request_validator import RequestValidator

from app import bot, db, traffic, ads


TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
CRON_SECRET = os.getenv("CRON_SECRET", "change-me-in-production")

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
twilio_validator = RequestValidator(TWILIO_AUTH_TOKEN)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("LagosGo starting up 🚦")
    yield
    print("LagosGo shutting down")


app = FastAPI(title="LagosGo", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "LagosGo"}


@app.post("/webhook/whatsapp", response_class=PlainTextResponse)
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
):
    # Validate Twilio signature in production
    if TWILIO_AUTH_TOKEN and TWILIO_AUTH_TOKEN != "dev":
        url = str(request.url)
        form_data = dict(await request.form())
        sig = request.headers.get("X-Twilio-Signature", "")
        if not twilio_validator.validate(url, form_data, sig):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    phone = From.replace("whatsapp:", "")
    reply = await bot.handle_message(phone, Body)
    _send_whatsapp(phone, reply)
    return "OK"


@app.post("/cron/morning")
async def morning_alerts(x_cron_secret: str = Header(default="")):
    """
    Fire this endpoint from a cron job roughly 90-120 mins before rush hour.
    Recommended: 5:30 AM, 6:00 AM, 7:00 AM Lagos time (UTC+1).
    """
    if not hmac.compare_digest(x_cron_secret, CRON_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")

    alert_routes = db.get_all_alert_routes()
    sent = 0
    errors = 0

    for route in alert_routes:
        try:
            phone = route["phone"]
            user_data = route.get("users") or {}
            name = user_data.get("name", "")
            is_premium = user_data.get("is_premium", False)

            arrive_h, arrive_m = map(int, route["arrive_by"].split(":"))
            result = await traffic.find_optimal_departure(
                origin=route["origin"],
                destination=route["destination"],
                arrive_by_hour=arrive_h,
                arrive_by_minute=arrive_m,
            )

            if "error" in result:
                continue

            now_utc = datetime.now(timezone.utc)
            opt_dep = result["optimal_departure"]
            opt_dep_utc = opt_dep.replace(tzinfo=timezone.utc) + timedelta(hours=-1)
            delta_mins = (opt_dep_utc - now_utc).total_seconds() / 60

            if not (-5 <= delta_mins <= 120):
                continue

            message = traffic.format_recommendation(result, user_name=name)
            message = ads.append_ad(message, phone, is_premium=is_premium)
            _send_whatsapp(phone, message)
            sent += 1
        except Exception as e:
            print(f"Error sending alert to {route.get('phone')}: {e}")
            errors += 1

    return {"sent": sent, "errors": errors}


def _send_whatsapp(to_phone: str, message: str) -> None:
    twilio_client.messages.create(
        from_=TWILIO_WHATSAPP_FROM,
        to=f"whatsapp:{to_phone}",
        body=message,
    )
