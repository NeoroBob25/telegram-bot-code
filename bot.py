import os
import asyncio
import json
import urllib.parse
import re
from datetime import datetime
import sqlite3
import requests
import importlib
import sys
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

# Налаштування
TOKEN = "8097225217:AAERSuN5K68msP6JZzpSG9NR7XiDTeXBH6Y"  # Твій токен
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

ADMIN_ID = 385298897
ALLOWED_USERS = {ADMIN_ID}

# URL для оновлення коду (заміни на твій із GitHub)
CODE_UPDATE_URL = "https://raw.githubusercontent.com/твій_юзернейм/telegram-bot-code/main/bot.py"

# База даних (динамічний шлях для локального запуску і Fly.io)
DB_PATH = "/data/bot.db" if os.getenv("FLY_APP_NAME") else "bot.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS clients
                     (user_id INTEGER, client_name TEXT, trainings INTEGER, contact TEXT, profile TEXT, archive TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS members
                     (user_id INTEGER PRIMARY KEY, chat_id INTEGER, interacted INTEGER, role TEXT)''')
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Помилка ініціалізації бази даних: {e}")

def save_client(user_id, client_name, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO clients (user_id, client_name, trainings, contact, profile, archive) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, client_name, data.get('trainings', 0), data.get('contact', ''),
               json.dumps(data.get('profile', {})), json.dumps(data.get('progress_archive', []))))
    conn.commit()
    conn.close()

def load_clients(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT client_name, trainings, contact, profile, archive FROM clients WHERE user_id = ?", (user_id,))
    clients = {row[0]: {'trainings': row[1], 'contact': row[2], 'profile': json.loads(row[3]), 'progress_archive': json.loads(row[4])} for row in c.fetchall()}
    conn.close()
    return clients

def save_member(user_id, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO members (user_id, chat_id, interacted, role) VALUES (?, ?, ?, ?)",
              (user_id, data.get('chat_id'), int(data.get('interacted', 0)), data.get('role', '')))
    conn.commit()
    conn.close()

def load_members():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id, chat_id, interacted, role FROM members")
    members = {row[0]: {'chat_id': row[1], 'interacted': bool(row[2]), 'role': row[3]} for row in c.fetchall()}
    conn.close()
    return members

init_db()

def parse_body_params(params):
    if not params or params == "Не вказано":
        return {}
    measurements = {}
    pattern = r"(\w+):\s*(\d+\.?\d*)\s*(см|kg)?"
    matches = re.finditer(pattern, params)
    for match in matches:
        key, value, unit = match.groups()
        measurements[key] = float(value)
    return measurements

class AddClient(StatesGroup):
    name = State()
    trainings = State()
    contact = State()

class EditProfile(StatesGroup):
    weight = State()
    age = State()
    body_params = State()
    extra_info = State()
    photos = State()

class SetTrainings(StatesGroup):
    new_trainings = State()

class ManageAccess(StatesGroup):
    user_id = State()
    access_type = State()

# Команда /update
@router.message(Command("update"))
async def update_code(message: Message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.answer("Ви не маєте прав для цієї дії.")
        return

    try:
        response = requests.get(CODE_UPDATE_URL)
        if response.status_code != 200:
            await message.answer(f"Помилка завантаження коду: {response.status_code}")
            return

        new_code = response.text

        # Зберігаємо тимчасовий файл у правильному місці
        temp_file_path = "/data/bot_temp.py" if os.getenv("FLY_APP_NAME") else "bot_temp.py"
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(new_code)

        print("Починаємо перезавантаження модуля...")
        if "bot" in sys.modules:
            importlib.reload(sys.modules["bot"])
            print("Модуль перезавантажено.")
        else:
            importlib.import_module("bot")
            print("Модуль імпортовано.")

        global router, dp
        router = Router()
        dp.include_router(router)

        print("Реєструємо нові обробники...")
        register_handlers()
        print("Обробники зареєстровано.")

        await message.answer("Бот успішно оновлено! Зачекай кілька секунд і виконай /start для перевірки.")
        # Примусово перезапускаємо додаток на Fly.io
        os.system("flyctl apps restart telegram-bot-wild-frog-9619 &")
    except Exception as e:
        await message.answer(f"Помилка при оновленні: {str(e)}")

def register_handlers():
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
                ],
                resize_keyboard=True
            )
            await message.answer("Вітаю! Ось доступні дії для тренера:", reply_markup=keyboard)
        else:
            if user_id not in members or not members.get(user_id, {}).get("interacted", False):
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Так - стаю членом команди", callback_data=f"join_{user_id}")],
                    [InlineKeyboardButton(text="Ні, дякую", callback_data=f"decline_{user_id}")]
                ])
                await message.answer(
                    "Привіт, друже! Якщо маєш бажання приєднатися до команди підопічних Богдана, щоб я потім міг сповіщати тебе про кількість тренувань, тоді просто:",
                    reply_markup=keyboard
                )
                if user_id not in members:
                    members[user_id] = {"chat_id": chat_id, "interacted": False}
                else:
                    members[user_id]["interacted"] = False
                save_member(user_id, members[user_id])
            else:
                keyboard = ReplyKeyboardMarkup(
                    keyboard=[
                        [KeyboardButton(text="Перегляд моїх даних")],
                    ],
                    resize_keyboard=True
                )
                await message.answer("Вітаю! Ось доступні дії для тебе:", reply_markup=keyboard)

    @router.callback_query(lambda c: c.data.startswith("join_"))
    async def join_team(callback: types.CallbackQuery):
        print(f"Отримано callback для join_team: {callback.data}")
        user_id = int(callback.data.replace("join_", ""))
        if user_id == callback.from_user.id:
            username = callback.from_user.username or f"User_{user_id}"
            chat_id = callback.message.chat.id
            members = load_members()
            members[user_id] = {"chat_id": chat_id, "interacted": True}
            save_member(user_id, members[user_id])
            clients = load_clients(user_id)
            clients[username] = {"trainings": 0, "contact": f"@{username}" if username.startswith("User_") else f"@{username}"}
            save_client(user_id, username, clients[username])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            await callback.message.edit_text("Дякую! Ти успішно приєднався до команди Богдана.", reply_markup=keyboard)
            await callback.answer()
        else:
            await callback.answer("Це не твоя дія! Спробуй ще раз.", show_alert=True)

    @router.callback_query(lambda c: c.data.startswith("decline_"))
    async def decline_team(callback: types.CallbackQuery):
        print(f"Отримано callback для decline_team: {callback.data}")
        user_id = int(callback.data.replace("decline_", ""))
        if user_id == callback.from_user.id:
            members = load_members()
            members[user_id] = {"chat_id": callback.message.chat.id, "interacted": True}
            save_member(user_id, members[user_id])
            keyboard = InlineKeyboardMarkup(inline_keyboard=[])
            await callback.message.edit_text("Дякую за відповідь! Якщо передумаєш, запусти /start знову.")
            await callback.answer()
        else:
            await callback.answer("Це не твоя дія! Спробуй ще раз.", show_alert=True)

    @router.message(lambda message: message.text == "Перегляд моїх даних")
    async def view_my_data(message: Message):
        user_id = message.from_user.id
        username = message.from_user.username or f"User_{user_id}"
        members = load_members()
        if user_id not in members or not members[user_id]["interacted"]:
            await message.answer("Ви не є членом команди. Запустіть /start, щоб приєднатися.")
            return
        clients = load_clients(user_id)
        if username in clients:
            info = clients[username]
            response = f"Ваші дані:\n👤 {username} | 🏋️‍♂️ Тренування: {info['trainings']}"
            await message.answer(response)
        else:
            await message.answer("Ваші дані відсутні. Зверніться до Богдана для додавання.")

    @router.message(Command("refresh"))
    async def refresh_data(message: Message):
        user_id = message.from_user.id
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await message.answer("Ви не маєте прав для цієї дії.")
            return
        if user_id in ALLOWED_USERS:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Додати клієнта")],
                    [KeyboardButton(text="Перегляд клієнтів")],
                    [KeyboardButton(text="Відкрити доступ для іншого тренера/юзера")],
                ],
                resize_keyboard=True
            )
            await message.answer("Дані оновлено! Ось головний екран:", reply_markup=keyboard)
        else:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Додати клієнта")],
                    [KeyboardButton(text="Перегляд клієнтів")],
                ],
                resize_keyboard=True
            )
            await message.answer("Дані оновлено! Ось головний екран:", reply_markup=keyboard)

    @router.message(lambda message: message.text == "Додати клієнта")
    async def add_client(message: Message, state: FSMContext):
        user_id = message.from_user.id
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await message.answer("Ви не маєте прав для цієї дії. Зверніться до Богдана.")
            return
        await state.update_data(user_id=user_id)
        await state.set_state(AddClient.name)
        await message.answer("Вкажіть ім'я клієнта:\nПримітка: клієнт має запустити /start у бота.")

    @router.message(AddClient.name)
    async def add_client_step_2(message: Message, state: FSMContext):
        user_id = message.from_user.id
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await message.answer("Ви не маєте прав для цієї дії.")
            await state.clear()
            return
        await state.update_data(name=message.text)
        await state.set_state(AddClient.trainings)
        await message.answer("Вкажіть кількість тренувань:")

    @router.message(AddClient.trainings)
    async def add_client_step_3(message: Message, state: FSMContext):
        user_id = message.from_user.id
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await message.answer("Ви не маєте прав для цієї дії.")
            await state.clear()
            return
        try:
            trainings = int(message.text)
            if trainings < 0:
                raise ValueError
            await state.update_data(trainings=trainings)
            await state.set_state(AddClient.contact)
            await message.answer("Вкажіть юзернейм (наприклад, @username):")
        except ValueError:
            await message.answer("Введіть додатне число!")

    @router.message(AddClient.contact)
    async def add_client_final(message: Message, state: FSMContext):
        user_id = message.from_user.id
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await message.answer("Ви не маєте прав для цієї дії.")
            await state.clear()
            return
        data = await state.get_data()
        user_id = data["user_id"]
        clients = load_clients(user_id)
        clients[data['name']] = {"trainings": data['trainings'], "contact": message.text}
        save_client(user_id, data['name'], clients[data['name']])
        await state.clear()
        await message.answer(f"Клієнта {data['name']} додано для користувача {user_id}!")

    @router.message(lambda message: message.text == "Перегляд клієнтів")
    async def view_clients(message: Message):
        user_id = message.from_user.id
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await message.answer("Ви не маєте прав для цієї дії. Зверніться до Богдана.")
            return
        user_clients = load_clients(user_id)
        if not user_clients:
            await message.answer("Список клієнтів порожній.")
            return
        response = "Список твоїх клієнтів:\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for name, info in user_clients.items():
            response += f"👤 {name} | 🏋️‍♂️ Тренування: {info['trainings']} | 📞 {info['contact']}\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=f"⬅️ -1 {name}", callback_data=f"decrease_{user_id}_{name}"),
                InlineKeyboardButton(text=f"➡️ +1 {name}", callback_data=f"increase_{user_id}_{name}"),
                InlineKeyboardButton(text=f"❌ Видалити {name}", callback_data=f"delete_{user_id}_{name}"),
                InlineKeyboardButton(text=f"ℹ️ {name}", callback_data=f"info_{user_id}_{name}")
            ])
        await message.answer(response, reply_markup=keyboard)

    @router.callback_query(lambda c: c.data.startswith("decrease_") or c.data.startswith("increase_"))
    async def change_trainings(callback: types.CallbackQuery, state: FSMContext):
        print(f"Отримано callback: {callback.data}")
        user_id = int(callback.data.split("_")[1])
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
            return
        action, _, name = callback.data.split("_", 2)
        user_clients = load_clients(user_id)
        if name not in user_clients:
            await callback.answer("Клієнта не знайдено!")
            return
        if action == "decrease":
            user_clients[name]["trainings"] = max(0, user_clients[name]["trainings"] - 1)
            change = "-1"
        else:
            user_clients[name]["trainings"] += 1
            change = "+1"
        save_client(user_id, name, user_clients[name])
        notification_text = f"Твій тренер повідомляє: Кількість твоїх тренувань змінено: {change}. Поточна кількість: {user_clients[name]['trainings']} ✅"
        contact = user_clients[name]["contact"]
        encoded_text = urllib.parse.quote(notification_text)
        url = f"tg://resolve?domain={contact[1:]}&text={encoded_text}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Надіслати сповіщення", url=url)],
            [InlineKeyboardButton(text="📝 Змінити кількість", callback_data=f"set_trainings_{user_id}_{urllib.parse.quote(name)}")]
        ])
        await callback.message.edit_text(f"Кількість тренувань для {name} змінено на {user_clients[name]['trainings']}\nНатисни кнопку для дій:", reply_markup=keyboard)
        await callback.answer()

    @router.callback_query(lambda c: c.data.startswith("set_trainings_"))
    async def set_trainings(callback: types.CallbackQuery, state: FSMContext):
        print(f"Отримано callback для set_trainings: {callback.data}")
        try:
            # Розбиваємо callback.data: "set_trainings_<user_id>_<name>"
            parts = callback.data.split("_", 2)  # Розбиваємо на 3 частини
            if len(parts) != 3 or parts[0] != "set_trainings":
                raise ValueError(f"Неправильний формат callback.data: {callback.data}")
            user_id = int(parts[1])  # Другий елемент — user_id
            name = urllib.parse.unquote(parts[2])  # Третій елемент — закодоване ім'я
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

    @router.callback_query(lambda c: c.data.startswith("delete_"))
    async def delete_client(callback: types.CallbackQuery):
        print(f"Отримано callback для delete_client: {callback.data}")
        user_id = int(callback.data.split("_")[1])
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
            return
        _, _, name = callback.data.split("_", 2)
        user_clients = load_clients(user_id)
        if name in user_clients:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM clients WHERE user_id = ? AND client_name = ?", (user_id, name))
            conn.commit()
            conn.close()
            await callback.message.edit_text(f"Клієнта {name} видалено.", reply_markup=None)
        else:
            await callback.answer("Клієнта не знайдено!")
        await callback.answer()

    @router.callback_query(lambda c: c.data.startswith("info_"))
    async def show_client_info(callback: types.CallbackQuery, state: FSMContext):
        print(f"Отримано callback для show_client_info: {callback.data}")
        user_id = int(callback.data.split("_")[1])
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
            return
        _, _, name = callback.data.split("_", 2)
        user_clients = load_clients(user_id)
        if name not in user_clients:
            await callback.answer("Клієнта не знайдено!")
            return
        client = user_clients[name]
        profile = client.get("profile", {})
        photos = "\n".join([f"📷 {photo}" for photo in profile.get("photos", [])[:3]]) or "Немає світлин"
        info_text = (
            f"📋 Анкета клієнта: {name}\n"
            f"Поточна вага: {profile.get('weight', 'Не вказано')}\n"
            f"Вік: {profile.get('age', 'Не вказано')}\n"
            f"Параметри тіла: {profile.get('body_params', 'Не вказано')}\n"
            f"Додаткова інформація: {profile.get('extra_info', 'Не вказано')}\n"
            f"Світлини: {photos}\n"
            f"Дата прогресу: {profile.get('progress_date', 'Не встановлено')}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Редагувати анкету", callback_data=f"edit_profile_{user_id}_{name}")],
            [InlineKeyboardButton(text="Поділитися з клієнтом", callback_data=f"share_profile_{user_id}_{name}")],
            [InlineKeyboardButton(text="Архів прогресу", callback_data=f"view_archive_{user_id}_{name}")],
            [InlineKeyboardButton(text="Проаналізувати результати", callback_data=f"analyze_results_{user_id}_{name}")]
        ])
        await callback.message.edit_text(info_text, reply_markup=keyboard)
        await callback.answer()

    @router.callback_query(lambda c: c.data.startswith("edit_profile_"))
    async def edit_client_profile(callback: types.CallbackQuery, state: FSMContext):
        print(f"Отримано callback для edit_client_profile: {callback.data}")
        user_id = int(callback.data.split("_")[1])
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
            return
        _, _, name = callback.data.split("_", 2)
        user_clients = load_clients(user_id)
        if name not in user_clients:
            await callback.answer("Клієнта не знайдено!")
            return

        current_profile = user_clients[name].get("profile", {})
        if current_profile and any(current_profile.values()):
            archive_entry = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "weight": current_profile.get("weight", "Не вказано"),
                "age": current_profile.get("age", "Не вказано"),
                "body_params": current_profile.get("body_params", "Не вказано"),
                "extra_info": current_profile.get("extra_info", "Не вказано"),
                "photos": current_profile.get("photos", [])
            }
            user_clients[name].setdefault("progress_archive", []).append(archive_entry)
            save_client(user_id, name, user_clients[name])

        await state.update_data(user_id=user_id, name=name)
        await state.set_state(EditProfile.weight)
        await callback.message.edit_text("Вкажіть поточну вагу (наприклад, 80 кг) або пропустіть:", reply_markup=None)
        await callback.answer()

    @router.message(EditProfile.weight)
    async def set_weight(message: Message, state: FSMContext):
        data = await state.get_data()
        user_id = data["user_id"]
        name = data["name"]
        user_clients = load_clients(user_id)
        user_clients[name].setdefault("profile", {})["weight"] = message.text or "Не вказано"
        save_client(user_id, name, user_clients[name])
        await state.set_state(EditProfile.age)
        await message.answer("Вкажіть вік або пропустіть:")

    @router.message(EditProfile.age)
    async def set_age(message: Message, state: FSMContext):
        data = await state.get_data()
        user_id = data["user_id"]
        name = data["name"]
        user_clients = load_clients(user_id)
        user_clients[name]["profile"]["age"] = message.text or "Не вказано"
        save_client(user_id, name, user_clients[name])
        await state.set_state(EditProfile.body_params)
        await message.answer("Вкажіть параметри тіла (наприклад, Талія: 85 см) або пропустіть:")

    @router.message(EditProfile.body_params)
    async def set_body_params(message: Message, state: FSMContext):
        data = await state.get_data()
        user_id = data["user_id"]
        name = data["name"]
        user_clients = load_clients(user_id)
        user_clients[name]["profile"]["body_params"] = message.text or "Не вказано"
        save_client(user_id, name, user_clients[name])
        await state.set_state(EditProfile.extra_info)
        await message.answer("Вкажіть додаткову інформацію або пропустіть:")

    @router.message(EditProfile.extra_info)
    async def set_extra_info(message: Message, state: FSMContext):
        data = await state.get_data()
        user_id = data["user_id"]
        name = data["name"]
        user_clients = load_clients(user_id)
        user_clients[name]["profile"]["extra_info"] = message.text or "Не вказано"
        save_client(user_id, name, user_clients[name])
        await state.set_state(EditProfile.photos)
        await message.answer("Надішліть 1–3 світлини (або пропустіть, надіславши /skip):")

    @router.message(EditProfile.photos)
    async def set_photos(message: Message, state: FSMContext):
        data = await state.get_data()
        user_id = data["user_id"]
        name = data["name"]
        user_clients = load_clients(user_id)
        photos = user_clients[name]["profile"].get("photos", [])
        if message.text == "/skip" or not message.photo:
            pass
        elif message.photo and len(photos) < 3:
            photo_id = message.photo[-1].file_id
            photos.append(photo_id)
            user_clients[name]["profile"]["photos"] = photos[:3]
        user_clients[name]["profile"]["progress_date"] = datetime.now().strftime("%Y-%m-%d")
        save_client(user_id, name, user_clients[name])
        await state.clear()
        await message.answer(f"Анкета для {name} оновлена! Натисни 'ℹ️' для перегляду.")

    @router.callback_query(lambda c: c.data.startswith("share_profile_"))
    async def share_client_profile(callback: types.CallbackQuery):
        print(f"Отримано callback для share_client_profile: {callback.data}")
        user_id = int(callback.data.split("_")[1])
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
            return
        _, _, name = callback.data.split("_", 2)
        user_clients = load_clients(user_id)
        if name not in user_clients:
            await callback.answer("Клієнта не знайдено!")
            return
        client = user_clients[name]
        profile = client.get("profile", {})
        photos = profile.get("photos", [])
        info_text = (
            f"📋 Анкета клієнта: {name}\n"
            f"Поточна вага: {profile.get('weight', 'Не вказано')}\n"
            f"Вік: {profile.get('age', 'Не вказано')}\n"
            f"Параметри тіла: {profile.get('body_params', 'Не вказано')}\n"
            f"Додаткова інформація: {profile.get('extra_info', 'Не вказано')}\n"
            f"Дата прогресу: {profile.get('progress_date', 'Не встановлено')}"
        )
        contact = client["contact"]
        if contact.startswith("@"):
            target = contact[1:]
            await bot.send_message(f"@{target}", info_text)
            for photo_id in photos:
                await bot.send_photo(f"@{target}", photo=photo_id)
            await callback.answer("Анкета успішно надіслана клієнту!")
        else:
            await callback.answer("Неможливо надіслати: контакт не є Telegram-юзернеймом.", show_alert=True)

    @router.callback_query(lambda c: c.data.startswith("view_archive_"))
    async def view_archive(callback: types.CallbackQuery):
        print(f"Отримано callback для view_archive: {callback.data}")
        user_id = int(callback.data.split("_")[1])
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
            return
        _, _, name = callback.data.split("_", 2)
        user_clients = load_clients(user_id)
        if name not in user_clients:
            await callback.answer("Клієнта не знайдено!")
            return
        archive = user_clients[name].get("progress_archive", [])
        if not archive:
            await callback.message.edit_text(f"📜 Архів прогресу для {name} порожній.")
            return

        archive_text = f"📜 Архів прогресу для {name}:\n"
        for idx, entry in enumerate(archive, 1):
            photos = "\n".join([f"📷 {photo}" for photo in entry.get("photos", [])[:3]]) or "Немає світлин"
            archive_text += (
                f"\n--- Запис {idx} ---\n"
                f"Дата: {entry['date']}\n"
                f"Вага: {entry.get('weight', 'Не вказано')}\n"
                f"Вік: {entry.get('age', 'Не вказано')}\n"
                f"Параметри тіла: {entry.get('body_params', 'Не вказано')}\n"
                f"Додаткова інформація: {entry.get('extra_info', 'Не вказано')}\n"
                f"Світлини: {photos}"
            )
        await callback.message.edit_text(archive_text)
        await callback.answer()

    @router.callback_query(lambda c: c.data.startswith("analyze_results_"))
    async def analyze_results(callback: types.CallbackQuery):
        print(f"Отримано callback для analyze_results: {callback.data}")
        user_id = int(callback.data.split("_")[1])
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
            return
        _, _, name = callback.data.split("_", 2)
        user_clients = load_clients(user_id)
        if name not in user_clients:
            await callback.answer("Клієнта не знайдено!")
            return
        client = user_clients[name]
        profile = client.get("profile", {})
        archive = client.get("progress_archive", [])

        all_data = archive + [profile] if profile else archive
        if not all_data or len(all_data) < 1:
            await callback.message.edit_text(f"📊 Для {name} недостатньо даних для аналізу.")
            return

        all_data.sort(key=lambda x: x.get("date", "1970-01-01"))
        first_entry = all_data[0]
        last_entry = all_data[-1]

        first_weight = float(re.search(r"(\d+\.?\d*)", first_entry.get("weight", "0")).group(1)) if "kg" in first_entry.get("weight", "") else 0
        last_weight = float(re.search(r"(\d+\.?\d*)", last_entry.get("weight", "0")).group(1)) if "kg" in last_entry.get("weight", "") else 0
        weight_change = last_weight - first_weight
        weight_trend = "схуд" if weight_change < 0 else "набрав" if weight_change > 0 else "не змінив"

        first_params = parse_body_params(first_entry.get("body_params", ""))
        last_params = parse_body_params(last_entry.get("body_params", ""))
        body_changes = {}
        for key in set(first_params.keys()).union(last_params.keys()):
            change = last_params.get(key, 0) - first_params.get(key, 0)
            if change != 0:
                trend = "збільшився" if change > 0 else "зменшився"
                body_changes[key] = f"{abs(change):.1f} см ({trend})"

        analysis_text = f"📊 Аналіз результатів для {name}:\n"
        analysis_text += f"- Період: {first_entry['date']} – {last_entry['date']}\n"
        analysis_text += f"- Зміна ваги: {abs(weight_change):.1f} кг ({weight_trend})\n"
        if body_changes:
            analysis_text += "- Зміни параметрів тіла:\n"
            for part, change in body_changes.items():
                analysis_text += f"  - {part}: {change}\n"
        else:
            analysis_text += "- Зміни параметрів тіла: Немає даних\n"
        analysis_text += "Примітка: Аналіз базується на перших і останніх записах."

        await callback.message.edit_text(analysis_text)
        await callback.answer()

    @router.message(lambda message: message.text == "Відкрити доступ для іншого тренера/юзера")
    async def manage_access(message: Message, state: FSMContext):
        user_id = message.from_user.id
        if user_id not in ALLOWED_USERS:
            await message.answer("Ви не маєте прав для цієї дії. Зверніться до Богдана.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Безкоштовна підписка", callback_data="free_access")],
            [InlineKeyboardButton(text="Платна підписка", callback_data="paid_access")],
            [InlineKeyboardButton(text="Прибрати підписку", callback_data="remove_access")]
        ])
        await message.answer("Обери опцію:", reply_markup=keyboard)
        await state.set_state(ManageAccess.access_type)

    @router.callback_query(ManageAccess.access_type)
    async def process_access_type(callback: types.CallbackQuery, state: FSMContext):
        print(f"Отримано callback для process_access_type: {callback.data}")
        user_id = callback.from_user.id
        if user_id not in ALLOWED_USERS:
            await callback.answer("Ви не маєте прав для цієї дії!", show_alert=True)
            return
        access_type = callback.data
        await state.update_data(access_type=access_type)
        await state.set_state(ManageAccess.user_id)
        await callback.message.edit_text("Введи ID, юзернейм (@username) або телефон нового тренера для надання доступу:")
        await callback.answer()

    @router.message(ManageAccess.user_id)
    async def process_user_id(message: Message, state: FSMContext):
        user_id = message.from_user.id
        if user_id not in ALLOWED_USERS:
            await message.answer("Ви не маєте прав для цієї дії.")
            await state.clear()
            return
        target_id = message.text.replace("@", "")
        try:
            target_id = int(target_id) if target_id.isdigit() else target_id
        except ValueError:
            pass
        data = await state.get_data()
        access_type = data["access_type"]

        members = load_members()
        if access_type in ["free_access", "paid_access"]:
            if target_id not in members:
                members[target_id] = {"chat_id": None, "interacted": True, "role": "trainer"}
                save_member(target_id, members[target_id])
                await message.answer(f"Доступ {access_type.replace('_', ' ')} надано для {target_id}!")
            else:
                members[target_id]["role"] = "trainer"
                save_member(target_id, members[target_id])
                await message.answer(f"Доступ {access_type.replace('_', ' ')} оновлено для {target_id}!")
            if access_type == "paid_access":
                await message.answer("Платна підписка активована. (Примітка: логіка сплати ще не реалізована.)")
        elif access_type == "remove_access":
            if target_id in members and members[target_id].get("role") == "trainer":
                members[target_id]["role"] = ""
                save_member(target_id, members[target_id])
                await message.answer(f"Доступ прибрано для {target_id}!")
            else:
                await message.answer(f"У {target_id} немає доступу або він не є тренером.")

        await state.clear()

    @router.message(Command("stats"))
    async def show_stats(message: Message):
        user_id = message.from_user.id
        members = load_members()
        if user_id not in ALLOWED_USERS and (user_id not in members or members[user_id].get("role") != "trainer"):
            await message.answer("Ви не маєте прав для цієї дії. Зверніться до Богдана для доступу.")
            return
        user_clients = load_clients(user_id)
        if not user_clients:
            await message.answer("Список клієнтів порожній. Немає статистики.")
            return
        total_clients = len(user_clients)
        total_trainings = sum(client["trainings"] for client in user_clients.values())
        average_trainings = total_trainings / total_clients if total_clients > 0 else 0
        stats_text = (
            f"📊 Твоя статистика:\n"
            f"- Кількість клієнтів: {total_clients}\n"
            f"- Середня кількість тренувань: {average_trainings:.2f}"
        )
        await message.answer(stats_text)

    @router.message(Command("add_user"))
    async def add_allowed_user(message: Message):
        user_id = message.from_user.id
        if user_id != ADMIN_ID:
            await message.answer("Ви не маєте прав для цієї дії.")
            return
        try:
            new_user_id = int(message.text.split()[1])
            ALLOWED_USERS.add(new_user_id)
            await message.answer(f"Користувач з ID {new_user_id} отримав доступ.")
        except (IndexError, ValueError):
            await message.answer("Неправильний формат. Використовуйте: /add_user <user_id>")

    @router.message(Command("remove_user"))
    async def remove_allowed_user(message: Message):
        user_id = message.from_user.id
        if user_id != ADMIN_ID:
            await message.answer("Ви не маєте прав для цієї дії.")
            return
        try:
            remove_user_id = int(message.text.split()[1])
            if remove_user_id in ALLOWED_USERS and remove_user_id != ADMIN_ID:
                ALLOWED_USERS.remove(remove_user_id)
                await message.answer(f"Доступ для користувача з ID {remove_user_id} видалено.")
            else:
                await message.answer("Цей користувач не має доступу або це ти (адмін).")
        except (IndexError, ValueError):
            await message.answer("Неправильний формат. Використовуйте: /remove_user <user_id>")

register_handlers()

async def main():
    dp.include_router(router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        print(f"Помилка при видаленні вебхука: {e}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
