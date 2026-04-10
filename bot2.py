from telebot import types
import telebot
import sqlite3
from openai import OpenAI
import random
from gtts import gTTS
import os

# ===== НАСТРОЙКИ =====
TOKEN = "8315601912:AAHoo0mcZHJV8qtlDdjze7HQvM6tXgM9U88"
OPENAI_API_KEY = "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"
ADMIN_ID = 123456789

bot = telebot.TeleBot(TOKEN)
client = OpenAI(api_key=OPENAI_API_KEY)

user_mode = {}

# ===== БАЗА =====
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    best_score INTEGER DEFAULT 0,
    premium INTEGER DEFAULT 0,
    lang TEXT DEFAULT 'ru'
)
""")
conn.commit()

# ===== ДАННЫЕ =====
user_score = {}
user_total = {}
current_question = {}

# ===== ЯЗЫК =====
def detect_lang(text):
    kazakh_letters = "әіңғүұқөһ"
    for ch in text.lower():
        if ch in kazakh_letters:
            return "kk"
    return "ru"

def get_lang(uid):
    row = cursor.fetchone()
    return row[0] if row else "ru"

# ===== МЕНЮ =====
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🚀 Тест", "🤖 ИИ")
    markup.add("📊 Статистика", "🏆 Топ")
    markup.add("🎤 Голос", "💎 Премиум")
    markup.add("🌐 Язык")
    return markup

# ===== СТАРТ =====
@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,))
    conn.commit()

    bot.send_message(uid,
        "Добро пожаловать 🚀\nВыбери режим:",
        reply_markup=main_menu())

# ===== ЯЗЫК ВЫБОР =====
@bot.message_handler(func=lambda m: m.text in ["Қазақша", "Русский"])
def set_language(message):
    uid = message.from_user.id
    
    lang = "kk" if message.text == "Қазақша" else "ru"
    
    cursor.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, uid))
    conn.commit()
    
    bot.send_message(message.chat.id, "Тіл сақталды ✅" if lang=="kk" else "Язык сохранён ✅")

# ===== ВОПРОС =====
def generate_question():
    a = random.randint(2, 20)
    b = random.randint(2, 20)
    correct = a * b

    options = list(set([correct,
        correct + random.randint(1,5),
        correct - random.randint(1,5),
        correct + random.randint(6,10)
    ]))

    while len(options) < 4:
        options.append(correct + random.randint(1,10))

    random.shuffle(options)

    letters = ["A","B","C","D"]
    correct_letter = letters[options.index(correct)]

    text = f"{a} * {b}?\n"
    for i in range(4):
        text += f"{letters[i]}) {options[i]}\n"

    return text, correct_letter, correct

# ===== ТЕСТ =====
@bot.message_handler(func=lambda m: m.text == "🚀 Тест")
def start_test(message):
    uid = message.from_user.id
    user_score[uid] = 0
    user_total[uid] = 0
    send_question(message)

def send_question(message):
    uid = message.from_user.id

    if user_total.get(uid,0) >= 10:
        finish_test(message)
        return

    q, letter, value = generate_question()
    current_question[uid] = (letter, value)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("A","B","C","D")

    bot.send_message(uid, q, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["A","B","C","D"])
def answer(message):
    uid = message.from_user.id

    if uid not in current_question:
        return

    correct_letter, correct_value = current_question[uid]
    user_total[uid] += 1

    if message.text == correct_letter:
        user_score[uid] += 1
        bot.send_message(uid, f"Правильно ✅ {user_score[uid]}/{user_total[uid]}")
    else:
        bot.send_message(uid, f"Неправильно ❌ {correct_letter} ({correct_value})")

    send_question(message)

def finish_test(message):
    uid = message.from_user.id
    score = user_score[uid]

    cursor.execute("SELECT best_score FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()

    if row:
        if score > row[0]:
            cursor.execute("UPDATE users SET best_score=? WHERE user_id=?", (score, uid))
    else:
        cursor.execute("INSERT INTO users (user_id,best_score) VALUES (?,?)",(uid,score))

    conn.commit()

    bot.send_message(uid, f"Тест завершён 🎯\n{score}/10", reply_markup=main_menu())

    del user_score[uid]
    del user_total[uid]
    del current_question[uid]

# ===== ИИ =====
@bot.message_handler(func=lambda m: m.text == "🤖 ИИ")
def ai_mode(message):
    bot.send_message(message.chat.id, "Задай вопрос ✍️")

@bot.message_handler(func=lambda m: True)
def chat(message):
    uid = message.from_user.id

    if user_mode.get(uid) != "ai":
     return
    lang = get_lang(uid)

    try:
        prompt = message.text

        if lang == "kk":
            prompt = "Жауапты қазақ тілінде бер: " + prompt

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}]
        )

        bot.send_message(uid, response.choices[0].message.content)

    except:
        bot.send_message(uid, "Ошибка ИИ 😢")

# ===== ГОЛОС =====
@bot.message_handler(func=lambda m: m.text == "🎤 Голос")
def voice_mode(message):
    bot.send_message(message.chat.id, "Напиши текст с ! в начале\nПример: !Привет")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("!"))
def voice(message):
    uid = message.from_user.id
    text = message.text[1:]

    lang = detect_lang(text)

    tts = gTTS(text=text, lang=lang)
    file = "voice.mp3"
    tts.save(file)

    with open(file,"rb") as f:
        bot.send_voice(uid, f)

    os.remove(file)

# ===== ПРЕМИУМ =====
@bot.message_handler(func=lambda m: m.text == "💎 Премиум")
def premium(message):
    bot.send_message(message.chat.id,
        "💎 Премиум\nПереведи 1000₸ на Kaspi\n87000000000\nПосле: /pay 1234")

@bot.message_handler(commands=['pay'])
def pay(message):
    uid = message.from_user.id
    cursor.execute("UPDATE users SET premium=1 WHERE user_id=?", (uid,))
    conn.commit()

    bot.send_message(uid, "Премиум активирован 🚀")

# ===== СТАТИСТИКА =====
@bot.message_handler(func=lambda m: m.text == "📊 Статистика")
def stats(message):
    uid = message.from_user.id
    cursor.execute("SELECT best_score FROM users WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    best = row[0] if row else 0
    bot.send_message(uid, f"Лучший результат: {best}")

# ===== ТОП =====
@bot.message_handler(func=lambda m: m.text == "🏆 Топ")
def top(message):
    cursor.execute("SELECT best_score FROM users ORDER BY best_score DESC LIMIT 5")
    rows = cursor.fetchall()

    text = "🏆 ТОП:\n"
    for i,r in enumerate(rows,1):
        text += f"{i}. {r[0]}\n"

    bot.send_message(message.chat.id, text)

# ===== ЗАПУСК =====
print("Бот запущен 🚀")
bot.infinity_polling()