import os
import json
import logging
import re
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

API_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

DATA_FILE = "users.json"

client = OpenAI(api_key=OPENAI_KEY)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ===== STORAGE =====

def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = load_users()

def get_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "lang": "ru",
            "subject": None,
            "topic": None,
            "level": "easy",
            "correct": 0,
            "wrong": 0,
            "history": [],
            "last_q": None,
            "busy": False
        }
    return users[uid]


# ===== UI =====

def t(u, ru, kz):
    return kz if u.get("lang") == "kz" else ru

def kb_main(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"📚 Предметы","📚 Пәндер"),
           t(u,"🧠 Тренировка","🧠 Жаттығу"))
    kb.add(t(u,"📊 Статистика","📊 Статистика"),
       t(u,"💳 Доступ","💳 Қолжетімділік"))

    kb.add(t(u,"🌐 Язык","🌐 Тіл"))
    
    return kb

def kb_subjects(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика","История")
    kb.add("География","Биология")
    kb.add("⬅️ Назад")
    return kb

def kb_topics(subject):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    data = {
        "Математика": ["Алгебра","Геометрия","Проценты","Логарифмы"],
        "История": ["Казахстан","Мировая","Даты","Персоны"],
        "География": ["Климат","Страны","Ресурсы","Карты"],
        "Биология": ["Клетка","Генетика","Анатомия","Экология"]
    }
    for tpc in data.get(subject, []):
        kb.add(tpc)
    kb.add("⬅️ Назад")
    return kb

def kb_level():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий","🟡 Средний","🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def kb_answers():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

def kb_lang():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский","Қазақша")
    kb.add("⬅️ Назад")
    return kb

# ===== HELPERS =====

def clean(text):
    if not text:
        return ""
    text = re.sub(r"\\frac\{(.+?)\}\{(.+?)\}", r"(\1/\2)", text)
    text = text.replace("\\(", "").replace("\\)", "")
    return text.strip()

def parse(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    q = ""
    opts = []

    for l in lines:
        if re.match(r"^(Вопрос|Сұрақ)", l):
            q = l
        if re.match(r"^[A-D]\)", l):
            opts.append(l)

    correct_match = re.search(r"(Ответ|Жауап)\s*:\s*([A-D])", text)
    correct_letter = correct_match.group(2) if correct_match else None

    # фикс: гарантируем корректность
    if correct_letter not in ["A","B","C","D"]:
        correct_letter = None

    expl = re.search(r"(Объяснение|Түсіндіру)\s*:\s*(.+)", text, re.DOTALL)

    return {
        "q": q or (lines[0] if lines else ""),
        "opts": opts[:4],
        "correct": correct_letter,
        "expl": expl.group(2).strip() if expl else ""
    }

# ===== AI =====

def build_prompt(u):
    if u["lang"] == "kz":
        return f"""
Тек қазақ тілінде.

Пән: {u['subject']}
Тақырып: {u['topic']}
Деңгей: {u['level']}

⚠️ Басқа пәнге өтпе.

Сұрақ: ...
A) ...
B) ...
C) ...
D) ...
Жауап: A
Түсіндіру: ...
"""
    else:
        return f"""
Только русский язык.

Предмет: {u['subject']}
Тема: {u['topic']}
Сложность: {u['level']}

⚠️ НЕ смешивай предметы.

Вопрос: ...
A) ...
B) ...
C) ...
D) ...
Ответ: A
Объяснение: ...
"""

async def gen(u):
    for _ in range(5):
        try:
            r = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": build_prompt(u)}]
            )
            q = parse(r.choices[0].message.content)

            if len(q["opts"]) == 4 and q["correct"]:
                return q

        except Exception as e:
            print("GEN ERR:", e)

    raise Exception("fail")

# ===== HANDLERS =====

@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    u = get_user(m.from_user.id)
    await m.answer(t(u,"👋 Добро пожаловать","👋 Қош келдіңіз"),
                   reply_markup=kb_main(u))

@dp.message_handler(lambda m: "Назад" in m.text)
async def back(m):
    u = get_user(m.from_user.id)
    await m.answer("Меню", reply_markup=kb_main(u))

@dp.message_handler(lambda m: "Язык" in m.text or "Тіл" in m.text)
async def lang(m):
    u=get_user(m.from_user.id)
    await m.answer(t(u,"Выбери язык","Тілді таңда"),
                   reply_markup=kb_lang())

@dp.message_handler(lambda m: m.text in ["Русский","Қазақша"])
async def set_lang(m):
    u=get_user(m.from_user.id)
    u["lang"]="kz" if m.text=="Қазақша" else "ru"
    save_users(users)
    await m.answer("OK",reply_markup=kb_main(u))

@dp.message_handler(lambda m:"Предмет" in m.text or "Пән" in m.text)
async def subjects(m):
    u=get_user(m.from_user.id)
    await m.answer(t(u,"Выбери предмет","Пәнді таңда"),
                   reply_markup=kb_subjects(u))

@dp.message_handler(lambda m:m.text in ["Математика","История","География","Биология"])
async def set_sub(m):
    u=get_user(m.from_user.id)
    u["subject"]=m.text
    u["topic"]=None  # фикс перемешки
    save_users(users)
    await m.answer("Выбери тему",reply_markup=kb_topics(m.text))

@dp.message_handler(lambda m:m.text in [
"Алгебра","Геометрия","Проценты","Логарифмы",
"Казахстан","Мировая","Даты","Персоны",
"Климат","Страны","Ресурсы","Карты",
"Клетка","Генетика","Анатомия","Экология"])
async def set_topic(m):
    u=get_user(m.from_user.id)
    u["topic"]=m.text
    save_users(users)
    await m.answer("Выбери сложность",reply_markup=kb_level())

@dp.message_handler(lambda m:"Легкий" in m.text or "Жеңіл" in m.text)
async def lvl1(m):
    u=get_user(m.from_user.id)
    u["level"]="easy"
    await ask(m)

@dp.message_handler(lambda m:"Средний" in m.text)
async def lvl2(m):
    u=get_user(m.from_user.id)
    u["level"]="medium"
    await ask(m)

@dp.message_handler(lambda m:"Сложный" in m.text)
async def lvl3(m):
    u=get_user(m.from_user.id)
    u["level"]="hard"
    await ask(m)

async def ask(m):
    u=get_user(m.from_user.id)

    msg=await m.answer("⏳")
    try:
        q=await gen(u)
    except:
        await msg.edit_text("Ошибка генерации")
        return

    await msg.delete()

    u["last_q"]=q
    save_users(users)

    text=f"{clean(q['q'])}\n\n"+"\n".join(q["opts"])
    await m.answer(text,reply_markup=kb_answers())

@dp.message_handler(lambda m:m.text in ["A","B","C","D"])
async def ans(m):
    u=get_user(m.from_user.id)
    q=u.get("last_q")
    if not q:
        return

    ok = m.text == q["correct"]

lang = u.get("lang","ru")

if ok:
    u["correct"] += 1
    if lang == "kz":
        await m.answer("✅ Дұрыс")
    else:
        await m.answer("✅ Правильно")
else:
    u["wrong"] += 1
    if lang == "kz":
        await m.answer(f"❌ Дұрыс жауап: {q['correct']}")
    else:
        await m.answer(f"❌ Правильный ответ: {q['correct']}")

    await m.answer(clean(q["expl"]))
    save_users(users)

    await ask(m)

@dp.message_handler(lambda m: "Доступ" in m.text or "Қолжетімділік" in m.text)
async def pay(m):
    u = get_user(m.from_user.id)

    text = (
        "💳 Оплата\n"
        "Бауыpжан\n"
        "@Bautest_pedagog\n"
        "503301815\n\n"
        "После оплаты нажми 'Я оплатил'"
    )

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Я оплатил")
    kb.add("⬅️ Назад")

    await m.answer(text, reply_markup=kb)

@dp.message_handler(lambda m: m.text == "Я оплатил")
async def paid(m):
    user_id = m.from_user.id
    username = m.from_user.username
    name = m.from_user.full_name

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней", "30 дней")
    kb.add("❌ Отказать")

    text = (
        f"💳 Оплата\n"
        f"{name}\n"
        f"@{username}\n"
        f"{user_id}"
    )

    await bot.send_message(ADMIN_ID, text, reply_markup=kb)
    await m.answer("⏳ Заявка отправлена")

@dp.message_handler(lambda m: m.text in ["7 дней","30 дней","❌ Отказать"])
async def admin_action(m):
    if m.from_user.id != ADMIN_ID:
        return

    # получаем последнее сообщение (где был user_id)
    text = m.reply_to_message.text if m.reply_to_message else ""

    user_id = None
    for line in text.split("\n"):
        if line.isdigit():
            user_id = int(line)

    if not user_id:
        return

    if m.text == "❌ Отказать":
        await bot.send_message(user_id, "❌ Оплата отклонена")
        return

    days = 7 if "7" in m.text else 30

    u = get_user(user_id)
    u["paid_until"] = days  # пока просто сохраняем

    save_users(users)

    await bot.send_message(user_id, f"✅ Доступ открыт на {days} дней")

@dp.message_handler(lambda m: "Статистика" in m.text)
async def stats(m):
    u = get_user(m.from_user.id)
    lang = u.get("lang","ru")

    if lang == "kz":
        text = f"📊\nДұрыс: {u['correct']}\nҚате: {u['wrong']}"
    else:
        text = f"📊\nПравильно: {u['correct']}\nОшибок: {u['wrong']}"

    await m.answer(text)

# ===== RUN =====

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
