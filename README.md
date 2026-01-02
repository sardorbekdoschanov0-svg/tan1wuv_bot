import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

# --- KONFIGURATSIYA ---
API_TOKEN = '8214656085:AAF7UWA5PWGVT5G4GbuIJQcSbb5El7O_p5o' # BotFather dan olgan tokenni qo'ying
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- BAZA BILAN ISHLASH ---
def db_init():
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, ism TEXT, yosh INTEGER, jins TEXT, rasm TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_chats 
                      (user1_id INTEGER, user2_id INTEGER)''')
    conn.commit()
    conn.close()

# --- RENDER UCHUN WEB SERVER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- HOLATLAR ---
class Steps(StatesGroup):
    ism = State()
    yosh = State()
    jins = State()
    rasm = State()
    suhbatda = State()

# --- TUGMALAR ---
def main_menu():
    kb = [
        [types.KeyboardButton(text="🔍 Sherik izlash")],
        [types.KeyboardButton(text="👤 Mening profilim"), types.KeyboardButton(text="📝 Anketa")],
        [types.KeyboardButton(text="🏠 Menyu")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Xush kelibsiz! O'zingizga mos sherik toping.", reply_markup=main_menu())

# ANKETA TO'LDIRISH
@dp.message(F.text == "📝 Anketa")
async def start_anketa(message: types.Message, state: FSMContext):
    await message.answer("Ismingiz nima?", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Steps.ism)

@dp.message(Steps.ism)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(ism=message.text)
    await message.answer("Yoshingiz nechada?")
    await state.set_state(Steps.yosh)

@dp.message(Steps.yosh)
async def get_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Faqat raqam kiriting!")
        return
    await state.update_data(yosh=int(message.text))
    kb = [[types.KeyboardButton(text="Erkak")], [types.KeyboardButton(text="Ayol")]]
    await message.answer("Jinsingiz?", reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
    await state.set_state(Steps.jins)

@dp.message(Steps.jins)
async def get_gender(message: types.Message, state: FSMContext):
    if message.text not in ["Erkak", "Ayol"]:
        await message.answer("Tugmalardan birini tanlang!")
        return
    await state.update_data(jins=message.text)
    await message.answer("Rasmingizni yuboring:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(Steps.rasm)

@dp.message(Steps.rasm, F.photo)
async def get_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO users VALUES (?, ?, ?, ?, ?)", 
                   (message.from_user.id, data['ism'], data['yosh'], data['jins'], photo_id))
    conn.commit()
    conn.close()
    await message.answer("Profilingiz saqlandi!", reply_markup=main_menu())
    await state.clear()

# MENING PROFILIM
@dp.message(F.text == "👤 Mening profilim")
async def my_profile(message: types.Message):
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        kb = [[types.InlineKeyboardButton(text="❌ Profilni o'chirish", callback_data="delete_my_profile")]]
        markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
        caption = f"Sizning profilingiz:\n\nIsm: {user[1]}\nYosh: {user[2]}\nJins: {user[3]}"
        await message.answer_photo(user[4], caption=caption, reply_markup=markup)
    else:
        await message.answer("Sizda hali profil yo'q. '📝 Anketa' tugmasini bosing.")

@dp.callback_query(F.data == "delete_my_profile")
async def delete_profile(call: types.CallbackQuery):
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (call.from_user.id,))
    conn.commit()
    conn.close()
    await call.message.answer("Profilingiz o'chirildi.")
    await call.answer()

# JINS BO'YICHA QIDIRUV
@dp.message(F.text.in_(["🔍 Sherik izlash", "Keyingisi ➡️"]))
async def search_partner(message: types.Message):
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT jins FROM users WHERE user_id = ?", (message.from_user.id,))
    me = cursor.fetchone()
    
    if not me:
        await message.answer("Avval o'zingiz haqingizda ma'lumot kiriting (📝 Anketa).")
        return

    target_gender = "Ayol" if me[0] == "Erkak" else "Erkak"
    cursor.execute("SELECT * FROM users WHERE user_id != ? AND jins = ? ORDER BY RANDOM() LIMIT 1", 
                   (message.from_user.id, target_gender))
    user = cursor.fetchone()
    conn.close()

    if user:
        kb = [[types.InlineKeyboardButton(text="💬 Suhbatga taklif qilish", callback_data=f"chat_{user[0]}")]]
        markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
        caption = f"👤 {user[1]}, {user[2]} yosh\n👫 {user[3]}"
        await message.answer_photo(user[4], caption=caption, reply_markup=markup)
    else:
        await message.answer(f"Hozircha bazada {target_gender}lar yo'q.")

# CHAT SO'ROVI VA ANONIM CHAT HANDLERLARI (Oldingi koddagidek)
@dp.callback_query(F.data.startswith("chat_"))
async def invite_chat(call: types.CallbackQuery):
    target_id = int(call.data.split("_")[1])
    kb = [[types.InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"acc_{call.from_user.id}")]]
    await bot.send_message(target_id, "Siz bilan kimdir anonim gaplashmoqchi!", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer("Taklif yuborildi!")

@dp.callback_query(F.data.startswith("acc_"))
async def accept_chat(call: types.CallbackQuery, state: FSMContext):
    partner_id = int(call.data.split("_")[1])
    my_id = call.from_user.id
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO active_chats VALUES (?, ?)", (my_id, partner_id))
    conn.commit()
    conn.close()
    await state.set_state(Steps.suhbatda)
    await dp.fsm.get_context(bot, partner_id, partner_id).set_state(Steps.suhbatda)
    stop_kb = types.ReplyKeyboardMarkup(keyboard=[[types.KeyboardButton(text="❌ Suhbatni yakunlash")]], resize_keyboard=True)
    await call.message.answer("Suhbat boshlandi!", reply_markup=stop_kb)
    await bot.send_message(partner_id, "Suhbatdosh qabul qildi!", reply_markup=stop_kb)

@dp.message(Steps.suhbatda)
async def anonymous_chat(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user1_id, user2_id FROM active_chats WHERE user1_id = ? OR user2_id = ?", (message.from_user.id, message.from_user.id))
    chat = cursor.fetchone()
    conn.close()
    
    partner_id = None
    if chat: partner_id = chat[1] if chat[0] == message.from_user.id else chat[0]

    if message.text == "❌ Suhbatni yakunlash":
        conn = sqlite3.connect('tanishuv_bot.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_chats WHERE user1_id = ? OR user2_id = ?", (message.from_user.id, message.from_user.id))
        conn.commit()
        conn.close()
        await state.clear()
        if partner_id:
            await dp.fsm.get_context(bot, partner_id, partner_id).clear()
            await bot.send_message(partner_id, "Suhbat yakunlandi.", reply_markup=main_menu())
        await message.answer("Suhbat yakunlandi.", reply_markup=main_menu())
        return

    if partner_id:
        if message.text: await bot.send_message(partner_id, f"📩: {message.text}")
        elif message.photo: await bot.send_photo(partner_id, message.photo[-1].file_id)

@dp.message(F.text == "🏠 Menyu")
async def back_menu(message: types.Message):
    await message.answer("Asosiy menyu", reply_markup=main_menu())

# --- ISHGA TUSHIRISH ---
async def main():
    db_init()
    await start_web_server()
    print("Bot Renderda ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
