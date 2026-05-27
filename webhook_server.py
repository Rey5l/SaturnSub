import json
import logging
import sys
from pathlib import Path

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

# Папка, где лежит этот файл (важно, если запускаете из другой директории)
BASE_DIR = Path(__file__).resolve().parent
LINKNI_WEBHOOK_SECRET = "reyslAndAmir1331"
DB_PATH = str(BASE_DIR / "bot_database.db")

# Боевые статусы от Linkni (status "test" обрабатывается отдельно)
LINKNI_STATUSES = ("subscribed", "not_subscribed", "no_sponsors")

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    """Срабатывает при любом запуске через uvicorn (не только python webhook_server.py)."""
    logger.info("=" * 50)
    logger.info("Webhook-сервер стартовал")
    logger.info("Файл: %s", Path(__file__).resolve())
    logger.info("Рабочая директория (cwd): %s", Path.cwd())
    logger.info("База данных: %s", DB_PATH)
    logger.info("Flyer:  POST /webhook/flyer")
    logger.info("Linkni: POST /webhook/linkni/<secret>")
    logger.info("Health: GET  /health")
    logger.info("=" * 50)


@app.post("/webhook/flyer")
async def webhook_handler(request: Request):
    try:
        data = await request.json()
        logger.info("[Flyer] payload: %s", data)

        if data.get("type") == "test":
            return {"status": True}
        if data.get("type") == "sub_completed":
            return {"status": True}
        if data.get("type") == "new_status" and data.get("data", {}).get("status") == "abort":
            return {"status": True}

    except Exception as e:
        logger.exception("[Flyer] ошибка: %s", e)

    return {"status": True}


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
        logger.warning("[Linkni] неверный секрет в URL")
        raise HTTPException(status_code=404, detail="Not found")

    try:
        data = await request.json()
    except Exception:
        logger.warning("[Linkni] невалидный JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logger.info("[Linkni] JSON: %s", data)

    status = data.get("status")
    sell_code = data.get("sell_code")
    sub_code = data.get("sub_code")

    # Тест из панели Linkni: {"user_id": 0, "status": "test", "sell_code": "..."}
    if status == "test":
        logger.info("[Linkni] тестовый запрос — OK")
        return {"ok": True, "test": True}

    try:
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        logger.warning("[Linkni] user_id не число: %r", data.get("user_id"))
        raise HTTPException(status_code=400, detail="user_id must be int")

    if user_id <= 0:
        raise HTTPException(status_code=400, detail="user_id must be positive")

    if status not in LINKNI_STATUSES:
        logger.warning("[Linkni] неверный status: %r", status)
        raise HTTPException(status_code=400, detail="invalid status")
    if not sell_code or not isinstance(sell_code, str):
        raise HTTPException(status_code=400, detail="sell_code required")
    if sub_code is not None and not isinstance(sub_code, str):
        raise HTTPException(status_code=400, detail="sub_code must be string")

    raw = json.dumps(data, ensure_ascii=False)

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
        logger.info(
            "[Linkni] сохранено: user_id=%s status=%s sell_code=%s sub_code=%s",
            user_id, status, sell_code, sub_code,
        )
    except Exception as e:
        logger.exception("[Linkni] ошибка записи в БД (%s): %s", DB_PATH, e)
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
    # Нужен только при запуске: python webhook_server.py
    # Если запускаете через uvicorn — этот блок не выполняется, но startup-логи всё равно будут.
    logger.info("Запуск через __main__ на http://0.0.0.0:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
