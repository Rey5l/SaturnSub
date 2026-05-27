import json
import uvicorn
import aiosqlite
from fastapi import FastAPI, Request, HTTPException

app = FastAPI()


@app.post('/webhook/flyer')
async def webhook_handler(request: Request):
    try:
        data = await request.json()
        print("DATA:", data)

        if data.get('type') == 'test':
            return {'status': True}

        elif data.get('type') == 'sub_completed':
            return {'status': True}

        elif data.get('type') == 'new_status' and data.get('data', {}).get('status') == 'abort':
            return {'status': True}

    except Exception as e:
        print("ERROR:", e)

    return {'status': True}


# =========================
# Linkni webhook
# =========================
# Секрет для URL. Поставьте длинную случайную строку.
# URL будет таким:
# https://preopposed-tabitha-whirly.ngrok-free.dev/webhook/linkni/<LINKNI_WEBHOOK_SECRET>
LINKNI_WEBHOOK_SECRET = "reyslAndAmir1331"

# Путь к базе бота (SQLite). Обычно рядом с проектом.
DB_PATH = "bot_database.db"


@app.post("/webhook/linkni/{secret}")
async def linkni_webhook(secret: str, request: Request):
    """
    Linkni присылает:
    {
      "user_id": 123,
      "status": "subscribed"|"not_subscribed"|"no_sponsors",
      "sell_code": "2tz9",
      "sub_code": "MYCODE"
    }
    """
    if secret != LINKNI_WEBHOOK_SECRET:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    user_id = data.get("user_id")
    status = data.get("status")
    sell_code = data.get("sell_code")
    sub_code = data.get("sub_code")

    if not isinstance(user_id, int):
        raise HTTPException(status_code=400, detail="user_id must be int")
    if status not in ("subscribed", "not_subscribed", "no_sponsors"):
        raise HTTPException(status_code=400, detail="invalid status")
    if not sell_code or not isinstance(sell_code, str):
        raise HTTPException(status_code=400, detail="sell_code required")
    if sub_code is not None and not isinstance(sub_code, str):
        raise HTTPException(status_code=400, detail="sub_code must be string")

    raw = json.dumps(data, ensure_ascii=False)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS linkni_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                sell_code TEXT NOT NULL,
                sub_code TEXT,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                raw_json TEXT
            )
            """
        )
        await db.execute(
            """
            INSERT INTO linkni_subscriptions (user_id, status, sell_code, sub_code, raw_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, status, sell_code, sub_code, raw),
        )
        await db.commit()

    return {"ok": True}
