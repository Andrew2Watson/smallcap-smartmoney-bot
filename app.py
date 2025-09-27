# app.py  (Render-ready: Flask web + Telegram bot thread)
import os
import threading
import time
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify
import telebot

# Load .env locally (Render will use dashboard env vars)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WHALE_ALERT_API_KEY = os.getenv("WHALE_ALERT_API_KEY", "")
BITQUERY_API_KEY = os.getenv("BITQUERY_API_KEY", "")
MORALIS_API_KEY = os.getenv("MORALIS_API_KEY", "")
COVALENT_API_KEY = os.getenv("COVALENT_API_KEY", "")
WHALE_MIN_USD = int(os.getenv("WHALE_MIN_USD", "500000"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Set it in .env (local) or in Render dashboard.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# ---------- Helpers ----------
def http_get_json(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        if r.status_code == 200:
            return r.json()
        return {"__error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"__error": str(e)}

# ---------- Commands ----------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.reply_to(
        message,
        "Hi 👋\nI'm online 24/7 on Render.\n\n*Commands:*\n"
        "• `/sentiment` → Crypto Fear & Greed Index\n"
        "• `/retail` → Retail sentiment (CoinGecko)\n"
        "• `/whale [minUsd]` → Live whale transfers (if API key set)\n"
        "• `/help` → Show help"
    )

@bot.message_handler(commands=['help'])
def cmd_help(message):
    bot.reply_to(
        message,
        "*Commands:*\n"
        "• `/sentiment` → Crypto Fear & Greed Index\n"
        "• `/retail` → Retail sentiment (CoinGecko)\n"
        "• `/whale [minUsd]` → Whale transfers (last 60m)\n"
        "  example: `/whale 1000000`"
    )

@bot.message_handler(commands=['sentiment'])
def cmd_sentiment(message):
    data = http_get_json("https://api.alternative.me/fng/", params={"limit": 1})
    if "__error" in data:
        bot.reply_to(message, f"❌ Error: `{data['__error']}`", parse_mode="Markdown")
        return
    try:
        v = data["data"][0]
        score = v["value"]
        label = v["value_classification"]
        updated = v["timestamp"]
        bot.reply_to(
            message,
            f"*📊 Crypto Fear & Greed Index*\nScore: *{score}* ({label})\nLast updated: `{updated}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Parse error: `{e}`")

@bot.message_handler(commands=['retail'])
def cmd_retail(message):
    # Using CoinGecko public API for quick sentiment proxy
    data = http_get_json("https://api.coingecko.com/api/v3/coins/bitcoin",
                         params={"localization":"false","tickers":"false","market_data":"false",
                                 "community_data":"true","developer_data":"false","sparkline":"false"})
    if "__error" in data:
        bot.reply_to(message, f"❌ Error: `{data['__error']}`", parse_mode="Markdown")
        return
    try:
        up = data.get("sentiment_votes_up_percentage", 0)
        down = data.get("sentiment_votes_down_percentage", 0)
        bot.reply_to(
            message,
            "🧑‍🤝‍🧑 *Retail Sentiment (CoinGecko)*\n"
            f"👍 Positive: *{up}%*\n"
            f"👎 Negative: *{down}%*",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Parse error: `{e}`")

@bot.message_handler(commands=['whale'])
def cmd_whale(message):
    """ /whale [minUsd]  → last 60 minutes, min value filter """
    parts = message.text.strip().split()
    try:
        min_usd = int(parts[1]) if len(parts) > 1 else WHALE_MIN_USD
    except:
        min_usd = WHALE_MIN_USD

    end_ts = int(time.time())
    start_ts = end_ts - 60*60

    # Prefer Whale Alert if key present (simple & broad)
    if WHALE_ALERT_API_KEY:
        url = "https://api.whale-alert.io/v1/transactions"
        data = http_get_json(url, params={
            "api_key": WHALE_ALERT_API_KEY,
            "start": start_ts,
            "end": end_ts,
            "min_value": min_usd
        })
        if "__error" in data:
            bot.reply_to(message, f"❌ Whale API error: `{data['__error']}`", parse_mode="Markdown")
            return
        txs = data.get("transactions", [])[:10]
        if not txs:
            bot.reply_to(message, f"No whale transfers ≥ ${min_usd:,} in last 60 minutes.")
            return
        lines = [f"🐳 *Whale Transfers (last 60m)*  Min: *${min_usd:,}*"]
        for t in txs:
            usd = int(t.get("amount_usd") or 0)
            sym = (t.get("symbol") or "").upper()
            fro = (t.get("from") or {}).get("owner_type") or "unknown"
            to  = (t.get("to") or {}).get("owner_type") or "unknown"
            ts  = t.get("timestamp", "")
            lines.append(f"• ${usd:,} {sym} | {fro} → {to} | ts: {ts}")
        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")
        return

    # Fallback: no API key configured
    bot.reply_to(
        message,
        "ℹ️ Whale data requires an API key.\n"
        "- Set `WHALE_ALERT_API_KEY` (preferred), or\n"
        "- Later we can add Bitquery/Moralis/Covalent routes.",
        parse_mode="Markdown"
    )

# ---------- Bot runner (thread) ----------
def run_bot():
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            # retry after short sleep
            time.sleep(5)

# ---------- Flask keepalive (Render needs a web port) ----------
app = Flask(__name__)

@app.route("/")
def index():
    return "OK: SmallCap SmartMoney bot running"

@app.route("/healthz")
def healthz():
    return jsonify(ok=True)

if __name__ == "__main__":
    # Start bot in background thread
    t = threading.Thread(target=run_bot, daemon=True)
    t.start()
    # Start Flask web server (Render will hit this)
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
