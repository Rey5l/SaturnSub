import json
import logging
import sys
from pathlib import Path

import aiohttp
import aiosqlite
import uvicorn
from fastapi import FastAPI, Request, HTTPException

# =========================
# Логирование
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("webhook_server")

BASE_DIR = Path(__file__).resolve().parent
LINKNI_WEBHOOK_SECRET = "reyslAndAmir1331"
DB_PATH = str(BASE_DIR / "bot_database.db")

# Токен бота — для уведомлений о штрафе (тот же, что в app.py)
BOT_TOKEN = "8450626723:AAHkbONr-iGmAQgtcAMIBxZXkkI0_QM82AM"

LINKNI_STATUSES = ("subscribed", "not_subscribed", "no_sponsors")
FLYER_UNSUBSCRIBE_STATUSES = frozenset({"unsubscribed", "abort", "failed", "unsubscribe"})

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS flyer_webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                user_id INTEGER,
                signature TEXT,
                status TEXT,
                raw_json TEXT,
                processed INTEGER DEFAULT 0,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            await db.execute("ALTER TABLE frozen_transactions ADD COLUMN task_ref TEXT")
        except Exception:
            pass
        await db.commit()

    logger.info("=" * 50)
    logger.info("Webhook-сервер стартовал")
    logger.info("База: %s", DB_PATH)
    logger.info("Flyer:  POST /webhook/flyer")
    logger.info("Linkni: POST /webhook/linkni/<secret>")
    logger.info("=" * 50)


def parse_flyer_event(data: dict):
    """Разбор payload Flyer (разные форматы)."""
    event_type = data.get("type") or data.get("event")
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}

    user_id = inner.get("user_id") or data.get("user_id")
    signature = inner.get("signature") or data.get("signature")
    status = inner.get("status") or data.get("status")

    if user_id is not None:
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            user_id = None

    if signature is not None:
        signature = str(signature).strip()

    if status is not None:
        status = str(status).strip().lower()

    return event_type, user_id, signature, status


async def save_flyer_event(event_type, user_id, signature, status, raw_json, processed=0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            '''
            INSERT INTO flyer_webhook_events (event_type, user_id, signature, status, raw_json, processed)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (event_type, user_id, signature, status, raw_json, processed),
        )
        await db.commit()


async def notify_user(user_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json={"chat_id": user_id, "text": text, "parse_mode": "HTML"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning("[TG] не отправлено %s: %s", user_id, body[:200])
    except Exception as e:
        logger.warning("[TG] ошибка уведомления %s: %s", user_id, e)


async def apply_flyer_penalty(user_id: int, signature: str) -> bool:
    """
    Штраф за отписку от Flyer-задания (та же логика, что apply_penalty_for_transaction в app.py).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            '''
            SELECT id, user_id, amount, task_type, task_ref
            FROM frozen_transactions
            WHERE user_id = ? AND task_type = 'flyer'
              AND is_unfrozen = 0 AND COALESCE(penalty_applied, 0) = 0
              AND task_ref = ?
            LIMIT 1
            ''',
            (user_id, signature),
        ) as cur:
            tx = await cur.fetchone()

    if not tx:
        logger.warning("[Flyer] нет замороженной tx: user=%s sig=%s", user_id, signature)
        return False

    tx_id = tx["id"]
    amount = float(tx["amount"] or 0)
    penalty_total = round(amount * 1.2, 6)
    extra_needed = round(penalty_total - amount, 6)

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT frozen_balance, balance FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            frozen_balance = float(row[0] or 0) if row else 0.0

        frozen_to_deduct = min(frozen_balance, amount)
        if frozen_to_deduct > 0:
            await db.execute(
                "UPDATE users SET frozen_balance = frozen_balance - ? WHERE user_id = ?",
                (frozen_to_deduct, user_id),
            )

        remaining = round(amount - frozen_to_deduct, 6)
        if remaining > 0:
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (remaining, user_id),
            )

        if extra_needed > 0:
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (extra_needed, user_id),
            )

        await db.execute(
            '''
            UPDATE frozen_transactions
            SET is_unfrozen = 1, penalty_applied = 1, penalty_amount = ?
            WHERE id = ?
            ''',
            (penalty_total, tx_id),
        )

        await db.execute(
            '''
            INSERT INTO balance_history (user_id, amount, type, admin_id, reason)
            VALUES (?, ?, 'penalty', NULL, ?)
            ''',
            (
                user_id,
                -penalty_total,
                f"Штраф Flyer webhook: отписка ({signature})",
            ),
        )

        await db.execute(
            '''
            INSERT OR REPLACE INTO completed_tasks (user_id, signature, status, completed_at)
            VALUES (?, ?, ?, datetime('now'))
            ''',
            (user_id, signature, "abort"),
        )

        await db.commit()

    await notify_user(
        user_id,
        f"❌ <b>Штраф за отписку от задания</b>\n\n"
        f"💰 Сумма: <b>{penalty_total:.3f}$</b> (включая +20%)\n\n"
        f"<i>Вы отписались от канала раньше срока.</i>",
    )
    logger.info("[Flyer] штраф применён: user=%s sig=%s amount=%s", user_id, signature, penalty_total)
    return True


async def process_flyer_webhook(data: dict) -> dict:
    event_type, user_id, signature, status = parse_flyer_event(data)
    raw = json.dumps(data, ensure_ascii=False)

    await save_flyer_event(event_type, user_id, signature, status, raw, processed=0)

    if event_type == "test":
        logger.info("[Flyer] test OK")
        return {"ok": True, "type": "test"}

    is_unsubscribe = False
    if event_type == "new_status" and status in FLYER_UNSUBSCRIBE_STATUSES:
        is_unsubscribe = True
    if status in FLYER_UNSUBSCRIBE_STATUSES and event_type not in ("test",):
        is_unsubscribe = True

    if is_unsubscribe and user_id and signature:
        applied = await apply_flyer_penalty(user_id, signature)
        await save_flyer_event(event_type, user_id, signature, status, raw, processed=1 if applied else 0)
        return {"ok": True, "penalty_applied": applied, "user_id": user_id, "signature": signature}

    if event_type == "sub_completed":
        logger.info("[Flyer] sub_completed user=%s sig=%s", user_id, signature)
        return {"ok": True, "type": "sub_completed"}

    logger.info("[Flyer] событие сохранено без штрафа: type=%s status=%s", event_type, status)
    return {"ok": True, "type": event_type, "status": status}


@app.post("/webhook/flyer")
async def webhook_handler(request: Request):
    try:
        data = await request.json()
    except Exception:
        logger.warning("[Flyer] невалидный JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info("[Flyer] POST: %s", data)

    try:
        result = await process_flyer_webhook(data)
        return result
    except Exception as e:
        logger.exception("[Flyer] ошибка обработки: %s", e)
        return {"ok": False, "error": str(e)}


@app.get("/webhook/flyer")
async def flyer_webhook_get():
    return {
        "ok": True,
        "message": "Flyer webhook активен. Нужен POST.",
        "url_register_in_flyer_panel": "https://ВАШ_ДОМЕН/webhook/flyer",
    }


# =========================
# Linkni webhook
# =========================


@app.get("/webhook/linkni/{secret}")
async def linkni_webhook_get(secret: str):
    if secret != LINKNI_WEBHOOK_SECRET:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "ok": True,
        "message": "Webhook работает. Linkni отправляет POST с JSON.",
        "method_required": "POST",
    }


@app.post("/webhook/linkni/{secret}")
async def linkni_webhook(secret: str, request: Request):
    client_ip = request.client.host if request.client else "?"
    logger.info("[Linkni] запрос от %s, secret_ok=%s", client_ip, secret == LINKNI_WEBHOOK_SECRET)

    if secret != LINKNI_WEBHOOK_SECRET:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info("[Linkni] JSON: %s", data)

    status = data.get("status")
    sell_code = data.get("sell_code")
    sub_code = data.get("sub_code")

    if status == "test":
        return {"ok": True, "test": True}

    try:
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="user_id must be int")

    if user_id <= 0:
        raise HTTPException(status_code=400, detail="user_id must be positive")

    if status not in LINKNI_STATUSES:
        raise HTTPException(status_code=400, detail="invalid status")
    if not sell_code or not isinstance(sell_code, str):
        raise HTTPException(status_code=400, detail="sell_code required")
    if sub_code is not None and not isinstance(sub_code, str):
        raise HTTPException(status_code=400, detail="sub_code must be string")

    raw = json.dumps(data, ensure_ascii=False)
    event_ts = (data.get("timestamp") or data.get("time") or data.get("created_at") or "")
    if event_ts:
        event_ts = str(event_ts).strip()[:32]
    sub_code_norm = (sub_code or "").strip() if sub_code else ""

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS linkni_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    sell_code TEXT NOT NULL,
                    sub_code TEXT,
                    event_ts TEXT,
                    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    raw_json TEXT
                )
                """
            )
            try:
                await db.execute("ALTER TABLE linkni_subscriptions ADD COLUMN event_ts TEXT")
            except Exception:
                pass

            if event_ts:
                async with db.execute(
                    """
                    SELECT 1 FROM linkni_subscriptions
                    WHERE user_id = ? AND sell_code = ?
                      AND COALESCE(sub_code, '') = ? AND event_ts = ?
                    """,
                    (user_id, sell_code, sub_code_norm, event_ts),
                ) as cur:
                    if await cur.fetchone():
                        return {"ok": True, "duplicate": True}
            elif status == "subscribed":
                async with db.execute(
                    """
                    SELECT 1 FROM linkni_subscriptions
                    WHERE user_id = ? AND status = ? AND sell_code = ?
                      AND COALESCE(sub_code, '') = ?
                      AND received_at > datetime('now', '-5 minutes')
                    """,
                    (user_id, status, sell_code, sub_code_norm),
                ) as cur:
                    if await cur.fetchone():
                        return {"ok": True, "duplicate": True}

            await db.execute(
                """
                INSERT INTO linkni_subscriptions
                (user_id, status, sell_code, sub_code, event_ts, raw_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, status, sell_code, sub_code_norm or None, event_ts or None, raw),
            )
            await db.commit()
        logger.info("[Linkni] сохранено: user=%s status=%s", user_id, status)
    except Exception as e:
        logger.exception("[Linkni] ошибка БД: %s", e)
        raise HTTPException(status_code=500, detail="database error")

    return {"ok": True}


@app.get("/")
@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": "webhook_server",
        "db_path": DB_PATH,
        "cwd": str(Path.cwd()),
    }


if __name__ == "__main__":
    logger.info("Запуск на http://0.0.0.0:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
