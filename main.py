import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# --- SOZLAMALAR ---
API_TOKEN = '8214656085:AAF7UWA5PWGVT5G4GbuIJQcSbb5El7O_p5o'
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- BAZA BILAN ISHLASH ---
def db_init():
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    # Foydalanuvchilar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                      (user_id INTEGER PRIMARY KEY, ism TEXT, yosh INTEGER, jins TEXT, rasm TEXT)''')
    # Faol suhbatlar jadvali
    cursor.execute('''CREATE TABLE IF NOT EXISTS active_chats 
                      (user1_id INTEGER, user2_id INTEGER)''')
    conn.commit()
    conn.close()

def get_partner_id(user_id):
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT user1_id, user2_id FROM active_chats WHERE user1_id = ? OR user2_id = ?", (user_id, user_id))
    chat = cursor.fetchone()
    conn.close()
    if chat:
        return chat[1] if chat[0] == user_id else chat[0]
    return None

# --- HOLATLAR ---
class Steps(StatesGroup):
    ism = State()
    yosh = State()
    jins = State()
    rasm = State()
    suhbatda = State() # Anonim chat holati

# --- TUGMALAR ---
def main_menu():
    kb = [[types.KeyboardButton(text="📝 Anketa"), types.KeyboardButton(text="🔍 Sherik izlash")]]
    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Salom! Tanishuv va Anonim Chat botiga xush kelibsiz.", reply_markup=main_menu())

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
        await message.answer("Raqam kiriting!")
        return
    await state.update_data(yosh=int(message.text))
    kb = [[types.KeyboardButton(text="Erkak")], [types.KeyboardButton(text="Ayol")]]
    await message.answer("Jinsingiz?", reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))
    await state.set_state(Steps.jins)

@dp.message(Steps.jins)
async def get_gender(message: types.Message, state: FSMContext):
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
    await message.answer("Anketa saqlandi!", reply_markup=main_menu())
    await state.clear()

# QIDIRUV VA INLINE TUGMA
@dp.message(F.text.in_(["🔍 Sherik izlash", "Keyingisi ➡️"]))
async def search(message: types.Message):
    conn = sqlite3.connect('tanishuv_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id != ? ORDER BY RANDOM() LIMIT 1", (message.from_user.id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        kb = [[types.InlineKeyboardButton(text="💬 Suhbatga taklif qilish", callback_data=f"chat_{user[0]}")]]
        markup = types.InlineKeyboardMarkup(inline_keyboard=kb)
        text = f"👤 {user[1]}, {user[2]} yosh\n👫 {user[3]}"
        await message.answer_photo(user[4], caption=text, reply_markup=markup)
        await message.answer("Boshqasini ko'rish uchun 'Keyingisi ➡️' bosing.", reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Keyingisi ➡️"), types.KeyboardButton(text="🏠 Menyu")]], resize_keyboard=True))
    else:
        await message.answer("Hozircha hech kim yo'q.")

# CHAT SO'ROVI
@dp.callback_query(F.data.startswith("chat_"))
async def invite_chat(call: types.CallbackQuery):
    target_id = int(call.data.split("_")[1])
    kb = [[types.InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"acc_{call.from_user.id}")]]
    await bot.send_message(target_id, "Siz bilan kimdir anonim gaplashmoqchi!", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer("Taklif yuborildi!")

# CHATNI QABUL QILISH
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
    await call.message.answer("Suhbat boshlandi! Xabaringizni yozing.", reply_markup=stop_kb)
    await bot.send_message(partner_id, "Suhbatdosh taklifni qabul qildi! Yozishingiz mumkin.", reply_markup=stop_kb)

# ANONIM XABAR ALMASHISH
@dp.message(Steps.suhbatda)
async def anonymous_chat(message: types.Message, state: FSMContext):
    partner_id = get_partner_id(message.from_user.id)
    
    if message.text == "❌ Suhbatni yakunlash":
        conn = sqlite3.connect('tanishuv_bot.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_chats WHERE user1_id = ? OR user2_id = ?", (message.from_user.id, message.from_user.id))
        conn.commit()
        conn.close()
        
        await state.clear()
        if partner_id:
            await dp.fsm.get_context(bot, partner_id, partner_id).clear()
            await bot.send_message(partner_id, "Suhbatdosh suhbatni tark etdi.", reply_markup=main_menu())
        await message.answer("Suhbat yakunlandi.", reply_markup=main_menu())
        return

    if partner_id:
        if message.text:
            await bot.send_message(partner_id, f"📩: {message.text}")
        elif message.photo:
            await bot.send_photo(partner_id, message.photo[-1].file_id, caption="📩 (Rasm)")

@dp.message(F.text == "🏠 Menyu")
async def back_menu(message: types.Message):
    await message.answer("Asosiy menyu", reply_markup=main_menu())

async def main():
    db_init()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())