import os
import json
import sqlite3
import requests
from flask import Flask, request
from datetime import datetime

# === CONFIG ===
TELEGRAM_BOT_TOKEN = "7580676982:AAFC6HMWe5gVhbTM8YBvPyH06seNF9UPEe8"
TELEGRAM_CHAT_ID = "6251161332"
TARGET_WALLET = "gasTzr94Pmp4Gf8vknQnqxeYxdgwFjbgdJa4msYRpnB"
HELIUS_API_KEY = "aae17b37-6805-43cd-8f67-921c96ce5c54"

# Flask App
app = Flask(__name__)

# === SQLite Setup ===
DB_FILE = "tokens.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS detected_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mint TEXT UNIQUE,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def token_exists(mint):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM detected_tokens WHERE mint=?", (mint,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def save_token(mint):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO detected_tokens (mint) VALUES (?)", (mint,))
    conn.commit()
    conn.close()

# === Telegram Alert ===
def send_telegram_alert(token_name, token_symbol, mint, amount, signature, token_age):
    message = f"""
🚨 New Token Buy Detected! 🚨

👛 Wallet: {TARGET_WALLET}
🪙 Token: {token_name} ({token_symbol})
🔖 Mint: {mint}
💰 Amount: {amount}
⏳ Token Age: {token_age} minutes
🔗 Tx: https://solscan.io/tx/{signature}
"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message})


# === Token Metadata (Helius) ===
def get_token_age(mint):
    try:
        url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_API_KEY}"
        payload = {"mintAccounts": [mint]}
        res = requests.post(url, json=payload).json()

        if res and "onChainMetadata" in res[0]:
            created_at = res[0]["onChainMetadata"]["creationTime"]
            now = datetime.utcnow().timestamp()
            age_minutes = int((now - created_at) / 60)
            return age_minutes
    except Exception as e:
        print("Error getting token age:", e)
        return "Unknown"
    return "Unknown"


# === Webhook Route ===
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if not data:
        return {"status": "no data"}, 400

    signature = data.get("signature")
    token_transfers = data.get("tokenTransfers", [])

    for t in token_transfers:
        to_wallet = t.get("toUserAccount")
        mint = t.get("mint")
        token_name = t.get("tokenName", "Unknown")
        token_symbol = t.get("tokenSymbol", "???")
        amount = t.get("amount")

        # Detect if it's first-time token buy
        if to_wallet == TARGET_WALLET and not token_exists(mint):
            save_token(mint)  # Save in DB
            token_age = get_token_age(mint)
            send_telegram_alert(token_name, token_symbol, mint, amount, signature, token_age)

    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(port=5000, use_reloader=False)

