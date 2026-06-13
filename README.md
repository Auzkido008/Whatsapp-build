# 🚦 LagosGo — Lagos Commute Optimizer

A WhatsApp bot that tells you the **exact minute to leave** based on real-time Google Maps traffic for your Lagos route.

Free tier with ads. Premium ad-free tier at ₦1,500/month.

---

## How it works

1. User messages the WhatsApp number
2. Bot saves their route (origin → destination, arrival time)
3. Bot queries Google Maps Directions API with 5-minute departure increments over a 2-hour window
4. Returns the departure time with the **shortest in-traffic travel time**
5. Morning alerts fire automatically before rush hour
6. Free users see one rotating sponsor ad per message

---

## Stack

| Layer | Tech |
|---|---|
| WhatsApp | Twilio WhatsApp API |
| Traffic data | Google Maps Directions API (`departure_time` + `traffic_model=best_guess`) |
| Backend | Python 3.12 + FastAPI |
| Database | Supabase (Postgres) |
| Hosting | Railway (free tier sufficient for MVP) |
| Morning alerts | GitHub Actions cron → POST `/cron/morning` |

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/Auzkido008/Whatsapp-build.git
cd Whatsapp-build
pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Fill in: GOOGLE_MAPS_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
#          SUPABASE_URL, SUPABASE_ANON_KEY, CRON_SECRET
```

### 3. Set up Supabase

- Create a free project at [supabase.com](https://supabase.com)
- Open the SQL Editor and run `schema.sql`
- Copy your **service role key** (not anon key) into `SUPABASE_ANON_KEY`

### 4. Set up Google Maps

- Go to [Google Cloud Console](https://console.cloud.google.com/apis/library)
- Enable **Directions API**
- Create an API key, restrict it to Directions API
- Add to `.env` as `GOOGLE_MAPS_API_KEY`

### 5. Set up Twilio WhatsApp

- Sign up at [twilio.com](https://twilio.com)
- Go to **Messaging → Try it out → Send a WhatsApp message**
- Join the sandbox (send "join <code>" to the sandbox number)
- Set your webhook URL in the Twilio Console:
  - Sandbox webhook: `https://your-railway-url.up.railway.app/webhook/whatsapp`
  - Method: POST

### 6. Deploy to Railway

```bash
railway login
railway init
railway up
```

Add all env vars in Railway dashboard → Variables.

### 7. Set up morning alerts

In your GitHub repo → Settings → Secrets, add:
- `LAGOSGO_BASE_URL` = `https://your-railway-url.up.railway.app`
- `LAGOSGO_CRON_SECRET` = same value as `CRON_SECRET` in your `.env`

The workflow `.github/workflows/morning_alerts.yml` fires at 5:30, 6:00, and 7:00 AM Lagos time on weekdays.

---

## Bot commands

| Command | Action |
|---|---|
| `HI` / `START` | Onboard new user |
| `CHECK` / `GO` | Get optimal departure time now |
| `ADD` | Save a new route |
| `ROUTES` | List saved routes |
| `DELETE [name]` | Delete a route |
| `PAUSE` | Stop morning alerts |
| `RESUME` | Restart morning alerts |
| `UPGRADE` | Premium info |
| `HELP` | Show command list |

---

## Revenue model

| Tier | Price | Features |
|---|---|---|
| Free | ₦0 | 1 route, morning alerts, 1 ad per message |
| Premium | ₦1,500/month | 5 routes, no ads, multi-alert windows |

**Ad inventory** is in `app/ads.py` — swap in real paying advertisers.  
**Premium verification** is manual for MVP (payment screenshot → admin flips `is_premium` in Supabase). Automate with Paystack later.

---

## Folder structure

```
lagosgo/
├── app/
│   ├── __init__.py
│   ├── main.py        # FastAPI app, Twilio webhook
│   ├── bot.py         # Conversation state machine
│   ├── traffic.py     # Google Maps optimizer
│   ├── db.py          # Supabase queries
│   └── ads.py         # Ad rotation
├── .github/
│   └── workflows/
│       └── morning_alerts.yml
├── schema.sql          # Supabase table definitions
├── requirements.txt
├── Procfile
├── railway.json
├── .env.example
└── README.md
```
