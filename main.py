from aiogram import Bot, Dispatcher, types, executor
from config import TOKEN, OWNER_ID, MODERATORS, DATA_FILE
import json, os

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"scam": {}, "suspect": {}, "fakegarant": {}, "garant": {}}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_mod(id): return id == OWNER_ID or id in MODERATORS

@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    await msg.reply("🤖 TRUSTIX бот запущен. Введите /help для списка команд.")

@dp.message_handler(commands=["help"])
async def help(msg: types.Message):
    await msg.reply("""
📘 Команды:
/add @user причина
/suspect @user причина
/fakegarant @user причина
/garant @user @канал_отзывов
/remove @user
/check @user
/garantlist
""")

@dp.message_handler(commands=["add", "suspect", "fakegarant"])
async def add_to_base(msg: types.Message):
    if not is_mod(msg.from_user.id): return
    parts = msg.text.split()
    if len(parts) < 3: return await msg.reply("❌ Формат: /add @user причина")
    cmd, user, reason = parts[0][1:], parts[1], ' '.join(parts[2:])
    data = load_data()
    data[cmd][user] = reason
    save_data(data)
    await msg.reply(f"✅ {user} добавлен в {cmd}.")

@dp.message_handler(commands=["garant"])
async def add_garant(msg: types.Message):
    if not is_mod(msg.from_user.id): return
    parts = msg.text.split()
    if len(parts) != 3: return await msg.reply("❌ Формат: /garant @user @канал_отзывов")
    _, user, channel = parts
    data = load_data()
    data["garant"][user] = {"reviews": channel}
    save_data(data)
    await msg.reply(f"✅ {user} добавлен как проверенный гарант.")

@dp.message_handler(commands=["garantlist"])
async def garant_list(msg: types.Message):
    data = load_data()
    text = "✅ Проверенные гаранты:

"
    for user, val in data["garant"].items():
        text += f"{user}
ОТЗЫВЫ: {val['reviews']}

"
    await msg.reply(text if data["garant"] else "Список пуст.")

@dp.message_handler(commands=["remove"])
async def remove_user(msg: types.Message):
    if not is_mod(msg.from_user.id): return
    parts = msg.text.split()
    if len(parts) != 2: return await msg.reply("❌ Формат: /remove @user")
    user = parts[1]
    data = load_data()
    found = False
    for cat in data:
        if user in data[cat]:
            del data[cat][user]
            found = True
    save_data(data)
    await msg.reply("✅ Удалён." if found else "❌ Не найден.")

@dp.message_handler(commands=["check"])
async def check_user(msg: types.Message):
    parts = msg.text.split()
    if len(parts) != 2: return await msg.reply("❌ Формат: /check @user")
    user = parts[1]
    data = load_data()
    if user in data["fakegarant"]:
        await msg.reply(f"❗ {user} — СКАМЕР-ГАРАНТ
Причина: {data['fakegarant'][user]}")
    elif user in data["scam"]:
        await msg.reply(f"🚫 {user} — СКАМЕР
Причина: {data['scam'][user]}")
    elif user in data["suspect"]:
        await msg.reply(f"⚠️ {user} — ПОДОЗРИТЕЛЬНЫЙ
Причина: {data['suspect'][user]}")
    elif user in data["garant"]:
        await msg.reply(f"✅ {user} — ПРОВЕРЕННЫЙ ГАРАНТ
ОТЗЫВЫ: {data['garant'][user]['reviews']}")
    else:
        await msg.reply("ℹ️ Не найден в базе.")

if __name__ == "__main__":
    executor.start_polling(dp)