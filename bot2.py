import os
import json
import logging
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor

API_TOKEN = os.getenv("BOT_TOKEN")

# ⚠️ РЕКВИЗИТЫ ТЕПЕРЬ ЧЕРЕЗ ENV
KASPI = os.getenv("KASPI_CARD")  # пример: 4400....
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DATA_FILE = "users.json"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ===== БАЗА =====

QUESTIONS = {
    "Математика": {
        "Алгебра": [
            {"q":"2+2=?","opts":["A) 3","B) 4","C) 5","D) 6"],"correct":"B","expl":"2+2=4"},
            {"q":"5*3=?","opts":["A)15","B)10","C)8","D)20"],"correct":"A","expl":"5×3=15"}
        ]
    },
    "История": {
        "Казахстан": [
            {"q":"Год независимости Казахстана?","opts":["A)1989","B)1991","C)2000","D)1985"],"correct":"B","expl":"1991 год"}
        ]
    }
}

# ===== STORAGE =====

def load_users():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE,"r",encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

users = load_users()

def get_user(uid):
    uid=str(uid)
    if uid not in users:
        users[uid]={
            "lang":"ru",
            "subject":None,
            "topic":None,
            "correct":0,
            "wrong":0,
            "history":[],
            "last_q":None,
            "paid":False,
            "limit":10
        }
    return users[uid]

# ===== TEXT =====

def t(u,ru,kz):
    return kz if u["lang"]=="kz" else ru

# ===== UI =====

def kb_main(u):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📚 "+t(u,"Предметы","Пәндер"))
    kb.add("🧠 "+t(u,"Тренировка","Жаттығу"))
    kb.add("📊 "+t(u,"Статистика","Статистика"))
    kb.add("💳 "+t(u,"Доступ","Қолжетімділік"))
    kb.add("🌐 "+t(u,"Язык","Тіл"))
    return kb

def kb_answers():
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    return kb

# ===== АДАПТИВКА =====

def pick_question(u):
    s = u["subject"]
    tpc = u["topic"]

    pool = QUESTIONS.get(s, {}).get(tpc, [])
    if not pool:
        return None

    # убираем использованные
    unused = [q for q in pool if q["q"] not in u["used"]]

    if not unused:
        u["used"] = []  # сброс
        unused = pool

    q = random.choice(unused)

    u["used"].append(q["q"])

    return q

def gen_math():
    a = random.randint(2, 20)
    b = random.randint(2, 20)

    correct = a + b

    options = [
        correct,           
        correct + random.randint(1,5),
        correct - random.randint(1,3),
        correct + random.randint(6,10)
    ]

    random.shuffle(options)

    letters = ["A","B","C","D"]
    opts = [f"{letters[i]}) {options[i]}" for i in range(4)]

    correct_letter = letters[options.index(correct)]

    return {
        "q": f"{a} + {b} = ?",
        "opts": opts,
        "correct": correct_letter,
        "expl": f"{a} + {b} = {correct}"
    }

# ===== ЛОГИКА =====

@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    u=get_user(m.from_user.id)
    await m.answer(t(u,"Добро пожаловать","Қош келдіңіз"),reply_markup=kb_main(u))

@dp.message_handler(lambda m:"Язык" in m.text or "Тіл" in m.text)
async def lang(m):
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Русский","Қазақша")
    await m.answer("Выбери язык / Тілді таңда",reply_markup=kb)

@dp.message_handler(lambda m:m.text in ["Русский","Қазақша"])
async def set_lang(m):
    u=get_user(m.from_user.id)
    u["lang"]="kz" if "Қазақша" in m.text else "ru"
    save_users(users)
    await m.answer("OK",reply_markup=kb_main(u))

@dp.message_handler(lambda m:"Предмет" in m.text or "Пән" in m.text)
async def subjects(m):
    u=get_user(m.from_user.id)
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Математика","История")
    await m.answer(t(u,"Выбери предмет","Пән таңда"),reply_markup=kb)

@dp.message_handler(lambda m:m.text in ["Математика","История"])
async def set_subject(m):
    u=get_user(m.from_user.id)
    u["subject"]=m.text

    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    if m.text=="Математика":
        kb.add("Алгебра")
    if m.text=="История":
        kb.add("Казахстан")

    await m.answer("Выбери тему",reply_markup=kb)

@dp.message_handler(lambda m:m.text in ["Алгебра","Казахстан"])
async def set_topic(m):
    u=get_user(m.from_user.id)
    u["topic"]=m.text
    save_users(users)
    await ask(m)

async def ask(m):
    u=get_user(m.from_user.id)

    if not u["paid"] and (u["correct"]+u["wrong"])>=u["limit"]:
        await m.answer(t(u,
            f"🔒 Лимит достигнут. Оплата: {KASPI}",
            f"🔒 Лимит бітті. Төлем: {KASPI}"
        ))
        return

     if u["subject"] == "Математика":
        q = gen_math()
    else:
        q = pick_question(u)
        if not q:
        await m.answer("Нет вопросов")
         return

    u["last_q"]=q
    save_users(users)

    text=q["q"]+"\n\n"+"\n".join(q["opts"])
    await m.answer(text,reply_markup=kb_answers())

@dp.message_handler(lambda m:m.text in ["A","B","C","D"])
async def answer(m):
    u=get_user(m.from_user.id)
    q=u["last_q"]

    if not q:
        return

    ok=m.text==q["correct"]

    if ok:
        u["correct"]+=1
        await m.answer("✅")
    else:
        u["wrong"]+=1
        await m.answer(f"❌ {q['correct']}")

    await m.answer(q["expl"])

    u["history"].append({"topic":u["topic"],"ok":ok})
    save_users(users)

    await ask(m)

@dp.message_handler(lambda m:"Доступ" in m.text or "Қолжетімділік" in m.text)
async def access(m):
    u=get_user(m.from_user.id)
    await m.answer(t(u,
        f"Оплата Kaspi:\n{KASPI}\nПосле оплаты нажми 'Я оплатил'",
        f"Kaspi төлем:\n{KASPI}\nТөлеген соң 'Мен төледім'"
    ))

@dp.message_handler(lambda m:"оплатил" in m.text.lower() or "төледім" in m.text.lower())
async def paid(m):
    u=get_user(m.from_user.id)

    await bot.send_message(ADMIN_ID,
        f"Оплата от {m.from_user.id}"
    )

    await m.answer("⏳ Проверка...")

@dp.message_handler(lambda m:"Статистика" in m.text or "Статистика" in m.text)
async def stat(m):
    u=get_user(m.from_user.id)
    total=u["correct"]+u["wrong"]
    p=int(u["correct"]/total*100) if total else 0
    await m.answer(f"{u['correct']} / {u['wrong']} ({p}%)")

# ===== RUN =====

if __name__=="__main__":
    executor.start_polling(dp,skip_updates=True)
