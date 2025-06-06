import sqlite3
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime
import random

# === CONFIG ===
TOKEN = '7377520849:AAFH3Yt6JOzFYOwPkrzUfrzNLmnHqK-TaAA'
OWNER_ID = 1725224593
REVIEW_CHANNEL_ID = -1002567963097

# === SETUP ===
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# === DATABASE SETUP ===
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS stats (
    id INTEGER PRIMARY KEY,
    reviews INTEGER,
    completed_orders INTEGER
)''')
c.execute('''INSERT OR IGNORE INTO stats (id, reviews, completed_orders) VALUES (1, 0, 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    description TEXT,
    start_time TEXT,
    status TEXT,
    taken_by INTEGER
)''')

c.execute('''CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
)''')
c.execute('''INSERT OR IGNORE INTO admins (user_id) VALUES (?)''', (OWNER_ID,))

conn.commit()

class ReviewState(StatesGroup):
    waiting_for_review = State()

class OrderState(StatesGroup):
    waiting_for_description = State()

def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📝 Оставить отзыв", "📦 Заказать услугу")
    kb.add("📊 Статистика", "📌 Примеры отзывов")
    kb.add("❓ FAQ", "💬 Связаться с гарантом")
    return kb

def admin_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🧹 Обнулить отзывы", "🧹 Обнулить заказы")
    kb.add("➖ -1 отзыв", "➖ -1 заказ")
    kb.add("📊 Статистика", "/start")
    return kb

def is_admin(user_id: int) -> bool:
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

def update_stat(field: str, value: int):
    c.execute(f"UPDATE stats SET {field} = {field} + ? WHERE id = 1", (value,))
    conn.commit()

def get_stats():
    c.execute("SELECT reviews, completed_orders FROM stats WHERE id = 1")
    return c.fetchone()

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    kb = admin_keyboard() if is_admin(message.from_user.id) else main_keyboard()
    await message.answer("Добро пожаловать!", reply_markup=kb)

@dp.message_handler(commands=["admin"])
async def cmd_admin(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        new_admin_id = int(message.get_args())
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin_id,))
        conn.commit()
        await message.answer(f"✅ Пользователю {new_admin_id} выданы права администратора.")
    except Exception:
        await message.answer("⚠️ Используйте: /admin <user_id>")

@dp.message_handler(commands=["unadmin"])
async def cmd_unadmin(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    try:
        admin_id = int(message.get_args())
        if admin_id == OWNER_ID:
            await message.answer("⚠️ Нельзя удалить владельца из админов.")
            return
        c.execute("DELETE FROM admins WHERE user_id = ?", (admin_id,))
        conn.commit()
        await message.answer(f"❌ Пользователь {admin_id} удалён из админов.")
    except Exception:
        await message.answer("⚠️ Используйте: /unadmin <user_id>")

@dp.message_handler(lambda m: m.text == "📝 Оставить отзыв")
async def ask_review(message: types.Message):
    await message.answer("✍️ Введите ваш отзыв:")
    await ReviewState.waiting_for_review.set()

@dp.message_handler(state=ReviewState.waiting_for_review)
async def save_review(message: types.Message, state: FSMContext):
    user_info = f"ID: <code>{message.from_user.id}</code>
Username: @{message.from_user.username or 'Без ника'}"
    review_text = f"🗣 Новый отзыв:

{message.text}

👤 {user_info}"
    await bot.send_message(REVIEW_CHANNEL_ID, review_text, parse_mode="HTML")
    update_stat("reviews", 1)
    await message.answer("✅ Спасибо за отзыв!", reply_markup=main_keyboard())
    await state.finish()

@dp.message_handler(lambda m: m.text == "📌 Примеры отзывов")
async def examples(message: types.Message):
    await message.answer("ℹ️ Примеры отзывов больше не отображаются. Оставьте реальный отзыв!")

@dp.message_handler(lambda m: m.text == "📦 Заказать услугу")
async def ask_order(message: types.Message):
    await message.answer("📋 Опишите, что вам нужно:")
    await OrderState.waiting_for_description.set()

@dp.message_handler(state=OrderState.waiting_for_description)
async def handle_order(message: types.Message, state: FSMContext):
    description = message.text
    c.execute("INSERT INTO orders (user_id, description, status) VALUES (?, ?, 'new')", (message.from_user.id, description))
    conn.commit()
    order_id = c.lastrowid
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Принять", callback_data=f"accept_{order_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"decline_{order_id}")
    )
    c.execute("SELECT user_id FROM admins")
    for (admin_id,) in c.fetchall():
        await bot.send_message(admin_id, f"📥 Новый заказ #{order_id} от @{message.from_user.username or message.from_user.id}:
{description}", reply_markup=keyboard)
    await message.answer("🕐 Заказ отправлен. Ожидайте ответа.", reply_markup=main_keyboard())
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("accept_"))
async def accept_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    c.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    if not (row := c.fetchone()) or row[0] != "new":
        await callback.answer("Заказ уже обработан.", show_alert=True)
        return
    now = datetime.now().isoformat()
    c.execute("UPDATE orders SET status = 'accepted', start_time = ?, taken_by = ? WHERE id = ?", (now, callback.from_user.id, order_id))
    conn.commit()
    await callback.message.edit_reply_markup()
    await callback.message.answer("🟢 Заказ принят. Таймер запущен.", reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order_id}"),
        InlineKeyboardButton("✅ Выполнено", callback_data=f"done_{order_id}")
    ))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("decline_"))
async def decline_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    c.execute("SELECT status FROM orders WHERE id = ?", (order_id,))
    if not (row := c.fetchone()) or row[0] != "new":
        await callback.answer("Заказ уже обработан.", show_alert=True)
        return
    c.execute("UPDATE orders SET status = 'declined' WHERE id = ?", (order_id,))
    conn.commit()
    await callback.message.edit_reply_markup()
    await callback.answer("Заказ отклонён.")

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_"))
async def cancel_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    c.execute("SELECT start_time, taken_by FROM orders WHERE id = ? AND status = 'accepted'", (order_id,))
    result = c.fetchone()
    if result and result[1] == callback.from_user.id:
        duration = datetime.now() - datetime.fromisoformat(result[0])
        c.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        conn.commit()
        await callback.message.answer(f"⛔ Заказ отменён. Время обработки: {str(duration).split('.')[0]}")
        await callback.answer()
    else:
        await callback.answer("Вы не можете отменить этот заказ.", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("done_"))
async def done_order(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    c.execute("SELECT start_time, taken_by FROM orders WHERE id = ? AND status = 'accepted'", (order_id,))
    result = c.fetchone()
    if result and result[1] == callback.from_user.id:
        duration = datetime.now() - datetime.fromisoformat(result[0])
        c.execute("UPDATE orders SET status = 'completed' WHERE id = ?", (order_id,))
        update_stat("completed_orders", 1)
        conn.commit()
        await callback.message.answer(f"✅ Заказ завершён. Время выполнения: {str(duration).split('.')[0]}")
        await callback.answer()
    else:
        await callback.answer("Вы не можете завершить этот заказ.", show_alert=True)

@dp.message_handler(lambda m: is_admin(m.from_user.id))
async def admin_panel(message: types.Message):
    text = message.text
    if text == "🧹 Обнулить отзывы":
        c.execute("UPDATE stats SET reviews = 0 WHERE id = 1")
    elif text == "🧹 Обнулить заказы":
        c.execute("UPDATE stats SET completed_orders = 0 WHERE id = 1")
    elif text == "➖ -1 отзыв":
        c.execute("UPDATE stats SET reviews = CASE WHEN reviews > 0 THEN reviews - 1 ELSE 0 END WHERE id = 1")
    elif text == "➖ -1 заказ":
        c.execute("UPDATE stats SET completed_orders = CASE WHEN completed_orders > 0 THEN completed_orders - 1 ELSE 0 END WHERE id = 1")
    elif text == "📊 Статистика":
        reviews, completed = get_stats()
        await message.answer(f"📈 Статистика:
Отзывы: {reviews}
Выполненные заказы: {completed}", reply_markup=admin_keyboard())
        conn.commit()
        return
    else:
        await message.answer("Команда не распознана.", reply_markup=admin_keyboard())
        return
    conn.commit()
    await message.answer("✅ Готово.", reply_markup=admin_keyboard())

@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def show_stats(message: types.Message):
    reviews, completed = get_stats()
    await message.answer(f"📈 Статистика:
Отзывы: {reviews}
Выполненные заказы: {completed}")

@dp.message_handler(lambda m: m.text == "❓ FAQ")
async def faq(message: types.Message):
    await message.answer("❓ Часто задаваемые вопросы скоро появятся.")

@dp.message_handler(lambda m: m.text == "💬 Связаться с гарантом")
async def contact(message: types.Message):
    await message.answer(f"📬 Связь с гарантом: @{(await bot.get_chat(OWNER_ID)).username}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)