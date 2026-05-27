import asyncio
import aiosqlite
import aiogram
from aiogram import Bot, Dispatcher, types, F, Router, BaseMiddleware
from aiogram.filters import Command, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, Message, \
    CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from flyerapi import Flyer
import aiohttp
import json
import time
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

last_withdrawal_notification = {}

global FLYER_API_KEY, flyer, flyer_enabled

BOT_TOKEN = "8450626723:AAHkbONr-iGmAQgtcAMIBxZXkkI0_QM82AM"
FLYER_API_KEY = "FL-GeBnNH-utNjHN-IbxtAT-eLiEzk"
ADMIN_IDS = [7975675184, 1723065839]
FLZAD = 0.011
# 🔹 Глобальные переменные криптобота
DEFAULT_CRYPTO_BOT_TOKEN = "531539:AAYxjA3c1WDN8MebfWxqRxEL6JCFqUy1JwGd"

CRYPTO_BOT_TOKEN: str = DEFAULT_CRYPTO_BOT_TOKEN
crypto_enabled: bool = True

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# Состояния для FSM
class WithdrawalStates(StatesGroup):
    waiting_for_amount = State()


class AdminStates(StatesGroup):
    waiting_payments_channel = State()
    waiting_payments_channell = State()
    waiting_chat_link = State()
    waiting_flyer_key = State()
    waiting_min_withdrawal = State()
    waiting_currency = State()
    waiting_broadcast = State()
    waiting_broadcast_buttons = State()
    waiting_approve_receipt = State()
    waiting_user_id = State()
    waiting_balance_amount = State()
    waiting_ban_reason = State()
    waiting_task_name = State()
    waiting_task_description = State()
    waiting_task_url = State()
    waiting_task_button_text = State()
    waiting_task_max_completions = State()
    waiting_custom_task_price = State()
    waiting_edit_value = State()
    waiting_for_amount = State()
    waiting_for_amount = State()
    waiting_crypto_token = State()
    waiting_ref_level1 = State()
    waiting_ref_level2 = State()
    waiting_promotion_price = State()
    waiting_ref_bonus_level1 = State()
    waiting_ref_bonus_level2 = State()
    waiting_ref_tasks_level1 = State()
    waiting_ref_tasks_level2 = State()
    waiting_gramads_token = State()


class TGRASSS(StatesGroup):
    wait_tgrass_key = State()


class AdTopupStates(StatesGroup):
    waiting_for_amount = State()


# ✅ ДОБАВЬТЕ ЭТОТ КЛАСС ДЛЯ ПОПОЛНЕНИЯ РЕЗЕРВА
class ReserveTopupStates(StatesGroup):
    waiting_for_amount = State()


# В обработчике баланса резерва
import pytz
from datetime import datetime, timedelta

# Часовой пояс Москва (МСК)
MSK = pytz.timezone("Europe/Moscow")


def now_msk() -> datetime:
    """Возвращает текущее московское время"""
    return datetime.now(MSK)


# ==================== GRAMADS INTEGRATION ====================
GRAMADS_API_URL = "https://api.gramads.net/ad/SendPost"
GRAMADS_TOKEN = ""
gramads_enabled = False
last_ad_times = {}  # Кеш останніх показів реклами
AD_COOLDOWN = 300  # 10 хвилин між показами


async def load_gramads_token():
    """Загрузка токена Gramads из БД"""
    global GRAMADS_TOKEN, gramads_enabled

    token_from_db = await get_setting("gramads_token")

    if token_from_db and token_from_db.startswith("eyJ"):
        GRAMADS_TOKEN = token_from_db
        gramads_enabled = True
        print(f"✅ Загружен токен Gramads из БД")
        return True
    else:
        gramads_enabled = False
        print("⚠️ Токен Gramads не найден в БД")
        return False


async def show_gramads_ad(user_id: int):
    """Показать рекламу через Gramads API"""
    global gramads_enabled, GRAMADS_TOKEN

    if not gramads_enabled or not GRAMADS_TOKEN:
        print(f"⚠️ Gramads отключен для пользователя {user_id}")
        return False

    # Проверяем кэш последних показов
    current_time = time.time()
    if user_id in last_ad_times:
        time_diff = current_time - last_ad_times[user_id]
        if time_diff < AD_COOLDOWN:
            print(f"⏰ Пользователю {user_id} недавно показывали рекламу ({int(time_diff)} сек назад)")
            return False

    try:
        headers = {
            'Authorization': f'Bearer {GRAMADS_TOKEN}',
            'Content-Type': 'application/json',
        }

        print(f"📺 Показываем рекламу пользователю {user_id}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    GRAMADS_API_URL,
                    headers=headers,
                    json={'SendToChatId': user_id},
                    timeout=10
            ) as response:

                # Получаем текст ответа в любом формате
                response_text = await response.text()

                # Проверяем статус код
                if response.status == 200:
                    print(f"✅ Реклама успешно показана пользователю {user_id}")
                    print(f"📊 Ответ API: {response_text}")

                    # Пытаемся разобрать JSON, если это возможно
                    try:
                        data = json.loads(response_text)
                        print(f"📦 JSON данные: {data}")
                    except json.JSONDecodeError:
                        # Если ответ не JSON, но статус 200 - всё равно считаем успехом
                        print(f"⚠️ Ответ не в JSON формате, но статус 200: {response_text}")

                    # Обновляем время последнего показа
                    last_ad_times[user_id] = current_time

                    # Сохраняем в БД для persistence
                    await set_setting(f"last_ad_{user_id}", str(current_time))

                    return True
                else:
                    print(f"❌ Ошибка Gramads API: {response.status} - {response_text}")

                    # Если ошибка авторизации - отключаем Gramads
                    if response.status == 401:
                        gramads_enabled = False
                        print("🔴 Gramads отключен из-за ошибки авторизации")

                    return False

    except asyncio.TimeoutError:
        print(f"⚠️ Timeout при показе рекламы пользователю {user_id}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при показе рекламы: {e}")
        return False


async def show_ad_at_opportunity(user_id: int, context: str = "general"):
    """Показать рекламу при удобном случае"""
    try:
        # Пропускаем админов
        if user_id in ADMIN_IDS:
            return False

        # Пропускаем ботов
        if len(str(user_id)) <= 6:
            return False

        # Проверяем настройки пользователя (можно добавить позже)
        # user = await get_user(user_id)
        # if user.get('disable_ads', False):
        #     return False

        # Определяем вероятность показа в зависимости от контекста
        probabilities = {
            "after_task": 1,  # 80% после задания
            "after_withdrawal": 1,  # 60% после вывода
            "after_topup": 1,  # 70% после пополнения
            "general": 1  # 30% в общих случаях
        }

        prob = probabilities.get(context, 0.3)

        # Случайное решение показывать или нет
        import random
        if random.random() > prob:
            print(f"🎲 Пропускаем рекламу для {user_id} (вероятность {prob})")
            return False

        # Показываем рекламу
        return await show_gramads_ad(user_id)

    except Exception as e:
        print(f"❌ Ошибка в show_ad_at_opportunity: {e}")
        return False


async def schedule_periodic_ads():
    """Периодический показ рекламы активным пользователям"""
    while True:
        try:
            if gramads_enabled:
                print("📢 Запуск периодического показа рекламы...")

                # Получаем активных пользователей (последние 7 дней)
                async with aiosqlite.connect('bot_database.db') as db:
                    async with db.execute('''
                        SELECT user_id FROM users 
                        WHERE is_blocked = FALSE 
                        AND user_id NOT IN (SELECT user_id FROM users WHERE user_id IN ?)
                        LIMIT 50
                    ''', (tuple(ADMIN_IDS),)) as cursor:
                        users = await cursor.fetchall()

                print(f"📊 Найдено {len(users)} пользователей для рекламы")

                for user_row in users:
                    user_id = user_row[0]

                    # Показываем с меньшей вероятностью для периодических показов
                    import random
                    if random.random() < 0.2:  # 20% вероятность
                        await show_ad_at_opportunity(user_id, "periodic")

                    # Небольшая задержка между пользователями
                    await asyncio.sleep(0.5)

            # Ждем 1 час до следующей проверки
            await asyncio.sleep(3600)

        except Exception as e:
            print(f"❌ Ошибка в schedule_periodic_ads: {e}")
            await asyncio.sleep(300)


class LanguageMessageMiddleware(BaseMiddleware):
    async def __call__(self, handler, message: Message, data):
        user = message.from_user
        if not user:
            return await handler(message, data)

        if user.id in ADMIN_IDS:
            return await handler(message, data)
        enabled = await get_setting("req_language")
        if enabled != "1":
            return await handler(message, data)

        allowed = [
            x.strip().lower()
            for x in (await get_setting("allowed_languages") or "ru").split(",")
            if x.strip()
        ]

        user_lang = (user.language_code or "").lower().split("-")[0]

        if user_lang not in allowed:
            await message.answer(
                "❌ Доступ заблокирован.\n\n"
                "Язык вашего Telegram не поддерживается."
            )
            return  # ⬅️ КРИТИЧНО

        return await handler(message, data)


class LanguageCallbackMiddleware(BaseMiddleware):
    async def __call__(self, handler, call: CallbackQuery, data):
        user = call.from_user
        if not user:
            return await handler(call, data)

        if user.id in ADMIN_IDS:
            return await handler(call, data)
        enabled = await get_setting("req_language")
        if enabled != "1":
            return await handler(call, data)

        allowed = [
            x.strip().lower()
            for x in (await get_setting("allowed_languages") or "ru").split(",")
            if x.strip()
        ]

        user_lang = (user.language_code or "").lower().split("-")[0]

        if user_lang not in allowed:
            await call.answer(
                "Язык Telegram не поддерживается",
                show_alert=True
            )
            return  # ⬅️ КРИТИЧНО

        return await handler(call, data)


dp.message.middleware(LanguageMessageMiddleware())
dp.callback_query.middleware(LanguageCallbackMiddleware())


class GramadsMiddleware(BaseMiddleware):
    """Middleware для показа рекламы после взаимодействия с главным меню"""

    def __init__(self):
        self.ad_cooldown = 300  # 5 минут между показами
        self.last_ad_times = {}

    async def __call__(self, handler, event, data):
        # Сначала обрабатываем событие
        result = await handler(event, data)

        try:
            if isinstance(event, Message) and event.text:
                user_id = event.from_user.id

                # Список ВСЕХ кнопок главного меню, при которых хотим показывать рекламу
                main_menu_buttons = [
                    "📝 Задания",
                    "👥 Рефералы",
                    "📱 Кабинет",
                    "📚 Инфо"
                ]

                # Проверяем, является ли текст кнопкой главного меню
                if event.text in main_menu_buttons:
                    current_time = time.time()
                    last_time = self.last_ad_times.get(user_id, 0)

                    # Проверяем прошло ли достаточно времени
                    if current_time - last_time < self.ad_cooldown:
                        print(
                            f"⏰ Пользователю {user_id} недавно показывали рекламу ({int(current_time - last_time)} сек назад)")
                        return result

                    # Показываем рекламу с вероятностью 30% (можно настроить)
                    import random
                    show_probability = 1  # 30% вероятность показа

                    if random.random() < show_probability:
                        print(f"🎲 Показываем рекламу пользователю {user_id} (кнопка: {event.text})")
                        success = await show_gramads_ad(user_id)
                        if success:
                            self.last_ad_times[user_id] = current_time
                            print(f"✅ Реклама успешно показана пользователю {user_id}")
                        else:
                            print(f"❌ Не удалось показать рекламу пользователю {user_id}")

        except Exception as e:
            print(f"⚠️ Ошибка в GramadsMiddleware: {e}")

        return result


# Добавьте middleware в диспетчер (после инициализации dp)
dp.update.middleware(GramadsMiddleware())


@dp.message(F.text == "💰 Баланс резерва")
async def admin_balance_btn(message: Message):
    await asyncio.sleep(0.1)

    total_balance = await get_crypto_bot_balance()

    # Определяем статус резерва
    if total_balance < 1:
        reserve_status = "🚨 КРИТИЧЕСКИ НИЗКИЙ"
        reserve_emoji = "🔴"
        recommendation = "❌ СРОЧНО ПОПОЛНИТЕ РЕЗЕРВ!"
    elif total_balance < 1:
        reserve_status = "⚠️ НИЗКИЙ"
        reserve_emoji = "🟡"
        recommendation = "💡 Рекомендуется пополнить резерв"
    elif total_balance < 5:
        reserve_status = "ℹ️ СРЕДНИЙ"
        reserve_emoji = "🟢"
        recommendation = "✅ Резерв в норме"
    else:
        reserve_status = "✅ ДОСТАТОЧНЫЙ"
        reserve_emoji = "💚"
        recommendation = "🎉 Отличный запас!"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 Пополнить резерв", callback_data="reserve_topup")]
    ])

    await message.answer(
        f"💰 <b>БАЛАНС СИСТЕМЫ</b>\n\n"
        f"💵 Текущий баланс: <b>{total_balance:.2f} USDT</b>\n"
        f"📊 Статус: {reserve_emoji} <b>{reserve_status}</b>\n\n"
        f"<i>{recommendation}</i>",
        parse_mode='HTML',
        reply_markup=kb
    )


@dp.callback_query(F.data == "reserve_topup")
async def admin_topup_callback(call: CallbackQuery, state: FSMContext):
    await call.answer()
    total_balance = await get_crypto_bot_balance()

    await call.message.edit_text(
        f"💵 <b>Пополнение резерва системы</b>\n\n"
        f"💰 Текущий баланс кошелька: <b>{total_balance:.2f} USDT</b>\n\n"
        f"Введите сумму в USDT для пополнения:",
        parse_mode='HTML'
    )
    await state.set_state(ReserveTopupStates.waiting_for_amount)


@dp.message(ReserveTopupStates.waiting_for_amount)
async def process_topup_amount(message: Message, state: FSMContext):
    """Обрабатывает введенную сумму для пополнения"""
    try:
        amount = float(message.text.strip())

        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return

        if amount < 1:
            await message.answer("❌ Минимальная сумма пополнения: 1 USDT")
            return

        # Создаем инвойс для пополнения
        invoice_url = await create_reserve_topup_invoice(amount, message.from_user.id)

        if invoice_url and invoice_url != "https://t.me/CryptoBot":
            await message.answer(
                f"💳 <b>ИНВОЙС ДЛЯ ПОПОЛНЕНИЯ РЕЗЕРВА</b>\n\n"
                f"💰 Сумма: <b>{amount:.2f} USDT</b>\n"
                f"📎 Ссылка для оплаты: {invoice_url}\n\n"
                f"⚠️ <i>После оплаты средства поступят в резерв системы.</i>\n"
                f"🔧 <i>Используется тот же кошелек, что и для выплат.</i>",
                reply_markup=get_admin_keyboard(),
                parse_mode='HTML'
            )

            # Уведомляем других админов
            for admin_id in ADMIN_IDS:
                if admin_id != message.from_user.id:
                    try:
                        await bot.send_message(
                            admin_id,
                            f"👤 Админ @{message.from_user.username or 'N/A'} создал инвойс\n"
                            f"💰 Сумма: {amount:.2f} USDT\n"
                            f"💳 Для пополнения резерва",
                            parse_mode='HTML'
                        )
                    except:
                        pass

        else:
            await message.answer("❌ Не удалось создать инвойс. Попробуйте позже.")

    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректную сумму (например: 10.5)")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

    await state.clear()


async def create_reserve_topup_invoice(amount, admin_id):
    """Создает инвойс для пополнения резерва системы"""
    try:
        payload = {
            "asset": "USDT",
            "amount": str(amount),
            "description": f"Пополнение резерва системы на {amount} USDT",
            "hidden_message": f"Пополнение от админа {admin_id}",
            "paid_btn_name": "openBot",
            "paid_btn_url": "https://t.me/your_bot",
            "payload": f"reserve_topup_{admin_id}_{int(time.time())}",
            "allow_comments": False,
            "allow_anonymous": False,
        }

        headers = {
            "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
            "Content-Type": "application/json"
        }

        endpoint = "https://pay.crypt.bot/api/createInvoice"

        print(f"🔧 СОЗДАЕМ ИНВОЙС ДЛЯ ПОПОЛНЕНИЯ РЕЗЕРВА: {amount} USDT")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=30
            ) as response:

                print(f"🔧 Статус ответа: {response.status}")
                response_text = await response.text()
                print(f"🔧 Текст ответа: {response_text}")

                if response.status == 200:
                    data = await response.json()
                    print(f"🔧 Разобранный ответ: {data}")

                    if data.get('ok'):
                        invoice_url = data['result']['pay_url']
                        print(f"✅ Инвойс для пополнения создан: {invoice_url}")
                        return invoice_url
                    else:
                        error_msg = data.get('error', {}).get('name', 'Unknown error')
                        print(f"❌ Ошибка создания инвойса: {error_msg}")
                        return "https://t.me/CryptoBot"
                else:
                    print(f"❌ HTTP ошибка: {response.status}")
                    return "https://t.me/CryptoBot"

    except Exception as e:
        print(f"❌ Ошибка создания инвойса для пополнения: {e}")
        return "https://t.me/CryptoBot"


async def create_ad_invoice(user_id: int, amount: float):
    """Создает инвойс через CryptoBot для пополнения рекламного баланса"""
    try:
        payload = {
            "asset": "USDT",
            "amount": str(amount),
            "description": f"Пополнение рекламного баланса пользователя {user_id}",
            "hidden_message": f"Рекламное пополнение {user_id}",
            "paid_btn_name": "openBot",
            "paid_btn_url": "https://t.me/your_bot",
            "payload": f"ad_{user_id}_{int(time.time())}",
            "allow_comments": False,
            "allow_anonymous": False,
        }

        headers = {
            "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post("https://pay.crypt.bot/api/createInvoice",
                                    json=payload, headers=headers) as response:
                data = await response.json()
                if data.get("ok"):
                    invoice = data["result"]
                    async with aiosqlite.connect('bot_database.db') as db:
                        await db.execute(
                            'INSERT INTO ad_topups (user_id, invoice_id, amount) VALUES (?, ?, ?)',
                            (user_id, invoice["invoice_id"], amount)
                        )
                        await db.commit()
                    return invoice["pay_url"]
                else:
                    print("❌ Ошибка создания инвойса:", data)
                    return None
    except Exception as e:
        print("❌ Ошибка create_ad_invoice:", e)
        return None


async def check_ad_invoice(invoice_id: str):
    """Проверяет оплату по конкретному invoice_id через CryptoBot"""
    try:
        headers = {
            "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
            "Content-Type": "application/json"
        }

        url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                print("📦 Ответ CryptoBot:", data)

                if not data.get("ok"):
                    return False

                items = data["result"].get("items", [])
                if not items:
                    print("❌ Инвойс не найден")
                    return False

                inv = items[0]
                status = inv.get("status")
                print(f"🔍 Статус инвойса {invoice_id}: {status}")

                if status == "paid":
                    async with aiosqlite.connect('bot_database.db') as db:
                        async with db.execute(
                                'SELECT status, user_id, amount FROM ad_topups WHERE invoice_id = ?',
                                (invoice_id,)
                        ) as c:
                            row = await c.fetchone()
                            if not row:
                                print("⚠️ Не найден инвойс в таблице ad_topups")
                                return False

                            status_db, user_id, amount = row
                            if status_db == "paid":
                                return "already_paid"

                            # 🔧 Приводим сумму к float, чтобы арифметика сработала
                            try:
                                amount = float(amount)
                            except Exception as e:
                                print(f"⚠️ Ошибка преобразования amount: {e}")
                                amount = 0.0

                            # 🔄 Обновляем статусы и баланс
                            await db.execute(
                                'UPDATE ad_topups SET status="paid", paid_at=CURRENT_TIMESTAMP WHERE invoice_id=?',
                                (invoice_id,)
                            )
                            await db.execute(
                                'UPDATE users SET ad_balance = COALESCE(ad_balance, 0) + ? WHERE user_id=?',
                                (amount, user_id)
                            )
                            await db.commit()

                            print(f"✅ Рекламный баланс пользователя {user_id} увеличен на {amount} $")

                            await bot.send_message(
                                user_id,
                                f"✅ Оплата подтверждена!\n💵 Рекламный баланс пополнен на {amount:.3f} $."
                            )
                            return True

                elif status in ["active", "pending"]:
                    print("🕐 Инвойс еще не оплачен")
                    return False

                else:
                    print(f"⚠️ Инвойс в статусе: {status}")
                    return False

    except Exception as e:
        print(f"❌ Ошибка check_ad_invoice: {e}")
        return False


async def get_setting(key):
    try:
        async with aiosqlite.connect('bot_database.db') as db:
            # Проверяем существование таблицы
            async with db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'") as cursor:
                if not await cursor.fetchone():
                    return None

            async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        print(f"❌ Ошибка получения настройки {key}: {e}")
        return None


async def set_setting(key, value):
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()


# Инициализация Flyer
flyer = None
flyer_enabled = False


# Инициализация базы данных
async def init_db():
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0,
                frozen_balance REAL DEFAULT 0,
                completed_tasks INTEGER DEFAULT 0,
                referrer_id INTEGER,
                is_blocked BOOLEAN DEFAULT FALSE,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ad_balance REAL DEFAULT 0,
                ref_paid_level1 INTEGER DEFAULT 0,
                ref_paid_level2 INTEGER DEFAULT 0
            )
        ''')

        try:
            await db.execute("ALTER TABLE users ADD COLUMN ref_paid_level1 INTEGER DEFAULT 0")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"⚠️ ref_paid_level1 уже существует или ошибка: {e}")

        try:
            await db.execute("ALTER TABLE users ADD COLUMN ref_paid_level2 INTEGER DEFAULT 0")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"⚠️ ref_paid_level2 уже существует или ошибка: {e}")

        try:
            await db.execute("ALTER TABLE users ADD COLUMN ref_paid_in_progress_lvl1 INTEGER DEFAULT 0")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"⚠️ ref_paid_in_progress_lvl1 уже существует или ошибка: {e}")

        try:
            await db.execute("ALTER TABLE users ADD COLUMN ref_paid_in_progress_lvl2 INTEGER DEFAULT 0")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"⚠️ ref_paid_in_progress_lvl2 уже существует или ошибка: {e}")

        await db.execute('''
            CREATE TABLE IF NOT EXISTS custom_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                url TEXT NOT NULL,
                button_text TEXT DEFAULT 'Выполнить',
                price REAL DEFAULT 0.015,
                max_completions INTEGER DEFAULT 0,
                current_completions INTEGER DEFAULT 0,
                task_type TEXT DEFAULT 'url',  -- 'url', 'subscribe_channel'
                channel_username TEXT,  -- для заданий типа подписка
                is_active BOOLEAN DEFAULT TRUE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS frozen_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                task_type TEXT,
                task_id INTEGER,
                frozen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                unfreeze_at TIMESTAMP,
                is_unfrozen BOOLEAN DEFAULT FALSE
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                receipt_url TEXT,
                admin_receipt_url TEXT,
                status TEXT DEFAULT 'pending',
                reject_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                admin_id INTEGER
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS balance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                admin_id INTEGER,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS custom_task_completions (
                task_id INTEGER,
                user_id INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (task_id, user_id)
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_notifications (
                user_id INTEGER PRIMARY KEY,
                last_notification TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS completed_tasks (
                user_id INTEGER,
                signature TEXT,
                status TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, signature)
            )
        ''')

        # Начальные настройки
        await db.execute('''
            INSERT OR IGNORE INTO settings (key, value) VALUES 
            ('min_withdrawal', '0.2'),
            ('currency', 'USD'),
            ('payments_channel', ''),
            ('chat_link', '')
        ''')
        # === Нові таблиці для продвижения ===
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_link TEXT NOT NULL,
                channel_username TEXT,
                price REAL DEFAULT 0.015,
                max_completions INTEGER NOT NULL,
                current_completions INTEGER DEFAULT 0,
                created_by INTEGER,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                task_type TEXT DEFAULT 'channel'
            )
        ''')
        try:
            await db.execute("ALTER TABLE user_tasks ADD COLUMN task_type TEXT DEFAULT 'channel'")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"⚠️ task_type уже существует или ошибка: {e}")

        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_task_completions (
                task_id INTEGER,
                user_id INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (task_id, user_id)
            )
        ''')

        await db.execute('''
            INSERT OR IGNORE INTO settings (key, value) VALUES ('promotion_price', '0.015')
        ''')
        await db.execute('''
            INSERT OR IGNORE INTO settings (key, value) VALUES 
            ('ref_bonus_level1', '0.05'),
            ('ref_bonus_level2', '0.03'),
            ('ref_tasks_required_level1', '3'),
            ('ref_tasks_required_level2', '5')
        ''')

        try:
            await db.execute("ALTER TABLE users ADD COLUMN ref_paid_level1 INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN ref_paid_level2 INTEGER DEFAULT 0")
        except:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN ref_tasks_completed INTEGER DEFAULT 0")
        except:
            pass
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # якщо нема запису — додаємо дефолтне значення
        await db.execute('INSERT OR IGNORE INTO settings (key, value) VALUES ("user_task_reward", "0.015")')

        # 🔹 Добавляем поле ad_balance, если его нет
        try:
            await db.execute("ALTER TABLE users ADD COLUMN ad_balance REAL DEFAULT 0")
        except:
            pass
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ad_topups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                invoice_id TEXT UNIQUE,
                amount REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP
            )
        ''')

        try:
            await db.execute("ALTER TABLE frozen_transactions ADD COLUMN penalty_applied INTEGER DEFAULT 0;")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"⚠️ penalty_applied already exists or error: {e}")

        try:
            await db.execute("ALTER TABLE frozen_transactions ADD COLUMN penalty_amount REAL DEFAULT 0;")
        except Exception as e:
            if "duplicate column" not in str(e).lower():
                print(f"⚠️ penalty_amount already exists or error: {e}")

        try:
            await db.execute("ALTER TABLE frozen_transactions ADD COLUMN task_ref TEXT")
        except Exception:
            pass

        await db.commit()


async def get_task_status(user_id, signature):
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute(
                'SELECT status FROM completed_tasks WHERE user_id = ? AND signature = ?',
                (user_id, signature)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None


async def set_task_status(user_id, signature, status):
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO completed_tasks (user_id, signature, status) 
            VALUES (?, ?, ?)
        ''', (user_id, signature, status))
        await db.commit()


async def load_crypto_token():
    """Загрузка токена криптобота из БД или установка дефолтного"""
    global CRYPTO_BOT_TOKEN, crypto_enabled

    token_from_db = await get_setting("CRYPTO_BOT_TOKEN")

    if token_from_db:
        CRYPTO_BOT_TOKEN = token_from_db
        crypto_enabled = True
        print(f"✅ Загружен токен криптобота из БД: {CRYPTO_BOT_TOKEN[:8]}...")
    else:
        CRYPTO_BOT_TOKEN = DEFAULT_CRYPTO_BOT_TOKEN
        crypto_enabled = True
        print("⚠️ Токен криптобота не найден в БД. Используется дефолтный токен.")


# --- TGRASS CONFIG ---
# --- TGRASS CONFIG ---
TGRASS_ENDPOINT = "https://tgrass.space/offers"


async def get_tgrass_offers(user_id: int, username: str = None, is_premium: bool = False):
    """Отримання офферів з TGRASS з оптимізацією"""
    api_key = await get_setting('tgrass_api_key')
    if not api_key:
        return {'offers': []}

    payload = {
        "tg_user_id": int(user_id),
        "tg_login": str(username) if username else "",
        "lang": "ru",
        "is_premium": is_premium
    }
    headers = {"Content-Type": "application/json", "Auth": api_key}

    try:
        async with aiohttp.ClientSession() as session:
            # Зменшити таймаут до 2 секунд
            async with session.post(TGRASS_ENDPOINT, json=payload, headers=headers, timeout=2) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    return {'offers': []}
    except asyncio.TimeoutError:
        print(f"⚠️ TGRASS timeout for user {user_id}")
        return {'offers': []}
    except Exception as e:
        print(f"⚠️ TGRASS error for user {user_id}: {e}")
        return {'offers': []}


class TgrassMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):

        user = data.get('event_from_user')

        if user.id in ADMIN_IDS:
            return await handler(event, data)

        # 1. СПОЧАТКУ перевіряємо мову
        enabled = await get_setting("req_language")
        if enabled == "1":
            allowed = [
                x.strip().lower()
                for x in (await get_setting("allowed_languages") or "ru").split(",")
                if x.strip()
            ]

            user_lang = (user.language_code or "").lower().split("-")[0]

            if user_lang not in allowed:
                if isinstance(event, Message):
                    await event.answer(
                        "❌ Доступ заблокирован.\n\n"
                        "Язык вашего Telegram не поддерживается."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "Язык Telegram не поддерживается",
                        show_alert=True
                    )
                return  # Блокуємо

        if isinstance(event, Message) and event.text:

            if event.text.startswith('/start'):
                return await handler(event, data)

            offers_data = await get_tgrass_offers(

                user.id,

                user.username,

                user.is_premium or False)

            if offers_data and offers_data.get('status') == 'not_ok':
                await self.show_tgrass_tasks(event, user.id, offers_data)

                return

        return await handler(event, data)
        # Показываем задания TGRASS

    async def show_tgrass_tasks(self, event, user_id: int, offers_data: dict):
        """Показывает задания TGRASS"""
        if not offers_data or 'offers' not in offers_data:
            return

        unsubscribed = [o for o in offers_data['offers'] if not o.get('subscribed')]

        if not unsubscribed:
            return

        kb = InlineKeyboardBuilder()
        for o in unsubscribed:
            kb.row(InlineKeyboardButton(
                text=f"🌿 Подписаться",
                url=o['link']
            ))
        kb.row(InlineKeyboardButton(
            text="✅ Я подписался",
            callback_data="check_tgrass_sub"
        ))

        text = (
            "⚠️ <b>Доступ заблокирован!</b>\n\n"
            "Чтобы пользоваться ботом, вы должны подписаться на каналы спонсоров:"
        )

        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")


# Обработчик проверки подписок
@dp.callback_query(F.data == "check_tgrass_sub")
async def check_tgrass_subscription(call: CallbackQuery):
    """Проверяет подписки через TGRASS"""
    user = call.from_user

    offers_data = await get_tgrass_offers(
        user.id,
        user.username,
        user.is_premium or False
    )

    if offers_data and offers_data.get('status') == 'ok':
        # Все подписки выполнены
        await call.message.delete()
        await call.answer("✅ Отлично! Теперь все функции бота доступны.", show_alert=False)

        # Показываем главное меню
        await cmd_start(call.message)
    else:
        # Не все подписки выполнены
        unsubscribed = [o for o in offers_data.get('offers', []) if not o.get('subscribed')]

        if unsubscribed:
            kb = InlineKeyboardBuilder()
            for o in unsubscribed:
                kb.row(InlineKeyboardButton(
                    text=f"🌿 Подписаться",
                    url=o['link']
                ))
            kb.row(InlineKeyboardButton(
                text="✅ Я подписался",
                callback_data="check_tgrass_sub"
            ))

            await call.message.edit_text(
                "❌ Вы подписались не на все каналы!",
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
            await call.answer("Пожалуйста, подпишитесь на все каналы", show_alert=True)
        else:
            await call.answer("❌ Произошла ошибка проверки", show_alert=True)


# Добавьте обработчик для команды /tgrass для тестирования
@dp.message(Command("tgr"))
async def tgrass_test_command(message: Message):
    """Тестирование TGRASS API"""
    user = message.from_user

    offers_data = await get_tgrass_offers(
        user.id,
        user.username,
        user.is_premium or False
    )

    if offers_data:
        text = f"""
📊 <b>TGRASS Debug Info:</b>

🆔 User ID: {user.id}
👤 Username: @{user.username}
🔑 API Key: {await get_setting('tgrass_api_key')[:10]}...

📋 <b>Response:</b>
Status: {offers_data.get('status', 'N/A')}
Offers count: {len(offers_data.get('offers', []))}

📝 <b>Offers:</b>
"""
        for i, offer in enumerate(offers_data.get('offers', [])[:5], 1):
            text += f"{i}. {offer.get('name')} - Subscribed: {offer.get('subscribed')}\n"

        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("❌ Не удалось получить данные от TGRASS")


# АДМІНКА: Зміна ключа
@dp.callback_query(F.data == "admin_tgrass_settings")
async def admin_tgrass(call: CallbackQuery):
    key = await get_setting('tgrass_api_key') or "Не установлен"
    await call.message.edit_text(
        f"⚙️ <b>Настройки Tgrass OP</b>\n\nТекущий ключ: <code>{key}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить ключ", callback_data="set_tgrass_key")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_main")]
        ]), parse_mode="HTML"
    )


@dp.callback_query(F.data == "set_tgrass_key")
async def set_tgrass_key_step1(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Пришлите новый API Ключ Tgrass:")
    await state.set_state(TGRASSS.wait_tgrass_key)


@dp.message(TGRASSS.wait_tgrass_key)
async def save_tgrass_key(message: Message, state: FSMContext):
    await set_setting('tgrass_api_key', message.text.strip())
    await message.answer("✅ Ключ успешно сохранен в базу данных!")
    await state.clear()


# -------------------------
# Подсчёт заявок по статусу
# -------------------------
async def count_withdrawals_by_status(status: str) -> int:
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("SELECT COUNT(*) FROM withdrawals WHERE status = ?", (status,)) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row and row[0] is not None else 0


async def get_user(user_id):
    async with aiosqlite.connect('bot_database.db') as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
            user = await cursor.fetchone()

            if user:
                def safe_float(value):
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return 0.0

                def safe_int(value):
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        return 0

                # ✅ КОРЕКТНИЙ СПОСІБ - перевіряємо чи є поле, потім отримуємо значення
                def get_field(field_name, default_value=None):
                    """Безпечно отримує значення поля з Row"""
                    if field_name in user.keys():
                        return user[field_name]
                    return default_value

                # Отримуємо всі поля безпечно
                balance = safe_float(get_field('balance', 0))
                frozen_balance = safe_float(get_field('frozen_balance', 0))
                ad_balance = safe_float(get_field('ad_balance', 0))
                completed_tasks = get_field('completed_tasks', 0)
                referrer_id = get_field('referrer_id')
                is_blocked = get_field('is_blocked', False)
                ref_paid_level1 = safe_int(get_field('ref_paid_level1', 0))
                ref_paid_level2 = safe_int(get_field('ref_paid_level2', 0))
                username = get_field('username', f"user_{user_id}")

                return {
                    'user_id': user_id,
                    'username': username,
                    'balance': balance,
                    'frozen_balance': frozen_balance,
                    'completed_tasks': completed_tasks,
                    'referrer_id': referrer_id,
                    'is_blocked': bool(is_blocked),
                    'ad_balance': ad_balance,
                    'ref_paid_level1': ref_paid_level1,
                    'ref_paid_level2': ref_paid_level2
                }

            # Якщо користувача немає — створюємо нового
            username = f"user_{user_id}"
            try:
                chat = await bot.get_chat(user_id)
                username = chat.username or chat.first_name or username
            except:
                pass

            # Створюємо нового користувача з усіма полями
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute('''
                    INSERT OR IGNORE INTO users 
                    (user_id, username, balance, frozen_balance, ad_balance, 
                     completed_tasks, referrer_id, is_blocked, 
                     ref_paid_level1, ref_paid_level2, 
                     ref_paid_in_progress_lvl1, ref_paid_in_progress_lvl2)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, username, 0, 0, 0, 0, None, False, 0, 0, 0, 0))
                await db.commit()

            return {
                'user_id': user_id,
                'username': username,
                'balance': 0.0,
                'frozen_balance': 0.0,
                'completed_tasks': 0,
                'referrer_id': None,
                'is_blocked': False,
                'ad_balance': 0.0,
                'ref_paid_level1': 0,
                'ref_paid_level2': 0
            }


async def update_user_balance(user_id, amount=0, frozen_amount=0, completed_tasks=0):
    print(
        f"🔧 update_user_balance вызвана: user_id={user_id}, amount={amount}, frozen_amount={frozen_amount}, completed_tasks={completed_tasks}")

    max_retries = 3
    retry_delay = 0.5

    for attempt in range(max_retries):
        try:
            async with aiosqlite.connect('bot_database.db') as db:
                if amount != 0:
                    await db.execute(
                        'UPDATE users SET balance = balance + ? WHERE user_id = ?',
                        (amount, user_id)
                    )
                    print(f"💳 Изменен баланс: {amount}$")

                if frozen_amount != 0:
                    await db.execute(
                        'UPDATE users SET frozen_balance = frozen_balance + ? WHERE user_id = ?',
                        (frozen_amount, user_id)
                    )
                    print(f"❄️ Изменен замороженный баланс: {frozen_amount}$")

                if completed_tasks != 0:
                    await db.execute(
                        'UPDATE users SET completed_tasks = completed_tasks + ? WHERE user_id = ?',
                        (completed_tasks, user_id)
                    )
                    print(f"📝 Изменено количество заданий: {completed_tasks}")

                await db.commit()
                print(f"✅ Баланс пользователя {user_id} обновлен")

                # ⬇️ ДОДАЄМО ВИКЛИК ПЕРЕВІРКИ РЕФЕРАЛЬНИХ БОНУСІВ
                if completed_tasks > 0:
                    await check_and_pay_referral_bonus(user_id)

                return True

        except Exception as e:
            print(f"❌ Попытка {attempt + 1}/{max_retries} не удалась: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                print(f"❌ Не удалось обновить баланс пользователя {user_id} после {max_retries} попыток")
                return False


async def safe_db_operation(operation, *args, **kwargs):
    """Безопасное выполнение операций с БД с повторными попытками"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await operation(*args, **kwargs)
        except Exception as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            else:
                raise e


async def create_withdrawal_request(user_id, amount):
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute(
            'INSERT INTO withdrawals (user_id, amount) VALUES (?, ?)',
            (user_id, amount)
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_withdrawals():
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('''
            SELECT w.*, u.username 
            FROM withdrawals w 
            LEFT JOIN users u ON w.user_id = u.user_id 
            WHERE w.status = 'pending'
            ORDER BY w.created_at
        ''') as cursor:
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in await cursor.fetchall()]


async def get_withdrawal(withdrawal_id):
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('''
            SELECT w.*, u.username 
            FROM withdrawals w 
            LEFT JOIN users u ON w.user_id = u.user_id 
            WHERE w.id = ?
        ''', (withdrawal_id,)) as cursor:
            columns = [column[0] for column in cursor.description]
            row = await cursor.fetchone()
            return dict(zip(columns, row)) if row else None


async def update_withdrawal_status(withdrawal_id, status, admin_id=None, admin_receipt_url=None, reject_reason=None):
    try:
        async with aiosqlite.connect('bot_database.db') as db:
            if status == 'approved':
                await db.execute('''
                    UPDATE withdrawals 
                    SET status = ?, admin_id = ?, admin_receipt_url = ?, processed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (status, admin_id, admin_receipt_url, withdrawal_id))

            elif status in ('rejected', 'declined'):
                # declined == отклонено без возврата
                await db.execute('''
                    UPDATE withdrawals 
                    SET status = ?, admin_id = ?, reject_reason = ?, processed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (status, admin_id, reject_reason or 'Отклонено администратором', withdrawal_id))

            elif status == 'refunded':
                await db.execute('''
                    UPDATE withdrawals 
                    SET status = ?, admin_id = ?, processed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, admin_id, withdrawal_id))

            await db.commit()

            # Возвращаем средства если статус подразумевает возврат
            if status in ('rejected', 'refunded') or status == 'rejected':
                # Если логіка твоя — only for 'refunded' возврат, то убери 'rejected'
                if status == 'refunded':
                    withdrawal = await get_withdrawal(withdrawal_id)
                    if withdrawal:
                        await update_user_balance(withdrawal['user_id'], amount=withdrawal['amount'])

    except Exception as e:
        print(f"❌ Ошибка при обновлении статуса вывода: {e}")


async def get_referral_data(user_id):
    async with aiosqlite.connect('bot_database.db') as db:
        # Рефералы 1 уровня
        async with db.execute('SELECT COUNT(*) FROM users WHERE referrer_id = ?', (user_id,)) as cursor:
            level1_count = (await cursor.fetchone())[0]

        # Рефералы 2 уровня
        async with db.execute('''
            SELECT COUNT(*) FROM users 
            WHERE referrer_id IN (SELECT user_id FROM users WHERE referrer_id = ?)
        ''', (user_id,)) as cursor:
            level2_count = (await cursor.fetchone())[0]

        return {'level1_count': level1_count, 'level2_count': level2_count}


async def get_all_users():
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT user_id, username FROM users WHERE is_blocked = FALSE') as cursor:
            return await cursor.fetchall()


async def update_user_notification_time(user_id):
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('''
            INSERT OR REPLACE INTO user_notifications (user_id, last_notification) 
            VALUES (?, CURRENT_TIMESTAMP)
        ''', (user_id,))
        await db.commit()


async def get_user_last_notification(user_id):
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT last_notification FROM user_notifications WHERE user_id = ?',
                              (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                print(f"📅 В базе: пользователь {user_id} - последнее уведомление {result[0]}")
            else:
                print(f"📅 В базе: пользователь {user_id} - записей об уведомлениях нет")
            return result[0] if result else None


# Инициализация Flyer
def init_flyer():
    global flyer, flyer_enabled
    try:
        if FLYER_API_KEY and FLYER_API_KEY != 'your_flyer_api_key_here':
            flyer = Flyer(FLYER_API_KEY)
            flyer_enabled = True
            print("✅ Flyer API инициализирован")
            return True
        else:
            print("⚠️ Flyer API ключ не настроен")
            return False
    except Exception as e:
        print(f"❌ Ошибка инициализации Flyer: {e}")
        return False


# Проверка новых заданий и уведомление пользователей
async def check_new_tasks_for_user(user_id, language_code):
    global flyer_enabled
    """Проверяет новые задания для пользователя и отправляет уведомление"""
    if not flyer_enabled:
        print(f"❌ Flyer отключен для пользователя {user_id}")
        return

    try:
        # Пропускаем ботов (user_id с 5-6 знаками обычно боты)
        if len(str(user_id)) <= 6:
            print(f"⏭️ Пропускаем бота с ID: {user_id}")
            return

        # Используем get_tasks для проверки наличия новых заданий
        tasks = await flyer_get_tasks(user_id, language_code, limit=10)
        print(f"🔍 Для пользователя {user_id} получено {len(tasks)} заданий")

        if tasks:
            # Проверяем, когда последний раз уведомляли пользователя
            last_notification = await get_user_last_notification(user_id)
            now = datetime.now()

            if last_notification:
                time_diff = (now - datetime.fromisoformat(last_notification)).total_seconds()
                print(f"⏰ Пользователь {user_id}: последнее уведомление было {time_diff:.0f} сек назад")
            else:
                print(f"⏰ Пользователь {user_id}: уведомлений еще не было")

            # Проверяем условие времени (10 минут = 600 секунд)
            if not last_notification or (now - datetime.fromisoformat(last_notification)).total_seconds() > 600:

                print(f"✅ Условие для уведомления выполнено для пользователя {user_id}")

                # Отправляем уведомление
                try:
                    notification_text = (
                        f"🎉 <b>Появилось новое задание!</b>\n\n"
                        f"➡️ Перейдите в раздел <b>\"📝 Задания\"</b> чтобы выполнить его!"
                    )

                    await bot.send_message(user_id, notification_text, parse_mode='HTML')
                    print(f"📨 Уведомление отправлено пользователю {user_id}")

                    # Обновляем время последнего уведомления
                    await update_user_notification_time(user_id)
                    print(f"✅ Время уведомления обновлено для пользователя {user_id}")

                except Exception as e:
                    print(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")
            else:
                print(f"⏳ Для пользователя {user_id} еще не прошло 30 минут с последнего уведомления")
        else:
            print(f"ℹ️ Для пользователя {user_id} нет заданий для уведомления")

    except Exception as e:
        print(f"❌ Ошибка проверки заданий для пользователя {user_id}: {e}")


async def scheduled_task_checker():
    """Періодично перевіряє нові завдання для всіх користувачів"""
    while True:
        try:
            if flyer_enabled:
                users = await get_all_users()
                print(f"🔍 Проверяем новые задания для {len(users)} пользователей...")

                # Обмежте кількість одночасних перевірок
                semaphore = asyncio.Semaphore(10)  # Не більше 10 одночасно

                async def check_user_with_semaphore(user_id):
                    async with semaphore:
                        try:
                            await check_new_tasks_for_user(user_id, 'ru')
                            await asyncio.sleep(0.1)  # Зменшена затримка
                        except Exception as e:
                            print(f"Error checking tasks for user {user_id}: {e}")

                # Запускаємо перевірку паралельно
                tasks = [check_user_with_semaphore(user[0]) for user in users]
                await asyncio.gather(*tasks, return_exceptions=True)

            # ✅ Збільште інтервал до 30 хвилин
            print("⏰ Следующая проверка заданий через 30 минут...")
            await asyncio.sleep(1800)  # 30 хвилин

        except Exception as e:
            print(f"Error in scheduled task checker: {e}")
            await asyncio.sleep(300)


# Проверка блокировки пользователя
async def check_user_blocked(user_id):
    user = await get_user(user_id)
    return user['is_blocked']


# Главное меню (Reply клавиатура внизу экрана)
def get_main_keyboard(user_id: int):
    keyboard = ReplyKeyboardBuilder()
    keyboard.button(text="Задания", style='primary', icon_custom_emoji_id='5253742260054409879')  # 👈 нова кнопка
    keyboard.button(text="Рефералы", icon_custom_emoji_id='5271604874419647061')
    keyboard.button(text="Кабинет", icon_custom_emoji_id='5416041192905265756')  # 👈 нова кнопка
    keyboard.button(text="Статистика", icon_custom_emoji_id='5244837092042750681')
    if user_id in ADMIN_IDS:
        keyboard.button(text="👨‍💻 Админка")
    keyboard.adjust(2, 2, 1)
    return keyboard.as_markup(resize_keyboard=True)


class PromotionStates(StatesGroup):
    waiting_channel_link = State()
    waiting_task_type = State()
    waiting_bot_link = State()
    waiting_count = State()
    waiting_confirm = State()


from math import ceil


async def get_user_promo_counts(user_id: int):
    """Возвращает количество активных и завершённых заказов"""
    async with aiosqlite.connect("bot_database.db") as db:
        # Активные
        async with db.execute(
                "SELECT COUNT(*) FROM user_tasks WHERE created_by=? AND is_active=TRUE",
                (user_id,)
        ) as cursor:
            active = (await cursor.fetchone())[0]

        # Завершённые
        async with db.execute(
                "SELECT COUNT(*) FROM user_tasks WHERE created_by=? AND is_active=FALSE",
                (user_id,)
        ) as cursor:
            done = (await cursor.fetchone())[0]

        return active, done


@dp.callback_query(F.data.regexp(r"promo_(active|done)_page_\d+"))
async def show_promo_page(call: types.CallbackQuery):
    """Показ активных или завершённых заказов"""
    parts = call.data.split("_")
    mode = parts[1]  # active или done
    page = int(parts[-1])
    user_id = call.from_user.id

    per_page = 5
    offset = (page - 1) * per_page
    is_active = 1 if mode == "active" else 0

    async with aiosqlite.connect("bot_database.db") as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
                "SELECT * FROM user_tasks WHERE created_by=? AND is_active=? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, is_active, per_page, offset)
        ) as cursor:
            rows = await cursor.fetchall()

        async with db.execute(
                "SELECT COUNT(*) FROM user_tasks WHERE created_by=? AND is_active=?",
                (user_id, is_active)
        ) as cursor:
            total = (await cursor.fetchone())[0]

    total_pages = max(1, ceil(total / per_page))

    if not rows:
        await call.message.edit_text(
            "❌ У вас пока нет таких заказов.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="promo_back_menu")]]
            )
        )
        return

    title = "📈 Активные заказы" if is_active else "✅ Завершённые заказы"

    await call.message.edit_text(
        f"{title}\n\nСтраница {page}/{total_pages}",
        reply_markup=promo_pagination_keyboard(rows, page, total_pages, mode),
        parse_mode="HTML"
    )


async def promotion_menu(message: types.Message):
    user = await get_user(message.from_user.id)
    promo_price = float(await get_setting("promotion_price") or 0.015)
    ad_balance = float(user.get("ad_balance", 0))
    possible = int(ad_balance // promo_price)
    bot_username = (await bot.get_me()).username
    active_count, done_count = await get_user_promo_counts(message.from_user.id)

    text = (
        f"📢 <b>Продвижение канала/бота</b>\n\n"
        f"✈️ Наш бот предлагает Вам возможность создать задание на подписку Вашего телеграмм Канала/бота реальными людьми.\n\n"
        f"👤 1 задание — <b>{promo_price:.3f} $</b>\n"
        f"💳 Рекламный баланс — <b>{ad_balance:.3f} $</b>\n"
        f"📊 Его хватит на <b>{possible}</b> выполнений\n\n"
        f"⏱ Активных заказов: <b>{active_count}</b>\n"
        f"✅ Завершённых заказов: <b>{done_count}</b>\n\n"
        f"❗️ Наш бот @{bot_username} должен быть администратором продвигаемого объекта!"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать задание", callback_data="promo_create")],
        [InlineKeyboardButton(text="📈 Активные", callback_data="promo_active_page_1"),
         InlineKeyboardButton(text="✅ Завершённые", callback_data="promo_done_page_1")]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


def promo_pagination_keyboard(tasks, page, total_pages, mode):
    """Создаёт клавиатуру для страниц"""
    kb = InlineKeyboardBuilder()
    for task in tasks:
        kb.button(
            text=f"📢 {task['channel_username']} ({task['current_completions']}/{task['max_completions']})",
            callback_data=f"promo_info_{task['id']}"
        )
    kb.adjust(1)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"promo_{mode}_page_{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"promo_{mode}_page_{page + 1}"))
    if nav:
        kb.row(*nav)
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="promo_back_menu"))
    return kb.as_markup()


@dp.callback_query(F.data == "promo_back_menu")
async def promo_back_menu(call: types.CallbackQuery):
    """Возврат в главное меню продвижения"""
    await call.message.delete()
    await promotion_menu(call.message)


@dp.callback_query(F.data.regexp(r"promo_info_\d+"))
async def show_promo_info(call: types.CallbackQuery):
    task_id = int(call.data.split("_")[-1])
    async with aiosqlite.connect("bot_database.db") as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_tasks WHERE id=?", (task_id,)) as cursor:
            task = await cursor.fetchone()

    if not task:
        await call.answer("❌ Заказ не найден.", show_alert=True)
        return

    # Определяем тип задания - використовуємо перевірку через keys()
    task_type = task["task_type"] if "task_type" in task.keys() else "channel"
    type_text = "Канал" if task_type == "channel" else "Бот"
    type_emoji = "📢" if task_type == "channel" else "🤖"

    # Конвертация времени в МСК
    created_at = datetime.fromisoformat(task['created_at'])
    msk_time = created_at.astimezone(MSK).strftime("%d.%m.%Y %H:%M:%S")

    text = (
        f"{type_emoji} <b>Информация о заказе #{task['id']}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📂 Тип: <b>{type_text}</b>\n"
        f"📎 Ссылка: {task['channel_link']}\n"
        f"👤 Username: @{task['channel_username']}\n"
        f"💰 Цена за выполнение: <b>{task['price']:.3f}$</b>\n"
        f"📊 Выполнено: <b>{task['current_completions']}/{task['max_completions']}</b>\n"
        f"📅 Создано: {msk_time} (МСК)\n"
        f"🟢 Статус: {'Активный' if task['is_active'] else 'Завершённый'}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"promo_{'active' if task['is_active'] else 'done'}_page_1"
        )]
    ])

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


async def is_valid_bot_link(link: str) -> bool:
    """Просто проверяет, является ли текст ссылкой"""
    return link.startswith("https://t.me/") or link.startswith("@")


# === Создание задания ===
@dp.callback_query(F.data == "promo_create")
async def promo_create_start(call: types.CallbackQuery, state: FSMContext):
    """Начало создания задания - выбор типа"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал", callback_data="promo_type_channel")],
        [InlineKeyboardButton(text="🤖 Бот", callback_data="promo_type_bot")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="promo_back_menu")]
    ])

    await call.message.answer(
        "📝 <b>Выберите тип задания:</b>\n\n"
        "• <b>Канал</b> - пользователи должны подписаться на канал (проверяется автоматически)\n"
        "• <b>Бот</b> - пользователи должны запустить бота (засчитывается сразу)",
        parse_mode="HTML",
        reply_markup=kb
    )
    await call.answer()


@dp.callback_query(F.data == "promo_type_channel")
async def promo_type_channel(call: types.CallbackQuery, state: FSMContext):
    """Выбран тип "Канал"""
    await state.update_data(task_type="channel")
    await call.message.edit_text("📎 Отправьте ссылку на Ваш канал (пример: https://t.me/example):")
    await state.set_state(PromotionStates.waiting_channel_link)
    await call.answer()


@dp.callback_query(F.data == "promo_type_bot")
async def promo_type_bot(call: types.CallbackQuery, state: FSMContext):
    """Выбран тип "Бот"""
    await state.update_data(task_type="bot")
    await call.message.edit_text("🤖 Отправьте ссылку на Вашего бота (пример: https://t.me/example_bot):")
    await state.set_state(PromotionStates.waiting_bot_link)
    await call.answer()


@dp.message(PromotionStates.waiting_channel_link)
async def promo_receive_channel_link(message: types.Message, state: FSMContext):
    link = message.text.strip()

    if not link.startswith("https://t.me/"):
        await message.answer(
            "❌ Неверная ссылка. Больше не нужно вводить ссылку."
        )
        await state.clear()  # знімаємо стан, FSM більше не чекає
        return

    try:
        username = link.split("t.me/")[1].replace("/", "")
        if not username.startswith("@"):
            username = f"@{username}"

        # Получаем чат
        chat = await bot.get_chat(username)
        me = await bot.get_me()

        # Проверяем, что бот админ
        admins = await bot.get_chat_administrators(chat.id)
        if not any(admin.user.id == me.id for admin in admins):
            await message.answer(
                f"❌ Бот @{me.username} не является администратором этого канала."
            )
            await state.clear()
            return

    except Exception as e:
        await message.answer(
            f"❌ Ошибка проверки канала: {e}."
        )
        await state.clear()
        return

    # Всё ок, продолжаем
    await state.update_data(link=link, username=username.replace("@", ""))
    await message.answer("✏️ Введите количество подписок (минимум 10):")
    await state.set_state(PromotionStates.waiting_count)


@dp.message(PromotionStates.waiting_bot_link)
async def promo_receive_bot_link(message: types.Message, state: FSMContext):
    """Получение ссылки на бота - просто проверяем что это ссылка"""
    link = message.text.strip()

    # Просто проверяем что это похоже на ссылку
    if not (link.startswith("https://t.me/")):
        await message.answer(
            "❌ Это не ссылка!\n"
            "Ссылка должна начинаться с https://t.me/\n"
            "Начните заново через меню Продвижения."
        )
        await state.clear()
        return

    # Сохраняем ОРИГИНАЛЬНУЮ ссылку без изменений
    await state.update_data(
        link=link,  # Оригинальная ссылка как есть
        username=link.split("t.me/")[-1].replace("@", "").split("?")[0] if "t.me/" in link else link.replace("@", ""),
        task_type="bot"
    )

    await message.answer("✏️ Введите количество запусков бота (минимум 10):")
    await state.set_state(PromotionStates.waiting_count)


@dp.message(PromotionStates.waiting_count)
async def promo_count(message: types.Message, state: FSMContext):
    try:
        count = int(message.text.strip())
        if count < 10:
            await message.answer("❌ Минимум 10 выполнений.")
            return

        data = await state.get_data()
        link = data["link"]
        username = data["username"]
        task_type = data.get("task_type", "channel")  # Получаем тип задания

        promo_price = float(await get_setting("promotion_price") or 0.015)
        total = count * promo_price
        user = await get_user(message.from_user.id)

        if user["ad_balance"] < total:
            await message.answer("❌ Недостаточно средств на рекламном балансе.")
            await state.clear()
            return

        # Определяем текст в зависимости от типа
        if task_type == "channel":
            task_info = f"📢 <b>Канал:</b> {link}\n"
        else:
            task_info = f"🤖 <b>Бот:</b> {link}\n"

        task_info += f"👥 <b>Количество:</b> {count}\n"

        # Для канала добавляем проверку админства
        if task_type == "channel":
            me = await bot.get_me()
            task_info += f"👨‍💼 <b>Админ:</b> @{me.username} должен быть администратором\n"

        preview = (
            f"📋 <b>Подтверждение задания</b>\n\n"
            f"{task_info}"
            f"💵 <b>Стоимость:</b> {total:.3f} $\n\n"
            f"<i>Средства будут списаны с рекламного баланса</i>"
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="promo_confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="promo_cancel")]
        ])
        await state.update_data(count=count, total=total)
        await message.answer(preview, parse_mode="HTML", reply_markup=kb)
        await state.set_state(PromotionStates.waiting_confirm)
    except:
        await message.answer("❌ Введите корректное число.")


@dp.callback_query(F.data == "promo_confirm")
async def promo_confirm(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = call.from_user.id
    link = data["link"]
    username = data["username"]
    count = data["count"]
    total = data["total"]
    task_type = data.get("task_type", "channel")  # Получаем тип задания

    try:
        async with aiosqlite.connect("bot_database.db") as db:
            # Списываем баланс
            await db.execute(
                "UPDATE users SET ad_balance = ad_balance - ? WHERE user_id = ?",
                (total, user_id)
            )

            # Создаем задание с указанием типа
            await db.execute('''
                INSERT INTO user_tasks (channel_link, channel_username, price, max_completions, created_by, task_type)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (link, username, 0.015, count, user_id, task_type))
            await db.commit()

        # Текст подтверждения в зависимости от типа
        if task_type == "channel":
            success_text = "✅ Задание на подписку на канал успешно создано!"
        else:
            success_text = "✅ Задание на запуск бота успешно создано!"

        await call.message.edit_text(
            f"{success_text}\n\nОно появится в разделе «📝 Задания».",
            parse_mode="HTML"
        )
        await state.clear()

        # Рассылка всем пользователям про новое задание
        await notify_all_users_about_task()

    except Exception as e:
        print(f"❌ Ошибка при создании задания: {e}")
        await call.message.answer(f"⚠️ Ошибка при создании задания: {e}", parse_mode='HTML')


# Функція розсилки
async def notify_all_users_about_task():
    try:
        users = await get_all_users()
        notification_text = (
            f"🎉 <b>Появилось новое задание!</b>\n\n"
            f"➡️ Перейдите в раздел <b>\"📝 Задания\"</b> чтобы выполнить его!"
        )

        async def send_notification(user_id: int, delay: int):
            try:
                await asyncio.sleep(delay)
                await bot.send_message(user_id, notification_text, parse_mode='HTML')
                await update_user_notification_time(user_id)
            except Exception as e:
                print(f"❌ Ошибка уведомления пользователя {user_id}: {e}")

        tasks = []
        for user in users:
            uid = user[0]
            tasks.append(asyncio.create_task(send_notification(uid, 0)))

        # Запускаємо без блокування
        asyncio.create_task(asyncio.gather(*tasks))

    except Exception as e:
        print(f"❌ Ошибка при рассылке уведомлений: {e}")


@dp.callback_query(F.data == "promo_cancel")
async def promo_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Создание задания отменено.")


async def is_user_subscribed(bot, user_id: int, channel_username: str) -> bool:
    """
    Перевіряє, чи користувач підписаний на канал.
    Повертає True, якщо підписаний, інакше False.
    """
    try:
        if not channel_username.startswith("@"):
            channel_username = f"@{channel_username}"

        chat = await bot.get_chat(channel_username)
        member = await bot.get_chat_member(chat.id, user_id)
        return member.status in ("member", "administrator", "creator")

    except Exception:
        # Якщо бот не має доступу до каналу або помилка — вважаємо, що не підписаний
        return False


def normalize_tg_link(value: str) -> str:
    if not value:
        return ""
    value = value.strip()
    if value.startswith("@"):
        return f"https://t.me/{value[1:]}"
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://t.me/{value}"


async def show_user_tasks(message: types.Message):
    user_id = message.from_user.id

    async with aiosqlite.connect("bot_database.db") as db:
        db.row_factory = aiosqlite.Row
        # беремо всі активні завдання, які користувач ще не виконував
        all_tasks = await db.execute_fetchall('''
            SELECT * FROM user_tasks
            WHERE is_active = TRUE
              AND current_completions < max_completions
              AND id NOT IN (
                  SELECT task_id FROM user_task_completions WHERE user_id = ?
              )
        ''', (user_id,))

    # 🔹 Виплата за одне завдання
    reward = float(await get_setting("user_task_reward") or 0.015)

    # 🔹 Фільтруємо завдання
    channel_tasks = []
    bot_tasks = []

    for task in all_tasks:
        # Отримуємо task_type без .get() - використовуємо індекс
        task_type = task["task_type"] if "task_type" in task.keys() else "channel"

        # Проверяем выполнил ли уже пользователь
        if task_type == "channel":
            # Для каналов проверяем подписку
            username = task["channel_username"]
            subscribed = await is_user_subscribed(bot, user_id, username)
            if not subscribed:
                channel_tasks.append(task)
        else:
            # Для ботов - всегда добавляем (проверки нет)
            bot_tasks.append(task)

    if not channel_tasks and not bot_tasks:
        await message.answer("🤷🏻‍♂️ Нет доступных заданий — вы уже выполнили все доступные задания.")
        return

    total_reward = (len(channel_tasks) + len(bot_tasks)) * reward

    main_keyboard = InlineKeyboardBuilder()

    # Кнопки для каналов
    for task in channel_tasks:
        link = normalize_tg_link(task["channel_link"])
        main_keyboard.button(
            text="Подписаться",
            icon_custom_emoji_id='5424818078833715060',
            url=link
        )

    # Кнопки для ботов
    for task in bot_tasks:
        link = normalize_tg_link(task["channel_link"])
        main_keyboard.button(
            text="Запустить бота",
            icon_custom_emoji_id='5287684458881756303',
            url=link
        )

    main_keyboard.adjust(2)
    main_keyboard.row(
        InlineKeyboardButton(
            text="Проверить все задания",
            callback_data="check_user_tasks",
            style='success',
            icon_custom_emoji_id='5206607081334906820'
        )
    )

    text = (
        f"📝 <b>Доступных заданий: {len(channel_tasks) + len(bot_tasks)}</b>\n"
        f"───────────────\n"
    )

    text += f"<tg-emoji emoji-id='5224257782013769471'>💫</tg-emoji> <b>Можно заработать: {total_reward:.3f}$</b>\n"

    await message.answer(text, reply_markup=main_keyboard.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "check_user_tasks")
async def check_user_tasks(call: types.CallbackQuery):
    user_id = call.from_user.id
    completed = 0
    total_reward = 0.0

    # ⬇️ Беремо виплату з БД
    reward = float(await get_setting("user_task_reward") or 0.015)

    async with aiosqlite.connect("bot_database.db") as db:
        db.row_factory = aiosqlite.Row
        tasks = await db.execute_fetchall('''
            SELECT * FROM user_tasks
            WHERE is_active = TRUE
              AND current_completions < max_completions
              AND id NOT IN (
                  SELECT task_id FROM user_task_completions WHERE user_id = ?
              )
        ''', (user_id,))

    for task in tasks:
        try:
            # Замінюємо .get() на перевірку через ключі
            task_type = task["task_type"] if "task_type" in task.keys() else "channel"

            if task_type == "channel":
                # Проверяем подписку на канал
                username = task["channel_username"]
                if not username.startswith("@"):
                    username = f"@{username}"

                chat = await bot.get_chat(username)
                member = await bot.get_chat_member(chat.id, user_id)

                if member.status in ("member", "administrator", "creator"):
                    should_reward = True
                else:
                    should_reward = False
            else:
                # Для бота - всегда засчитываем (проверки нет)
                should_reward = True

            if should_reward:
                async with aiosqlite.connect("bot_database.db") as db:
                    await db.execute('''
                        INSERT OR IGNORE INTO user_task_completions (task_id, user_id)
                        VALUES (?, ?)
                    ''', (task["id"], user_id))
                    await db.execute('''
                        UPDATE user_tasks
                        SET current_completions = current_completions + 1
                        WHERE id = ?
                    ''', (task["id"],))
                    await db.execute('''
                        UPDATE user_tasks
                        SET is_active = FALSE
                        WHERE id = ? AND current_completions >= max_completions
                    ''', (task["id"],))
                    await db.commit()

                # ⬇️ Нарахування суми з БД
                await update_user_balance(user_id, frozen_amount=reward, completed_tasks=1)
                await add_frozen_transaction(user_id, reward, 'user_task', task["id"])
                completed += 1
                total_reward += reward

        except Exception as e:
            print(f"⚠️ Ошибка при проверке задания: {e}")
            continue

    if completed > 0:
        asyncio.create_task(show_ad_at_opportunity(user_id, "after_task"))
        result_text = (
            f"✅ <b>Проверка завершена!</b>\n\n"
            f"📊 Выполнено заданий: <b>{completed}</b>\n"
            f"💰 Начислено: <b>{total_reward:.3f}$</b>\n\n"
            f"💸 Средства заморожены на 24 часа"
        )
        await call.message.edit_text(result_text, parse_mode='HTML')
    else:
        await call.answer("❌ Вы ещё не выполнили ни одного задания.", show_alert=True)


# Админ клавиатура
def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Баланс резерва")],
            [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="🧹 Проверка неактивных")],  # ← НОВАЯ КНОПКА
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="📢 Рассылка")],
            [KeyboardButton(text="🧾 Заявки на вывод")],
            [KeyboardButton(text="🔙 Главное меню")]
        ],
        resize_keyboard=True
    )
    return keyboard


@dp.message(F.text == "🧾 Заявки на вывод")
async def show_withdrawal_menu(message: types.Message):
    pending = await count_withdrawals_by_status("pending")
    approved = await count_withdrawals_by_status("approved")
    refunded = await count_withdrawals_by_status("refunded")
    declined = await count_withdrawals_by_status("declined")

    kb = InlineKeyboardBuilder()
    kb.button(text=f"🕓 Ожидающие [{pending}]", callback_data="wd_list_pending")
    kb.button(text=f"✅ Подтвержд. [{approved}]", callback_data="wd_list_approved")
    kb.button(text=f"↩️ Отклонённые [{refunded}]", callback_data="wd_list_refunded")
    kb.button(text=f"❌ Без возврата [{declined}]", callback_data="wd_list_declined")
    kb.adjust(2, 2)

    await message.answer(
        "<b>Выберите категорию заявок:</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


def paginate_list(items, page: int, page_size: int = 12):
    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": items[start:end],
        "page": page,
        "total_pages": total_pages
    }


@dp.callback_query(F.data == "noop")
async def noop_handler(call: CallbackQuery):
    await call.answer()


@dp.callback_query(F.data.startswith("wd_list_"))
async def show_withdrawal_list(call: CallbackQuery):
    parts = call.data.split("_")

    # wd_list_pending_1
    status = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 1

    async with aiosqlite.connect("bot_database.db") as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT w.*, u.username
            FROM withdrawals w
            LEFT JOIN users u ON w.user_id = u.user_id
            WHERE w.status = ?
            ORDER BY w.created_at DESC
        """, (status,)) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await call.answer("Пусто.", show_alert=True)
        return

    # --- ПАГІНАЦІЯ ---
    pagination = paginate_list(rows, page)
    chunk = pagination["items"]

    kb = InlineKeyboardBuilder()

    for row in chunk:
        wid = row["id"]
        amount = row["amount"]
        username = row["username"] or "Без имени"
        kb.button(text=f"{username} [{amount}$]", callback_data=f"withdraw_view_{wid}")

    kb.adjust(2)

    # Навігація сторінок
    nav = InlineKeyboardBuilder()

    if pagination["page"] > 1:
        nav.button(
            text="◀️",
            callback_data=f"wd_list_{status}_{pagination['page'] - 1}"
        )

    nav.button(
        text=f"📄 {pagination['page']}/{pagination['total_pages']}",
        callback_data="noop"
    )

    if pagination["page"] < pagination["total_pages"]:
        nav.button(
            text="▶️",
            callback_data=f"wd_list_{status}_{pagination['page'] + 1}"
        )

    nav.adjust(3)

    # Кнопка назад
    back_kb = InlineKeyboardBuilder()
    back_kb.button(text="🔙 Назад", callback_data="wd_back_menu")
    back_kb.adjust(1)

    await call.message.edit_text(
        f"<b>Заявки ({status}) — страница {pagination['page']}/{pagination['total_pages']}:</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=kb.export() + nav.export() + back_kb.export()
        ),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "wd_back_menu")
async def wd_back_menu(call: CallbackQuery):
    pending = await count_withdrawals_by_status("pending")
    approved = await count_withdrawals_by_status("approved")
    refunded = await count_withdrawals_by_status("refunded")
    declined = await count_withdrawals_by_status("declined")

    kb = InlineKeyboardBuilder()
    kb.button(text=f"🕓 Ожидающие [{pending}]", callback_data="wd_list_pending")
    kb.button(text=f"✅ Подтвержд. [{approved}]", callback_data="wd_list_approved")
    kb.button(text=f"↩️ Отклонённые [{refunded}]", callback_data="wd_list_refunded")
    kb.button(text=f"❌ Без возврата [{declined}]", callback_data="wd_list_declined")
    kb.adjust(2, 2)

    await call.message.edit_text(
        "<b>Выберите категорию заявок:</b>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()


from datetime import datetime, timedelta


@dp.callback_query(F.data.startswith("withdraw_view_"))
async def view_withdraw_request(call: CallbackQuery):
    wid = int(call.data.split("_")[-1])
    wd = await get_withdrawal(wid)

    if not wd:
        await call.answer("❌ Заявка не найдена.", show_alert=True)
        return

    # Если pending — переиспользуем существующий обработчик
    if wd["status"] == "pending":
        await open_withdraw_request(call)
        return

    user = await get_user(wd["user_id"])

    # 🔥 Конвертация даты в МСК
    created_at = datetime.fromisoformat(wd["created_at"]) + timedelta(hours=3)
    created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")

    text = f"""
📄 <b>Заявка #{wid}</b>

🆔 User ID: <code>{user['user_id']}</code>
👤 Username: @{user['username'] or 'нет'}

💵 Сумма: <b>{wd['amount']}$</b>
📅 Создано: <i>{created_at}</i>
⏳ Статус: <b>{wd['status']}</b>
"""

    # 🔥 Тут потрібно створити клавіатуру ДО додавання кнопок
    kb = InlineKeyboardBuilder()

    # Кнопка чека (якщо є)
    if wd["admin_receipt_url"]:
        kb.button(text="📎 Чек", url=wd["admin_receipt_url"])
    else:
        kb.button(text="❌ НЕ СОЗДАН", callback_data="noop")

    # Кнопка "О пользователе"
    kb.button(text="👤 О пользователе", callback_data=f"wd_userinfo:{wd['user_id']}")

    kb.adjust(1)

    await call.message.edit_text(
        text,
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("withdraw_open_"))
async def open_withdraw_request(call: types.CallbackQuery):
    wid = int(call.data.split("_")[-1])
    wd = await get_withdrawal(wid)

    if not wd:
        await call.answer("❌ Заявка не найдена.", show_alert=True)
        return

    user = await get_user(wd["user_id"])

    # Получаем резерв
    total_balance = await get_crypto_bot_balance()
    reserve_status, reserve_emoji, rec = await get_reserve_status(total_balance)

    # === КНОПКИ ТОЧНО КАК В send_withdraw_request_to_admins ===
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=f"wd_confirm:{wid}")
    kb.button(text="❌ Отклонить (без возврата)", callback_data=f"wd_norefund:{wid}")
    kb.button(text="↩️ Отклонить (с возвратом)", callback_data=f"wd_refund:{wid}")
    kb.button(text="👤 О пользователе", callback_data=f"wd_userinfo:{wd['user_id']}")
    kb.adjust(1, 2, 1)

    # === СООБЩЕНИЕ — ТОЧНО КАК ПРИ УВЕДОМЛЕНИИ АДМИНОВ ===
    text = f"""
📨 <b>ЗАЯВКА НА ВЫВОД</b>

🆔 User ID: <code>{user['user_id']}</code>
👤 Username: @{user['username'] or 'нет'}

💵 Сумма вывода: <b>{wd['amount']}$</b>
🔖 ID заявки: <code>{wid}</code>
⏳ Статус: <b>{wd['status']}</b>
━━━━━━━━━━━━━━━━━━
💰 <b>Резерв Системы</b>

🔢 Баланс: <b>{total_balance:.2f} USDT</b>

<i>{rec}</i>
"""

    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await call.answer()


# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject = None):
    user_id = message.from_user.id

    # Реферальная система
    if command and command.args:
        try:
            # Поддерживаем payload вида "123", "ref123", "ref_123"
            raw_args = (command.args or "").strip()
            digits = "".join(ch for ch in raw_args if ch.isdigit())
            referrer_id = int(digits) if digits else None
            if not referrer_id:
                raise ValueError("no referrer id in payload")
            if referrer_id != user_id:
                user = await get_user(user_id)
                if not user['referrer_id']:
                    # Защита от мусорных/левый referrer_id:
                    # ставим реферера только если он уже есть в базе (то есть реально пользователь бота).
                    async with aiosqlite.connect('bot_database.db') as db:
                        async with db.execute(
                            "SELECT 1 FROM users WHERE user_id = ?",
                            (referrer_id,)
                        ) as cur:
                            exists = await cur.fetchone()
                        if exists:
                            await db.execute(
                                'UPDATE users SET referrer_id = ? WHERE user_id = ?',
                                (referrer_id, user_id)
                            )
                            await db.commit()
        except ValueError:
            pass

    # Проверка блокировки
    if await check_user_blocked(user_id):
        await message.answer("❌ Ваш аккаунт заблокирован. Обратитесь к администратору.")
        return

    await message.answer(
        "👋 Добро пожаловать в бот для заработка!\n\n"
        "Выполняйте задания, приглашайте друзей и зарабатывайте деньги!",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


# Задания - используем flyer_get_tasks
@dp.message(F.text.lower() == "задания")
async def show_tasks(message: types.Message):
    user_id = message.from_user.id

    if await check_user_blocked(user_id):
        await message.answer("❌ Ваш аккаунт заблокирован. Обратитесь к администратору.")
        return

    flyer_tasks = await flyer_get_tasks(user_id, message.from_user.language_code or 'ru', limit=10)

    custom_tasks = await get_active_custom_tasks()

    all_tasks = []
    completed_count = 0

    for task in custom_tasks:
        try:
            async with aiosqlite.connect('bot_database.db') as db:
                async with db.execute('SELECT 1 FROM custom_task_completions WHERE task_id = ? AND user_id = ?',
                                      (task['id'], user_id)) as cursor:
                    has_completed = await cursor.fetchone()

                    if not has_completed:
                        all_tasks.append({
                            'type': 'custom',
                            'id': task['id'],
                            'name': task['name'],
                            'description': task.get('description', ''),
                            'url': task['url'],
                            'button_text': task.get('button_text', '💫 Выполнить'),
                            'price': task['price'],
                            'signature': f"custom_{task['id']}"
                        })
                    else:
                        completed_count += 1
        except Exception as e:
            print(f"❌ Ошибка при проверке кастомного задания: {e}")

    if flyer_tasks:
        for task in flyer_tasks:
            signature = task.get('signature', '')
            if signature:
                saved_status = await get_task_status(user_id, signature)
                if not saved_status:
                    current_status = await flyer_check_task(signature, user_id)
                    await set_task_status(user_id, signature, current_status)
                    saved_status = current_status

                if saved_status in ['completed', 'done', 'complete', True, 'waiting']:
                    completed_count += 1
                    continue
                else:
                    task['type'] = 'flyer'
                    all_tasks.append(task)
            else:
                task['type'] = 'flyer'
                all_tasks.append(task)

    print(f"🔍 Для пользователя {user_id}: {len(all_tasks)} активных, {completed_count} выполненных заданий")

    if not all_tasks:
        await message.answer(
            "🤷🏻‍♂️ Вы выполнили все доступные задания!\n\nПока нет новых, но они обязательно появятся. Заходите позже!")
        return

    main_keyboard = InlineKeyboardBuilder()

    for task in all_tasks:
        if task['type'] == 'custom':
            main_keyboard.button(text=task['button_text'], url=task['url'])
        else:
            task_type = task.get('task', '')
            task_link = task.get('link', '')
            resource_id = task.get('resource_id', '')
            username = task.get('username')
            links_list = task.get('links')  # 👈 нове поле від Flyer

            url = None

            # 1️⃣ Якщо Flyer повернув поле "links" (масив) — беремо перший елемент
            if links_list and isinstance(links_list, list) and len(links_list) > 0:
                url = links_list[0]

            # 2️⃣ Інакше використовуємо link або username
            elif task_link and task_link.startswith("https://t.me/"):
                url = task_link
            elif username:
                username = username.replace("@", "")
                url = f"https://t.me/{username}"

            # 3️⃣ Якщо все одно нічого — fallback
            elif resource_id:
                resource_str = str(resource_id)
                if resource_str.startswith("-100"):
                    channel_id = resource_str.replace("-100", "")
                    url = f"https://t.me/c/{channel_id}"
                else:
                    clean_resource = resource_str.replace("@", "")
                    url = f"https://t.me/{clean_resource}"

            # 4️⃣ Формуємо кнопки
            if url:
                if task_type == "subscribe channel":
                    main_keyboard.button(text="Подписаться", url=url)
                elif task_type == "start bot":
                    main_keyboard.button(text="Запустить", url=url)
                elif task_type == "visit website":
                    main_keyboard.button(text="Перейти", url=url)
                elif task_type == "boost channel":
                    main_keyboard.button(text="Голосовать", url=url)
                else:
                    main_keyboard.button(text="Выполнить", url=url)
            else:
                main_keyboard.button(text="Выполнить", url="#")

    # Располагаем кнопки выполнения по 3 в ряд
    main_keyboard.adjust(2)

    main_keyboard.row(InlineKeyboardButton(text="Проверить все задания", callback_data="check_all_tasks", style='success', icon_custom_emoji_id='5206607081334906820'))
    DEFAULT_FLYER_REWARD = FLZAD
    potential_earnings = 0.0
    actual_task_count = 0

    debug_lines = []

    for task in all_tasks:
        try:
            task_type = task.get('type', 'flyer')  # очікуємо 'custom' або 'flyer'
            # Якщо це кастомне завдання — намагаємось взяти його реальну ціну
            if task_type == 'custom':
                raw = task.get('price', 0)
                reward = float(raw or 0)
                # Рахуємо тільки позитивні винагороди
                if reward > 0:
                    potential_earnings += reward
                    actual_task_count += 1
                    debug_lines.append(f"custom: {reward}")
            else:
                reward = DEFAULT_FLYER_REWARD
                if reward > 0:
                    potential_earnings += reward
                    actual_task_count += 1
                    debug_lines.append(f"flyer: {reward}")

        except Exception as e:
            print(f"⚠️ Ошибка при подсчете награды: {e}")

    # Лог для діагностики — можна закоментувати, якщо все працює
    if debug_lines:
        print("🔍 POTENTIAL EARNINGS DEBUG:", ", ".join(debug_lines))

    # Формуємо заголовок
    text = (
        f"📝 <b>Доступных заданий: {actual_task_count}</b>\n"
        f"───────────────\n"
        f"💫 <b>Можно заработать: {potential_earnings:.3f}$</b>\n"
    )

    for i, task in enumerate(all_tasks, 1):
        task_name = task.get('name', 'Задание')

        if isinstance(task_name, str) and ' - ' in task_name:
            task_name = task_name.split(' - ')[0].strip()

        if len(task_name) > 25:
            display_name = task_name[:25] + '...'
        else:
            display_name = task_name

    await message.answer(text, reply_markup=main_keyboard.as_markup(), parse_mode='HTML')


# Обработчик проверки нескольких заданий
@dp.callback_query(F.data.startswith("check_tasks_"))
async def check_multiple_tasks(call: types.CallbackQuery):
    signatures = call.data.replace("check_tasks_", "").split('_')
    user_id = call.from_user.id

    if not flyer_enabled or not flyer:
        await call.answer("❌ Система проверки временно недоступна", show_alert=True)
        return

    try:
        completed_tasks = 0
        total_reward = 0

        for signature in signatures:
            status = await flyer_check_task(signature, user_id)

            if status is True or status == "completed":
                completed_tasks += 1
                tasks = await flyer_get_tasks(user_id, 'ru', limit=10)
                for task in tasks:
                    if task.get('signature') == signature:
                        reward = float(task.get('price', 0))
                        if reward > 0:
                            total_reward += reward
                            await update_user_balance(user_id, frozen_amount=reward)
                            await update_user_balance(user_id, completed_tasks=1)
                        break

        if completed_tasks > 0:
            if total_reward > 0:
                await call.answer(
                    f"✅ Проверка завершена!\n"
                    f"Выполнено заданий: {completed_tasks}\n"
                    f"Начислено: {total_reward:.4f}$",
                    show_alert=True
                )
            else:
                await call.answer(
                    f"✅ Проверка завершена!\n"
                    f"Выполнено заданий: {completed_tasks}",
                    show_alert=True
                )

            try:
                new_text = call.message.text + f"\n\n✅ <b>Проверено! Выполнено: {completed_tasks}</b>"
                await call.message.edit_text(new_text, parse_mode='HTML')
            except:
                pass
        else:
            await call.answer("❌ Ни одно задание еще не выполнено", show_alert=True)

    except Exception as e:
        print(f"Ошибка проверки заданий: {e}")
        await call.answer("❌ Ошибка при проверке заданий", show_alert=True)

    await call.answer()


# Обработчик проверки одного задания (оставляем для не-канальных заданий)
@dp.callback_query(F.data.startswith("check_task_"))
async def check_task_completion(call: types.CallbackQuery):
    signature = call.data.replace("check_task_", "")
    user_id = call.from_user.id

    try:
        if flyer_enabled and flyer:
            status = await flyer_check_task(signature, user_id)
            print(f"🔍 Результат проверки задания {signature}: {status}")

            # Сохраняем статус в базу
            await set_task_status(user_id, signature, status)

            if status in [True, "completed", "done", "complete", "waiting"]:
                reward = FLZAD

                # Проверяем не начисляли ли уже
                saved_status = await get_task_status(user_id, signature)
                if saved_status not in ['completed', 'done', 'complete']:
                    # Замораживаем средства
                    await update_user_balance(user_id, frozen_amount=reward)
                    await update_user_balance(user_id, completed_tasks=1)

                    # Записываем транзакцию для автоматического размороживания
                    await add_frozen_transaction(user_id, reward, 'flyer', signature)

                    if status == "waiting":
                        message_text = f"✅ Задание принято на проверку! Награда {FLZAD}$ заморожена."
                    else:
                        message_text = f"✅ Задание выполнено! Награда {reward}$ заморожена на 24 часов."

                    await call.answer(message_text, show_alert=True)

                    # УДАЛЯЕМ сообщение с заданием
                    try:
                        await call.message.delete()
                    except Exception as e:
                        print(f"Ошибка при удалении сообщения: {e}")
                else:
                    await call.answer("✅ Задание уже проверено!", show_alert=True)
                    try:
                        await call.message.delete()
                    except Exception as e:
                        print(f"Ошибка при удалении сообщения: {e}")

            elif status in [False, "incomplete"]:
                await call.answer("❌ Задание еще не выполнено.", show_alert=True)

            else:
                await call.answer(f"📊 Статус: {status}", show_alert=True)

        else:
            await call.answer("❌ Система проверки недоступна", show_alert=True)

    except Exception as e:
        print(f"❌ Ошибка проверки задания: {e}")
        await call.answer("❌ Ошибка при проверке", show_alert=True)

    await call.answer()


@dp.callback_query(F.data.startswith("check_tasks_"))
async def check_multiple_tasks(call: types.CallbackQuery):
    signatures = call.data.replace("check_tasks_", "").split('_')
    user_id = call.from_user.id

    if not flyer_enabled or not flyer:
        await call.answer("❌ Система проверки временно недоступна", show_alert=True)
        return

    try:
        completed_tasks = 0
        total_reward = 0

        for signature in signatures:
            status = await flyer_check_task(signature, user_id)

            if status is True or status == "completed":
                completed_tasks += 1
                # НАЧИСЛЯЕМ ФИКСИРОВАННУЮ ЦЕ
                reward = FLZAD
                total_reward += reward
                await update_user_balance(user_id, frozen_amount=reward)
                await update_user_balance(user_id, completed_tasks=1)

        if completed_tasks > 0:
            await call.answer(
                f"✅ Проверка завершена!\n"
                f"Выполнено заданий: {completed_tasks}\n"
                f"Начислено: {total_reward:.2f}$",
                show_alert=True
            )

            try:
                new_text = call.message.text + f"\n\n✅ <b>Проверено! Выполнено: {completed_tasks}</b>"
                await call.message.edit_text(new_text, parse_mode='HTML')
            except:
                pass
        else:
            await call.answer("❌ Ни одно задание еще не выполнено", show_alert=True)

    except Exception as e:
        print(f"Ошибка проверки заданий: {e}")
        await call.answer("❌ Ошибка при проверке заданий", show_alert=True)

    await call.answer()


async def flyer_get_tasks(user_id, language_code, limit=15):
    global flyer_enabled

    if not flyer_enabled or not flyer:
        print("❌ Flyer не инициализирован")
        return []

    try:
        tasks = await flyer.get_tasks(
            user_id=user_id,
            language_code=language_code,
            limit=limit
        )

        if tasks:
            print(f"✅ Flyer вернул {len(tasks)} заданий для пользователя {user_id}")

            # 🔍 Додаємо детальне логування для діагностики
            print("📦 FLYER RAW TASKS (DEBUG):")
            import json
            for i, task in enumerate(tasks, 1):
                try:
                    print(f"\n🔸 Task #{i}")
                    print(f"Задание: {task.get('task')}")
                    print(f"Цена: {task.get('price')}")
                    print(f"Ссылкв: {task.get('links')[0] if task.get('links') else '—'}")
                    print(f"Название: {task.get('name')}")
                except Exception as e:
                    print(f"⚠️ Ошибка при выводе задачи #{i}: {e}")

        return tasks or []

    except Exception as e:
        print(f"❌ Flyer get_tasks error: {e}")
        # Якщо проблема з авторизацією — вимикаємо Flyer
        if "auth" in str(e).lower() or "key" in str(e).lower() or "401" in str(e):
            flyer_enabled = False
            print("❌ Flyer отключен из-за ошибки авторизации")
        return []


# Flyer проверка задания
async def flyer_check_task(signature, user_id=None):
    global flyer_enabled

    if not flyer_enabled or not flyer:
        return None

    try:
        # Используем метод check_task из библиотеки
        status = await flyer.check_task(
            user_id=user_id,
            signature=signature
        )

        print(f"🔍 Flyer check_task result: {status}")
        return status

    except Exception as e:
        print(f"❌ Flyer check_task error: {e}")
        return None


async def get_expected_withdrawal(user_id: int) -> float:
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("""
            SELECT SUM(amount)
            FROM withdrawals
            WHERE user_id = ? AND status = 'pending'
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return float(row[0]) if row and row[0] else 0.0


async def get_withdrawn_amount(user_id: int) -> float:
    async with aiosqlite.connect("bot_database.db") as db:
        async with db.execute("""
            SELECT SUM(amount)
            FROM withdrawals
            WHERE user_id = ? AND status = 'approved'
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()
            return float(row[0]) if row and row[0] else 0.0


@dp.message(F.text.lower() == "кабинет")
async def show_cabinet(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    currency = await get_setting('currency') or 'USD'
    expected_withdrawal = await get_expected_withdrawal(user_id)
    withdrawn = await get_withdrawn_amount(user_id)

    text = (
        f"📱 <b>Ваш кабинет:</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📋 Выполнено заданий: <b>{user['completed_tasks']}</b>\n"
        f"────────────────\n"
        f"💳 Баланс для вывода: <b>{user['balance']:.3f} {currency}</b>\n"  # ← .3f вместо .4f
        f"├ 💸 Ожидается к выплате: <b>{expected_withdrawal:.3f} {currency}</b>\n"
        f"╰ 💰 Выведено: <b>{withdrawn:.3f} USD</b>\n"
        f"🧊 Замороженый баланс: <b>{user['frozen_balance']:.3f} {currency}</b>\n"
        f"────────────────"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Пополнить", callback_data="ad_topup", icon_custom_emoji_id='5409048419211682843')
    keyboard.button(text="Вывести", callback_data="withdraw", style='success', icon_custom_emoji_id='5472250091332993630')
    keyboard.adjust(2, 2)

    await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')


class ConvertBalanceStates(StatesGroup):
    waiting_for_amount = State()


async def start_convert_balance(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    user = await get_user(user_id)

    if user['balance'] <= 0:
        await call.answer("❌ У вас нет доступного баланса для конвертации.", show_alert=True)
        return

    await call.message.answer(
        f"♻️ <b>Конвертация баланса</b>\n\n"
        f"💰 Доступно: <b>{user['balance']:.3f} $</b>\n"
        f"Введите сумму, которую хотите перевести в рекламный баланс:",
        parse_mode='HTML'
    )
    await state.set_state(ConvertBalanceStates.waiting_for_amount)
    await call.answer()


@dp.message(ConvertBalanceStates.waiting_for_amount)
async def process_convert_balance(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    user = await get_user(user_id)

    try:
        amount = float(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0.")
            return
        if amount > user['balance']:
            await message.answer("❌ Недостаточно средств на основном балансе.")
            return

        # ✅ Конвертуємо
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute(
                "UPDATE users SET balance = balance - ?, ad_balance = ad_balance + ? WHERE user_id = ?",
                (amount, amount, user_id)
            )
            await db.commit()

        await message.answer(
            f"✅ <b>Конвертация успешно выполнена!</b>\n\n"
            f"💳 {amount:.3f} $ переведено с обычного баланса на рекламный.",
            parse_mode='HTML'
        )
        await state.clear()

    except ValueError:
        await message.answer("❌ Введите корректное число (например: 1.5).")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()


async def ad_topup_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("💵 Введите сумму в $ для пополнения рекламного баланса:")
    await state.set_state(AdTopupStates.waiting_for_amount)


@dp.message(AdTopupStates.waiting_for_amount)
async def ad_topup_process(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        if amount < 0.1:
            await message.answer("❌ Минимальная сумма пополнения — 0.1 $")
            return

        invoice_url = await create_ad_invoice(message.from_user.id, amount)
        if invoice_url:
            await message.answer(
                f"💳 <b>ИНВОЙС ДЛЯ ПОПОЛНЕНИЯ</b>\n\n"
                f"💰 Сумма: <b>{amount:.2f} $</b>\n"
                f"📎 Ссылка для оплаты: {invoice_url}\n\n"
                f"После оплаты нажмите кнопку ниже:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="confirm_ad_payment")]
                ]),
                parse_mode='HTML'
            )
        else:
            await message.answer("❌ Ошибка при создании инвойса. Попробуйте позже.")
    except ValueError:
        await message.answer("❌ Введите корректную сумму.")
    await state.clear()


@dp.callback_query(F.data == "confirm_ad_payment")
async def confirm_ad_payment(call: types.CallbackQuery):
    user_id = call.from_user.id

    # 🔍 Беремо тільки останній НЕоплачений інвойс (pending)
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute("""
            SELECT invoice_id 
            FROM ad_topups 
            WHERE user_id = ? AND status = 'pending'
            ORDER BY id DESC LIMIT 1
        """, (user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            await call.answer("❌ У вас нет активных неоплаченных инвойсов", show_alert=True)
            return

        invoice_id = row[0]

    # 🧾 Перевіряємо оплату через CryptoBot API
    if not invoice_id:
        await call.answer("⚠️ Ошибка: пустой ID платежа", show_alert=True)
        return

    result = await check_ad_invoice(invoice_id)

    # ✅ Результат перевірки
    if result == "already_paid":
        await call.answer("⚠️ Этот платёж уже был зачислен ранее", show_alert=True)
    elif result is True:
        await call.answer("✅ Оплата подтверждена, баланс пополнен!", show_alert=True)
    elif result is False:
        await call.answer("❌ Оплата не найдена, попробуйте позже", show_alert=True)
    else:
        await call.answer(f"⚠️ Неизвестный ответ от системы: {result}", show_alert=True)


@dp.message(F.text.lower() == "рефералы")
async def show_referrals(message: types.Message):
    user_id = message.from_user.id
    ref_data = await get_referral_data(user_id)

    # Отримуємо налаштування для відображення
    bonus_lvl1 = float(await get_setting('ref_bonus_level1') or 0.05)
    bonus_lvl2 = float(await get_setting('ref_bonus_level2') or 0.03)
    tasks_lvl1 = int(await get_setting('ref_tasks_required_level1') or 3)
    tasks_lvl2 = int(await get_setting('ref_tasks_required_level2') or 5)

    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"

    text = (
        "🎯 <b>Реферальная система</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"👥 Ваших рефералов — <b>{ref_data['level1_count']}</b>\n\n"
        f"💰 <b>Бонусы:</b>\n"
        f"• <b>1 ур.</b> — <b>{bonus_lvl1:.2f}$</b> за <b>{tasks_lvl1}</b> заданий реферала\n"
        f"• <b>2 ур.</b> — <b>{bonus_lvl2:.2f}$</b> за <b>{tasks_lvl2}</b> заданий\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Топ рефоводов", callback_data="top_ref_all", icon_custom_emoji_id='5409008750893734809', style='primary')],
        [InlineKeyboardButton(text="За 24 часа", callback_data="top_ref_day", icon_custom_emoji_id='5451646226975955576'), ],
        [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals")]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("top_ref_"))
async def show_top_referrals(call: types.CallbackQuery):
    mode = call.data.split("_")[2]  # all / day
    await call.answer()

    # Мапа emoji для місць
    NUM_EMOJI = {
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
        6: "6️⃣",
        7: "7️⃣",
        8: "8️⃣",
        9: "9️⃣",
        10: "🔟"
    }

    async with aiosqlite.connect("bot_database.db") as db:
        db.row_factory = aiosqlite.Row
        if mode == "day":
            since = datetime.utcnow() - timedelta(days=1)
            query = """
                SELECT referrer_id AS user_id, COUNT(*) AS refs
                FROM users
                WHERE referrer_id IS NOT NULL AND registered_at > ?
                GROUP BY referrer_id
                ORDER BY refs DESC
                LIMIT 10
            """
            params = (since,)
        else:
            query = """
                SELECT referrer_id AS user_id, COUNT(*) AS refs
                FROM users
                WHERE referrer_id IS NOT NULL
                GROUP BY referrer_id
                ORDER BY refs DESC
                LIMIT 10
            """
            params = ()

        rows = await db.execute_fetchall(query, params)

    # Формування тексту
    if not rows:
        text = "😕 Пока нет данных для отображения."
    else:
        lines = [f"🏆 <b>Топ рефоводов {'за 24 часа' if mode == 'day' else '(всего)'}:</b>\n━━━━━━━━━━━━━━━"]

        for i, row in enumerate(rows, start=1):
            try:
                user = await call.bot.get_chat(row["user_id"])
                name = user.first_name or "Пользователь"
                username = (
                    f"@{user.username}"
                    if user.username
                    else f"<a href='tg://user?id={user.id}'>{name}</a>"
                )
            except Exception:
                username = f"<a href='tg://user?id={row['user_id']}'>User</a>"

            place_emoji = NUM_EMOJI.get(i, str(i))
            lines.append(f"{place_emoji} {username}: <b>{row['refs']}</b> реф.")

        text = "\n".join(lines)

    # Кнопки
    buttons = []

    if mode == "all":
        buttons.append([InlineKeyboardButton(text="Топ за 24 часа", callback_data="top_ref_day", icon_custom_emoji_id='5451646226975955576')])
    else:
        buttons.append([InlineKeyboardButton(text="Топ рефоводов", callback_data="top_ref_all", icon_custom_emoji_id='5409008750893734809', style='primary')])

    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_ref_menu")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "back_to_ref_menu")
async def back_to_ref_menu(call: types.CallbackQuery):
    """Повернення назад до меню рефералів"""
    user_id = call.from_user.id
    ref_data = await get_referral_data(user_id)

    # Отримуємо налаштування для відображення
    bonus_lvl1 = float(await get_setting('ref_bonus_level1') or 0.05)
    bonus_lvl2 = float(await get_setting('ref_bonus_level2') or 0.03)
    tasks_lvl1 = int(await get_setting('ref_tasks_required_level1') or 3)
    tasks_lvl2 = int(await get_setting('ref_tasks_required_level2') or 5)

    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"

    text = (
        "🎯 <b>Реферальная система</b>\n"
        "━━━━━━━━━━━━━━━━━\n"
        f"👥 Ваших рефералов — <b>{ref_data['level1_count']}</b>\n\n"
        f"💰 <b>Бонусы:</b>\n"
        f"• <b>1 ур.</b> — <b>{bonus_lvl1:.2f}$</b> за <b>{tasks_lvl1}</b> заданий реферала\n"
        f"• <b>2 ур.</b> — <b>{bonus_lvl2:.2f}$</b> за <b>{tasks_lvl2}</b> заданий\n\n"
        f"🔗 <b>Ваша ссылка:</b>\n<code>{ref_link}</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Топ рефоводов", callback_data="top_ref_all", icon_custom_emoji_id='5409008750893734809', style='primary')],
        [InlineKeyboardButton(text="За 24 часа", callback_data="top_ref_day", icon_custom_emoji_id='5451646226975955576')],
        [InlineKeyboardButton(text="👥 Мои рефералы", callback_data="my_referrals")]
    ])

    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data == "my_referrals")
async def show_my_referrals(call: types.CallbackQuery):
    """Показ списка рефералов пользователя и выполненных ими заданий"""
    await call.answer()
    await _render_my_referrals_page(call, page=1)


@dp.callback_query(F.data.regexp(r"my_referrals_page_\d+"))
async def show_my_referrals_page(call: types.CallbackQuery):
    await call.answer()
    try:
        page = int(call.data.split("_")[-1])
    except Exception:
        page = 1
    await _render_my_referrals_page(call, page=page)


async def _render_my_referrals_page(call: types.CallbackQuery, page: int = 1):
    """
    Быстрый вывод рефералов постранично:
    - не дергаем Telegram API (get_chat) для каждого реферала
    - используем username из БД (users.username)
    - LIMIT/OFFSET чтобы не зависать на больших списках
    """
    user_id = call.from_user.id
    page_size = 20
    page = max(1, page)
    offset = (page - 1) * page_size

    async with aiosqlite.connect('bot_database.db') as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE referrer_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            total_refs = int(row["cnt"] if row and row["cnt"] is not None else 0)

        rows = await db.execute_fetchall(
            """
            SELECT user_id, username, completed_tasks, registered_at
            FROM users
            WHERE referrer_id = ?
            ORDER BY completed_tasks DESC, registered_at DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, page_size, offset)
        )

        async with db.execute(
            "SELECT COALESCE(SUM(completed_tasks), 0) AS s FROM users WHERE referrer_id = ?",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            total_tasks = int(row["s"] if row and row["s"] is not None else 0)

    if total_refs == 0:
        text = "😕 У вас пока нет рефералов."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_ref_menu")]
        ])
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        return

    total_pages = max(1, (total_refs + page_size - 1) // page_size)
    page = min(page, total_pages)

    lines = [
        "👥 <b>Ваши рефералы:</b>",
        "━━━━━━━━━━━━━━━━━",
        f"📄 Страница: <b>{page}/{total_pages}</b>",
        ""
    ]

    if not rows:
        lines.append("На этой странице пусто.")
    else:
        for r in rows:
            rid = r["user_id"]
            uname = (r["username"] or "").strip()
            completed = int(r["completed_tasks"] or 0)

            if uname:
                user_label = f"@{uname.lstrip('@')}"
            else:
                # clickable-ссылка без запроса к Telegram API
                user_label = f"<a href='tg://user?id={rid}'>ID:{rid}</a>"

            lines.append(f"• {user_label} — 📋 <b>{completed}</b>")

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━",
        f"📊 <b>Всего рефералов:</b> {total_refs}",
        f"📊 <b>Всего выполнено заданий:</b> {total_tasks}",
    ]

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"my_referrals_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"my_referrals_page_{page + 1}"))

    kb_rows = []
    if nav_row:
        kb_rows.append(nav_row)
    kb_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_ref_menu")])

    await call.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )


@dp.message(F.text.lower() == "статистика")
async def show_info(message: types.Message):
    async with aiosqlite.connect('bot_database.db') as db:
        # Всего пользователей
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            total_users = (await cursor.fetchone())[0]

        # Пользователей сегодня
        async with db.execute(
                "SELECT COUNT(*) FROM users WHERE DATE(registered_at) = DATE('now', 'localtime')"
        ) as cursor:
            today_users = (await cursor.fetchone())[0]

        # Всего выполнено заданий
        async with db.execute('SELECT SUM(completed_tasks) FROM users') as cursor:
            total_tasks = (await cursor.fetchone())[0] or 0

        # Общая сумма выводов
        async with db.execute(
                "SELECT SUM(amount) FROM withdrawals WHERE status = 'approved'"
        ) as cursor:
            total_withdrawn = (await cursor.fetchone())[0] or 0

        # Сумма выводов сегодня
        async with db.execute(
                "SELECT SUM(amount) FROM withdrawals WHERE status = 'approved' AND DATE(processed_at) = DATE('now', 'localtime')"
        ) as cursor:
            today_withdrawn = (await cursor.fetchone())[0] or 0

        # Общая сумма пополнений рекламного баланса
        async with db.execute(
                "SELECT SUM(amount) FROM ad_topups WHERE status = 'paid'"
        ) as cursor:
            total_ad_topups = (await cursor.fetchone())[0] or 0

    # Формируем красивый текст
    text = (
        "📚 <b>Информация о нашем боте:</b>\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"👥 Пользователей всего: <b>{total_users}</b>\n"
        f"╰• 👥 За сегодня: <b>{today_users}</b>\n"
        f"────────────────\n"
        f"📝 Выполнено заданий: <b>{total_tasks}</b>\n"
        f"────────────────\n"
        f"💸 Выведено всего: <b>{total_withdrawn:.2f}$</b>\n"
        f"╰• 💸 За сегодня: <b>{today_withdrawn:.2f}$</b>\n"
        f"────────────────\n"
        f"📢 Пополнено средств: <b>{total_ad_topups:.2f}$</b>\n"
        f"────────────────\n"
        "📈 <i>Статистика обновляется в реальном времени.</i>"
    )

    payments_channel = await get_setting("payments_channel")
    chat_link = await get_setting("chat_link")
    payments_channell = await get_setting("payments_channell")

    keyboard = InlineKeyboardBuilder()

    # ✅ Callback-кнопки
    keyboard.button(text="Помощь", callback_data="infoquyfa", icon_custom_emoji_id='5436113877181941026')
    keyboard.adjust(1)

    # ✅ URL-кнопки (добавляем только если URL не пустой)
    if payments_channel and str(payments_channel).startswith("http"):
        keyboard.button(text="Канал", url=str(payments_channel), icon_custom_emoji_id='5424818078833715060')

    if chat_link and str(chat_link).startswith("http"):
        keyboard.button(text="Чат", url=str(chat_link), style='primary', icon_custom_emoji_id='5443038326535759644')

    if payments_channell:
        # Если это ID канала или @username, преобразуем в ссылку
        if str(payments_channell).startswith("-100") or str(payments_channell).startswith("@"):
            payments_url = f"https://t.me/{payments_channell.lstrip('@')}"
        elif str(payments_channell).startswith("http"):
            payments_url = str(payments_channell)
        else:
            payments_url = None
        if payments_url:
            keyboard.button(text="✅ Канал выплат", url=payments_url)

    keyboard.adjust(1, 2, 1)

    await message.answer(
        text,
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "infoquyfa")
async def infoquyfa(call: types.CallbackQuery):
    text = (
        f"<b> • Помощь по боту.\n❓ Выбирите раздел:</b>")
    keyboard = InlineKeyboardBuilder()

    keyboard.button(text="❓ Рефералы", callback_data="info_referrals")
    keyboard.button(text="❓ Заработок", callback_data="info_earnings")
    keyboard.adjust(1, 1)
    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


@dp.message(F.text == "👨‍💻 Админка")
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав администратора.")
        return

    await message.answer("👨‍💻 <b>Админ панель</b>", reply_markup=get_admin_keyboard(), parse_mode='HTML')


@dp.message(F.text == "🔙 Главное меню")
async def back_to_main(message: types.Message):
    await message.answer("Возвращаемся в главное меню:", reply_markup=get_main_keyboard(message.from_user.id))


from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

USERS_PER_PAGE = 10  # количество пользователей на одной странице


@dp.message(F.text == "👥 Пользователи")
async def admin_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📋 Все пользователи", callback_data="all_users:0:tasks:desc")
    keyboard.button(text="🔍 Найти пользователя", callback_data="find_user")
    keyboard.button(text="📊 Статистика", callback_data="users_stats")
    keyboard.adjust(1, 2)

    users = await get_all_users()
    total_users = len(users)

    text = f"👥 <b>Всего пользователей: {total_users}</b>\n\n" \
           f"Нажми <b>📋 Все пользователи</b> чтобы открыть список."

    await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data.startswith("all_users"))
async def show_all_users(callback: types.CallbackQuery):
    _, page, sort_field, sort_dir = callback.data.split(":")
    page = int(page)

    # Загружаем пользователей
    users = await get_all_users()  # должен возвращать список (user_id, ...)
    users_data = []

    for user in users:
        data = await get_user(user[0])
        users_data.append({
            "id": user[0],
            "balance": data["balance"],
            "tasks": data["completed_tasks"]
        })

    # Сортировка
    reverse = (sort_dir == "desc")
    users_data.sort(key=lambda x: x[sort_field], reverse=reverse)

    # Пагинация
    start = page * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    page_users = users_data[start:end]
    users = await get_all_users()
    total_users = len(users)
    text = f"📋 <b>Пользователи: <b>{total_users}</b></b>\n"
    text += f"Страница <b>{page + 1}</b>/<b>{(len(users_data) - 1) // USERS_PER_PAGE + 1}</b>\n"
    text += f"Фильтр: <b>{'📝 Задания' if sort_field == 'tasks' else '💰 Баланс'}</b> ({'⇧' if not reverse else '⇩'})\n\n"

    for u in page_users:
        text += (
            f"👤 <code>{u['id']}</code> | 💰 {u['balance']:.2f}$ | 📝 {u['tasks']}\n"
            f"────────────────\n"
        )

    # Кнопки
    keyboard = InlineKeyboardBuilder()

    # ✅ Переключатель фильтра (Задания / Баланс)
    keyboard.button(
        text="📝 Задания" if sort_field != "tasks" else "💰 Баланс",
        callback_data=f"all_users:{page}:{'balance' if sort_field == 'tasks' else 'tasks'}:{sort_dir}"
    )

    # ✅ Переключение направления сортировки
    keyboard.button(
        text="⇳ Сортировка",
        callback_data=f"all_users:{page}:{sort_field}:{'asc' if sort_dir == 'desc' else 'desc'}"
    )

    keyboard.adjust(2)

    # ✅ Пагинация
    if start > 0:
        keyboard.button(
            text="⇦",
            callback_data=f"all_users:{page - 1}:{sort_field}:{sort_dir}"
        )
    if end < len(users_data):
        keyboard.button(
            text="⇨",
            callback_data=f"all_users:{page + 1}:{sort_field}:{sort_dir}"
        )

    keyboard.adjust(2)

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode="HTML")


@dp.callback_query(F.data == "find_user")
async def find_user_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.answer("🔍 Введите ID пользователя для поиска:")
    await state.set_state(AdminStates.waiting_user_id)
    await call.answer()


@dp.message(AdminStates.waiting_user_id)
async def show_user_info(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        user = await get_user(user_id)

        if not user:
            await message.answer("❌ Пользователь не найден")
            await state.clear()
            return

        # Получаем данные о рефералах
        ref_data = await get_referral_data(user_id)

        # Получаем историю выводов
        async with aiosqlite.connect('bot_database.db') as db:
            async with db.execute(
                    'SELECT COUNT(*), SUM(amount) FROM withdrawals WHERE user_id = ? AND status = "approved"',
                    (user_id,)) as cursor:
                result = await cursor.fetchone()
                withdrawals_count = result[0] or 0
                total_withdrawn = result[1] or 0

        referrer_text = "⭕"
        if user.get("referrer_id"):
            ref_user = await get_user(user["referrer_id"])
            if ref_user:
                referrer_text = f"@{ref_user['username']}" if ref_user["username"] else f"{ref_user['user_id']}"

        text = (
            f"👤 <b>Информация о пользователе</b>\n\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📛 Имя: @{user['username']}\n"
            f"👥 Пригласил: <b>{referrer_text}</b>\n"
            f"📅 Зарегистрирован: {user.get('registered_at', 'Неизвестно')}\n\n"
            f"💰 <b>Финансы:</b>\n"
            f"• Баланс: <b>{user['balance']:.3f}$</b>\n"
            f"• Заморожено: <b>{user['frozen_balance']:.3f}$</b>\n"
            f"• Всего выведено: <b>{total_withdrawn:.3f}$</b> ({withdrawals_count} выводов)\n\n"
            f"📊 <b>Активность:</b>\n"
            f"• Выполнено заданий: <b>{user['completed_tasks']}</b>\n"
            f"• Рефералы 1 ур: <b>{ref_data['level1_count']}</b>\n"
            f"• Рефералы 2 ур: <b>{ref_data['level2_count']}</b>\n"
            f"• Статус: {'❌ Заблокирован' if user['is_blocked'] else '✅ Активен'}\n"
        )

        keyboard = InlineKeyboardBuilder()

        # Кнопки управления балансом
        keyboard.button(text="💰 Начислить", callback_data=f"add_balance_{user_id}")
        keyboard.button(text="➖ Снять", callback_data=f"remove_balance_{user_id}")

        # Кнопки блокировки/разблокировки
        if user['is_blocked']:
            keyboard.button(text="🔓 Разблокировать", callback_data=f"unban_{user_id}")
        else:
            keyboard.button(text="🔒 Заблокировать", callback_data=f"ban_{user_id}")

        # Кнопки рефералов
        keyboard.button(text="👥 Рефералы", callback_data=f"show_refs_{user_id}")
        keyboard.button(text="📊 Статистика", callback_data=f"user_stats_{user_id}")
        keyboard.button(text="🗑 Очистить БД", callback_data=f"clean_userdb:{user_id}")

        keyboard.button(text="🔙 Назад", callback_data="users_back")
        keyboard.adjust(2, 2, 1, 1)

        await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
        await state.clear()

    except ValueError:
        await message.answer("❌ Введите корректный ID пользователя (только цифры)")


@dp.callback_query(F.data.startswith("add_balance_"))
async def add_balance_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = int(call.data.split("_")[2])
    await state.update_data(user_id=user_id, action="add")
    await call.message.answer(f"💵 Введите сумму для начисления пользователю {user_id}:")
    await state.set_state(AdminStates.waiting_balance_amount)
    await call.answer()


@dp.callback_query(F.data.startswith("remove_balance_"))
async def remove_balance_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = int(call.data.split("_")[2])
    await state.update_data(user_id=user_id, action="remove")
    await call.message.answer(f"💵 Введите сумму для снятия с пользователя {user_id}:")
    await state.set_state(AdminStates.waiting_balance_amount)
    await call.answer()


@dp.message(AdminStates.waiting_balance_amount)
async def process_balance_change(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']
    action = data['action']

    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            await state.clear()
            return

        user = await get_user(user_id)

        if action == "remove" and amount > user['balance']:
            await message.answer("❌ Недостаточно средств на балансе пользователя")
            await state.clear()
            return

        # Применяем изменение баланса
        change_amount = amount if action == "add" else -amount
        await update_user_balance(user_id, amount=change_amount)

        # Записываем в историю
        async with aiosqlite.connect('bot_database.db') as db:
            await db.execute(
                'INSERT INTO balance_history (user_id, amount, type, admin_id, reason) VALUES (?, ?, ?, ?, ?)',
                (user_id, change_amount, 'admin_adjustment', message.from_user.id,
                 f"{'Начисление' if action == 'add' else 'Списание'} администратором")
            )
            await db.commit()

        action_text = "начислено" if action == "add" else "списано"
        await message.answer(f"✅ Пользователю {user_id} {action_text} {amount:.3f}$")

        # Уведомляем пользователя
        try:
            await bot.send_message(
                user_id,
                f"📢 <b>Изменение баланса</b>\n\n"
                f"💵 Сумма: <b>{amount:.3f}$</b>\n"
                f"📝 Тип: {'Начисление' if action == 'add' else 'Списание'}\n"
                f"💰 Новый баланс: <b>{(user['balance'] + change_amount):.3f}$</b>",
                parse_mode='HTML'
            )
        except:
            pass

        await state.clear()

    except ValueError:
        await message.answer("❌ Введите корректную сумму")


@dp.callback_query(F.data.startswith("ban_"))
async def ban_user(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = int(call.data.split("_")[1])
    await state.update_data(user_id=user_id)
    await call.message.answer(f"📝 Укажите причину блокировки пользователя {user_id}:")
    await state.set_state(AdminStates.waiting_ban_reason)
    await call.answer()


@dp.callback_query(F.data.startswith("unban_"))
async def unban_user(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = int(call.data.split("_")[1])

    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('UPDATE users SET is_blocked = FALSE WHERE user_id = ?', (user_id,))
        await db.commit()

    await call.message.answer(f"✅ Пользователь {user_id} разблокирован")

    # Уведомляем пользователя
    try:
        await bot.send_message(user_id, "✅ Ваш аккаунт разблокирован администратором")
    except:
        pass

    await call.answer()


@dp.message(Command("debug_penalties"))
async def debug_penalties(message: types.Message):
    """Диагностика системы штрафов"""
    if message.from_user.id not in ADMIN_IDS:
        return

    try:
        # Проверяем есть ли пользователи с заморозкой
        async with aiosqlite.connect('bot_database.db') as db:
            async with db.execute('SELECT COUNT(*) FROM users WHERE frozen_balance > 0') as cursor:
                users_with_frozen = (await cursor.fetchone())[0]

            async with db.execute('SELECT COUNT(*) FROM frozen_transactions WHERE is_unfrozen = FALSE') as cursor:
                active_transactions = (await cursor.fetchone())[0]

        text = (
            f"🔍 <b>Диагностика штрафов</b>\n\n"
            f"👥 Пользователей с заморозкой: <b>{users_with_frozen}</b>\n"
            f"💸 Активных транзакций: <b>{active_transactions}</b>\n"
            f"🔧 Flyer статус: <b>{'✅ Включен' if flyer_enabled else '❌ Выключен'}</b>\n"
            f"🔄 Проверка отписок: <b>{'✅ Запущена' if 'check_completed_tasks' in globals() else '❌ Не найдена'}</b>"
        )

        await message.answer(text, parse_mode='HTML')

    except Exception as e:
        await message.answer(f"❌ Ошибка диагностики: {e}")


@dp.message(AdminStates.waiting_ban_reason)
async def process_ban_reason(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data['user_id']
    reason = message.text

    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('UPDATE users SET is_blocked = TRUE WHERE user_id = ?', (user_id,))
        await db.commit()

    await message.answer(f"✅ Пользователь {user_id} заблокирован\nПричина: {reason}")

    # Уведомляем пользователя
    try:
        await bot.send_message(
            user_id,
            f"❌ <b>Ваш аккаунт заблокирован</b>\n\n"
            f"📝 Причина: {reason}\n"
            f"🔄 Для разблокировки обратитесь к администратору",
            parse_mode='HTML'
        )
    except:
        pass

    await state.clear()


@dp.callback_query(F.data.startswith("show_refs_"))
async def show_user_referrals(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = int(call.data.split("_")[2])

    # Получаем рефералов 1 уровня
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT user_id, username, registered_at FROM users WHERE referrer_id = ?',
                              (user_id,)) as cursor:
            level1_refs = await cursor.fetchall()

    text = f"👥 <b>Рефералы пользователя {user_id}</b>\n\n"
    text += f"📊 Рефералы 1 уровня: {len(level1_refs)}\n\n"

    if level1_refs:
        text += "<b>Список рефералов:</b>\n"
        for ref in level1_refs[:20]:  # Ограничиваем показ
            ref_user = await get_user(ref[0])
            text += f"👤 <code>{ref[0]}</code> | @{ref[1]} |📝 {ref_user['completed_tasks']}\n"
    else:
        text += "❌ Рефералов нет"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data=f"back_to_user_{user_id}")

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


# Обработчик кнопки "Назад" в меню пользователей
@dp.callback_query(F.data == "users_back")
async def users_back(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    # Возвращаемся к списку пользователей
    users = await get_all_users()
    total_users = len(users)

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔍 Найти пользователя", callback_data="find_user")
    keyboard.button(text="📊 Статистика", callback_data="users_stats")
    keyboard.adjust(1)

    text = f"👥 <b>Всего пользователей: {total_users}</b>\n\n"
    text += "<b>Последние 10 пользователей:</b>\n"

    for user in users[:10]:
        user_data = await get_user(user[0])
        text += f"👤 ID: <code>{user[0]}</code> | 💰 {user_data['balance']:.2f}$ | 📝 {user_data['completed_tasks']} заданий\n"

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


# Обработчик кнопки "Статистика"
@dp.callback_query(F.data == "users_stats")
async def users_stats(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            total_users = (await cursor.fetchone())[0]

        async with db.execute('SELECT COUNT(*) FROM users WHERE is_blocked = FALSE') as cursor:
            active_users = (await cursor.fetchone())[0]

        async with db.execute('SELECT COUNT(*) FROM users WHERE is_blocked = TRUE') as cursor:
            banned_users = (await cursor.fetchone())[0]

        async with db.execute('SELECT SUM(balance) FROM users') as cursor:
            total_balance = (await cursor.fetchone())[0] or 0

        async with db.execute('SELECT SUM(frozen_balance) FROM users') as cursor:
            total_frozen = (await cursor.fetchone())[0] or 0

        async with db.execute('SELECT SUM(completed_tasks) FROM users') as cursor:
            total_tasks = (await cursor.fetchone())[0] or 0

        async with db.execute('SELECT COUNT(*), SUM(amount) FROM withdrawals WHERE status = "approved"') as cursor:
            result = await cursor.fetchone()
            total_withdrawals = result[0] or 0
            total_withdrawn = result[1] or 0

    text = (
        "📊 <b>Общая статистика бота</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: <b>{total_users}</b>\n"
        f"• Активных: <b>{active_users}</b>\n"
        f"• Заблокировано: <b>{banned_users}</b>\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"• Общий баланс: <b>{total_balance:.3f}$</b>\n"
        f"• Заморожено: <b>{total_frozen:.3f}$</b>\n"
        f"• Всего выведено: <b>{total_withdrawn:.3f}$</b>\n"
        f"• Количество выводов: <b>{total_withdrawals}</b>\n\n"
        f"📝 <b>Активность:</b>\n"
        f"• Выполнено заданий: <b>{total_tasks}</b>"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="users_back")

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


# Обработчик кнопки "Назад к пользователю"
@dp.callback_query(F.data.startswith("back_to_user_"))
async def back_to_user(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = int(call.data.split("_")[3])
    await show_user_details(call, user_id)
    await call.answer()


# Вспомогательная функция для отображения деталей пользователя
async def show_user_details(call: types.CallbackQuery, user_id: int):
    user = await get_user(user_id)

    if not user:
        await call.message.edit_text("❌ Пользователь не найден")
        return

    # Получаем данные о рефералах
    ref_data = await get_referral_data(user_id)

    # Получаем историю выводов
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT COUNT(*), SUM(amount) FROM withdrawals WHERE user_id = ? AND status = "approved"',
                              (user_id,)) as cursor:
            result = await cursor.fetchone()
            withdrawals_count = result[0] or 0
            total_withdrawn = result[1] or 0
    # Визначаємо рефера
    referrer_text = "⭕"
    if user.get("referrer_id"):
        ref_user = await get_user(user["referrer_id"])
        if ref_user:
            referrer_text = f"@{ref_user['username']}" if ref_user['username'] else f"{ref_user['user_id']}"

    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📛 Имя: @{user['username']}\n"
        f"👥 Пригласил: <b>{referrer_text}</b>\n"
        f"📅 Зарегистрирован: {user.get('registered_at', 'Неизвестно')}\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"• Баланс: <b>{user['balance']:.3f}$</b>\n"
        f"• Заморожено: <b>{user['frozen_balance']:.3f}$</b>\n"
        f"• Всего выведено: <b>{total_withdrawn:.3f}$</b> ({withdrawals_count} выводов)\n\n"
        f"📊 <b>Активность:</b>\n"
        f"• Выполнено заданий: <b>{user['completed_tasks']}</b>\n"
        f"• Рефералы 1 ур: <b>{ref_data['level1_count']}</b>\n"
        f"• Рефералы 2 ур: <b>{ref_data['level2_count']}</b>\n"
        f"• Статус: {'❌ Заблокирован' if user['is_blocked'] else '✅ Активен'}\n"
    )

    keyboard = InlineKeyboardBuilder()

    keyboard.button(text="💰 Начислить", callback_data=f"add_balance_{user_id}")
    keyboard.button(text="➖ Снять", callback_data=f"remove_balance_{user_id}")

    if user['is_blocked']:
        keyboard.button(text="🔓 Разблокировать", callback_data=f"unban_{user_id}")
    else:
        keyboard.button(text="🔒 Заблокировать", callback_data=f"ban_{user_id}")

    keyboard.button(text="👥 Рефералы", callback_data=f"show_refs_{user_id}")
    keyboard.button(text="📊 Статистика", callback_data=f"user_stats_{user_id}")

    keyboard.button(text="🗑 Очистить БД", callback_data=f"clean_userdb:{user_id}")
    keyboard.button(text="🔙 Назад", callback_data="users_back")
    keyboard.adjust(2, 2, 1, 1)

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')


@dp.callback_query(F.data.startswith("user_stats_"))
async def user_stats_detail(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = int(call.data.split("_")[2])

    # Получаем детальную статистику пользователя
    async with aiosqlite.connect('bot_database.db') as db:
        # История баланса
        async with db.execute('SELECT COUNT(*), SUM(amount) FROM balance_history WHERE user_id = ? AND amount > 0',
                              (user_id,)) as cursor:
            result = await cursor.fetchone()
            balance_additions = result[0] or 0
            total_added = result[1] or 0

        # История списаний
        async with db.execute('SELECT COUNT(*), SUM(amount) FROM balance_history WHERE user_id = ? AND amount < 0',
                              (user_id,)) as cursor:
            result = await cursor.fetchone()
            balance_removals = result[0] or 0
            total_removed = result[1] or 0

        # Выводы
        async with db.execute('SELECT COUNT(*), SUM(amount) FROM withdrawals WHERE user_id = ?', (user_id,)) as cursor:
            result = await cursor.fetchone()
            withdrawals_count = result[0] or 0
            total_withdrawn = result[1] or 0

    user = await get_user(user_id)

    text = (
        f"📊 <b>Детальная статистика пользователя {user_id}</b>\n\n"
        f"👤 {user['username']}\n\n"
        f"💰 <b>Финансовая история:</b>\n"
        f"• Начислений: <b>{balance_additions}</b> на сумму <b>{total_added:.3f}$</b>\n"
        f"• Списаний: <b>{balance_removals}</b> на сумму <b>{abs(total_removed):.3f}$</b>\n"
        f"• Запросов на вывод: <b>{withdrawals_count}</b> на сумму <b>{total_withdrawn:.3f}$</b>\n\n"
        f"📝 <b>Текущие показатели:</b>\n"
        f"• Баланс: <b>{user['balance']:.3f}$</b>\n"
        f"• Заморожено: <b>{user['frozen_balance']:.3f}$</b>\n"
        f"• Выполнено заданий: <b>{user['completed_tasks']}</b>"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data=f"back_to_user_{user_id}")

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


@dp.callback_query(F.data == "flyer_settings")
async def flyer_settings(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    # Получаем информацию о текущем ключе
    current_key = FLYER_API_KEY
    key_display = f"{current_key[:8]}...{current_key[-4:]}" if current_key and len(current_key) > 12 else "Не настроен"

    # Проверяем статус API
    status = "✅ Активен" if flyer_enabled else "❌ Неактивен"

    text = (
        "🔑 <b>НАСТРОЙКИ FLYER API</b>\n\n"
        f"📊 Текущий ключ: <code>{key_display}</code>\n"
        f"🔄 Статус: {status}\n\n"
        "💡 <b>Функции Flyer API:</b>\n"
        "• Проверка подписки на каналы\n"
        "• Проверка выполнения заданий\n"
        "• Защита от ботов\n\n"
        "<b>Выберите действие:</b>"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🧪 Тест API", callback_data="test_flyer_api")
    keyboard.button(text="🔙 Назад", callback_data="admin_settings_back")
    keyboard.adjust(1)

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


@dp.callback_query(F.data == "test_flyer_api")
async def test_flyer_api(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.edit_text("🧪 <b>Тестируем Flyer API...</b>", parse_mode='HTML')

    test_results = []

    try:
        # Тест 1: Получение заданий
        test_results.append("🔍 Получение заданий...")
        tasks = await flyer_get_tasks(call.from_user.id, 'ru', limit=1)
        if tasks is not None:
            if tasks:
                test_results.append(f"✅ Получено {len(tasks)} заданий")
                # Показываем первое задание
                if tasks[0]:
                    task = tasks[0]
                    test_results.append(f"📝 Задание: {task.get('name', 'Название')}")
                    test_results.append(f"💰 Цена: {task.get('price', '0')}$")
                    test_results.append(f"📌 Тип: {task.get('task', 'Неизвестно')}")
            else:
                test_results.append("⚠️ Заданий нет (это нормально)")
        else:
            test_results.append("❌ Ошибка получения заданий")

        # Тест 2: Проверка метода check_task (если есть задания)
        if tasks and len(tasks) > 0 and tasks[0].get('signature'):
            signature = tasks[0]['signature']
            test_results.append(f"🔍 Проверка задания {signature[:8]}...")
            status = await flyer_check_task(signature, call.from_user.id)
            test_results.append(f"📊 Статус: {status}")

    except Exception as e:
        test_results.append(f"❌ Ошибка тестирования: {str(e)}")

    text = "🧪 <b>РЕЗУЛЬТАТЫ ТЕСТА FLYER API</b>\n\n" + "\n".join(test_results)

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔄 Повторить тест", callback_data="test_flyer_api")
    keyboard.button(text="🔙 Назад", callback_data="flyer_settings")
    keyboard.adjust(1)

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


# Обнови функцию admin_settings чтобы добавить кнопку Flyer
@dp.message(F.text == "⚙️ Настройки")
async def admin_settings(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    promo_price = float(await get_setting("promotion_price") or 0.015)
    current_value = await get_setting("user_task_reward") or "0.015"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔑 Настройки Flyer", callback_data="flyer_settings")
    keyboard.button(text="📺 Настройки Gramads", callback_data="gramads_settings")  # НОВАЯ КНОПКА
    keyboard.button(text="✏️ Сменить канал", callback_data="change_payments_channel")
    keyboard.button(text="💬 Сменить чат", callback_data="change_chat")
    keyboard.button(text="💰 Мин. вывод", callback_data="change_min_withdrawal")
    keyboard.button(text="💵 Валюта", callback_data="change_currency")
    keyboard.button(text="📝 Управление заданиями", callback_data="manage_tasks")
    keyboard.button(text=f"💰 CryptoPay", callback_data="set_crypto_token")
    keyboard.button(text="💸 Настройки рефералов", callback_data="change_referral_settings")
    keyboard.button(text=f"✏️ Цена зад. {promo_price:.3f}", callback_data="edit_promotion_price")
    keyboard.button(text=f"✏️ Выпл.польз.зад. {current_value}", callback_data="edit_user_task_reward")
    keyboard.button(text="📡 Канал выплат", callback_data="set_payment_channel")
    keyboard.button(text="🛡 Требования вывода", callback_data="withdraw_requirements")
    keyboard.button(text="🌿 OP Tgrass", callback_data="admin_tgrass_settings")

    keyboard.adjust(2, 2, 2, 2, 2, 2, 1)

    await message.answer("⚙️ <b>Настройки бота:</b>", reply_markup=keyboard.as_markup(), parse_mode='HTML')


@dp.callback_query(F.data == "gramads_settings")
async def gramads_settings_menu(call: types.CallbackQuery):
    """Меню настроек Gramads"""
    if call.from_user.id not in ADMIN_IDS:
        return

    # Получаем текущий токен
    current_token = await get_setting("gramads_token") or "Не установлен"

    # Обрезаем для отображения
    if len(current_token) > 30:
        token_display = f"{current_token[:15]}...{current_token[-15:]}"
    else:
        token_display = current_token

    # Статус
    status = "🟢 Включен" if gramads_enabled else "🔴 Выключен"

    # Статистика
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = FALSE") as cursor:
            total_users = (await cursor.fetchone())[0]

    text = (
        f"📺 <b>НАСТРОЙКИ GRAMADS</b>\n\n"
        f"📊 Статус: {status}\n"
        f"👥 Пользователей: {total_users}\n"
        f"🔑 Токен: <code>{token_display}</code>\n\n"
        f"<i>Реклама — дополнительный доход для бота</i>"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить токен", callback_data="set_gramads_token")
    kb.button(text="🧪 Тест рекламы", callback_data="test_gramads")
    kb.button(text="📊 Статистика показов", callback_data="gramads_stats")
    kb.button(text="🔄 Перезагрузить настройки", callback_data="reload_gramads")
    kb.button(text="🔙 Назад", callback_data="admin_settings_back")
    kb.adjust(1)

    await call.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode='HTML')
    await call.answer()


@dp.callback_query(F.data == "set_gramads_token")
async def set_gramads_token_start(call: types.CallbackQuery, state: FSMContext):
    """Запрос нового токена Gramads"""
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.answer(
        "🔑 <b>Введите новый токен Gramads:</b>\n\n"
        "Токен должен начинаться с <code>eyJ</code> (JWT формат)\n"
        "Пример: <code>eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...</code>",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_gramads_token)
    await call.answer()


@dp.message(AdminStates.waiting_gramads_token)
async def save_gramads_token(message: types.Message, state: FSMContext):
    """Сохранение токена Gramads"""
    global GRAMADS_TOKEN, gramads_enabled

    new_token = message.text.strip()

    # Проверяем формат токена (JWT обычно начинается с eyJ)
    if not new_token.startswith('eyJ'):
        await message.answer(
            "❌ <b>Неверный формат токена!</b>\n\n"
            "Токен Gramads должен быть в JWT формате и начинаться с <code>eyJ</code>",
            parse_mode='HTML'
        )
        await state.clear()
        return

    # Сохраняем в БД
    await set_setting("gramads_token", new_token)

    # Обновляем глобальные переменные
    GRAMADS_TOKEN = new_token
    gramads_enabled = True

    await message.answer(
        f"✅ <b>Токен Gramads успешно сохранен!</b>\n\n"
        f"📊 Токен: <code>{new_token[:20]}...{new_token[-20:]}</code>\n"
        f"🔄 Система рекламы активирована",
        parse_mode='HTML'
    )
    await state.clear()


@dp.callback_query(F.data == "test_gramads")
async def test_gramads_ad(call: types.CallbackQuery):
    """Тест рекламы Gramads"""
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = call.from_user.id

    await call.message.edit_text("🧪 <b>Тестируем показ рекламы...</b>", parse_mode='HTML')

    success = await show_gramads_ad(user_id)

    if success:
        text = "✅ <b>Реклама успешно показана!</b>\n\nПроверьте свой Telegram для подтверждения."
    else:
        text = "❌ <b>Не удалось показать рекламу</b>\n\nПроверьте:\n1. Корректность токена\n2. Наличие активных рекламных кампаний\n3. Доступность API Gramads"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Повторить тест", callback_data="test_gramads")
    kb.button(text="🔙 Назад", callback_data="gramads_settings")
    kb.adjust(1)

    await call.message.edit_text(text, parse_mode='HTML', reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data == "gramads_stats")
async def show_gramads_stats(call: types.CallbackQuery):
    """Статистика показов рекламы"""
    if call.from_user.id not in ADMIN_IDS:
        return

    # Считаем пользователей, которым показывали рекламу
    ad_users_count = len(last_ad_times)

    # Можно добавить больше статистики из БД
    text = (
        f"📊 <b>СТАТИСТИКА GRAMADS</b>\n\n"
        f"🔄 Статус: {'🟢 Активен' if gramads_enabled else '🔴 Отключен'}\n"
        f"👥 Показано рекламы: {ad_users_count} пользователям\n"
        f"⏰ Кеш последних показов: {len(last_ad_times)} записей\n\n"
        f"<i>Статистика обновляется в реальном времени</i>"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="gramads_stats")
    kb.button(text="🔙 Назад", callback_data="gramads_settings")
    kb.adjust(1)

    await call.message.edit_text(text, parse_mode='HTML', reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data == "reload_gramads")
async def reload_gramads_settings(call: types.CallbackQuery):
    """Перезагрузка настроек Gramads"""
    if call.from_user.id not in ADMIN_IDS:
        return

    await load_gramads_token()
    await call.answer("✅ Настройки Gramads перезагружены", show_alert=True)
    await gramads_settings_menu(call)


# ----------------- НАЧАЛО: Блок управления требованиями для вывода -----------------

ALL_LANGUAGES = [
    ("en", "🇺🇸", "Английский"),
    ("ar", "🇸🇦", "Арабский"),
    ("be", "🇧🇾", "Белорусский"),
    ("hu", "🇭🇺", "Венгерский"),
    ("he", "🇮🇱", "Иврит"),
    ("id", "🇮🇩", "Индонезийский"),
    ("es", "🇪🇸", "Испанский"),
    ("it", "🇮🇹", "Итальянский"),
    ("kk", "🇰🇿", "Казахский"),
    ("ca", "🇪🇸", "Каталанский"),
    ("ko", "🇰🇷", "Корейский"),
    ("ms", "🇲🇾", "Малайский"),
    ("de", "🇩🇪", "Немецкий"),
    ("nl", "🇳🇱", "Нидерландский"),
    ("nb", "🇳🇴", "Норвежский букмол"),
    ("fa", "🇮🇷", "Персидский"),
    ("pl", "🇵🇱", "Польский"),
    ("pt", "🇵🇹", "Португальский"),
    ("ru", "🇷🇺", "Русский"),
    ("sr", "🇷🇸", "Сербский"),
    ("sk", "🇸🇰", "Словацкий"),
    ("tr", "🇹🇷", "Турецкий"),
    ("uz", "🇺🇿", "Узбекский"),
    ("uk", "🇺🇦", "Украинский"),
    ("fi", "🇫🇮", "Финский"),
    ("fr", "🇫🇷", "Французский"),
    ("hr", "🇭🇷", "Хорватский"),
    ("cs", "🇨🇿", "Чешский"),
    ("sv", "🇸🇪", "Шведский")
]

LANGS_PER_PAGE = 9  # 3 buttons per row, 3 rows per сторінку


# --- Відкриваємо меню налаштувань вимог для виводу ---
@dp.callback_query(F.data == "withdraw_requirements")
async def withdraw_requirements_menu(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    username_req = await get_setting("req_username") == "1"
    avatar_req = await get_setting("req_avatar") == "1"
    lang_req = await get_setting("req_language") == "1"
    allowed = (await get_setting("allowed_languages") or "uk,ru").split(",")
    allowed_display = ", ".join([l for l in allowed if l])

    kb = InlineKeyboardBuilder()
    kb.button(text=f"👤 Юзернейм: {'🟢 Вкл' if username_req else '🔴 Выкл'}", callback_data="toggle_req_username")
    kb.button(text=f"🖼 Аватар: {'🟢 Вкл' if avatar_req else '🔴 Выкл'}", callback_data="toggle_req_avatar")
    kb.button(text=f"🌐 Язык: {'🟢 Вкл' if lang_req else '🔴 Выкл'}", callback_data="toggle_req_language")
    kb.button(text="🌎 Доступные языки", callback_data="edit_allowed_langs_page_1")
    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="settings_back"))
    kb.adjust(2, 2, 1)

    await call.message.edit_text(
        "🛡 <b>Требования для вывода</b>\n\nВыберите необходимые проверки и допустимые языки:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )
    await call.answer()


# --- Toggle handlers ---
@dp.callback_query(F.data == "toggle_req_username")
async def toggle_req_username(call: types.CallbackQuery):
    cur = await get_setting("req_username") or "0"
    await set_setting("req_username", "0" if cur == "1" else "1")
    await withdraw_requirements_menu(call)


@dp.callback_query(F.data == "toggle_req_avatar")
async def toggle_req_avatar(call: types.CallbackQuery):
    cur = await get_setting("req_avatar") or "0"
    await set_setting("req_avatar", "0" if cur == "1" else "1")
    await withdraw_requirements_menu(call)


@dp.callback_query(F.data == "toggle_req_language")
async def toggle_req_language(call: types.CallbackQuery):
    cur = await get_setting("req_language") or "0"
    await set_setting("req_language", "0" if cur == "1" else "1")
    await withdraw_requirements_menu(call)


# --- Меню вибору мов з пагінацією ---
def build_lang_page_markup(page: int, allowed: list[str]):
    # page: 1-based
    start = (page - 1) * LANGS_PER_PAGE
    end = start + LANGS_PER_PAGE
    slice_langs = ALL_LANGUAGES[start:end]

    kb = InlineKeyboardBuilder()

    # Додаємо кнопки мов — 3 в ряд
    row = []
    for i, (code, flag, name) in enumerate(slice_langs, 1):
        checked = "🟢" if code in allowed else "🔴"
        row.append(
            InlineKeyboardButton(text=f"{checked} {flag} {name}", callback_data=f"toggle_lang_{code}_page_{page}"))
        # вставка по 3 в ряд
        if len(row) == 3:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)

    # Навігація сторінок
    total_pages = (len(ALL_LANGUAGES) + LANGS_PER_PAGE - 1) // LANGS_PER_PAGE
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_allowed_langs_page_{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"Стр. {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="➡️ Далее", callback_data=f"edit_allowed_langs_page_{page + 1}"))
    kb.row(*nav)

    kb.row(InlineKeyboardButton(text="🔙 Назад", callback_data="withdraw_requirements"))
    return kb.as_markup()


@dp.callback_query(F.data.regexp(r"^edit_allowed_langs_page_\d+$"))
async def edit_allowed_langs(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    page = int(call.data.split("_")[-1])
    allowed = (await get_setting("allowed_languages") or "uk,ru").split(",")
    await call.message.edit_text(
        "🌐 <b>Выбор разрешённых языков</b>\n\n"
        "Нажмите на язык чтобы включить/выключить его.\n\n"
        "<i>Кнопка показывает состояние и название языка.</i>",
        parse_mode="HTML",
        reply_markup=build_lang_page_markup(page, allowed)
    )
    await call.answer()


# --- Тогл конкретної мови (з відкатом на ту ж сторінку) ---
@dp.callback_query(F.data.regexp(r"^toggle_lang_[a-z]{2,3}_page_\d+$"))
async def toggle_lang(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    parts = call.data.split("_")
    lang_code = parts[2]
    page = int(parts[-1])

    allowed = (await get_setting("allowed_languages") or "uk,ru").split(",")
    allowed = [x for x in allowed if x]

    if lang_code in allowed:
        allowed.remove(lang_code)
    else:
        allowed.append(lang_code)

    await set_setting("allowed_languages", ",".join(allowed))

    allowed = (await get_setting("allowed_languages") or "uk,ru").split(",")
    await call.message.edit_text(
        "🌐 <b>Выбор разрешённых языков</b>\n\n"
        "Нажмите на язык чтобы включить/выключить его.\n\n"
        "<i>Кнопка показывает состояние и название языка.</i>",
        parse_mode="HTML",
        reply_markup=build_lang_page_markup(page, allowed)
    )
    await call.answer()


# --- Накшталт noop для кнопки сторінки (щоб не було помилки) ---
@dp.callback_query(F.data == "noop")
async def noop(call: types.CallbackQuery):
    await call.answer()


# --- Повернення назад до головного меню налаштувань ---
@dp.callback_query(F.data == "settings_back")
async def settings_back(call: types.CallbackQuery):
    # Викликаємо туфункцію, що показує admin settings
    try:
        await admin_settings(call.message)
    except Exception:
        # якщо admin_settings очікує Message — спробуємо просто відповісти
        await call.message.edit_text("⚙️ Перенаправляю в настройки...", reply_markup=get_admin_keyboard())
    await call.answer()


# ----------------- КОНЕЦ: Блок управления требованиями для вывода -----------------


@dp.callback_query(F.data == "set_payment_channel")
async def ask_payment_channel(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await call.message.answer(
        "📡 Введите @username канала или ID (например: @mychannel или -1001234567890)"
    )
    await state.set_state(AdminStates.waiting_payments_channell)


@dp.message(AdminStates.waiting_payments_channell)
async def save_payment_channel(message: Message, state: FSMContext):
    channel = message.text.strip()
    await set_setting("payments_channell", channel)

    await message.answer(
        f"✅ Канал выплат сохранён: <code>{channel}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await state.clear()


# ========================== 👑 АДМІН: ЗМІНА ВИПЛАТИ ЗА ЗАДАНИЕ ==========================

class EditUserTaskReward(StatesGroup):
    waiting_for_new_value = State()


@dp.callback_query(F.data == "edit_user_task_reward")
async def edit_user_task_reward(call: CallbackQuery, state: FSMContext):
    await call.message.answer(
        f"💸 <b>Текущая выплата за пользовательское задание:</b>\n\n"
        f"Введите новое значение:",
        parse_mode="HTML"
    )
    await state.set_state(EditUserTaskReward.waiting_for_new_value)
    await call.answer()


@dp.message(EditUserTaskReward.waiting_for_new_value)
async def process_new_user_task_reward(message: Message, state: FSMContext):
    try:
        new_value = float(message.text.strip())
        if new_value <= 0:
            await message.answer("❌ Сумма должна быть больше 0.")
            return

        await set_setting("user_task_reward", str(new_value))
        await message.answer(f"✅ Выплата за юзер-задание успешно изменена на <b>{new_value}$</b>.", parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число (например: 0.02).")
        await state.clear()


@dp.callback_query(F.data == "edit_promotion_price")
async def edit_promotion_price(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ У вас нет доступа", show_alert=True)
        return

    await call.message.answer("💰 Введите новую цену за одно выполнение (в $):\nНапример: <b>0.02</b>",
                              parse_mode="HTML")
    await state.set_state(AdminStates.waiting_promotion_price)
    await call.answer()


@dp.message(AdminStates.waiting_promotion_price)
async def set_new_promotion_price(message: types.Message, state: FSMContext):
    try:
        new_price = float(message.text.strip().replace(",", "."))
        if new_price <= 0:
            await message.answer("❌ Цена должна быть больше 0.")
            return

        await set_setting("promotion_price", str(new_price))
        await message.answer(f"✅ Цена задания успешно изменена на <b>{new_price:.3f} $</b>!", parse_mode="HTML")
        await state.clear()

    except ValueError:
        await message.answer("❌ Введите корректное число, например: 0.015")


@dp.callback_query(F.data == "change_referral_settings")
async def change_referral_settings(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    # Отримуємо поточні налаштування
    bonus_lvl1 = await get_setting('ref_bonus_level1') or '0.05'
    bonus_lvl2 = await get_setting('ref_bonus_level2') or '0.03'
    tasks_lvl1 = await get_setting('ref_tasks_required_level1') or '3'
    tasks_lvl2 = await get_setting('ref_tasks_required_level2') or '5'

    kb = InlineKeyboardBuilder()
    kb.button(text=f"💰 1 ур. - {bonus_lvl1}$", callback_data="change_ref_bonus_level1")
    kb.button(text=f"📝 Заданий: {tasks_lvl1}", callback_data="change_ref_tasks_level1")
    kb.button(text=f"💰 2 ур. - {bonus_lvl2}$", callback_data="change_ref_bonus_level2")
    kb.button(text=f"📝 Заданий: {tasks_lvl2}", callback_data="change_ref_tasks_level2")
    kb.button(text="🔙 Назад", callback_data="admin_settings_back")
    kb.adjust(2, 2, 1)

    await call.message.edit_text(
        f"⚙️ <b>Настройки реферальной системы</b>\n\n"
        f"💰 <b>1 уровень</b>\n"
        f"├─ Бонус: <b>{bonus_lvl1}$</b>\n"
        f"└─ Нужно заданий: <b>{tasks_lvl1}</b>\n\n"
        f"💰 <b>2 уровень</b>\n"
        f"├─ Бонус: <b>{bonus_lvl2}$</b>\n"
        f"└─ Нужно заданий: <b>{tasks_lvl2}</b>\n\n"
        f"💡 Рефер получает выплату когда реферал выполнит нужное количество заданий.",
        parse_mode='HTML',
        reply_markup=kb.as_markup()
    )
    await call.answer()


@dp.callback_query(F.data == "change_ref_bonus_level1")
async def change_ref_bonus_level1(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("💰 Введите выплату за реферала 1 уровня (в $, например: 0.05):")
    await state.set_state(AdminStates.waiting_ref_bonus_level1)
    await call.answer()


@dp.callback_query(F.data == "change_ref_bonus_level2")
async def change_ref_bonus_level2(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("💰 Введите выплату за реферала 2 уровня (в $, например: 0.03):")
    await state.set_state(AdminStates.waiting_ref_bonus_level2)
    await call.answer()


@dp.callback_query(F.data == "change_ref_tasks_level1")
async def change_ref_tasks_level1(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📝 Введите количество заданий для получения бонуса 1 уровня (например: 3):")
    await state.set_state(AdminStates.waiting_ref_tasks_level1)
    await call.answer()


@dp.callback_query(F.data == "change_ref_tasks_level2")
async def change_ref_tasks_level2(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📝 Введите количество заданий для получения бонуса 2 уровня (например: 5):")
    await state.set_state(AdminStates.waiting_ref_tasks_level2)
    await call.answer()


@dp.message(AdminStates.waiting_ref_bonus_level1)
async def process_ref_bonus_level1(message: types.Message, state: FSMContext):
    try:
        value = float(message.text)
        if value <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        await set_setting('ref_bonus_level1', str(value))
        await message.answer(f"✅ Бонус 1 уровня установлен: {value}$")
    except ValueError:
        await message.answer("❌ Введите корректное число")
    await state.clear()


@dp.message(AdminStates.waiting_ref_bonus_level2)
async def process_ref_bonus_level2(message: types.Message, state: FSMContext):
    try:
        value = float(message.text)
        if value <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
        await set_setting('ref_bonus_level2', str(value))
        await message.answer(f"✅ Бонус 2 уровня установлен: {value}$")
    except ValueError:
        await message.answer("❌ Введите корректное число")
    await state.clear()


@dp.message(AdminStates.waiting_ref_tasks_level1)
async def process_ref_tasks_level1(message: types.Message, state: FSMContext):
    try:
        value = int(message.text)
        if value < 1:
            await message.answer("❌ Количество должно быть не менее 1")
            return
        await set_setting('ref_tasks_required_level1', str(value))
        await message.answer(f"✅ Заданий для 1 уровня: {value}")
    except ValueError:
        await message.answer("❌ Введите корректное число")
    await state.clear()


@dp.message(AdminStates.waiting_ref_tasks_level2)
async def process_ref_tasks_level2(message: types.Message, state: FSMContext):
    try:
        value = int(message.text)
        if value < 1:
            await message.answer("❌ Количество должно быть не менее 1")
            return
        await set_setting('ref_tasks_required_level2', str(value))
        await message.answer(f"✅ Заданий для 2 уровня: {value}")
    except ValueError:
        await message.answer("❌ Введите корректное число")
    await state.clear()


@dp.callback_query(F.data == "set_crypto_token")
async def admin_set_crypto_token(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🪙 Отправьте новый токен криптобота:")
    await state.set_state(AdminStates.waiting_crypto_token)


@dp.message(AdminStates.waiting_crypto_token)
async def process_crypto_token(message: types.Message, state: FSMContext):
    global CRYPTO_BOT_TOKEN, crypto_enabled

    new_token = message.text.strip()

    if not new_token or len(new_token) < 10:
        await message.answer("❌ Неверный формат токена. Попробуйте еще раз.")
        await state.clear()
        return

    # ✅ Сохраняем токен в базе данных
    await set_setting("CRYPTO_BOT_TOKEN", new_token)

    # ✅ Обновляем глобальные переменные
    CRYPTO_BOT_TOKEN = new_token
    crypto_enabled = True

    await message.answer(
        f"✅ Токен криптобота успешно обновлен!\n\n"
        f"🔐 Новый токен: <code>{CRYPTO_BOT_TOKEN[:8]}...{CRYPTO_BOT_TOKEN[-4:]}</code>",
        parse_mode="HTML"
    )

    await state.clear()


@dp.callback_query(F.data == "manage_tasks")
async def manage_tasks(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    # Получаем список заданий
    tasks = await get_active_custom_tasks()

    text = "📝 <b>Управление заданиями</b>\n\n"
    text += f"📊 Активных заданий: {len(tasks)}\n\n"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Добавить задание", callback_data="add_custom_task")

    if tasks:
        for task in tasks[:10]:  # Показываем первые 10
            completions_info = f"{task['current_completions']}/{task['max_completions']}" if task[
                                                                                                 'max_completions'] > 0 else f"{task['current_completions']}"
            keyboard.button(text=f"📝 {task['name'][:15]}... ({completions_info})",
                            callback_data=f"view_task_{task['id']}")

    keyboard.button(text="📊 Общая статистика", callback_data="tasks_stats")
    keyboard.button(text="🔙 Назад", callback_data="admin_settings_back")
    keyboard.adjust(1, 2, 1, 1)

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


@dp.message(F.text == "📢 Рассылка")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "📢 <b>Создание рассылки</b>\n\n"
        "Отправьте сообщение для рассылки (можно с медиа).\n"
        "После этого вы сможете добавить инлайн кнопки.",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_broadcast)


@dp.callback_query(F.data == "withdraw")
async def start_withdrawal(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    username = call.from_user.username
    # --- проверка username ---
    if await get_setting("req_username") == "1":
        if not call.from_user.username:
            await call.answer("❌ Для вывода требуется юзернейм!", show_alert=True)
            return

    # --- проверка аватарки ---
    if await get_setting("req_avatar") == "1":
        try:
            photos = await call.bot.get_user_profile_photos(call.from_user.id)
            if photos.total_count == 0:
                await call.answer("❌ Для вывода требуется аватарка!", show_alert=True)
                return
        except:
            await call.answer("❌ Не удалось проверить аватарку. Попробуйте позже.", show_alert=True)
            return

    # --- проверка языка ---
    if await get_setting("req_language") == "1":
        allowed = (await get_setting("allowed_languages") or "uk,ru").split(",")
        user_lang = (call.from_user.language_code or "").split("-")[0]
        if user_lang not in allowed:
            await call.answer(
                f"❌ Язык Telegram не поддерживается!\nРазрешённые: {', '.join(allowed)}",
                show_alert=True
            )
            return

    user = await get_user(user_id)
    min_amount = float(await get_setting('min_withdrawal') or 0.2)
    currency = await get_setting('currency') or 'USD'

    if user['balance'] < min_amount:
        await call.answer(f"❌ Минимальная сумма для вывода: {min_amount:.3f} {currency}", show_alert=True)
        return
    try:
        await call.message.delete()
    except:
        pass

    await call.message.answer(
        f"💵 Введите сумму для вывода (доступно: {user['balance']:.3f} {currency}):"
    )
    await state.set_state(WithdrawalStates.waiting_for_amount)
    await call.answer()


@dp.message(WithdrawalStates.waiting_for_amount)
async def process_withdrawal_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        user = await get_user(message.from_user.id)
        min_amount = float(await get_setting('min_withdrawal') or 0.1)

        if amount < min_amount:
            await message.answer(f"❌ Минимальная сумма для вывода: {min_amount}$")
            return

        if amount > user['balance']:
            await message.answer("❌ Недостаточно средств на балансе")
            return

        # 💰 Списываем баланс сразу!
        await update_user_balance(message.from_user.id, amount=-amount)

        # Создаем заявку
        withdrawal_id = await create_withdrawal_request(
            user_id=message.from_user.id,
            amount=amount
        )

        # Уведомляем юзера
        await message.answer(
            f"📨 <b>Заявка на вывод отправлена!</b>\n"
            f"💵 Сумма: <b>{amount:.3f}$</b>\n\n"
            f"⏳ Ожидайте решения администрации.",
            parse_mode="HTML"
        )

        # Отправляем админам
        await send_withdraw_request_to_admins(withdrawal_id)

        await state.clear()

    except ValueError:
        await message.answer("❌ Введите корректную сумму")


async def get_reserve_status(total_balance: float):
    if total_balance < 1:
        return "🚨 КРИТИЧЕСКИ НИЗКИЙ", "🔴", "❌ СРОЧНО ПОПОЛНИТЕ РЕЗЕРВ!"
    elif total_balance < 3:
        return "⚠️ НИЗКИЙ", "🟡", "💡 Рекомендуется пополнить резерв"
    elif total_balance < 5:
        return "ℹ️ СРЕДНИЙ", "🟢", "✅ Резерв в норме"
    else:
        return "✅ ДОСТАТОЧНЫЙ", "💚", "🎉 Отличный запас!"


async def send_withdraw_request_to_admins(withdrawal_id):
    wd = await get_withdrawal(withdrawal_id)
    user = await get_user(wd["user_id"])

    # Получаем резерв
    total_balance = await get_crypto_bot_balance()
    reserve_status, reserve_emoji, rec = await get_reserve_status(total_balance)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Подтвердить", callback_data=f"wd_confirm:{withdrawal_id}")
    kb.button(text="❌ Отклонить (без возврата)", callback_data=f"wd_norefund:{withdrawal_id}")
    kb.button(text="↩️ Отклонить (с возвратом)", callback_data=f"wd_refund:{withdrawal_id}")
    kb.button(text="👤 О пользователе", callback_data=f"wd_userinfo:{wd['user_id']}")
    kb.adjust(1, 2, 1)

    text = f"""
📨 <b>НОВАЯ ЗАЯВКА НА ВЫВОД</b>

🆔 User ID: <code>{user['user_id']}</code>
👤 Username: @{user['username'] or 'нет'}

💵 Сумма вывода: <b>{wd['amount']}$</b>
🔖 ID заявки: <code>{withdrawal_id}</code>
⏳ Статус: <b>Ожидает</b>
━━━━━━━━━━━━━━━━━━
💰 <b>Резерв Системы</b>

🔢 Баланс: <b>{total_balance:.2f} USDT</b>

<i>{rec}</i>
"""

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=kb.as_markup())
        except:
            pass


async def send_payment_notification(user_id: int, amount: float):
    channel = await get_setting("payments_channell")
    if not channel:
        return

    # Створюємо кликабельне слово "пользователю"
    user_link = f"<a href='tg://user?id={user_id}'>Пользователю</a>"

    text = (
        f"<b>✅ {user_link} выплачено {amount}$ на 💎 CryptoBot</b>"
    )

    # Твій бот
    me = await bot.get_me()
    bot_url = f"https://t.me/{me.username}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="💎 Открыть бота",
                url=bot_url
            )
        ]]
    )

    try:
        await bot.send_message(
            chat_id=channel,
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except Exception as e:
        print("Ошибка отправки уведомления:", e)


@dp.callback_query(F.data.startswith("wd_confirm:"))
async def wd_confirm_handler(call: CallbackQuery):
    withdrawal_id = int(call.data.split(":")[1])
    wd = await get_withdrawal(withdrawal_id)
    user = await get_user(wd["user_id"])

    amount = wd["amount"]

    # Генерация чека
    success, receipt_url = await generate_crypto_receipt(amount, user['user_id'])

    await update_withdrawal_status(
        withdrawal_id,
        status="approved",
        admin_id=call.from_user.id,
        admin_receipt_url=receipt_url
    )

    await send_payment_notification(user['user_id'], amount)
    chat_link = await get_setting("chat_link")

    # Уведомляем пользователя
    kb = InlineKeyboardBuilder()
    if success and receipt_url:
        kb.button(text="📎 Открыть чек", url=receipt_url)
    else:
        kb.button(text="❌ НЕ СОЗДАН", callback_data="noop")

    if chat_link and chat_link.startswith("http"):
        kb.button(text="💬 Оставить отзыв", url=chat_link)
    else:
        # Фолбек, если админ не установил чат
        kb.button(text="💬 Оставить отзыв", url="https://t.me/example_chat")
    kb.adjust(1)

    asyncio.create_task(show_ad_at_opportunity(user['user_id'], "after_withdrawal"))
    await bot.send_message(
        user['user_id'],
        f"🎉 <b>Ваш вывод одобрен!</b>\n"
        f"💵 Сумма: <b>{amount:.2f}$</b>\n"
        f"🌟 Оставьте пожалуйста отзыв о выплате в нашем чате.\n"
        f"<span class='tg-spoiler'><i>P.s: если не оставите отзыв о выводе — не получите выплату в следующий раз.</i></span>",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await call.message.edit_text(
        f"✅ <b>Вывод подтвержден!</b>\nID: <code>{withdrawal_id}</code>\nСумма: <b>{amount}$</b>",
        parse_mode="HTML"
    )
    await call.answer("Готово")


@dp.callback_query(F.data.startswith("wd_norefund:"))
async def wd_norefund_handler(call: CallbackQuery):
    withdrawal_id = int(call.data.split(":")[1])
    wd = await get_withdrawal(withdrawal_id)
    user = await get_user(wd["user_id"])

    await update_withdrawal_status(withdrawal_id, status="declined", admin_id=call.from_user.id)

    await bot.send_message(
        user['user_id'],
        "❌ <b>Ваш вывод отклонён.</b>",
        parse_mode="HTML"
    )

    await call.message.edit_text("❌ Вывод отклонён (без возврата).", parse_mode="HTML")
    await call.answer("Готово")


@dp.callback_query(F.data.startswith("wd_refund:"))
async def wd_refund_handler(call: CallbackQuery):
    withdrawal_id = int(call.data.split(":")[1])
    wd = await get_withdrawal(withdrawal_id)
    user = await get_user(wd["user_id"])

    # Возврат средств
    await update_user_balance(user['user_id'], amount=wd["amount"])

    await update_withdrawal_status(withdrawal_id, status="refunded", admin_id=call.from_user.id)

    await bot.send_message(
        user['user_id'],
        f"↩️ Ваш вывод отклонён.\n💵 <b>{wd['amount']}$</b> возвращены на баланс.",
        parse_mode="HTML"
    )

    await call.message.edit_text("↩️ Вывод отклонён с возвратом.", parse_mode="HTML")
    await call.answer("Готово")


@dp.callback_query(F.data.startswith("wd_userinfo:"))
async def wd_userinfo_handler(call: CallbackQuery):
    user_id = int(call.data.split(":")[1])
    user = await get_user(user_id)

    if not user:
        await call.answer("Пользователь не найден", show_alert=True)
        return

    # Рефералы
    ref_data = await get_referral_data(user_id)

    # История выводов
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute(
                'SELECT COUNT(*), SUM(amount) FROM withdrawals WHERE user_id = ? AND status = "approved"',
                (user_id,)
        ) as cursor:
            result = await cursor.fetchone()
            withdrawals_count = result[0] or 0
            total_withdrawn = result[1] or 0
    # Визначаємо рефера
    referrer_text = "⭕"
    if user.get("referrer_id"):
        ref_user = await get_user(user["referrer_id"])
        if ref_user:
            referrer_text = f"@{ref_user['username']}" if ref_user['username'] else f"{ref_user['user_id']}"

    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📛 Имя: @{user['username']}\n"
        f"👥 Пригласил: <b>{referrer_text}</b>\n"
        f"📅 Зарегистрирован: {user.get('registered_at', 'Неизвестно')}\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"• Баланс: <b>{user['balance']:.3f}$</b>\n"
        f"• Заморожено: <b>{user['frozen_balance']:.3f}$</b>\n"
        f"• Всего выведено: <b>{total_withdrawn:.3f}$</b> ({withdrawals_count} выводов)\n\n"
        f"📊 <b>Активность:</b>\n"
        f"• Выполнено заданий: <b>{user['completed_tasks']}</b>\n"
        f"• Рефералы 1 ур: <b>{ref_data['level1_count']}</b>\n"
        f"• Рефералы 2 ур: <b>{ref_data['level2_count']}</b>\n"
        f"• Статус: {'❌ Заблокирован' if user['is_blocked'] else '✅ Активен'}\n"
    )

    # === ИНЛАЙН КНОПКИ ===
    kb = InlineKeyboardBuilder()

    # Блокировка / разблокировка
    if user['is_blocked']:
        kb.button(text="🔓 Разблокировать", callback_data=f"unban_{user_id}")
    else:
        kb.button(text="🔒 Заблокировать", callback_data=f"ban_{user_id}")

    # Рефералы
    kb.button(text="👥 Рефералы", callback_data=f"show_refs_{user_id}")

    # Статистика
    kb.button(text="📊 Статистика", callback_data=f"user_stats_{user_id}")
    kb.button(text="🗑 Очистить БД", callback_data=f"clean_userdb:{user_id}")
    kb.adjust(1, 2)  # по одному в ряд, як у адмінці

    await call.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await call.answer()


@dp.callback_query(F.data.startswith("clean_userdb:"))
async def clean_userdb_menu(call: CallbackQuery):
    user_id = int(call.data.split(":")[1])

    kb = InlineKeyboardBuilder()

    kb.button(text="💰 Баланс", callback_data=f"cleanopt:balance:{user_id}")
    kb.button(text="🧊 Заморож. баланс", callback_data=f"cleanopt:frozen:{user_id}")
    kb.button(text="👤 Рефер", callback_data=f"cleanopt:referrer:{user_id}")
    kb.button(text="👥 Рефералы", callback_data=f"cleanopt:refs:{user_id}")
    kb.button(text="📊 Статистика", callback_data=f"cleanopt:stats:{user_id}")
    kb.button(text="🔥 Удалить все", callback_data=f"cleanopt:delete:{user_id}")
    kb.button(text="❌ Отмена", callback_data=f"cleanopt:cancel:{user_id}")

    kb.adjust(1, 1, 2, 2, 1)

    await call.message.edit_text(
        f"🗑 <b>Очистка данных пользователя {user_id}</b>\n"
        f"Выберите, что хотите очистить:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("cleanopt:"))
async def clean_userdb_confirm(call: CallbackQuery):
    _, action, user_id = call.data.split(":")
    user_id = int(user_id)

    if action == "cancel":
        await call.answer("Отменено")
        await call.message.delete()
        return

    # Запитуємо підтвердження
    kb = InlineKeyboardBuilder()
    kb.button(text="✔ Подтвердить", callback_data=f"cleanrun:{action}:{user_id}")
    kb.button(text="✖ Отмена", callback_data="cleanrun:cancel:0")
    kb.adjust(1)

    await call.message.edit_text(
        f"❗ Вы уверены, что хотите выполнить действие:\n<b>{action}</b>?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("cleanrun:"))
async def clean_userdb_execute(call: CallbackQuery):
    _, action, user_id = call.data.split(":")
    user_id = int(user_id)

    if action == "cancel":
        await call.answer("Отменено")
        await call.message.delete()
        return

    async with aiosqlite.connect("bot_database.db") as db:

        if action == "balance":
            await db.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))

        elif action == "frozen":
            await db.execute("UPDATE users SET frozen_balance = 0 WHERE user_id = ?", (user_id,))

        elif action == "referrer":
            await db.execute("UPDATE users SET referrer_id = NULL WHERE user_id = ?", (user_id,))

        elif action == "refs":
            try:
                await db.execute("DELETE FROM referrals WHERE user_id = ? OR referrer_id = ?", (user_id, user_id,))
            except Exception as e:
                print("⚠ Таблицы referrals нет, пропускаем")

        elif action == "stats":
            await db.execute("""
                UPDATE users SET completed_tasks = 0
                WHERE user_id = ?
            """, (user_id,))

        elif action == "delete":
            await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            try:
                await db.execute("DELETE FROM referrals WHERE user_id = ? OR referrer_id = ?", (user_id, user_id,))
            except:
                print("⚠ Таблицы referrals нет, пропускаем")
            await db.execute("DELETE FROM withdrawals WHERE user_id = ?", (user_id,))

        await db.commit()

    await call.message.edit_text(f"✅ Действие <b>{action}</b> успешно выполнено!")
    await call.answer("Готово")


# Информационные callback

@dp.callback_query(F.data == "info_referrals")
async def info_referrals(call: types.CallbackQuery):
    bonus_lvl1 = float(await get_setting('ref_bonus_level1') or 0.05)
    bonus_lvl2 = float(await get_setting('ref_bonus_level2') or 0.03)
    tasks_lvl1 = int(await get_setting('ref_tasks_required_level1') or 3)
    tasks_lvl2 = int(await get_setting('ref_tasks_required_level2') or 5)

    text = (
        "🔗 <b>Реферальная система (2 уровня)</b>\n\n"
        "👥 <b>Как работает:</b>\n"
        f"• <b>1 уровень</b> — вы получаете <b>{bonus_lvl1:.2f}$</b>\n"
        f"  когда реферал выполнит <b>{tasks_lvl1}</b> заданий\n\n"
        f"• <b>2 уровень</b> — вы получаете <b>{bonus_lvl2:.2f}$</b>\n"
        f"  когда реферал выполнит <b>{tasks_lvl2}</b> заданий\n\n"
        "📢 <b>Приглашайте друзей и зарабатывайте!</b>"
    )
    await call.message.answer(text, parse_mode='HTML')
    await call.answer()


@dp.callback_query(F.data == "info_earnings")
async def info_earnings(call: types.CallbackQuery):
    text = (
        "💰 <b>Как зарабатывать в боте</b>\n\n"
        "⏰ Каждые 2 часа появляются новые спонсорские каналы.\n"
        "Подписывайся ➝ получай деньги!\n\n"
        "‼️ <b>ВАЖНО ‼️</b>\n"
        "НЕЛЬЗЯ ОТПИСЫВАТЬСЯ ОТ КАНАЛОВ В ТЕЧЕНИИ 3-Х ДНЕЙ "
        "В ПРОТИВНОМ СЛУЧАЕ ВЫ БУДЕТЕ ОШТРАФОВАНЫ\n\n"
        "🔒 Средства замораживаются на 24 часов после они будут доступны для вывода.\n\n"
        "💵 Вывод приходит чеком на Crypto Bot"
    )
    await call.message.answer(text, parse_mode='HTML')
    await call.answer()


# Админ настройки callback
@dp.callback_query(F.data == "change_payments_channel")
async def change_payments_channel(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.answer("Введите новую ссылку на канал новостей:")
    await state.set_state(AdminStates.waiting_payments_channel)
    await call.answer()


@dp.message(AdminStates.waiting_payments_channel)
async def process_payments_channel(message: types.Message, state: FSMContext):
    await set_setting('payments_channel', message.text)
    await message.answer("✅ Ссылка на канал новостей обновлена")
    await state.clear()


@dp.callback_query(F.data == "change_chat")
async def change_chat(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.answer("Введите новую ссылку на чат:")
    await state.set_state(AdminStates.waiting_chat_link)
    await call.answer()


@dp.message(AdminStates.waiting_chat_link)
async def process_chat_link(message: types.Message, state: FSMContext):
    await set_setting('chat_link', message.text)
    await message.answer("✅ Ссылка на чат обновлена")
    await state.clear()


@dp.callback_query(F.data == "change_min_withdrawal")
async def change_min_withdrawal(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.answer("Введите новую минимальную сумму для вывода:")
    await state.set_state(AdminStates.waiting_min_withdrawal)
    await call.answer()


@dp.message(AdminStates.waiting_min_withdrawal)
async def process_min_withdrawal(message: types.Message, state: FSMContext):
    try:
        min_amount = float(message.text)
        await set_setting('min_withdrawal', str(min_amount))
        await message.answer(f"✅ Минимальная сумма для вывода обновлена: {min_amount}$")
    except ValueError:
        await message.answer("❌ Введите корректное число")
    await state.clear()


@dp.callback_query(F.data == "change_currency")
async def change_currency(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.answer("Введите новую валюту (3-4 символа, например USD или TEST):")
    await state.set_state(AdminStates.waiting_currency)
    await call.answer()


@dp.message(AdminStates.waiting_currency)
async def process_currency(message: types.Message, state: FSMContext):
    currency = message.text.strip()
    if 3 <= len(currency) <= 4:
        await set_setting('currency', currency)
        await message.answer(f"✅ Валюта обновлена: {currency}")
    else:
        await message.answer("❌ Введите 3-4 символа для валюты")
    await state.clear()


@dp.callback_query(F.data == "change_flyer_key")
async def change_flyer_key(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    current_key = FLYER_API_KEY
    if current_key:
        key_info = f"\n\n📊 Текущий ключ: <code>{current_key[:8]}...{current_key[-4:]}</code>"
    else:
        key_info = "\n\n⚠️ Ключ не настроен"

    await call.message.answer(
        f"🔑 <b>Смена ключа Flyer API</b>{key_info}\n\n"
        "Введите новый ключ Flyer API:",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_flyer_key)
    await call.answer()


# ← ДОБАВЬ ЭТОТ КОД ЗДЕСЬ
@dp.message(AdminStates.waiting_flyer_key)
async def process_flyer_key(message: types.Message, state: FSMContext):
    global FLYER_API_KEY, flyer, flyer_enabled  # ✅ добавлено, чтобы обновить глобальные переменные

    new_key = message.text.strip()

    # Проверяем формат ключа
    if not new_key.startswith('FL-') or len(new_key) < 10:
        await message.answer(
            "❌ Неверный формат ключа Flyer API. Ключ должен начинаться с 'FL-' и быть длиннее 10 символов."
        )
        await state.clear()
        return

    FLYER_API_KEY = new_key

    try:
        flyer = Flyer(FLYER_API_KEY)
        flyer_enabled = True
        print(f"✅ Flyer переинициализирован с новым ключом: {FLYER_API_KEY[:8]}...")
    except Exception as e:
        flyer_enabled = False
        print(f"❌ Ошибка инициализации Flyer: {e}")
        await message.answer(f"❌ Ошибка инициализации Flyer: {e}")
        await state.clear()
        return

    # Тестируем новый ключ
    await message.answer("🔄 Тестируем новый ключ...")

    try:
        test_tasks = await flyer_get_tasks(message.from_user.id, 'ru', limit=1)

        if test_tasks is not None:
            if test_tasks:
                status_text = f"✅ Ключ работает! Получено {len(test_tasks)} заданий"
            else:
                status_text = "⚠️ Ключ работает, но заданий нет"
        else:
            status_text = "❌ Ключ не работает - ошибка получения заданий"

        await message.answer(
            f"🔑 <b>Ключ Flyer API успешно обновлен!</b>\n\n"
            f"{status_text}\n\n"
            f"📊 Новый ключ: <code>{FLYER_API_KEY[:8]}...{FLYER_API_KEY[-4:]}</code>",
            parse_mode='HTML'
        )

    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка тестирования ключа:</b>\n\n"
            f"{str(e)}\n\n"
            f"⚠️ Ключ сохранен, но требует проверки",
            parse_mode='HTML'
        )

    await state.clear()


@dp.callback_query(F.data == "admin_settings_back")
async def admin_settings_back(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔑 Настройки Flyer", callback_data="flyer_settings")
    keyboard.button(text="✏️ Сменить канал выплат", callback_data="change_payments_channel")
    keyboard.button(text="💬 Сменить чат", callback_data="change_chat")
    keyboard.button(text="💰 Мин. вывод", callback_data="change_min_withdrawal")
    keyboard.button(text="💵 Валюта", callback_data="change_currency")
    keyboard.button(text="📝 Управление заданиями", callback_data="manage_tasks")
    keyboard.button(text=f"💰 CryptoPay", callback_data="set_crypto_token")
    keyboard.button(text="💸 Настройки рефералов", callback_data="change_referral_settings")
    keyboard.adjust(2, 2, 2, 2)

    await call.message.edit_text("⚙️ <b>Настройки бота:</b>", reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


@dp.message(AdminStates.waiting_broadcast)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    # Сохраняем сообщение для рассылки
    media_data = None
    text_data = None
    media_type = None

    if message.photo:
        # Фото с текстом
        media_data = message.photo[-1].file_id
        media_type = 'photo'
        text_data = message.caption if message.caption else None
    elif message.video:
        # Видео с текстом
        media_data = message.video.file_id
        media_type = 'video'
        text_data = message.caption if message.caption else None
    elif message.animation:
        # GIF с текстом
        media_data = message.animation.file_id
        media_type = 'animation'
        text_data = message.caption if message.caption else None
    elif message.text:
        # Только текст
        text_data = message.html_text
        media_type = 'text'
    elif message.document:
        # Документ с текстом
        media_data = message.document.file_id
        media_type = 'document'
        text_data = message.caption if message.caption else None
    else:
        await message.answer("❌ Неподдерживаемый тип сообщения для рассылки")
        return

    # Сохраняем в состояние
    await state.update_data(
        broadcast_text=text_data,
        broadcast_media=media_data,
        broadcast_media_type=media_type,
        broadcast_buttons=[]  # пустой список для кнопок
    )

    # Формируем предпросмотр
    preview_text = "✅ <b>Сообщение для рассылки получено!</b>\n\n"

    if media_type == 'photo':
        preview_text += "📷 <b>Тип:</b> Фото с текстом\n"
    elif media_type == 'video':
        preview_text += "🎥 <b>Тип:</b> Видео с текстом\n"
    elif media_type == 'animation':
        preview_text += "🎬 <b>Тип:</b> GIF с текстом\n"
    elif media_type == 'document':
        preview_text += "📎 <b>Тип:</b> Документ с текстом\n"
    else:
        preview_text += "📝 <b>Тип:</b> Только текст\n"

    if text_data:
        preview_text += f"<b>Текст:</b>\n{text_data[:200]}{'...' if len(text_data) > 200 else ''}\n\n"

    preview_text += "<b>Доступные действия:</b>\n"
    preview_text += "• Добавить инлайн кнопки\n"
    preview_text += "• Начать рассылку сразу\n\n"
    preview_text += "<i>Кнопки добавляются по одной. Максимум 5 кнопок.</i>"

    # Предлагаем добавить кнопки
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Добавить кнопку", callback_data="broadcast_add_button")
    keyboard.button(text="🚀 Начать рассылку", callback_data="broadcast_start")
    keyboard.button(text="❌ Отмена", callback_data="broadcast_cancel")
    keyboard.adjust(1)

    # Сохраняем превью-сообщение отдельно, чтобы потом его редактировать
    preview_message = None

    if media_type == 'photo' and media_data:
        # Показываем предпросмотр фото с текстом
        preview_message = await message.answer_photo(
            media_data,
            caption=preview_text,
            reply_markup=keyboard.as_markup(),
            parse_mode='HTML'
        )
    elif media_type == 'video' and media_data:
        # Показываем предпросмотр видео с текстом
        preview_message = await message.answer_video(
            media_data,
            caption=preview_text,
            reply_markup=keyboard.as_markup(),
            parse_mode='HTML'
        )
    elif media_type == 'animation' and media_data:
        # Показываем предпросмотр GIF с текстом
        preview_message = await message.answer_animation(
            media_data,
            caption=preview_text,
            reply_markup=keyboard.as_markup(),
            parse_mode='HTML'
        )
    elif media_type == 'document' and media_data:
        # Показываем предпросмотр документа с текстом
        preview_message = await message.answer_document(
            media_data,
            caption=preview_text,
            reply_markup=keyboard.as_markup(),
            parse_mode='HTML'
        )
    else:
        # Только текст
        preview_message = await message.answer(
            preview_text,
            reply_markup=keyboard.as_markup(),
            parse_mode='HTML'
        )

    # Сохраняем ID превью-сообщения для дальнейшего редактирования
    await state.update_data(preview_message_id=preview_message.message_id)


def check_flyer_methods():
    if flyer:
        methods = [method for method in dir(flyer) if not method.startswith('_')]
        print(f"🔧 Доступные методы Flyer: {methods}")
    else:
        print("❌ Flyer не инициализирован")


async def check_completed_tasks():
    """Периодично проверяет выполненные задания на отписки - БЕЗОПАСНАЯ ВЕРСИЯ"""
    while True:
        try:
            if not flyer_enabled:
                print("❌ Flyer отключен - пропускаем проверку отписок")
                await asyncio.sleep(3600)
                continue

            print("=" * 60)
            print("🔍 ЗАПУСК ПРОВЕРКИ ОТПИСОК - БЕЗОПАСНАЯ ВЕРСИЯ")
            print("=" * 60)

            # Получаем пользователей с замороженными средствами и их транзакции
            async with aiosqlite.connect('bot_database.db') as db:
                async with db.execute('''
                    SELECT ft.id, ft.user_id, ft.amount, ft.task_type, ft.task_ref,
                           ft.frozen_at, ft.unfreeze_at, ft.is_unfrozen, ft.penalty_applied,
                           u.username
                    FROM frozen_transactions ft
                    JOIN users u ON ft.user_id = u.user_id
                    WHERE ft.is_unfrozen = FALSE
                    AND ft.task_type = 'flyer'
                    AND COALESCE(ft.penalty_applied, 0) = 0
                    AND ft.task_ref IS NOT NULL AND ft.task_ref != ''
                ''') as cursor:
                    transactions_to_check = await cursor.fetchall()

            print(f"🔍 Найдено Flyer-транзакций для проверки: {len(transactions_to_check)}")

            total_penalties = 0
            strict_unsubscribe_statuses = ["unsubscribed", "abort", "failed", "unsubscribe"]

            for tx_row in transactions_to_check:
                tx_id, user_id, amount, task_type, signature = tx_row[0], tx_row[1], tx_row[2], tx_row[3], tx_row[4]
                username = tx_row[9]

                print(f"\n👤 {username} (ID: {user_id}) tx={tx_id} signature={signature}")

                status = await flyer_check_task(signature, user_id)
                print(f"   📊 Статус Flyer API: {status}")

                if status not in strict_unsubscribe_statuses:
                    print(f"   ✅ Подписка активна")
                    continue

                print(f"   🚨 Отписка: {status} — штраф")
                penalty_row = (tx_id, user_id, amount, task_type, signature)
                await apply_penalty_for_transaction(penalty_row)
                await set_task_status(user_id, signature, status)
                total_penalties += 1
                await asyncio.sleep(1)

            print(f"📊 Проверка завершена. Штрафов: {total_penalties}")
            print("⏰ Следующая проверка через 1 час")
            await asyncio.sleep(3600)  # 1 час

        except Exception as e:
            print(f"❌ Ошибка в check_completed_tasks: {e}")
            await asyncio.sleep(900)  # 15 минут при ошибке


async def apply_penalty_for_transaction(tx_row):
    """
    tx_row: (id, user_id, amount, task_type, task_id, frozen_at, unfreeze_at, is_unfrozen, .)
    Штраф = сумма задания + 20%.
    """
    try:
        tx_id = tx_row[0]
        user_id = tx_row[1]
        amount = float(tx_row[2] or 0.0)
        task_type = tx_row[3]
        task_ref = tx_row[4]

        penalty_total = round(amount * 1.2, 6)
        extra_needed = round(penalty_total - amount, 6)

        async with aiosqlite.connect('bot_database.db') as db:
            # Получаем баланс
            async with db.execute('SELECT frozen_balance, balance FROM users WHERE user_id = ?', (user_id,)) as cur:
                row = await cur.fetchone()
                if not row:
                    print(f"⚠️ Не найден пользователь при штрафе: {user_id}")
                    frozen_balance = 0.0
                    balance = 0.0
                else:
                    frozen_balance = float(row[0] or 0.0)
                    balance = float(row[1] or 0.0)

            # 1️⃣ Снимаем замороженную часть
            frozen_to_deduct = min(frozen_balance, amount)
            if frozen_to_deduct > 0:
                await db.execute(
                    'UPDATE users SET frozen_balance = frozen_balance - ? WHERE user_id = ?',
                    (frozen_to_deduct, user_id)
                )

            # 2️⃣ Если замороженной суммы не хватило — добираем с обычного баланса
            remaining_uncovered = round(amount - frozen_to_deduct, 6)
            if remaining_uncovered > 0:
                await db.execute(
                    'UPDATE users SET balance = balance - ? WHERE user_id = ?',
                    (remaining_uncovered, user_id)
                )

            # 3️⃣ Дополнительный штраф 20%
            if extra_needed > 0:
                await db.execute(
                    'UPDATE users SET balance = balance - ? WHERE user_id = ?',
                    (extra_needed, user_id)
                )

            # 4️⃣ Обновляем транзакцию
            await db.execute(
                'UPDATE frozen_transactions SET is_unfrozen = TRUE, penalty_applied = 1, penalty_amount = ? WHERE id = ?',
                (penalty_total, tx_id)
            )

            # 5️⃣ История операций
            reason = f"Штраф за отписку/блокировку ({task_type}:{task_ref})"
            await db.execute(
                'INSERT INTO balance_history (user_id, amount, type, admin_id, reason) VALUES (?, ?, ?, ?, ?)',
                (user_id, -penalty_total, "penalty", None, reason)
            )

            await db.commit()

        # 💬 Уведомление пользователю
        try:
            await bot.send_message(
                user_id,
                f"❌ <b>Штраф за нарушение правил</b>\n\n"
                f"Мы заметили, что вы <b>отписались от канала</b> или <b>заблокировали бота</b> после выполнения задания.\n\n"
                f"💰 Сумма штрафа: <b>{penalty_total:.6f}$</b> (включая +20% к выплате).\n\n"
                f"⚠️ Не отписывайтесь от каналов в течение 3 дней после выполнения заданий!",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Пользователь {user_id} недоступен для уведомления: {e}")

        # 📢 Уведомление админам
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"🔔 Пользователь {user_id} получил штраф {penalty_total:.6f}$ за {task_type}:{task_ref}"
                )
            except:
                pass

    except Exception as e:
        print(f"❌ Ошибка apply_penalty_for_transaction: {e}")


@dp.callback_query(F.data == "users_back")
async def users_back(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await admin_users(call.message)
    await call.answer()


@dp.callback_query(F.data.startswith("back_to_user_"))
async def back_to_user(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    user_id = int(call.data.split("_")[3])
    user = await get_user(user_id)
    await call.answer()


async def create_custom_task(name, description, url, button_text, price, max_completions, created_by):
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('''
            INSERT INTO custom_tasks (name, description, url, button_text, price, max_completions, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, url, button_text, price, max_completions, created_by))
        await db.commit()
        return cursor.lastrowid


async def get_active_custom_tasks():
    """Получает активные кастомные задания"""
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('''
            SELECT * FROM custom_tasks 
            WHERE is_active = TRUE 
            AND (max_completions = 0 OR current_completions < max_completions)
            ORDER BY created_at DESC
        ''') as cursor:
            columns = [column[0] for column in cursor.description]
            return [dict(zip(columns, row)) for row in await cursor.fetchall()]


async def complete_custom_task(task_id, user_id):
    """Отмечает задание как выполненное и возвращает True при успехе"""
    async with aiosqlite.connect('bot_database.db') as db:
        # Проверяем не выполнял ли уже пользователь это задание
        async with db.execute('SELECT 1 FROM custom_task_completions WHERE task_id = ? AND user_id = ?',
                              (task_id, user_id)) as cursor:
            if await cursor.fetchone():
                print(f"⚠️ Пользователь {user_id} уже выполнял задание {task_id}")
                return False  # Уже выполнял

        # Добавляем запись о выполнении
        await db.execute('INSERT INTO custom_task_completions (task_id, user_id) VALUES (?, ?)', (task_id, user_id))

        # Увеличиваем счетчик выполнений
        await db.execute('UPDATE custom_tasks SET current_completions = current_completions + 1 WHERE id = ?',
                         (task_id,))

        await db.commit()
        print(f"✅ Задание {task_id} отмечено как выполненное для пользователя {user_id}")
        return True  # Успешно выполнено


async def get_custom_task_completions_count(task_id):
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT COUNT(*) FROM custom_task_completions WHERE task_id = ?', (task_id,)) as cursor:
            return (await cursor.fetchone())[0]


@dp.callback_query(F.data == "add_custom_task")
async def add_custom_task_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    print("🔧 Начало создания задания")
    await call.message.answer("📝 Введите название задания:")
    await state.set_state(AdminStates.waiting_task_name)
    await call.answer()


@dp.message(AdminStates.waiting_task_name)
async def process_task_name(message: types.Message, state: FSMContext):
    print(f"🔧 Получено название: {message.text}")
    await state.update_data(name=message.text, task_type='subscribe_channel')
    await message.answer("📄 Введите описание задания:")
    await state.set_state(AdminStates.waiting_task_description)


@dp.message(AdminStates.waiting_task_description)
async def process_task_description(message: types.Message, state: FSMContext):
    print(f"🔧 Получено описание: {message.text}")
    await state.update_data(description=message.text)
    await message.answer("🔗 Введите username канала (например: @channel_name):")
    await state.set_state(AdminStates.waiting_task_url)


@dp.message(AdminStates.waiting_task_url)
async def process_task_url(message: types.Message, state: FSMContext):
    print(f"🔧 Получен URL: {message.text}")
    data = await state.get_data()
    url = message.text

    # Формируем URL для канала
    if url.startswith('@'):
        channel_username = url[1:]
    else:
        channel_username = url.replace('@', '')

    url = f"https://t.me/{channel_username}"
    await state.update_data(url=url, channel_username=channel_username, button_text="Подписаться")

    await message.answer("💰 Введите цену за это задание (например: 0.015 или 1.0):")
    await state.set_state(AdminStates.waiting_custom_task_price)


@dp.message(AdminStates.waiting_custom_task_price)
async def process_custom_task_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return

        await state.update_data(price=price)
        await message.answer("👥 Введите максимальное количество выполнений (0 - без ограничений):")
        await state.set_state(AdminStates.waiting_task_max_completions)

    except ValueError:
        await message.answer("❌ Введите корректное число (например: 0.015 или 1.0)")


@dp.message(AdminStates.waiting_task_max_completions)
async def process_task_max_completions(message: types.Message, state: FSMContext):
    try:
        max_completions = int(message.text)
        data = await state.get_data()

        # Создаем задание
        task_id = await create_custom_task(
            name=data['name'],
            description=data['description'],
            url=data['url'],
            button_text=data['button_text'],
            price=data['price'],
            max_completions=max_completions,
            task_type=data.get('task_type', 'subscribe_channel'),
            channel_username=data.get('channel_username'),
            created_by=message.from_user.id
        )

        await message.answer(
            f"✅ <b>Задание создано!</b>\n\n"
            f"📝 Название: {data['name']}\n"
            f"💰 Цена: {data['price']}$\n"
            f"👥 Макс. выполнений: {max_completions if max_completions > 0 else 'без ограничений'}\n"
            f"🆔 ID задания: {task_id}\n\n"
            f"⚠️ <b>ВАЖНО!</b> Добавьте бота @{(await bot.get_me()).username} в администраторы канала {data.get('channel_username')}",
            parse_mode='HTML'
        )

        await state.clear()

        try:
            users = await get_all_users()
            notification_text = (
                f"🎉 <b>Появилось новое задание!</b>\n\n"
                f"➡️ Перейдите в раздел <b>\"📝 Задания\"</b> чтобы выполнить его!"
            )

            async def send_notification(user_id: int, delay: int):
                try:
                    await asyncio.sleep(delay)
                    await bot.send_message(user_id, notification_text, parse_mode='HTML')
                    await update_user_notification_time(user_id)
                except Exception as e:
                    print(f"❌ Ошибка уведомления пользователя {user_id}: {e}")

            # Створюємо задачі для всіх користувачів
            tasks = []
            for user in users:
                uid = user[0]
                tasks.append(asyncio.create_task(send_notification(uid, 0)))

            # Чекаємо завершення всіх задач, але не блокуємо адміна
            asyncio.create_task(asyncio.gather(*tasks))

            await message.answer("📢 Рассылка о новом задании запущена.", parse_mode='HTML')

        except Exception as e:
            await message.answer(f"⚠️ Ошибка при рассылке уведомлений: {e}")

    except ValueError:
        await message.answer("❌ Введите корректное число для максимальных выполнений.")


@dp.callback_query(F.data.startswith("check_custom_"))
async def check_custom_task(call: types.CallbackQuery):
    task_id = int(call.data.replace("check_custom_", ""))
    user_id = call.from_user.id

    try:
        # Получаем информацию о задании
        task = await get_custom_task(task_id)

        if not task:
            await call.answer("❌ Задание не найдено", show_alert=True)
            return

        # Проверяем не выполнял ли уже
        async with aiosqlite.connect('bot_database.db') as db:
            async with db.execute('SELECT 1 FROM custom_task_completions WHERE task_id = ? AND user_id = ?',
                                  (task_id, user_id)) as cursor:
                already_completed = await cursor.fetchone()

        if already_completed:
            await call.answer("❌ Вы уже выполняли это задание", show_alert=True)
            return

        # ПРОВЕРКА ВЫПОЛНЕНИЯ В ЗАВИСИМОСТИ ОТ ТИПА ЗАДАНИЯ
        if task['task_type'] == 'subscribe_channel' and task['channel_username']:
            # Проверяем подписку на канал
            await check_channel_subscription(task_id, user_id, task, call)
        else:
            # Для обычных ссылок - сразу начисляем награду
            await complete_and_reward(task_id, user_id, task, call)

    except Exception as e:
        print(f"❌ Ошибка проверки кастомного задания: {e}")
        await call.answer("❌ Ошибка при проверке", show_alert=True)

    await call.answer()


async def check_channel_subscription(task_id, user_id, task, call):
    """Проверяет подписку на канал"""
    try:
        channel_username = task['channel_username']

        # Проверяем подписку
        chat_member = await bot.get_chat_member(f"@{channel_username}", user_id)

        if chat_member.status in ['member', 'administrator', 'creator']:
            # Пользователь подписан - начисляем награду
            await complete_and_reward(task_id, user_id, task, call)
        else:
            await call.answer(
                f"❌ Вы не подписаны на канал @{channel_username}!\n\n"
                f"Подпишитесь и попробуйте снова.",
                show_alert=True
            )

    except Exception as e:
        print(f"❌ Ошибка проверки подписки: {e}")

        error_msg = str(e).lower()

        if "member list is inaccessible" in error_msg:
            await call.answer(
                f"🔒 <b>Ошибка прав доступа!</b>\n\n"
                f"Бот @{(await bot.get_me()).username} не имеет права 'Просмотр участников' в канале @{task['channel_username']}\n\n"
                f"📋 <b>Решение:</b>\n"
                f"1. Откройте настройки канала\n"
                f"2. Перейдите в 'Администраторы'\n"
                f"3. Найдите @{(await bot.get_me()).username}\n"
                f"4. Включите право <b>'Просмотр участников'</b>\n\n"
                f"⚠️ Без этого права проверка подписки невозможна",
                parse_mode='HTML',
                show_alert=True
            )
        elif "user not found" in error_msg or "chat not found" in error_msg:
            await call.answer(
                f"❌ Ошибка проверки подписки!\n\n"
                f"Бот не добавлен в администраторы канала @{task['channel_username']}\n"
                f"или канал не существует.",
                show_alert=True
            )
        else:
            await call.answer(
                f"❌ Ошибка проверки подписки!\n\n{str(e)}",
                show_alert=True
            )


async def complete_and_reward(task_id, user_id, task, call):
    """Начисляет награду за выполненное задание"""

    print(f"💰 Начинаем начисление награды за задание {task_id}")

    # ПРОВЕРЯЕМ не выполнял ли уже (правильная логика)
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT 1 FROM custom_task_completions WHERE task_id = ? AND user_id = ?',
                              (task_id, user_id)) as cursor:
            already_completed = await cursor.fetchone()

    if already_completed:
        print(f"❌ Пользователь {user_id} уже выполнял задание {task_id}")
        await call.answer("❌ Вы уже выполняли это задание", show_alert=True)
        return

    # Отмечаем как выполненное
    success = await complete_custom_task(task_id, user_id)
    if not success:
        print(f"❌ Ошибка при отметке задания {task_id} как выполненного")
        await call.answer("❌ Ошибка при отметке задания как выполненного", show_alert=True)
        return

    reward = task['price']
    print(f"💵 Награда: {reward}$")

    # Замораживаем средства
    await update_user_balance(user_id, frozen_amount=reward)
    await update_user_balance(user_id, completed_tasks=1)

    # Записываем транзакцию для автоматического размороживания
    await add_frozen_transaction(user_id, reward, 'custom_subscribe', task_id)

    print(f"✅ Награда {reward}$ заморожена для пользователя {user_id}")
    await call.answer(f"✅ Задание выполнено! Награда {reward}$ заморожена на 24 часов.", show_alert=True)

    # Удаляем сообщение
    try:
        await call.message.delete()
        print("✅ Сообщение с заданием удалено")
    except Exception as e:
        print(f"⚠️ Не удалось удалить сообщение: {e}")


@dp.message(AdminStates.waiting_custom_task_price)
async def process_custom_task_price(message: types.Message, state: FSMContext):
    """Обработчик для цены конкретного кастомного задания"""
    try:
        price = float(message.text)
        if price <= 0:
            await message.answer("❌ Цена должна быть больше 0")
            return

        # Сохраняем цену
        await state.update_data(price=price)

        # Запрашиваем максимальное количество выполнений
        await message.answer("👥 Введите максимальное количество выполнений (0 - без ограничений):")
        await state.set_state(AdminStates.waiting_task_max_completions)

    except ValueError:
        await message.answer("❌ Введите корректное число (например: 0.015 или 1.0)")


async def get_custom_task(task_id):
    """Получает информацию о кастомном задании"""
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT * FROM custom_tasks WHERE id = ?', (task_id,)) as cursor:
            columns = [column[0] for column in cursor.description]
            row = await cursor.fetchone()
            return dict(zip(columns, row)) if row else None


@dp.callback_query(F.data.startswith("view_task_"))
async def view_custom_task(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("view_task_", ""))

    # Получаем информацию о задании
    task = await get_custom_task(task_id)  # ← ДОБАВЬТЕ ЭТУ СТРОЧКУ

    if not task:
        await call.answer("❌ Задание не найдено")
        return

    # Получаем количество выполнений
    completions_count = await get_custom_task_completions_count(task_id)
    max_completions = task['max_completions'] if task['max_completions'] > 0 else '∞'

    text = (
        f"📝 <b>Информация о задании</b>\n\n"
        f"🆔 ID: <code>{task_id}</code>\n"
        f"📛 Название: {task['name']}\n"
        f"📄 Описание: {task.get('description', 'Нет описания')}\n"
        f"🔗 URL: {task['url']}\n"
        f"🔄 Текст кнопки: {task.get('button_text', 'Выполнить')}\n"
        f"💰 Цена: <b>{task['price']}$</b>\n"
        f"👥 Выполнений: <b>{completions_count}/{max_completions}</b>\n"
        f"📊 Статус: {'✅ Активно' if task['is_active'] else '❌ Неактивно'}\n"
        f"📅 Создано: {task['created_at'][:16]}"
    )

    keyboard = InlineKeyboardBuilder()

    # Кнопки управления
    if task['is_active']:
        keyboard.button(text="⏸️ Приостановить", callback_data=f"deactivate_task_{task_id}")
    else:
        keyboard.button(text="▶️ Активировать", callback_data=f"activate_task_{task_id}")

    keyboard.button(text="✏️ Редактировать", callback_data=f"edit_task_{task_id}")
    keyboard.button(text="🗑️ Удалить", callback_data=f"delete_task_{task_id}")
    keyboard.button(text="📊 Статистика", callback_data=f"task_stats_{task_id}")
    keyboard.button(text="🔙 Назад", callback_data="manage_tasks")

    keyboard.adjust(2, 2, 1, 1)

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


async def get_custom_task_completions_count(task_id):
    """Получает количество выполнений задания"""
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT COUNT(*) FROM custom_task_completions WHERE task_id = ?', (task_id,)) as cursor:
            return (await cursor.fetchone())[0]


@dp.callback_query(F.data.startswith("deactivate_task_"))
async def deactivate_task(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("deactivate_task_", ""))

    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('UPDATE custom_tasks SET is_active = FALSE WHERE id = ?', (task_id,))
        await db.commit()

    await call.answer("✅ Задание приостановлено")

    # Вместо изменения call.data, просто вызываем view_custom_task с новым callback
    await view_custom_task_handler(call, task_id)


@dp.callback_query(F.data.startswith("activate_task_"))
async def activate_task(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("activate_task_", ""))

    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('UPDATE custom_tasks SET is_active = TRUE WHERE id = ?', (task_id,))
        await db.commit()

    await call.answer("✅ Задание активировано")

    # Вместо изменения call.data, просто вызываем view_custom_task с новым callback
    await view_custom_task_handler(call, task_id)


async def view_custom_task_handler(call: types.CallbackQuery, task_id: int):
    """Вспомогательная функция для отображения задания"""
    task = await get_custom_task(task_id)

    if not task:
        await call.answer("❌ Задание не найдено")
        return

    # Получаем количество выполнений
    completions_count = await get_custom_task_completions_count(task_id)
    max_completions = task['max_completions'] if task['max_completions'] > 0 else '∞'

    text = (
        f"📝 <b>Информация о задании</b>\n\n"
        f"🆔 ID: <code>{task_id}</code>\n"
        f"📛 Название: {task['name']}\n"
        f"📄 Описание: {task.get('description', 'Нет описания')}\n"
        f"🔗 URL: {task['url']}\n"
        f"🔄 Текст кнопки: {task.get('button_text', 'Выполнить')}\n"
        f"💰 Цена: <b>{task['price']}$</b>\n"
        f"👥 Выполнений: <b>{completions_count}/{max_completions}</b>\n"
        f"📊 Статус: {'✅ Активно' if task['is_active'] else '❌ Неактивно'}\n"
        f"📅 Создано: {task['created_at'][:16]}"
    )

    keyboard = InlineKeyboardBuilder()

    # Кнопки управления
    if task['is_active']:
        keyboard.button(text="⏸️ Приостановить", callback_data=f"deactivate_task_{task_id}")
    else:
        keyboard.button(text="▶️ Активировать", callback_data=f"activate_task_{task_id}")

    keyboard.button(text="✏️ Редактировать", callback_data=f"edit_task_{task_id}")
    keyboard.button(text="🗑️ Удалить", callback_data=f"delete_task_{task_id}")
    keyboard.button(text="📊 Статистика", callback_data=f"task_stats_{task_id}")
    keyboard.button(text="🔙 Назад", callback_data="manage_tasks")

    keyboard.adjust(2, 2, 1, 1)

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')


@dp.callback_query(F.data.startswith("delete_task_"))
async def delete_task(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("delete_task_", ""))
    task = await get_custom_task(task_id)

    if not task:
        await call.answer("❌ Задание не найдено")
        return

    # Создаем клавиатуру для подтверждения удаления
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Да, удалить", callback_data=f"confirm_delete_{task_id}")
    keyboard.button(text="❌ Отмена", callback_data=f"view_task_{task_id}")
    keyboard.adjust(2)

    await call.message.edit_text(
        f"🗑️ <b>Подтверждение удаления</b>\n\n"
        f"Вы уверены, что хотите удалить задание?\n\n"
        f"📝 <b>{task['name']}</b>\n"
        f"💰 Цена: {task['price']}$\n"
        f"👥 Выполнений: {task['current_completions']}\n\n"
        f"<i>Это действие нельзя отменить!</i>",
        reply_markup=keyboard.as_markup(),
        parse_mode='HTML'
    )
    await call.answer()


@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_task(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("confirm_delete_", ""))
    task = await get_custom_task(task_id)

    if not task:
        await call.answer("❌ Задание не найдено")
        return

    try:
        async with aiosqlite.connect('bot_database.db') as db:
            # Удаляем задание и связанные записи о выполнениях
            await db.execute('DELETE FROM custom_tasks WHERE id = ?', (task_id,))
            await db.execute('DELETE FROM custom_task_completions WHERE task_id = ?', (task_id,))
            await db.commit()

        await call.answer("✅ Задание успешно удалено")

        # Возвращаемся к управлению заданиями через прямой вызов
        await manage_tasks(call)

    except Exception as e:
        print(f"❌ Ошибка при удалении задания: {e}")
        await call.answer("❌ Ошибка при удалении задания", show_alert=True)


@dp.callback_query(F.data.startswith("cancel_delete_"))
async def cancel_delete_task(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("cancel_delete_", ""))

    # Возвращаемся к просмотру задания
    from aiogram.types import CallbackQuery
    new_call = CallbackQuery(
        id=call.id,
        from_user=call.from_user,
        chat_instance=call.chat_instance,
        message=call.message,
        data=f"view_task_{task_id}"
    )
    await view_custom_task(new_call)
    await call.answer("❌ Удаление отменено")


@dp.callback_query(F.data.startswith("edit_task_"))
async def edit_task_start(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("edit_task_", ""))

    # Показываем меню редактирования вместо ошибки
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✏️ Изменить название", callback_data=f"edit_name_{task_id}")
    keyboard.button(text="📝 Изменить описание", callback_data=f"edit_desc_{task_id}")
    keyboard.button(text="💰 Изменить цену", callback_data=f"edit_price_{task_id}")
    keyboard.button(text="👥 Изменить лимит выполнений", callback_data=f"edit_limit_{task_id}")
    keyboard.button(text="🔗 Изменить URL", callback_data=f"edit_url_{task_id}")
    keyboard.button(text="🔄 Изменить текст кнопки", callback_data=f"edit_button_{task_id}")
    keyboard.button(text="🔙 Назад", callback_data=f"view_task_{task_id}")
    keyboard.adjust(2, 2, 1, 1)

    await call.message.edit_text(
        f"✏️ <b>Редактирование задания #{task_id}</b>\n\n"
        f"Выберите что хотите изменить:",
        reply_markup=keyboard.as_markup(),
        parse_mode='HTML'
    )
    await call.answer()


async def create_custom_task(name, description, url, button_text, price, max_completions, task_type='subscribe_channel',
                             channel_username=None, created_by=None):
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('''
            INSERT INTO custom_tasks (name, description, url, button_text, price, max_completions, task_type, channel_username, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, description, url, button_text, price, max_completions, task_type, channel_username, created_by))
        await db.commit()
        return cursor.lastrowid


async def update_db_structure():
    """Обновляет структуру базы данных при необходимости"""
    async with aiosqlite.connect('bot_database.db') as db:
        # ПЕРВОЕ: Проверяем таблицу users на наличие referrer_id (для реферальной системы)
        async with db.execute("PRAGMA table_info(users)") as cursor:
            user_columns = [column[1] for column in await cursor.fetchall()]

        if 'referrer_id' not in user_columns:
            await db.execute('ALTER TABLE users ADD COLUMN referrer_id INTEGER')
            print("✅ Добавлена колонка referrer_id в users (для реферальной системы)")
        else:
            print("✅ Колонка referrer_id уже существует в users")

        # ВТОРОЕ: Проверяем таблицу custom_tasks
        async with db.execute("PRAGMA table_info(custom_tasks)") as cursor:
            task_columns = [column[1] for column in await cursor.fetchall()]

        if 'task_type' not in task_columns:
            await db.execute('ALTER TABLE custom_tasks ADD COLUMN task_type TEXT DEFAULT "url"')
            print("✅ Добавлена колонка task_type в custom_tasks")

        if 'channel_username' not in task_columns:
            await db.execute('ALTER TABLE custom_tasks ADD COLUMN channel_username TEXT')
            print("✅ Добавлена колонка channel_username в custom_tasks")

        await db.commit()
        print("✅ Структура базы данных успешно обновлена")


@dp.callback_query(F.data.startswith("task_stats_"))
async def task_stats_detail(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("task_stats_", ""))
    task = await get_custom_task(task_id)

    if not task:
        await call.answer("❌ Задание не найдено")
        return

    # Получаем детальную статистику выполнения
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('''
            SELECT u.user_id, u.username, ctc.completed_at 
            FROM custom_task_completions ctc 
            JOIN users u ON ctc.user_id = u.user_id 
            WHERE ctc.task_id = ? 
            ORDER BY ctc.completed_at DESC
        ''', (task_id,)) as cursor:
            completions = await cursor.fetchall()

    # Получаем общее количество выполнений
    total_completions = await get_custom_task_completions_count(task_id)

    text = (
        f"📊 <b>Статистика задания:</b> {task['name']}\n\n"
        f"🆔 ID задания: <code>{task_id}</code>\n"
        f"💰 Цена: {task['price']}$\n"
        f"👥 Всего выполнений: <b>{total_completions}</b>\n"
        f"🎯 Макс. выполнений: {task['max_completions'] if task['max_completions'] > 0 else '∞'}\n\n"
    )

    if completions:
        text += "<b>Последние выполнения:</b>\n"
        for i, completion in enumerate(completions[:15], 1):  # Показываем последние 15
            user_id, username, completed_at = completion
            text += f"{i}. ID: <code>{user_id}</code> | @{username} | {completed_at[:16]}\n"

        if len(completions) > 15:
            text += f"\n... и еще {len(completions) - 15} выполнений"
    else:
        text += "❌ Выполнений еще нет"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад к заданию", callback_data=f"view_task_{task_id}")

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


@dp.callback_query(F.data == "tasks_stats")
async def tasks_overall_stats(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    # Получаем общую статистику по всем заданиям
    async with aiosqlite.connect('bot_database.db') as db:
        # Общее количество заданий
        async with db.execute('SELECT COUNT(*) FROM custom_tasks') as cursor:
            total_tasks = (await cursor.fetchone())[0]

        # Активные задания
        async with db.execute('SELECT COUNT(*) FROM custom_tasks WHERE is_active = TRUE') as cursor:
            active_tasks = (await cursor.fetchone())[0]

        # Общее количество выполнений
        async with db.execute('SELECT COUNT(*) FROM custom_task_completions') as cursor:
            total_completions = (await cursor.fetchone())[0]

        # Общая сумма выплат за задания
        async with db.execute('''
            SELECT SUM(ct.price) 
            FROM custom_task_completions ctc 
            JOIN custom_tasks ct ON ctc.task_id = ct.id
        ''') as cursor:
            total_payout = (await cursor.fetchone())[0] or 0

        # Самые популярные задания
        async with db.execute('''
            SELECT ct.id, ct.name, COUNT(ctc.task_id) as completions
            FROM custom_tasks ct 
            LEFT JOIN custom_task_completions ctc ON ct.id = ctc.task_id
            GROUP BY ct.id 
            ORDER BY completions DESC 
            LIMIT 5
        ''') as cursor:
            popular_tasks = await cursor.fetchall()

    text = (
        "📊 <b>Общая статистика заданий</b>\n\n"
        f"📝 Всего заданий: <b>{total_tasks}</b>\n"
        f"✅ Активных заданий: <b>{active_tasks}</b>\n"
        f"👥 Всего выполнений: <b>{total_completions}</b>\n"
        f"💰 Общая сумма выплат: <b>{total_payout:.3f}$</b>\n\n"
    )

    if popular_tasks:
        text += "<b>🏆 Самые популярные задания:</b>\n"
        for i, (task_id, task_name, completions) in enumerate(popular_tasks, 1):
            text += f"{i}. {task_name[:20]}... - <b>{completions}</b> выполнений\n"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="manage_tasks")

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')
    await call.answer()


# Обработчики для каждого типа редактирования
@dp.callback_query(F.data.startswith("edit_name_"))
async def edit_name_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("edit_name_", ""))
    task = await get_custom_task(task_id)

    await state.update_data(edit_task_id=task_id, edit_field='name')
    await call.message.answer(f"✏️ Введите новое название задания:\n\nТекущее: {task['name']}")
    await state.set_state(AdminStates.waiting_edit_value)
    await call.answer()


@dp.callback_query(F.data.startswith("edit_desc_"))
async def edit_desc_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("edit_desc_", ""))
    task = await get_custom_task(task_id)

    await state.update_data(edit_task_id=task_id, edit_field='description')
    await call.message.answer(
        f"📝 Введите новое описание задания:\n\nТекущее: {task.get('description', 'Нет описания')}")
    await state.set_state(AdminStates.waiting_edit_value)
    await call.answer()


@dp.callback_query(F.data.startswith("edit_price_"))
async def edit_price_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("edit_price_", ""))
    task = await get_custom_task(task_id)

    await state.update_data(edit_task_id=task_id, edit_field='price')
    await call.message.answer(f"💰 Введите новую цену задания:\n\nТекущая: {task['price']}$")
    await state.set_state(AdminStates.waiting_edit_value)
    await call.answer()


@dp.callback_query(F.data.startswith("edit_limit_"))
async def edit_limit_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("edit_limit_", ""))
    task = await get_custom_task(task_id)

    await state.update_data(edit_task_id=task_id, edit_field='max_completions')
    max_completions = task['max_completions'] if task['max_completions'] > 0 else 'без ограничений'
    await call.message.answer(
        f"👥 Введите новое максимальное количество выполнений (0 - без ограничений):\n\nТекущее: {max_completions}")
    await state.set_state(AdminStates.waiting_edit_value)
    await call.answer()


@dp.callback_query(F.data.startswith("edit_url_"))
async def edit_url_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("edit_url_", ""))
    task = await get_custom_task(task_id)

    await state.update_data(edit_task_id=task_id, edit_field='url')
    await call.message.answer(f"🔗 Введите новый URL задания:\n\nТекущий: {task['url']}")
    await state.set_state(AdminStates.waiting_edit_value)
    await call.answer()


@dp.callback_query(F.data.startswith("edit_button_"))
async def edit_button_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return

    task_id = int(call.data.replace("edit_button_", ""))
    task = await get_custom_task(task_id)

    await state.update_data(edit_task_id=task_id, edit_field='button_text')
    await call.message.answer(f"🔄 Введите новый текст кнопки:\n\nТекущий: {task.get('button_text', 'Выполнить')}")
    await state.set_state(AdminStates.waiting_edit_value)
    await call.answer()


# Общий обработчик для всех изменений
@dp.message(AdminStates.waiting_edit_value)
async def process_edit_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task_id = data['edit_task_id']
    field = data['edit_field']
    new_value = message.text.strip()

    try:
        async with aiosqlite.connect('bot_database.db') as db:
            if field == 'name':
                await db.execute('UPDATE custom_tasks SET name = ? WHERE id = ?', (new_value, task_id))
                field_name = "название"

            elif field == 'description':
                await db.execute('UPDATE custom_tasks SET description = ? WHERE id = ?', (new_value, task_id))
                field_name = "описание"

            elif field == 'price':
                new_price = float(new_value)
                if new_price <= 0:
                    await message.answer("❌ Цена должна быть больше 0")
                    return
                await db.execute('UPDATE custom_tasks SET price = ? WHERE id = ?', (new_price, task_id))
                field_name = "цена"

            elif field == 'max_completions':
                new_limit = int(new_value)
                if new_limit < 0:
                    await message.answer("❌ Количество выполнений не может быть отрицательным")
                    return
                await db.execute('UPDATE custom_tasks SET max_completions = ? WHERE id = ?', (new_limit, task_id))
                field_name = "лимит выполнений"

            elif field == 'url':
                await db.execute('UPDATE custom_tasks SET url = ? WHERE id = ?', (new_value, task_id))
                field_name = "URL"

            elif field == 'button_text':
                await db.execute('UPDATE custom_tasks SET button_text = ? WHERE id = ?', (new_value, task_id))
                field_name = "текст кнопки"

            await db.commit()

        await message.answer(f"✅ {field_name} успешно обновлен!")

        # Создаем кнопку для возврата к заданию
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📝 Посмотреть задание", callback_data=f"view_task_{task_id}")
        keyboard.button(text="⚙️ Управление заданиями", callback_data="manage_tasks")
        keyboard.adjust(1)

        await message.answer("Выберите действие:", reply_markup=keyboard.as_markup())

    except ValueError as e:
        if field == 'price':
            await message.answer("❌ Введите корректное число для цены (например: 0.015 или 1.0)")
        elif field == 'max_completions':
            await message.answer("❌ Введите корректное число для лимита выполнений")
        else:
            await message.answer(f"❌ Ошибка при обновлении: {e}")
    except Exception as e:
        await message.answer(f"❌ Ошибка при обновлении: {e}")

    await state.clear()


async def add_frozen_transaction(user_id, amount, task_type, task_id=None, task_ref=None):
    """Добавляет запись о замороженных средствах. task_ref — signature Flyer (строка)."""
    numeric_task_id = None
    ref = task_ref
    if ref is None and isinstance(task_id, str):
        ref = task_id
    elif isinstance(task_id, int):
        numeric_task_id = task_id
    elif task_id is not None and not isinstance(task_id, str):
        try:
            numeric_task_id = int(task_id)
        except (TypeError, ValueError):
            ref = str(task_id)

    try:
        async with aiosqlite.connect('bot_database.db') as db:
            try:
                await db.execute("ALTER TABLE frozen_transactions ADD COLUMN task_ref TEXT")
            except Exception:
                pass
            await db.execute(
                '''INSERT INTO frozen_transactions 
                   (user_id, amount, task_type, task_id, task_ref, unfreeze_at) 
                   VALUES (?, ?, ?, ?, ?, datetime("now", "+24 hours"))''',
                (user_id, amount, task_type, numeric_task_id, ref)
            )
            await db.commit()
            print(f"✅ Записана замороженная транзакция: {user_id} - {amount}$ - {task_type} ref={ref}")
    except Exception as e:
        print(f"❌ Ошибка записи замороженной транзакции: {e}")


async def auto_unfreeze_balances():
    """Автоматически размораживает средства через 24 часов"""
    while True:
        try:
            print("🔍 Проверяем средства для разморозки...")

            async with aiosqlite.connect('bot_database.db') as db:
                # Находим транзакции, которые нужно разморозить
                async with db.execute('''
                    SELECT ft.id, ft.user_id, ft.amount, u.username 
                    FROM frozen_transactions ft
                    JOIN users u ON ft.user_id = u.user_id
                    WHERE ft.unfreeze_at <= datetime('now') 
                    AND ft.is_unfrozen = FALSE
                ''') as cursor:
                    transactions_to_unfreeze = await cursor.fetchall()

                unfrozen_count = 0
                total_amount = 0

                for transaction in transactions_to_unfreeze:
                    transaction_id, user_id, amount, username = transaction

                    try:
                        # Перемещаем средства из frozen_balance в balance
                        await db.execute(
                            'UPDATE users SET frozen_balance = frozen_balance - ?, balance = balance + ? WHERE user_id = ?',
                            (amount, amount, user_id)
                        )

                        # Помечаем транзакцию как размороженную
                        await db.execute(
                            'UPDATE frozen_transactions SET is_unfrozen = TRUE WHERE id = ?',
                            (transaction_id,)
                        )

                        unfrozen_count += 1
                        total_amount += amount

                        print(f"✅ Разморожено {amount}$ для пользователя {username} (ID: {user_id})")

                    except Exception as e:
                        print(f"❌ Ошибка разморозки для пользователя {user_id}: {e}")

                if unfrozen_count > 0:
                    await db.commit()
                    print(f"✅ Всего разморожено {unfrozen_count} транзакций на сумму {total_amount:.3f}$")
                else:
                    print("ℹ️ Нет транзакций для разморозки")

            # Проверяем каждые 30 минут
            await asyncio.sleep(1800)

        except Exception as e:
            print(f"❌ Ошибка в auto_unfreeze_balances: {e}")
            await asyncio.sleep(300)


@dp.callback_query(F.data == "check_all_tasks")
async def check_all_tasks(call: types.CallbackQuery):
    user_id = call.from_user.id

    await call.answer("🔍 Начинаем проверку всех заданий...")

    try:
        completed_tasks = 0
        total_reward = 0

        # Получаем ВСЕ задания заново
        flyer_tasks = await flyer_get_tasks(user_id, 'ru', limit=20)
        custom_tasks = await get_active_custom_tasks()

        print(f"🔍 Получено Flyer заданий: {len(flyer_tasks)}")

        # Проверяем Flyer задания - САМОСТОЯТЕЛЬНАЯ ПРОВЕРКА ПОДПИСКИ
        # Проверяем Flyer задания - ПРОСТАЯ ЛОГИКА
        if flyer_tasks:
            for task in flyer_tasks:
                signature = task.get('signature', '')
                task_name = task.get('name', 'Unknown')

                if signature:
                    print(f"🔍 Проверяем Flyer задание: {task_name}")

                    # ПРОВЕРЯЕМ ЧЕРЕЗ FLYER STATUS
                    status = await flyer_check_task(signature, user_id)
                    print(f"🔍 Flyer статус: {status}")

                    # ЕСЛИ СТАТУС НЕ "INCOMPLETE" - ЗАДАНИЕ ВЫПОЛНЕНО
                    if status != "incomplete":
                        print(f"✅ Задание выполнено! Статус: {status}")

                        # Проверяем не начисляли ли уже
                        saved_status = await get_task_status(user_id, signature)
                        if saved_status not in ['completed', 'done', 'complete']:
                            completed_tasks += 1
                            reward = FLZAD
                            total_reward += reward

                            # Начисляем средства
                            await update_user_balance(user_id, frozen_amount=reward)
                            await update_user_balance(user_id, completed_tasks=1)
                            await set_task_status(user_id, signature, "completed")
                            await add_frozen_transaction(user_id, reward, 'flyer', signature)

                            print(f"✅ Начислено {reward}$ за задание: {task_name}")
                        else:
                            print(f"⚠️ Задание уже было начислено ранее: {task_name}")
                    else:
                        print(f"❌ Задание еще не выполнено: {task_name}")

        # Проверка кастомных заданий
        if custom_tasks:
            for task in custom_tasks:
                if task['task_type'] == 'subscribe_channel' and task['channel_username']:
                    try:
                        print(f"🔍 Проверяем кастомное задание: {task['name']}")

                        chat_member = await bot.get_chat_member(f"@{task['channel_username']}", user_id)

                        if chat_member.status in ['member', 'administrator', 'creator']:
                            async with aiosqlite.connect('bot_database.db') as db:
                                async with db.execute(
                                        'SELECT 1 FROM custom_task_completions WHERE task_id = ? AND user_id = ?',
                                        (task['id'], user_id)) as cursor:
                                    has_completed = await cursor.fetchone()

                            if not has_completed:
                                completed_tasks += 1
                                reward = task['price']
                                total_reward += reward

                                await complete_custom_task(task['id'], user_id)
                                await update_user_balance(user_id, frozen_amount=reward)
                                await update_user_balance(user_id, completed_tasks=1)
                                await add_frozen_transaction(user_id, reward, 'custom_subscribe', task['id'])

                                print(f"✅ Кастомное задание выполнено: {task['name']}")

                    except Exception as e:
                        print(f"❌ Ошибка проверки кастомного задания: {e}")

        # Результат
        if completed_tasks > 0:
            asyncio.create_task(show_ad_at_opportunity(user_id, "after_task"))
            result_text = (
                f"✅ <b>Проверка завершена!</b>\n\n"
                f"📊 Выполнено заданий: <b>{completed_tasks}</b>\n"
                f"💰 Начислено: <b>{total_reward:.3f}$</b>\n\n"
                f"💸 Средства заморожены на 24 часов"
            )

            await call.message.edit_text(result_text, parse_mode='HTML')
            await call.answer(f"✅ Выполнено: {completed_tasks} заданий\n💰 Начислено: {total_reward:.3f}$",
                              show_alert=True)

        else:
            await call.answer("❌ Ни одно задание еще не выполнено", show_alert=True)

    except Exception as e:
        print(f"❌ Ошибка проверки всех заданий: {e}")
        await call.answer("❌ Ошибка при проверке заданий", show_alert=True)


async def notify_admins_about_withdrawal(withdrawal_id, amount, username, receipt_url):
    """Отправляет отчет админам о выводе с защитой от дублирования"""
    global last_withdrawal_notification

    # Добавляем получение текущего времени
    current_time = time.time()

    # Проверяем, не отправляли ли мы уже уведомление для этого withdrawal_id в последние 10 секунд
    if (withdrawal_id in last_withdrawal_notification and
            current_time - last_withdrawal_notification[withdrawal_id] < 10):
        print(f"⚠️ Пропускаем дублирующее уведомление для вывода {withdrawal_id}")
        return

    # Используем реальный баланс кошелька
    total_balance = await get_crypto_bot_balance()

    # Определяем статус резерва
    if total_balance < 1:
        reserve_status = "🚨 КРИТИЧЕСКИ НИЗКИЙ"
        reserve_emoji = "🔴"
    elif total_balance < 10:
        reserve_status = "⚠️ НИЗКИЙ"
        reserve_emoji = "🟡"
    elif total_balance < 50:
        reserve_status = "ℹ️ СРЕДНИЙ"
        reserve_emoji = "🟢"
    else:
        reserve_status = "✅ ДОСТАТОЧНЫЙ"
        reserve_emoji = "💚"

    # Создаем сообщение для админа
    admin_message = f"""
📊 <b>АВТОМАТИЧЕСКИЙ ВЫВОД СРЕДСТВ</b>

👤 <b>Пользователь:</b> @{username or 'нет'}
🔹 <b>ID вывода:</b> <code>{withdrawal_id}</code>
💵 <b>Сумма:</b> <code>{amount:.3f}$</code>
📎 <b>Чек:</b> {receipt_url}

💰 <b>БАЛАНС КОШЕЛЬКА:</b>
├─ Доступно: <b>{total_balance:.2f} USDT</b>
└─ Статус: {reserve_emoji} <b>{reserve_status}</b>

⏰ <i>{datetime.now().strftime('%d.%m.%Y %H:%M')}</i>
"""

    # Отправляем сообщение всем админам
    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_message, parse_mode='HTML')
            sent_count += 1
        except Exception as e:
            print(f"❌ Не удалось уведомить админа {admin_id}: {e}")

    # Сохраняем время отправки
    last_withdrawal_notification[withdrawal_id] = current_time
    print(f"📨 Отчет о выводе {withdrawal_id} отправлен {sent_count} админам")


async def send_private_message_to_user(user_id, message):
    """Отправляет приватное сообщение пользователю"""
    try:
        await bot.send_message(
            user_id,
            message,
            parse_mode='HTML'
        )
        print(f"📩 [PRIVATE] Сообщение отправлено пользователю {user_id}")
    except Exception as e:
        print(f"❌ Не удалось отправить сообщение пользователю {user_id}: {e}")


async def get_total_system_balance():
    """Получает общий баланс системы"""
    async with aiosqlite.connect('bot_database.db') as db:
        async with db.execute('SELECT SUM(balance) + SUM(frozen_balance) FROM users') as cursor:
            result = await cursor.fetchone()
            return result[0] or 0


async def get_crypto_bot_balance():
    """Получает реальный баланс кошелька Crypto Bot"""
    try:
        headers = {
            "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
            "Content-Type": "application/json"
        }

        endpoint = "https://pay.crypt.bot/api/getBalance"

        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, headers=headers, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get('ok'):
                        balances = data['result']
                        usdt_balance = 0.0

                        # Ищем баланс USDT - используем currency_code вместо asset_code
                        for balance in balances:
                            currency_code = balance.get('currency_code')
                            available = balance.get('available', 0)

                            if currency_code == 'USDT':
                                usdt_balance = float(available)  # Уже в нормальных единицах!
                                break

                        print(f"💰 Реальный баланс кошелька: {usdt_balance} USDT")
                        return usdt_balance
                    else:
                        error_msg = data.get('error', {}).get('name', 'Unknown error')
                        print(f"❌ Ошибка получения баланса: {error_msg}")
                        return 0.0
                else:
                    print(f"❌ HTTP ошибка: {response.status}")
                    return 0.0

    except Exception as e:
        print(f"❌ Ошибка получения баланса кошелька: {e}")
        return 0.0


async def generate_crypto_receipt(amount, user_id):
    """Создает чек на ВЫВОД средств"""
    try:
        if amount <= 0:
            return False, None

        payload = {
            "asset": "USDT",
            "amount": str(amount),
            "description": f"Чек на вывод {amount} USDT",
        }

        headers = {
            "Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN,
            "Content-Type": "application/json"
        }

        endpoint = "https://pay.crypt.bot/api/createCheck"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=30
            ) as response:

                if response.status == 200:
                    data = await response.json()

                    if data.get('ok'):
                        check_url = data['result']['bot_check_url']
                        return True, check_url  # ✔ успіх
                    else:
                        return False, None  # ❌ API error
                else:
                    return False, None  # ❌ HTTP error

    except Exception:
        return False, None


async def check_and_pay_referral_bonus(user_id: int):
    """Перевіряє та виплачує реферальні бонуси ПРИ ДОСЯГНЕННІ потрібної кількості завдань"""
    try:
        user = await get_user(user_id)
        referrer_id = user.get('referrer_id')

        if not referrer_id:
            return

        # Отримуємо налаштування
        bonus_lvl1 = float(await get_setting('ref_bonus_level1') or 0.05)
        bonus_lvl2 = float(await get_setting('ref_bonus_level2') or 0.03)
        tasks_lvl1 = int(await get_setting('ref_tasks_required_level1') or 3)
        tasks_lvl2 = int(await get_setting('ref_tasks_required_level2') or 5)

        print(f"🔍 Проверка реф. бонусов для {user_id}: {user['completed_tasks']} заданий")
        print(f"  ref_paid_level1: {user.get('ref_paid_level1', 0)}")
        print(f"  ref_paid_level2: {user.get('ref_paid_level2', 0)}")

        # ✅ 1 РІВЕНЬ - виплачуємо ТІЛЬКИ КОЛИ досягаємо tasks_lvl1 І ще не платили
        if (user['completed_tasks'] >= tasks_lvl1 and
                not user.get('ref_paid_level1', 0) and
                not user.get('ref_paid_in_progress_lvl1', 0)):

            print(f"🎯 Умова 1 уровня выполнена! Доступно {user['completed_tasks']}/{tasks_lvl1}")

            # Захисник від повторної виплати
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute(
                    'UPDATE users SET ref_paid_in_progress_lvl1 = 1 WHERE user_id = ?',
                    (user_id,)
                )
                await db.commit()

            # Виплачуємо бонус реферу
            await update_user_balance(referrer_id, amount=bonus_lvl1)

            # Помічаємо як виплачено
            async with aiosqlite.connect('bot_database.db') as db:
                await db.execute(
                    'UPDATE users SET ref_paid_level1 = 1 WHERE user_id = ?',
                    (user_id,)
                )
                await db.execute(
                    'UPDATE users SET ref_paid_in_progress_lvl1 = 0 WHERE user_id = ?',
                    (user_id,)
                )

                # Запис в історію
                await db.execute(
                    'INSERT INTO balance_history (user_id, amount, type, reason) VALUES (?, ?, ?, ?)',
                    (referrer_id, bonus_lvl1, 'referral_bonus',
                     f'Реферальный бонус 1 уровня за пользователя {user_id} ({tasks_lvl1} заданий)')
                )
                await db.commit()

            # Повідомляємо рефера
            try:
                await bot.send_message(
                    referrer_id,
                    f"🎉 <b>Реферальный бонус 1 уровня!</b>\n\n"
                    f"👤 Ваш реферал выполнил {tasks_lvl1} заданий\n"
                    f"💰 Вы получили: <b>{bonus_lvl1}$</b>\n\n"
                    f"👥 Приглашайте больше друзей!",
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"⚠️ Не удалось уведомить реферала 1 уровня: {e}")

            print(f"✅ Выплачен бонус 1 уровня: {referrer_id} +{bonus_lvl1}$ за реферала {user_id}")

        # ✅ 2 РІВЕНЬ - аналогічно
        if referrer_id:
            referrer = await get_user(referrer_id)
            referrer_lvl2_id = referrer.get('referrer_id')

            if (referrer_lvl2_id and
                    user['completed_tasks'] >= tasks_lvl2 and
                    not user.get('ref_paid_level2', 0) and
                    not user.get('ref_paid_in_progress_lvl2', 0)):

                print(f"🎯 Умова 2 уровня выполнена! Доступно {user['completed_tasks']}/{tasks_lvl2}")

                # Захисник від повторної виплати
                async with aiosqlite.connect('bot_database.db') as db:
                    await db.execute(
                        'UPDATE users SET ref_paid_in_progress_lvl2 = 1 WHERE user_id = ?',
                        (user_id,)
                    )
                    await db.commit()

                # Виплачуємо бонус реферу 2 рівня
                await update_user_balance(referrer_lvl2_id, amount=bonus_lvl2)

                # Помічаємо як виплачено
                async with aiosqlite.connect('bot_database.db') as db:
                    await db.execute(
                        'UPDATE users SET ref_paid_level2 = 1 WHERE user_id = ?',
                        (user_id,)
                    )
                    await db.execute(
                        'UPDATE users SET ref_paid_in_progress_lvl2 = 0 WHERE user_id = ?',
                        (user_id,)
                    )

                    # Запис в історію
                    await db.execute(
                        'INSERT INTO balance_history (user_id, amount, type, reason) VALUES (?, ?, ?, ?)',
                        (referrer_lvl2_id, bonus_lvl2, 'referral_bonus',
                         f'Реферальный бонус 2 уровня за пользователя {user_id} ({tasks_lvl2} заданий)')
                    )
                    await db.commit()

                # Повідомляємо рефера 2 рівня
                try:
                    await bot.send_message(
                        referrer_lvl2_id,
                        f"🎉 <b>Реферальный бонус 2 уровня!</b>\n\n"
                        f"👤 Реферал вашего реферала выполнил {tasks_lvl2} заданий\n"
                        f"💰 Вы получили: <b>{bonus_lvl2}$</b>\n\n"
                        f"👥 Приглашайте больше друзей!",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    print(f"⚠️ Не удалось уведомить реферала 2 уровня: {e}")

                print(f"✅ Выплачен бонус 2 уровня: {referrer_lvl2_id} +{bonus_lvl2}$ за реферала {user_id}")

    except Exception as e:
        print(f"❌ Ошибка проверки реферальных бонусов: {e}")


async def check_unsubscribed_penalties():
    while True:
        try:
            # Текущая ставка выплаты из настроек
            current_reward = float(await get_setting("user_task_reward") or 0.015)

            async with aiosqlite.connect("bot_database.db") as db:
                db.row_factory = aiosqlite.Row
                # ДОБАВЛЯЄМО ПЕРЕВІРКУ ТИПУ ЗАВДАННЯ - лише канали
                completed_rows = await db.execute_fetchall("""
                    SELECT utc.task_id, utc.user_id, utc.completed_at, ut.channel_username, ut.task_type
                    FROM user_task_completions utc
                    JOIN user_tasks ut ON utc.task_id = ut.id
                    WHERE ut.task_type = 'channel'
                """)

            now = datetime.utcnow()

            for row in completed_rows:
                user_id = row["user_id"]
                task_id = row["task_id"]
                channel_username = row["channel_username"]
                completed_at = datetime.fromisoformat(row["completed_at"])

                # Сколько дней прошло с момента выполнения
                days_since = (now - completed_at).days

                # Прошло больше 3 дней — не штрафуем
                if days_since >= 2:
                    continue

                # Проверяем, подписан ли пользователь сейчас
                is_subscribed = await is_user_subscribed(bot, user_id, channel_username)
                if is_subscribed:
                    continue  # всё в порядке, подписка есть

                # Проверяем, был ли уже штраф
                async with aiosqlite.connect("bot_database.db") as db:
                    async with db.execute("""
                        SELECT 1 FROM frozen_transactions
                        WHERE user_id = ? AND task_id = ? AND task_type = 'unsubscribe_penalty'
                    """, (user_id, task_id)) as cursor:
                        already_penalized = await cursor.fetchone()

                if already_penalized:
                    continue  # уже штрафовали

                # Применяем штраф
                async with aiosqlite.connect("bot_database.db") as db:
                    await db.execute("""
                        UPDATE users
                        SET frozen_balance = frozen_balance - ?
                        WHERE user_id = ? AND frozen_balance >= ?
                    """, (current_reward, user_id, current_reward))

                    await db.execute("""
                        INSERT INTO frozen_transactions (user_id, amount, task_type, task_id, penalty_applied, penalty_amount)
                        VALUES (?, ?, 'unsubscribe_penalty', ?, 1, ?)
                    """, (user_id, -current_reward, task_id, current_reward))

                    await db.commit()

                # Уведомляем пользователя
                try:
                    await bot.send_message(
                        user_id,
                        f"⚠️ Вы отписались от канала @{channel_username} слишком рано!\n"
                        f"💸 Штраф: <b>{current_reward:.3f}$</b> списан с замороженного баланса.",
                        parse_mode='HTML'
                    )
                except:
                    pass

            # Проверка каждые 10 минут
            await asyncio.sleep(3600)

        except Exception as e:
            print(f"❌ Ошибка в check_unsubscribed_penalties: {e}")
            await asyncio.sleep(60)


@dp.callback_query(F.data == "broadcast_add_button")
async def broadcast_add_button(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    buttons = data.get('broadcast_buttons', [])

    if len(buttons) >= 5:
        await call.answer("❌ Максимум 5 кнопок в сообщении", show_alert=True)
        return

    await call.message.answer(
        "🔘 <b>Добавление кнопки</b>\n\n"
        "Отправьте текст кнопки и URL через знак |\n"
        "<b>Формат:</b> <code>Текст кнопки | https://example.com</code>\n\n"
        "<i>Пример:</i> <code>Наш канал | https://t.me/example</code>",
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_broadcast_buttons)
    await call.answer()


@dp.message(AdminStates.waiting_broadcast_buttons)
async def process_broadcast_button(message: types.Message, state: FSMContext):
    try:
        text, url = message.text.split('|', 1)
        text = text.strip()
        url = url.strip()

        if not text or not url:
            await message.answer("❌ Неверный формат. Используйте: Текст | URL")
            return

        if not url.startswith('http'):
            await message.answer("❌ URL должен начинаться с http:// или https://")
            return

        # Добавляем кнопку в список
        data = await state.get_data()
        buttons = data.get('broadcast_buttons', [])
        buttons.append({'text': text, 'url': url})

        await state.update_data(broadcast_buttons=buttons)

        # Показываем текущие кнопки
        buttons_text = "\n".join([f"• {btn['text']} -> {btn['url']}" for btn in buttons])

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="➕ Добавить еще кнопку", callback_data="broadcast_add_button")
        keyboard.button(text="🚀 Начать рассылку", callback_data="broadcast_start")
        keyboard.button(text="🗑️ Очистить все кнопки", callback_data="broadcast_clear_buttons")
        keyboard.button(text="❌ Отмена", callback_data="broadcast_cancel")
        keyboard.adjust(1)

        await message.answer(
            f"✅ <b>Кнопка добавлена!</b>\n\n"
            f"<b>Текущие кнопки:</b>\n{buttons_text}\n\n"
            f"Вы можете добавить еще кнопки или начать рассылку.",
            reply_markup=keyboard.as_markup(),
            parse_mode='HTML'
        )

    except ValueError:
        await message.answer(
            "❌ Неверный формат. Используйте:\n"
            "<code>Текст кнопки | https://example.com</code>",
            parse_mode='HTML'
        )


@dp.callback_query(F.data == "broadcast_clear_buttons")
async def broadcast_clear_buttons(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(broadcast_buttons=[])

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="➕ Добавить кнопку", callback_data="broadcast_add_button")
    keyboard.button(text="🚀 Начать рассылку", callback_data="broadcast_start")
    keyboard.button(text="❌ Отмена", callback_data="broadcast_cancel")
    keyboard.adjust(1)

    await call.message.edit_text(
        "✅ <b>Все кнопки очищены!</b>\n\n"
        "Теперь вы можете:\n"
        "• Добавить новые кнопки\n"
        "• Начать рассылку без кнопок",
        reply_markup=keyboard.as_markup(),
        parse_mode='HTML'
    )
    await call.answer("Кнопки очищены")


@dp.callback_query(F.data == "broadcast_start")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    await call.answer()

    data = await state.get_data()
    text = data.get('broadcast_text')
    media = data.get('broadcast_media')
    media_type = data.get('broadcast_media_type')
    buttons = data.get('broadcast_buttons', [])
    preview_message_id = data.get('preview_message_id')

    if not text and not media:
        await call.answer("❌ Нет контента для рассылки", show_alert=True)
        return

    # Создаем клавиатуру если есть кнопки
    reply_markup = None
    if buttons:
        keyboard = InlineKeyboardBuilder()
        for btn in buttons:
            keyboard.button(text=btn['text'], url=btn['url'])
        keyboard.adjust(1)
        reply_markup = keyboard.as_markup()

    # Получаем всех пользователей
    users = await get_all_users()
    total_users = len(users)

    # ОТПРАВЛЯЕМ НОВОЕ сообщение вместо редактирования старого
    status_message = await call.message.answer(
        f"🚀 <b>Начинаем рассылку...</b>\n\n👥 Получателей: {total_users}",
        parse_mode='HTML'
    )

    success_count = 0
    fail_count = 0
    blocked_count = 0

    # Обновляем статус каждые 50 пользователей
    update_interval = 50

    for i, (user_id, _) in enumerate(users):
        try:
            if media_type == 'photo' and media:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=media,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            elif media_type == 'video' and media:
                await bot.send_video(
                    chat_id=user_id,
                    video=media,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            elif media_type == 'animation' and media:
                await bot.send_animation(
                    chat_id=user_id,
                    animation=media,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            elif media_type == 'document' and media:
                await bot.send_document(
                    chat_id=user_id,
                    document=media,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )

            success_count += 1

            # Обновляем статус каждые update_interval пользователей
            if (i + 1) % update_interval == 0 or (i + 1) == total_users:
                try:
                    await status_message.edit_text(
                        f"🚀 <b>Рассылка в процессе...</b>\n\n"
                        f"📊 Прогресс: {i + 1}/{total_users}\n"
                        f"✅ Успешно: {success_count}\n"
                        f"❌ Ошибок: {fail_count}\n"
                        f"🚫 Заблокировали: {blocked_count}",
                        parse_mode='HTML'
                    )
                except:
                    pass  # Игнорируем ошибки редактирования

            # Небольшая задержка чтобы не спамить
            await asyncio.sleep(0.05)

        except aiogram.exceptions.TelegramForbiddenError:
            # Пользователь заблокировал бота
            blocked_count += 1
        except Exception as e:
            fail_count += 1
            print(f"❌ Ошибка отправки пользователю {user_id}: {e}")

    # Итоговое сообщение
    result_text = (
        f"📊 <b>Рассылка завершена!</b>\n\n"
        f"👥 Всего получателей: {total_users}\n"
        f"✅ Успешно отправлено: {success_count}\n"
        f"❌ Ошибок отправки: {fail_count}\n"
        f"🚫 Заблокировали бота: {blocked_count}\n\n"
        f"📈 Процент доставки: {(success_count / total_users * 100):.1f}%"
    )

    try:
        await status_message.edit_text(result_text, parse_mode='HTML')
    except:
        # Если не удалось отредактировать, отправляем новое сообщение
        await call.message.answer(result_text, parse_mode='HTML')

    # Удаляем превью-сообщение если оно было
    if preview_message_id:
        try:
            await bot.delete_message(chat_id=call.message.chat.id, message_id=preview_message_id)
        except:
            pass

    await state.clear()


@dp.callback_query(F.data == "broadcast_cancel")
async def broadcast_cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Рассылка отменена")
    await call.answer()


@dp.message(F.text == "🧹 Проверка неактивных")
async def check_inactive_users(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    # Показываем меню проверки
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔍 Найти неактивных", callback_data="find_inactive_users")
    keyboard.button(text="📊 Статистика неактивных", callback_data="inactive_stats")
    keyboard.button(text="🚫 Массовое удаление", callback_data="mass_cleanup")
    keyboard.adjust(1)

    await message.answer(
        "🧹 <b>Проверка неактивных пользователей</b>\n\n"
        "Здесь вы можете найти пользователей, которые:\n"
        "• Баланс: 0$\n"
        "• Не выполняли задания более 3 дней\n"
        "• Можно массово удалить из базы\n\n"
        "<i>Выберите действие:</i>",
        reply_markup=keyboard.as_markup(),
        parse_mode='HTML'
    )


@dp.callback_query(F.data == "find_inactive_users")
async def find_inactive_users(call: types.CallbackQuery):
    """Поиск неактивных пользователей"""
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.edit_text("🔍 <b>Ищу неактивных пользователей...</b>", parse_mode='HTML')

    inactive_users = await get_inactive_users()

    if not inactive_users:
        await call.message.edit_text(
            "✅ <b>Неактивных пользователей не найдено!</b>\n\n"
            "Все пользователи активны или имеют баланс/выполняли задания.",
            parse_mode='HTML'
        )
        return

    # Разбиваем на страницы по 10 пользователей
    users_per_page = 10
    total_pages = (len(inactive_users) + users_per_page - 1) // users_per_page

    await show_inactive_users_page(call, inactive_users, 1, users_per_page, total_pages)


async def show_inactive_users_page(call, inactive_users, page, users_per_page, total_pages):
    """Показывает страницу с неактивными пользователями"""
    start_idx = (page - 1) * users_per_page
    end_idx = start_idx + users_per_page
    users_page = inactive_users[start_idx:end_idx]

    text = f"🧹 <b>Неактивные пользователи</b>\n\n"
    text += f"📊 Найдено: <b>{len(inactive_users)}</b> пользователей\n"
    text += f"📄 Страница {page}/{total_pages}\n\n"

    for i, user in enumerate(users_page, start_idx + 1):
        last_active = user['last_activity'] or 'Никогда'
        text += f"{i}. ID: <code>{user['user_id']}</code> | @{user['username']}\n"
        text += f"   💰 Баланс: {user['balance']:.3f}$ | 📝 Заданий: {user['completed_tasks']}\n"
        text += f"   📅 Последняя активность: {last_active}\n\n"

    keyboard = InlineKeyboardBuilder()

    # Кнопки пагинации
    if page > 1:
        keyboard.button(text="⬅️ Назад", callback_data=f"inactive_page_{page - 1}")
    if page < total_pages:
        keyboard.button(text="➡️ Вперед", callback_data=f"inactive_page_{page + 1}")

    # Кнопки действий
    keyboard.button(text="🗑️ Удалить всех", callback_data="confirm_mass_delete")
    keyboard.button(text="📊 Статистика", callback_data="inactive_stats")
    keyboard.button(text="🔙 Назад", callback_data="inactive_back")

    keyboard.adjust(2, 1, 2)

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')


@dp.callback_query(F.data.startswith("inactive_page_"))
async def inactive_users_pagination(call: types.CallbackQuery):
    """Пагинация по неактивным пользователям"""
    if call.from_user.id not in ADMIN_IDS:
        return

    page = int(call.data.split("_")[2])
    inactive_users = await get_inactive_users()

    users_per_page = 10
    total_pages = (len(inactive_users) + users_per_page - 1) // users_per_page

    await show_inactive_users_page(call, inactive_users, page, users_per_page, total_pages)


async def get_inactive_users():
    """Находит пользователей с балансом 0 и без заданий за последние 3 дня"""
    async with aiosqlite.connect('bot_database.db') as db:
        # Получаем пользователей с балансом 0 и без активности 3 дня
        query = '''
            SELECT 
                u.user_id, 
                u.username, 
                u.balance, 
                u.frozen_balance,
                u.completed_tasks,
                u.registered_at,
                MAX(COALESCE(ct.completed_at, w.created_at, un.last_notification, u.registered_at)) as last_activity
            FROM users u
            LEFT JOIN completed_tasks ct ON u.user_id = ct.user_id AND ct.completed_at >= datetime('now', '-3 days')
            LEFT JOIN withdrawals w ON u.user_id = w.user_id AND w.created_at >= datetime('now', '-3 days')
            LEFT JOIN user_notifications un ON u.user_id = un.user_id AND un.last_notification >= datetime('now', '-3 days')
            WHERE u.balance = 0 
                AND u.frozen_balance = 0
                AND u.is_blocked = FALSE
            GROUP BY u.user_id
            HAVING last_activity < datetime('now', '-3 days') OR last_activity IS NULL
            ORDER BY last_activity ASC
        '''

        async with db.execute(query) as cursor:
            columns = [column[0] for column in cursor.description]
            users = [dict(zip(columns, row)) for row in await cursor.fetchall()]

            # Форматируем даты для красивого отображения
            for user in users:
                if user['last_activity']:
                    try:
                        dt = datetime.fromisoformat(user['last_activity'])
                        user['last_activity'] = dt.strftime("%d.%m.%Y %H:%M")
                    except:
                        pass
                else:
                    user['last_activity'] = "Никогда"

            return users


@dp.callback_query(F.data == "inactive_stats")
async def inactive_users_stats(call: types.CallbackQuery):
    """Статистика по неактивным пользователям"""
    if call.from_user.id not in ADMIN_IDS:
        return

    async with aiosqlite.connect('bot_database.db') as db:
        # Общее количество пользователей
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            total_users = (await cursor.fetchone())[0]

        # Заблокированные пользователи
        async with db.execute("SELECT COUNT(*) FROM users WHERE is_blocked = TRUE") as cursor:
            blocked_users = (await cursor.fetchone())[0]

        # Пользователи с балансом > 0
        async with db.execute("SELECT COUNT(*) FROM users WHERE balance > 0 OR frozen_balance > 0") as cursor:
            users_with_balance = (await cursor.fetchone())[0]

        # Активные за последние 3 дня
        async with db.execute('''
            SELECT COUNT(DISTINCT u.user_id) 
            FROM users u
            LEFT JOIN completed_tasks ct ON u.user_id = ct.user_id AND ct.completed_at >= datetime('now', '-3 days')
            LEFT JOIN withdrawals w ON u.user_id = w.user_id AND w.created_at >= datetime('now', '-3 days')
            WHERE ct.user_id IS NOT NULL OR w.user_id IS NOT NULL
        ''') as cursor:
            active_recently = (await cursor.fetchone())[0]

        # Неактивные (по нашей логике)
        inactive_users = await get_inactive_users()
        inactive_count = len(inactive_users)

    text = (
        "📊 <b>Статистика активности пользователей</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"✅ С балансом: <b>{users_with_balance}</b>\n"
        f"🔥 Активных (3 дня): <b>{active_recently}</b>\n"
        f"💀 Неактивных: <b>{inactive_count}</b>\n"
        f"🚫 Заблокированных: <b>{blocked_users}</b>\n\n"
        f"<i>Неактивные - баланс 0$ и нет активности 3+ дней</i>"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔍 Показать неактивных", callback_data="find_inactive_users")
    keyboard.button(text="🗑️ Массовое удаление", callback_data="confirm_mass_delete")
    keyboard.button(text="🔙 Назад", callback_data="inactive_back")
    keyboard.adjust(1)

    await call.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode='HTML')


@dp.callback_query(F.data == "confirm_mass_delete")
async def confirm_mass_delete(call: types.CallbackQuery):
    """Подтверждение массового удаления"""
    if call.from_user.id not in ADMIN_IDS:
        return

    inactive_users = await get_inactive_users()

    if not inactive_users:
        await call.answer("❌ Нет пользователей для удаления", show_alert=True)
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Да, удалить всех", callback_data="execute_mass_delete")
    keyboard.button(text="❌ Отмена", callback_data="find_inactive_users")
    keyboard.adjust(2)

    await call.message.edit_text(
        f"🚫 <b>Подтверждение массового удаления</b>\n\n"
        f"Вы уверены, что хотите удалить <b>{len(inactive_users)}</b> неактивных пользователей?\n\n"
        f"<i>Это действие нельзя отменить! Будут удалены все пользователи с:\n"
        f"• Баланс: 0$\n"
        f"• Нет активности 3+ дней</i>",
        reply_markup=keyboard.as_markup(),
        parse_mode='HTML'
    )


@dp.callback_query(F.data == "execute_mass_delete")
async def execute_mass_delete(call: types.CallbackQuery):
    """Выполняет массовое удаление неактивных пользователей"""
    if call.from_user.id not in ADMIN_IDS:
        return

    await call.message.edit_text("🗑️ <b>Начинаю массовое удаление...</b>", parse_mode='HTML')

    inactive_users = await get_inactive_users()
    deleted_count = 0

    if not inactive_users:
        await call.message.edit_text("❌ Нет пользователей для удаления", parse_mode='HTML')
        return

    try:
        async with aiosqlite.connect('bot_database.db') as db:
            for user in inactive_users:
                user_id = user['user_id']

                # Удаляем пользователя и связанные данные
                await db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM completed_tasks WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM user_notifications WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM frozen_transactions WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM custom_task_completions WHERE user_id = ?", (user_id,))
                await db.execute("DELETE FROM user_task_completions WHERE user_id = ?", (user_id,))

                deleted_count += 1

            await db.commit()

        # Обновляем реферальные связи для оставшихся пользователей
        await cleanup_referral_links()

        await call.message.edit_text(
            f"✅ <b>Массовое удаление завершено!</b>\n\n"
            f"🗑️ Удалено пользователей: <b>{deleted_count}</b>\n"
            f"📊 Осталось неактивных: <b>0</b>\n\n"
            f"<i>Все неактивные пользователи удалены из базы данных</i>",
            parse_mode='HTML'
        )

    except Exception as e:
        await call.message.edit_text(
            f"❌ <b>Ошибка при удалении:</b>\n\n{str(e)}",
            parse_mode='HTML'
        )


async def cleanup_referral_links():
    """Очищает реферальные ссылки после удаления пользователей"""
    async with aiosqlite.connect('bot_database.db') as db:
        await db.execute('''
            UPDATE users 
            SET referrer_id = NULL 
            WHERE referrer_id NOT IN (SELECT user_id FROM users)
        ''')
        await db.commit()


@dp.callback_query(F.data == "inactive_back")
async def inactive_back(call: types.CallbackQuery):
    """Возврат в меню проверки неактивных"""
    if call.from_user.id not in ADMIN_IDS:
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔍 Найти неактивных", callback_data="find_inactive_users")
    keyboard.button(text="📊 Статистика неактивных", callback_data="inactive_stats")
    keyboard.button(text="🚫 Массовое удаление", callback_data="mass_cleanup")
    keyboard.adjust(1)

    await call.message.edit_text(
        "🧹 <b>Проверка неактивных пользователей</b>\n\n"
        "Выберите действие:",
        reply_markup=keyboard.as_markup(),
        parse_mode='HTML'
    )


async def cleanup_database():
    while True:
        async with aiosqlite.connect("bot_database.db") as db:
            await db.execute("DELETE FROM user_notifications WHERE last_notification < datetime('now','-7 days')")

            await db.execute("DELETE FROM custom_task_completions WHERE completed_at < datetime('now','-10 days')")

            await db.execute("DELETE FROM user_task_completions WHERE completed_at < datetime('now','-10 days')")

            await db.execute("DELETE FROM completed_tasks WHERE completed_at < datetime('now','-10 days')")

            await db.execute(
                "DELETE FROM frozen_transactions WHERE is_unfrozen=1 AND frozen_at < datetime('now','-10 days')")

            await db.execute(
                "DELETE FROM withdrawals WHERE status!='approved' AND created_at < datetime('now','-20 days')")

            await db.execute("DELETE FROM ad_topups WHERE status!='paid' AND created_at < datetime('now','-20 days')")

            await db.execute("DELETE FROM balance_history WHERE created_at < datetime('now','-20 days')")

            await db.commit()

        await asyncio.sleep(172800)


async def load_ad_history_from_db():
    """Загрузка истории показов из БД при запуске"""
    try:
        async with aiosqlite.connect('bot_database.db') as db:
            async with db.execute("SELECT key, value FROM settings WHERE key LIKE 'last_ad_%'") as cursor:
                rows = await cursor.fetchall()

                for key, value in rows:
                    try:
                        user_id = int(key.replace('last_ad_', ''))
                        timestamp = float(value)
                        last_ad_times[user_id] = timestamp
                    except:
                        continue

        print(f"✅ Загружена история показов для {len(rows)} пользователей")
    except Exception as e:
        print(f"⚠️ Ошибка загрузки истории показов: {e}")


# Вызовите эту функцию в main перед запуском бота
# Запуск бота
async def main():
    # 1. Сначала инициализируем БД
    await init_db()

    # 2. Теперь можно загружать настройки из БД
    await load_crypto_token()
    await load_ad_history_from_db()

    # 3. Остальная инициализация
    init_flyer()
    await update_db_structure()
    check_flyer_methods()

    # 4. Запускаем фоновые задачи
    asyncio.create_task(check_completed_tasks())
    asyncio.create_task(cleanup_database())
    asyncio.create_task(check_unsubscribed_penalties())
    asyncio.create_task(scheduled_task_checker())
    asyncio.create_task(auto_unfreeze_balances())
    asyncio.create_task(schedule_periodic_ads())

    print("✅ Бот запускается...")
    print("🎯 Все фоновые задачи запущены!")

    # РЕЄСТРАЦІЯ (додайте це там, де ініціалізуєте dp)
    dp.message.outer_middleware(TgrassMiddleware())
    dp.callback_query.outer_middleware(TgrassMiddleware())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
