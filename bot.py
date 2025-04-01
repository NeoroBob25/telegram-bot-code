import os
import sys
import json
import sqlite3
import urllib.parse
import asyncio
import requests
from aiogram import Bot, Dispatcher, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import uvicorn
from fastapi import FastAPI

# Налаштування
TOKEN = "8097225217:AAERSuN5K68msP6JZzpSG9NR7XiDTeXBH6Y"  # Перевір, чи це твій токен
ADMIN_ID = 385298897  # Перевір, чи це твій Telegram ID
ALLOWED_USERS = [385298897, 666567798]  # Дозволені користувачі
CODE_UPDATE_URL = "https://raw.githubusercontent.com/bohdan123/telegram-bot-code/main/bot.py"  # Перевір, чи це правильний URL твого репозиторію

# Шлях до бази даних
DB_PATH = "/data/bot.db" if os.getenv("FLY_APP_NAME") else "bot.db"

# Ініціалізація FastAPI
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Bot is running"}

# Ініціалізація бота
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)
router = Router()

# Класи для станів
class SetTrainings(StatesGroup):
    new_trainings = State()

class AddClientData(StatesGroup):
    name = State()
    price = State()
    category = State()

# Ініціалізація бази даних
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Таблиця для клієнтів (існуюча)
        c.execute('''CREATE TABLE IF NOT EXISTS clients
                     (user_id INTEGER, client_name TEXT, trainings INTEGER, contact TEXT, profile TEXT, archive TEXT)''')
        # Таблиця для членів (існуюча)
        c.execute('''CREATE TABLE IF NOT EXISTS members
                     (user_id INTEGER PRIMARY KEY, chat_id INTEGER, interacted INTEGER, role TEXT)''')
        # Нова таблиця для даних клієнтів (персональні та групові тренування)
        c.execute('''CREATE TABLE IF NOT EXISTS client_data
                     (user_id INTEGER, client_name TEXT, category TEXT, price INTEGER, trainings INTEGER, total_earnings INTEGER)''')
        conn.commit()
        conn.close()
        print("База даних ініціалізована успішно.")
    except sqlite3.Error as e:
        print(f"Помилка ініціалізації бази даних: {e}")

init_db()

# Функції для роботи з базою даних
def load_clients(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT client_name, trainings, contact, profile, archive FROM clients WHERE user_id = ?", (user_id,))
        clients = {}
        for row in c.fetchall():
            client_name, trainings, contact, profile, archive = row
            clients[client_name] = {
                "trainings": trainings,
                "contact": contact,
                "profile": profile,
                "archive": archive
            }
        conn.close()
        return clients
    except sqlite3.Error as e:
        print(f"Помилка завантаження клієнтів: {e}")
        return {}

def save_client(user_id, client_name, client_data):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO clients (user_id, client_name, trainings, contact, profile, archive)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user_id, client_name, client_data["trainings"], client_data.get("contact", ""),
                   client_data.get("profile", ""), client_data.get("archive", "")))
        conn.commit()
        conn.close()
        print(f"Клієнт {client_name} збережено для user_id={user_id}")
    except sqlite3.Error as e:
        print(f"Помилка збереження клієнта: {e}")

def load_members():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id, chat_id, interacted, role FROM members")
        members = {}
        for row in c.fetchall():
            user_id, chat_id, interacted, role = row
            members[user_id] = {
                "chat_id": chat_id,
                "interacted": bool(interacted),
                "role": role
            }
        conn.close()
        return members
    except sqlite3.Error as e:
        print(f"Помилка завантаження членів: {e}")
        return {}

def save_member(user_id, member_data):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO members (user_id, chat_id, interacted, role)
                     VALUES (?, ?, ?, ?)''',
                  (user_id, member_data["chat_id"], int(member_data["interacted"]), member_data.get("role", "user")))
        conn.commit()
        conn.close()
        print(f"Член {user_id} збережено.")
    except sqlite3.Error as e:
        print(f"Помилка збереження члена: {e}")

def load_client_data(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT client_name, category, price, trainings, total_earnings FROM client_data WHERE user_id = ?", (user_id,))
        client_data = {}
        for row in c.fetchall():
            client_name, category, price, trainings, total_earnings = row
            if client_name not in client_data:
                client_data[client_name] = {}
            client_data[client_name][category] = {
                "price": price,
                "trainings": trainings,
                "total_earnings": total_earnings
            }
        conn.close()
        return client_data
    except sqlite3.Error as e:
        print(f"Помилка завантаження даних клієнтів: {e}")
        return {}

def save_client_data(user_id, client_name, category, data):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO client_data (user_id, client_name, category, price, trainings, total_earnings)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (user_id, client_name, category, data["price"], data["trainings"], data["total_earnings"]))
        conn.commit()
        conn.close()
        print(f"Дані клієнта {client_name} ({category}) збережено для user_id={user_id}")
    except sqlite3.Error as e:
        print(f"Помилка збереження даних клієнта: {e}")

def calculate_monthly_earnings(user_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT category, total_earnings FROM client_data WHERE user_id = ?", (user_id,))
        earnings = {"personal": 0, "group": 0}
        for row in c.fetchall():
            category, total_earnings = row
            if category == "personal":
                earnings["personal"] += total_earnings
            elif category == "group":
                earnings["group"] += total_earnings
        conn.close()
        return earnings
    except sqlite3.Error as e:
        print(f"Помилка підрахунку заробітку: {e}")
        return {"personal": 0, "group": 0}

# Обробники
@router.message(Command("start"))
async def handle_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    chat_id = message.chat.id

    print(f"User ID: {user_id}, Chat ID: {chat_id}, Username: {username}")
    members = load_members()
    if user_id in ALLOWED_USERS:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Додати клієнта")],
                [KeyboardButton(text="Перегляд клієнтів")],
                [KeyboardButton(text="Данні клієнтівℹ️")],
                [KeyboardButton(text="Відкрити доступ для іншого тренера/юзера")],
            ],
            resize_keyboard=True
        )
        await message.answer("Вітаю, Богдане! Ось доступні дії:", reply_markup=keyboard)
        if user_id not in members:
            members[user_id] = {"chat_id": chat_id, "interacted": True, "role": "admin"}
            save_member(user_id, members[user_id])
    elif user_id in members and members[user_id].get("role") == "trainer":
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Додати клієнта")],
                [KeyboardButton(text="Перегляд клієнтів")],
                [KeyboardButton(text="Данні клієнтівℹ️")],
            ],
            resize_keyboard=True
        )
        await message.answer(f"Вітаю, {username}! Ось доступні дії:", reply_markup=keyboard)
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Дізнатися більше")]],
            resize_keyboard=True
        )
        await message.answer("Вітаю! Я бот для тренерів. Якщо у вас є доступ, я допоможу вам керувати клієнтами.", reply_markup=keyboard)
        if user_id not in members:
            members[user_id] = {"chat_id": chat_id, "interacted": True, "role": "user"}
            save_member(user_id, members[user_id])

@router.message(lambda message: message.text == "Дізнатися більше")
async def learn_more(message: Message):
    user_id = message.from_user.id
    members = load_members()
    if user_id in members and members[user_id].get("role") == "trainer":
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Додати клієнта")],
                [KeyboardButton(text="Перегляд клієнтів")],
                [KeyboardButton(text="Данні клієнтівℹ️")],
            ],
            resize_keyboard=True
        )
        await message.answer("Ви тренер! Ось доступні дії:", reply_markup=keyboard)
    else:
        await message.answer("Щоб отримати доступ, зверніться до адміністратора.")

@router.message(lambda message: message.text == "Додати клієнта")
async def add_client(message: Message, state: FSMContext):
    user_id = message.from_user.id
    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await message.answer("Ви не маєте прав для цієї дії!")
        return
    await message.answer("Введіть ім'я клієнта:")
    await state.set_state("add_client_name")

@router.message(state="add_client_name")
async def process_client_name(message: Message, state: FSMContext):
    client_name = message.text.strip()
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    user_clients[client_name] = {"trainings": 0, "contact": "", "profile": "", "archive": ""}
    save_client(user_id, client_name, user_clients[client_name])
    await message.answer(f"Клієнта {client_name} додано!")
    await state.clear()

@router.message(lambda message: message.text == "Перегляд клієнтів")
async def view_clients(message: Message):
    user_id = message.from_user.id
    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await message.answer("Ви не маєте прав для цієї дії!")
        return

    user_clients = load_clients(user_id)
    if not user_clients:
        await message.answer("У вас немає клієнтів. Додайте нового клієнта через 'Додати клієнта'.")
        return

    for name, data in user_clients.items():
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ +1", callback_data=f"add_training_{user_id}_{urllib.parse.quote(name)}"),
             InlineKeyboardButton(text="📝 Змінити кількість", callback_data=f"set_trainings_{user_id}_{urllib.parse.quote(name)}")],
            [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_client_{user_id}_{urllib.parse.quote(name)}")]
        ])
        await message.answer(f"Клієнт: {name}\nТренувань: {data['trainings']}", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith("add_training_"))
async def add_training(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_", 2)
        user_id = int(parts[1])
        name = urllib.parse.unquote(parts[2])
    except (ValueError, IndexError) as e:
        print(f"Помилка при розборі callback.data: {e}")
        await callback.answer("Помилка обробки запиту. Спробуй ще раз.", show_alert=True)
        return

    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    user_clients = load_clients(user_id)
    if name not in user_clients:
        await callback.answer("Клієнта не знайдено!")
        return

    user_clients[name]["trainings"] = user_clients[name].get("trainings", 0) + 1
    save_client(user_id, name, user_clients[name])
    await callback.message.edit_text(f"Клієнт: {name}\nТренувань: {user_clients[name]['trainings']}",
                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                        [InlineKeyboardButton(text="➡️ +1", callback_data=f"add_training_{user_id}_{urllib.parse.quote(name)}"),
                                         InlineKeyboardButton(text="📝 Змінити кількість", callback_data=f"set_trainings_{user_id}_{urllib.parse.quote(name)}")],
                                        [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_client_{user_id}_{urllib.parse.quote(name)}")]
                                    ]))
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("set_trainings_"))
async def set_trainings(callback: types.CallbackQuery, state: FSMContext):
    print(f"Отримано callback для set_trainings: {callback.data}")
    try:
        parts = callback.data.split("_", 2)
        if len(parts) != 3 or parts[0] != "set_trainings":
            raise ValueError(f"Неправильний формат callback.data: {callback.data}")
        user_id = int(parts[1])
        name = urllib.parse.unquote(parts[2])
    except (ValueError, IndexError) as e:
        print(f"Помилка при розборі callback.data: {e}")
        await callback.answer("Помилка обробки запиту. Спробуй ще раз.", show_alert=True)
        return

    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    user_clients = load_clients(user_id)
    if name not in user_clients:
        await callback.answer("Клієнта не знайдено!")
        return

    await state.update_data(user_id=user_id, name=name)
    print(f"Збережено в стані: user_id={user_id}, name={name}")
    await state.set_state(SetTrainings.new_trainings)
    print(f"Перейшли в стан SetTrainings.new_trainings для {name}")
    await callback.message.edit_text(f"Введіть нову кількість тренувань для {name} (число):", reply_markup=None)
    await callback.answer()

@router.message(SetTrainings.new_trainings, lambda message: message.text.isdigit())
async def process_new_trainings(message: Message, state: FSMContext):
    print(f"Отримано повідомлення в стані SetTrainings.new_trainings: {message.text}")
    data = await state.get_data()
    user_id = data["user_id"]
    name = data["name"]
    print(f"Дані зі стану: user_id={user_id}, name={name}")
    user_clients = load_clients(user_id)
    try:
        new_trainings = int(message.text)
        if new_trainings < 0:
            raise ValueError
        user_clients[name]["trainings"] = new_trainings
        save_client(user_id, name, user_clients[name])
        await message.answer(f"Кількість тренувань для {name} змінено на {new_trainings}.")
    except ValueError:
        await message.answer("Будь ласка, введіть додатне число!")
    await state.clear()

@router.message(SetTrainings.new_trainings)
async def process_new_trainings_invalid(message: Message, state: FSMContext):
    await message.answer("Будь ласка, введіть число!")

@router.callback_query(lambda c: c.data.startswith("delete_client_"))
async def delete_client(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_", 2)
        user_id = int(parts[1])
        name = urllib.parse.unquote(parts[2])
    except (ValueError, IndexError) as e:
        print(f"Помилка при розборі callback.data: {e}")
        await callback.answer("Помилка обробки запиту. Спробуй ще раз.", show_alert=True)
        return

    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM clients WHERE user_id = ? AND client_name = ?", (user_id, name))
        conn.commit()
        conn.close()
        await callback.message.delete()
        await callback.answer(f"Клієнта {name} видалено.")
    except sqlite3.Error as e:
        print(f"Помилка видалення клієнта: {e}")
        await callback.answer("Помилка при видаленні клієнта.", show_alert=True)

@router.message(lambda message: message.text == "Відкрити доступ для іншого тренера/юзера")
async def open_access(message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.answer("Ви не маєте прав для цієї дії!")
        return
    await message.answer("Введіть Telegram ID користувача, якому хочете відкрити доступ:")

@router.message(lambda message: message.text.isdigit())
async def process_access(message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.answer("Ви не маєте прав для цієї дії!")
        return

    new_user_id = int(message.text)
    members = load_members()
    if new_user_id in members:
        members[new_user_id]["role"] = "trainer"
        save_member(new_user_id, members[new_user_id])
        await message.answer(f"Користувачу з ID {new_user_id} надано права тренера.")
    else:
        await message.answer(f"Користувач з ID {new_user_id} ще не взаємодіяв з ботом.")

@router.message(Command("update"))
async def update_code(message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.answer("Ви не маєте прав для цієї дії.")
        return

    try:
        print(f"Завантажуємо код із {CODE_UPDATE_URL}")
        response = requests.get(CODE_UPDATE_URL)
        response.raise_for_status()  # Перевіряємо, чи запит успішний
        if response.status_code != 200:
            await message.answer(f"Помилка завантаження коду: {response.status_code}")
            return

        new_code = response.text

        # Зберігаємо новий код у основний файл bot.py
        bot_file_path = "bot.py"
        print(f"Зберігаємо новий код у {bot_file_path}")
        with open(bot_file_path, "w", encoding="utf-8") as f:
            f.write(new_code)

        await message.answer("Бот успішно оновлено! Зачекай кілька секунд і виконай /start для перевірки.")
        # Завершуємо процес, щоб Fly.io перезапустив бота
        print("Завершуємо процес для перезапуску...")
        os._exit(0)  # Примусово завершуємо процес
    except requests.exceptions.RequestException as e:
        print(f"Помилка при завантаженні коду: {e}")
        await message.answer(f"Помилка при заванталенні коду: {str(e)}")
    except Exception as e:
        print(f"Помилка при оновленні: {str(e)}")
        await message.answer(f"Помилка при оновленні: {str(e)}")

# Новий розділ "Данні клієнтівℹ️"
@router.message(lambda message: message.text == "Данні клієнтівℹ️")
async def client_data_menu(message: Message):
    user_id = message.from_user.id
    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await message.answer("Ви не маєте прав для цієї дії!")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Додати тренування", callback_data=f"add_client_data_{user_id}")],
        [InlineKeyboardButton(text="Переглянути персональні", callback_data=f"view_personal_{user_id}")],
        [InlineKeyboardButton(text="Переглянути групові", callback_data=f"view_group_{user_id}")],
        [InlineKeyboardButton(text="Підсумок за місяць", callback_data=f"monthly_earnings_{user_id}")]
    ])
    await message.answer("Розділ 'Данні клієнтівℹ️':", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith("add_client_data_"))
async def add_client_data(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[3])
    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    await state.update_data(user_id=user_id)
    await state.set_state(AddClientData.name)
    await callback.message.edit_text("Введіть ім'я клієнта:", reply_markup=None)
    await callback.answer()

@router.message(AddClientData.name)
async def process_client_data_name(message: Message, state: FSMContext):
    client_name = message.text.strip()
    await state.update_data(name=client_name)
    await state.set_state(AddClientData.price)
    await message.answer("Введіть ціну за одне тренування (у грн, наприклад, 400):")

@router.message(AddClientData.price, lambda message: message.text.isdigit())
async def process_client_data_price(message: Message, state: FSMContext):
    price = int(message.text)
    if price <= 0:
        await message.answer("Ціна має бути додатним числом!")
        return
    await state.update_data(price=price)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Персональні", callback_data="category_personal")],
        [InlineKeyboardButton(text="Групові", callback_data="category_group")]
    ])
    await state.set_state(AddClientData.category)
    await message.answer("Оберіть категорію:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data.startswith("category_"))
async def process_client_data_category(callback: types.CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[1]
    data = await state.get_data()
    user_id = data["user_id"]
    client_name = data["name"]
    price = data["price"]

    client_data = load_client_data(user_id)
    if client_name not in client_data:
        client_data[client_name] = {}
    client_data[client_name][category] = {
        "price": price,
        "trainings": 0,
        "total_earnings": 0
    }
    save_client_data(user_id, client_name, category, client_data[client_name][category])
    await callback.message.edit_text(f"Клієнт {client_name} додано до категорії '{category}' з ціною {price} грн.")
    await state.clear()
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("view_personal_"))
async def view_personal_trainings(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    client_data = load_client_data(user_id)
    if not client_data:
        await callback.message.edit_text("Немає даних про клієнтів.")
        return

    found = False
    for client_name, categories in client_data.items():
        if "personal" in categories:
            found = True
            data = categories["personal"]
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ -1", callback_data=f"decrease_training_{user_id}_{urllib.parse.quote(client_name)}_personal"),
                 InlineKeyboardButton(text="➡️ +1", callback_data=f"increase_training_{user_id}_{urllib.parse.quote(client_name)}_personal")],
                [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_client_data_{user_id}_{urllib.parse.quote(client_name)}_personal")]
            ])
            await callback.message.answer(
                f"Клієнт: {client_name}\nКатегорія: Персональні\nТренувань: {data['trainings']}\nЦіна за тренування: {data['price']} грн\nЗагальний заробіток: {data['total_earnings']} грн",
                reply_markup=keyboard
            )
    if not found:
        await callback.message.edit_text("Немає персональних тренувань.")
    else:
        await callback.message.delete()
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("view_group_"))
async def view_group_trainings(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    client_data = load_client_data(user_id)
    if not client_data:
        await callback.message.edit_text("Немає даних про клієнтів.")
        return

    found = False
    for client_name, categories in client_data.items():
        if "group" in categories:
            found = True
            data = categories["group"]
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ -1", callback_data=f"decrease_training_{user_id}_{urllib.parse.quote(client_name)}_group"),
                 InlineKeyboardButton(text="➡️ +1", callback_data=f"increase_training_{user_id}_{urllib.parse.quote(client_name)}_group")],
                [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_client_data_{user_id}_{urllib.parse.quote(client_name)}_group")]
            ])
            await callback.message.answer(
                f"Клієнт: {client_name}\nКатегорія: Групові\nТренувань: {data['trainings']}\nЦіна за тренування: {data['price']} грн\nЗагальний заробіток: {data['total_earnings']} грн",
                reply_markup=keyboard
            )
    if not found:
        await callback.message.edit_text("Немає групових тренувань.")
    else:
        await callback.message.delete()
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("increase_training_"))
async def increase_training(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_", 3)
        user_id = int(parts[2])
        client_name = urllib.parse.unquote(parts[3])
        category = parts[4]
    except (ValueError, IndexError) as e:
        print(f"Помилка при розборі callback.data: {e}")
        await callback.answer("Помилка обробки запиту. Спробуй ще раз.", show_alert=True)
        return

    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    client_data = load_client_data(user_id)
    if client_name not in client_data or category not in client_data[client_name]:
        await callback.answer("Клієнта не знайдено!")
        return

    data = client_data[client_name][category]
    data["trainings"] += 1
    data["total_earnings"] = data["trainings"] * data["price"]
    save_client_data(user_id, client_name, category, data)
    await callback.message.edit_text(
        f"Клієнт: {client_name}\nКатегорія: {category}\nТренувань: {data['trainings']}\nЦіна за тренування: {data['price']} грн\nЗагальний заробіток: {data['total_earnings']} грн",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ -1", callback_data=f"decrease_training_{user_id}_{urllib.parse.quote(client_name)}_{category}"),
             InlineKeyboardButton(text="➡️ +1", callback_data=f"increase_training_{user_id}_{urllib.parse.quote(client_name)}_{category}")],
            [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_client_data_{user_id}_{urllib.parse.quote(client_name)}_{category}")]
        ])
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("decrease_training_"))
async def decrease_training(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_", 3)
        user_id = int(parts[2])
        client_name = urllib.parse.unquote(parts[3])
        category = parts[4]
    except (ValueError, IndexError) as e:
        print(f"Помилка при розборі callback.data: {e}")
        await callback.answer("Помилка обробки запиту. Спробуй ще раз.", show_alert=True)
        return

    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    client_data = load_client_data(user_id)
    if client_name not in client_data or category not in client_data[client_name]:
        await callback.answer("Клієнта не знайдено!")
        return

    data = client_data[client_name][category]
    if data["trainings"] <= 0:
        await callback.answer("Кількість тренувань не може бути меншою за 0!")
        return

    data["trainings"] -= 1
    data["total_earnings"] = data["trainings"] * data["price"]
    save_client_data(user_id, client_name, category, data)
    await callback.message.edit_text(
        f"Клієнт: {client_name}\nКатегорія: {category}\nТренувань: {data['trainings']}\nЦіна за тренування: {data['price']} грн\nЗагальний заробіток: {data['total_earnings']} грн",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ -1", callback_data=f"decrease_training_{user_id}_{urllib.parse.quote(client_name)}_{category}"),
             InlineKeyboardButton(text="➡️ +1", callback_data=f"increase_training_{user_id}_{urllib.parse.quote(client_name)}_{category}")],
            [InlineKeyboardButton(text="🗑️ Видалити", callback_data=f"delete_client_data_{user_id}_{urllib.parse.quote(client_name)}_{category}")]
        ])
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("delete_client_data_"))
async def delete_client_data(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_", 3)
        user_id = int(parts[2])
        client_name = urllib.parse.unquote(parts[3])
        category = parts[4]
    except (ValueError, IndexError) as e:
        print(f"Помилка при розборі callback.data: {e}")
        await callback.answer("Помилка обробки запиту. Спробуй ще раз.", show_alert=True)
        return

    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM client_data WHERE user_id = ? AND client_name = ? AND category = ?", (user_id, client_name, category))
        conn.commit()
        conn.close()
        await callback.message.delete()
        await callback.answer(f"Дані клієнта {client_name} ({category}) видалено.")
    except sqlite3.Error as e:
        print(f"Помилка видалення даних клієнта: {e}")
        await callback.answer("Помилка при видаленні даних.", show_alert=True)

@router.callback_query(lambda c: c.data.startswith("monthly_earnings_"))
async def monthly_earnings(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    members = load_members()
    if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
        await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
        return

    earnings = calculate_monthly_earnings(user_id)
    total = earnings["personal"] + earnings["group"]
    await callback.message.edit_text(
        f"Підсумок за місяць:\nПерсональні тренування: {earnings['personal']} грн\nГрупові тренування: {earnings['group']} грн\nЗагальний заробіток: {total} грн"
    )
    await callback.answer()

# Реєстрація обробників
def register_handlers():
    router.message.register(handle_start, Command("start"))
    router.message.register(update_code, Command("update"))
    # Додай інші обробники, якщо потрібно

# Головна функція
async def main():
    print("Починаємо ініціалізацію бота...")
    dp.include_router(router)
    try:
        print("Видаляємо вебхук...")
        await bot.delete_webhook(drop_pending_updates=True)
        print("Вебхук видалено успішно.")
    except Exception as e:
        print(f"Помилка при видаленні вебхука: {e}")
        raise
    print("Запускаємо polling у фоновому режимі...")
    asyncio.create_task(dp.start_polling(bot))
    print("Polling запущено.")

if __name__ == "__main__":
    print("Запускаємо бота...")
    try:
        # Запускаємо FastAPI-сервер на порту 8080
        config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
        server = uvicorn.Server(config)
        asyncio.run(server.serve())
    except Exception as e:
        print(f"Помилка при запуску бота: {e}")
