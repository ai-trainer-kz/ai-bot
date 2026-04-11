import os
import telebot
from telebot import types
import sqlite3
import random
from gtts import gTTS
from openai import OpenAI
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_server():
    server = HTTPServer(('0.0.0.0', 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_server).start()

# ====== НАСТРОЙКИ ======
TOKEN = os.getenv("TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

bot = telebot.TeleBot(TOKEN)

# ====== БАЗА ======
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    premium INTEGER DEFAULT 0,
    lang TEXT DEFAULT 'ru',
    score INTEGER DEFAULT 0
)
""")
conn.commit()

user_mode = {}

# ====== ВОПРОСЫ ======
questions = [
    {"q": "2 + 2 = ?", "options": ["3", "4", "5"], "answer": "4"},
    {"q": "Столица Казахстана?", "options": ["Алматы", "Астана", "Шымкент"], "answer": "Астана"},
    {"q": "5 * 6 = ?", "options": ["30", "25", "20"], "answer": "30"}
]

# ====== ПРОВЕРКА ПРЕМИУМ ======
def is_premium(user_id):
    cursor.execute("SELECT premium FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] == 1

# ====== СТАРТ ======
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 Тест", "🤖 ИИ")
    markup.add("📊 Статистика", "🏆 Топ")
    markup.add("🎤 Голос", "💎 Премиум")
    markup.add("🌍 Язык")

    bot.send_message(user_id, "Добро пожаловать 🚀\nВыбери режим:", reply_markup=markup)

# ====== ИИ ======
@bot.message_handler(func=lambda m: m.text == "🤖 ИИ")
def ai_mode(message):
    bot.send_message(message.chat.id, "Напиши вопрос 👇")
    user_mode[message.chat.id] = "ai"

# ====== ПРЕМИУМ ИИ ======
@bot.message_handler(func=lambda m: m.text == "💎 Премиум")
def premium_mode(message):
    user_id = message.chat.id
    bot.send_chat_action(user_id, "typing")  # ✅ теперь правильно

    bot.send_message(message.chat.id, "💎 Премиум режим активирован")
    user_mode[message.chat.id] = "premium"

# ====== ГОЛОС ======
@bot.message_handler(func=lambda m: m.text == "🎤 Голос")
def voice_mode(message):
    user_id = message.chat.id
    bot.send_chat_action(user_id, "record_voice")  # ✅

    bot.send_message(message.chat.id, "Отправь текст, я озвучу 🎤")
    user_mode[message.chat.id] = "voice"

# ====== ТЕСТ ======
@bot.message_handler(func=lambda m: m.text == "🚀 Тест")
def test_mode(message):
    user_id = message.chat.id

    q = random.choice(questions)

    # сохраняем вопрос
    user_mode[user_id] = {
        "mode": "test",
        "answer": q["answer"]
    }

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for opt in q["options"]:
        markup.add(opt)

    bot.send_message(user_id, q["q"], reply_markup=markup)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for opt in q["options"]:
        markup.add(opt)

    bot.send_message(message.chat.id, q["q"], reply_markup=markup)
    user_mode[message.chat.id] = q

# ====== ОБРАБОТКА ======
@bot.message_handler(func=lambda message: True)
def handle(message):
    user_id = message.chat.id
    text = message.text

# ===== ПРОВЕРКА ТЕСТА =====
if user_id in user_mode and isinstance(user_mode[user_id], dict):
    if user_mode[user_id].get("mode") == "test":
        correct = user_mode[user_id]["answer"]

        if text == correct:
            bot.send_message(user_id, "✅ Правильно!")
        else:
            bot.send_message(user_id, f"❌ Неправильно. Ответ: {correct}")

        # сброс
        user_mode[user_id] = {}
        return

    bot.send_chat_action(user_id, "typing")
    # ===== ТЕСТ =====
    if user_id in user_mode and isinstance(user_mode[user_id], dict):
        q = user_mode[user_id]

        if text == q["answer"]:
            bot.send_message(user_id, "✅ Правильно!")
            cursor.execute("UPDATE users SET score = score + 1 WHERE user_id=?", (user_id,))
            conn.commit()
        else:
            bot.send_message(user_id, f"❌ Неправильно. Ответ: {q['answer']}")

        del user_mode[user_id]
            return

    # ===== ИИ =====
    if user_mode.get(user_id) == "ai":
        bot.send_chat_action(chat_id, "typing")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты помощник по ЕНТ. Отвечай кратко и понятно."},
                {"role": "user", "content": text}
            ]
        )

        bot.send_message(user_id, response.choices[0].message.content)
        return

    # ===== ПРЕМИУМ =====
    if user_mode.get(user_id) == "premium":
        if not is_premium(user_id):
            bot.send_message(user_id, "❌ Купи премиум")
            return

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Ты продвинутый репетитор ЕНТ. Дай подробный ответ."},
                {"role": "user", "content": text}
            ]
        )

        bot.send_message(user_id, response.choices[0].message.content)
        return

    # ===== ГОЛОС =====
    if user_mode.get(user_id) == "voice":
        tts = gTTS(text=text, lang='ru')
        tts.save("voice.mp3")

        with open("voice.mp3", "rb") as audio:
            bot.send_voice(user_id, audio)
        return

# ====== СТАТИСТИКА ======
@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats(message):
    cursor.execute("SELECT score FROM users WHERE user_id=?", (message.chat.id,))
    score = cursor.fetchone()[0]
    bot.send_message(message.chat.id, f"📊 Твой счёт: {score}")

# ====== ЗАПУСК ======
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Ошибка: {e}")
