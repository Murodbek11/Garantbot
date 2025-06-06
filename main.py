
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime
import sqlite3
import random
import os

# === CONFIG ===
TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))
REVIEW_CHANNEL_ID = int(os.getenv("REVIEW_CHANNEL_ID"))

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

# === FSM STATES ===
class ReviewState(StatesGroup):
    waiting_for_review = State()

class OrderState(StatesGroup):
    waiting_for_description = State()

# === KEYBOARDS ===
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

# === HELPERS ===
def is_admin(user_id: int) -> bool:
    c.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,))
    return c.fetchone() is not None

def update_stat(field: str, value: int):
    c.execute(f"UPDATE stats SET {field} = {field} + ? WHERE id = 1", (value,))
    conn.commit()

def get_stats():
    c.execute("SELECT reviews, completed_orders FROM stats WHERE id = 1")
    return c.fetchone()

# === COMMANDS ===
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    kb = admin_keyboard() if is_admin(message.from_user.id) else main_keyboard()
    await message.answer("Добро пожаловать!", reply_markup=kb)

# === REVIEW HANDLERS ===
@dp.message_handler(lambda m: m.text == "📝 Оставить отзыв")
async def ask_review(message: types.Message):
    await message.answer("✍️ Введите ваш отзыв:")
    await ReviewState.waiting_for_review.set()

@dp.message_handler(state=ReviewState.waiting_for_review)
async def save_review(message: types.Message, state: FSMContext):
    user_info = f"{message.from_user.full_name} (@{message.from_user.username or 'без username'}, ID: {message.from_user.id})"
    text = f"🗣 Новый отзыв от {user_info}:

{message.text}"
    await bot.send_message(REVIEW_CHANNEL_ID, text)
    update_stat("reviews", 1)
    await message.answer("✅ Спасибо за отзыв!", reply_markup=main_keyboard())
    await state.finish()

# === OTHER HANDLERS ===
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def show_stats(message: types.Message):
    reviews, completed = get_stats()
    await message.answer(f"📈 Статистика:
Отзывы: {reviews}
Выполненные заказы: {completed}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
