import json
import os
import asyncio
import logging
import sys
import requests
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message, InlineKeyboardMarkup, InlineKeyboardButton
import uvicorn
from fastapi import FastAPI

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# Ініціалізація FastAPI
app = FastAPI()

# Ініціалізація бота
TOKEN = "8097225217:AAERSuN5K68msP6JZzpSG9NR7XiDTeXBH6Y"
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

# Дозволені користувачі
ALLOWED_USERS = [385298897, 666567798]

# Шляхи до файлів
DATA_PATH = "/data/data.json"
MEMBERS_PATH = "/data/members.json"

# Клас для станів
class ClientStates(StatesGroup):
    add_client_name = State()
    add_client_trainings = State()
    add_client_contact = State()
    change_trainings_count = State()
    client_info_age = State()
    client_info_weight = State()
    client_info_results = State()
    client_info_additional = State()
    edit_client_info_age = State()
    edit_client_info_weight = State()
    edit_client_info_results = State()
    edit_client_info_additional = State()
    select_client_for_tracking = State()
    select_date_for_edit = State()
    select_date_for_delete = State()

# Функції для роботи з базою даних
def load_data():
    try:
        with open(DATA_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=4)

def load_members():
    try:
        with open(MEMBERS_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_member(user_id, member_data):
    members = load_members()
    members[user_id] = member_data
    with open(MEMBERS_PATH, "w") as f:
        json.dump(members, f, indent=4)

def load_clients(user_id):
    data = load_data()
    return data.get(str(user_id), {})

def save_client(user_id, client_name, client_data):
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = {}
    data[str(user_id)][client_name] = client_data
    save_data(data)

# Обробник команди /start
@router.message(Command("start"))
async def handle_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"User_{user_id}"
    chat_id = message.chat.id

    print(f"[START] User ID: {user_id}, Chat ID: {chat_id}, Username: {username}")
    members = load_members()
    if user_id in ALLOWED_USERS:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Додати клієнта")],
                [KeyboardButton(text="Перегляд клієнтів")],
                [KeyboardButton(text="📈 Відслідковування показників клієнтів")],
            ],
            resize_keyboard=True
        )
        response = "Вітаю, Богдане! Ось доступні дії:"
        print(f"[START] Sending response: {response}")
        await message.answer(response, reply_markup=keyboard)
        if user_id not in members:
            members[user_id] = {"chat_id": chat_id, "interacted": True, "role": "admin"}
            save_member(user_id, members[user_id])
    else:
        response = "У вас немає доступу до бота."
        print(f"[START] Sending response: {response}")
        await message.answer(response)

# Обробник "Додати клієнта"
@router.message(F.text == "Додати клієнта")
async def add_client(message: Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        response = "У вас немає доступу до цієї функції."
        print(f"[ADD_CLIENT] Sending response: {response}")
        await message.answer(response)
        return
    response = "Введіть ім'я клієнта:"
    print(f"[ADD_CLIENT] Sending response: {response}")
    await message.answer(response)
    await state.set_state(ClientStates.add_client_name)

@router.message(StateFilter(ClientStates.add_client_name))
async def process_client_name(message: Message, state: FSMContext):
    client_name = message.text.strip()
    await state.update_data(client_name=client_name)
    response = "Введіть кількість тренувань:"
    print(f"[PROCESS_CLIENT_NAME] Sending response: {response}")
    await message.answer(response)
    await state.set_state(ClientStates.add_client_trainings)

@router.message(StateFilter(ClientStates.add_client_trainings))
async def process_client_trainings(message: Message, state: FSMContext):
    try:
        trainings = int(message.text.strip())
        await state.update_data(trainings=trainings)
        response = "Введіть контакт клієнта (юзернейм Telegram або номер телефону):"
        print(f"[PROCESS_CLIENT_TRAININGS] Sending response: {response}")
        await message.answer(response)
        await state.set_state(ClientStates.add_client_contact)
    except ValueError:
        response = "Будь ласка, введіть число для кількості тренувань."
        print(f"[PROCESS_CLIENT_TRAININGS] Sending response: {response}")
        await message.answer(response)

@router.message(StateFilter(ClientStates.add_client_contact))
async def process_client_contact(message: Message, state: FSMContext):
    contact = message.text.strip()
    data = await state.get_data()
    client_name = data["client_name"]
    trainings = data["trainings"]
    user_id = message.from_user.id

    user_clients = load_clients(user_id)
    user_clients[client_name] = {
        "trainings": trainings,
        "contact": contact,
        "profile": {"age": "", "weight": "", "results": "", "additional": ""},
        "archive": []
    }
    save_client(user_id, client_name, user_clients[client_name])
    response = f"Клієнта {client_name} додано! Кількість тренувань: {trainings}, Контакт: {contact}"
    print(f"[PROCESS_CLIENT_CONTACT] Sending response: {response}")
    await message.answer(response)
    await state.clear()

# Обробник "Перегляд клієнтів"
@router.message(F.text == "Перегляд клієнтів")
async def view_clients(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        response = "У вас немає доступу до цієї функції."
        print(f"[VIEW_CLIENTS] Sending response: {response}")
        await message.answer(response)
        return
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if not user_clients:
        response = "Список клієнтів порожній."
        print(f"[VIEW_CLIENTS] Sending response: {response}")
        await message.answer(response)
        return

    response = "Список твоїх клієнтів:\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for client_name, client_data in user_clients.items():
        contact = client_data["contact"]
        if contact.startswith("@"):
            contact = f"[{contact}](tg://user?id={contact})"
        else:
            contact = f"📞 {contact}"
        response += f"👤 {client_name} | 🏋️‍♂️ Тренування: {client_data['trainings']} | {contact}\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="⬅️", callback_data=f"minus_{client_name}"),
            InlineKeyboardButton(text=f"{client_name}: {client_data['trainings']} 📝", callback_data=f"change_{client_name}"),
            InlineKeyboardButton(text="➡️", callback_data=f"plus_{client_name}"),
            InlineKeyboardButton(text="🗑", callback_data=f"delete_{client_name}"),
            InlineKeyboardButton(text="ℹ️", callback_data=f"info_{client_name}")
        ])
    print(f"[VIEW_CLIENTS] Sending response: {response}")
    await message.answer(response, reply_markup=keyboard, parse_mode="Markdown")

# Обробник кнопок "⬅️" і "➡️"
@router.callback_query(F.data.startswith("minus_"))
async def minus_training(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        user_clients[client_name]["trainings"] -= 1
        change = -1
        new_trainings = user_clients[client_name]["trainings"]
        save_client(user_id, client_name, user_clients[client_name])

        # Підготовка повідомлення для клієнта
        contact = user_clients[client_name]["contact"]
        if contact:
            msg = f"Твій тренер повідомляє: Кількість твоїх тренувань змінено: {change:+d}. Поточна кількість: {new_trainings} ✅"
            if contact.startswith("@"):
                clean_contact = contact.lstrip("@")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Відправити клієнту", url=f"https://t.me/{clean_contact}?text={msg}")]
                ])
                response = f"Натисніть кнопку, щоб відправити повідомлення:\n{msg}"
                print(f"[MINUS_TRAINING] Sending response: {response}")
                await callback.message.answer(response, reply_markup=keyboard)
            else:
                response = f"Скопіюйте повідомлення та відправте клієнту через контакт {contact}:\n{msg}"
                print(f"[MINUS_TRAINING] Sending response: {response}")
                await callback.message.answer(response)

        # Оновлення таблиці
        response = "Список твоїх клієнтів:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for name, data in user_clients.items():
            contact = data["contact"]
            if contact.startswith("@"):
                contact = f"[{contact}](tg://user?id={contact})"
            else:
                contact = f"📞 {contact}"
            response += f"👤 {name} | 🏋️‍♂️ Тренування: {data['trainings']} | {contact}\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="⬅️", callback_data=f"minus_{name}"),
                InlineKeyboardButton(text=f"{name}: {data['trainings']} 📝", callback_data=f"change_{name}"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        print(f"[MINUS_TRAINING] Updating table: {response}")
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("plus_"))
async def plus_training(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        user_clients[client_name]["trainings"] += 1
        change = 1
        new_trainings = user_clients[client_name]["trainings"]
        save_client(user_id, client_name, user_clients[client_name])

        # Підготовка повідомлення для клієнта
        contact = user_clients[client_name]["contact"]
        if contact:
            msg = f"Твій тренер повідомляє: Кількість твоїх тренувань змінено: {change:+d}. Поточна кількість: {new_trainings} ✅"
            if contact.startswith("@"):
                clean_contact = contact.lstrip("@")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Відправити клієнту", url=f"https://t.me/{clean_contact}?text={msg}")]
                ])
                response = f"Натисніть кнопку, щоб відправити повідомлення:\n{msg}"
                print(f"[PLUS_TRAINING] Sending response: {response}")
                await callback.message.answer(response, reply_markup=keyboard)
            else:
                response = f"Скопіюйте повідомлення та відправте клієнту через контакт {contact}:\n{msg}"
                print(f"[PLUS_TRAINING] Sending response: {response}")
                await callback.message.answer(response)

        # Оновлення таблиці
        response = "Список твоїх клієнтів:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for name, data in user_clients.items():
            contact = data["contact"]
            if contact.startswith("@"):
                contact = f"[{contact}](tg://user?id={contact})"
            else:
                contact = f"📞 {contact}"
            response += f"👤 {name} | 🏋️‍♂️ Тренування: {data['trainings']} | {contact}\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="⬅️", callback_data=f"minus_{name}"),
                InlineKeyboardButton(text=f"{name}: {data['trainings']} 📝", callback_data=f"change_{name}"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        print(f"[PLUS_TRAINING] Updating table: {response}")
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

# Обробник кнопки "📝" у таблиці
@router.callback_query(F.data.startswith("change_"))
async def change_training_inline(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        await state.update_data(client_name=client_name)
        response = f"Введіть нову кількість тренувань для {client_name} (поточна: {user_clients[client_name]['trainings']}):"
        print(f"[CHANGE_TRAINING_INLINE] Sending response: {response}")
        await callback.message.answer(response)
        await state.set_state(ClientStates.change_trainings_count)
    await callback.answer()

@router.message(StateFilter(ClientStates.change_trainings_count))
async def process_change_trainings_count(message: Message, state: FSMContext):
    try:
        new_trainings = int(message.text.strip())
        data = await state.get_data()
        client_name = data["client_name"]
        user_id = message.from_user.id
        user_clients = load_clients(user_id)

        old_trainings = user_clients[client_name]["trainings"]
        user_clients[client_name]["trainings"] = new_trainings
        save_client(user_id, client_name, user_clients[client_name])

        # Підготовка повідомлення для клієнта
        contact = user_clients[client_name]["contact"]
        if contact:
            change = new_trainings - old_trainings
            msg = f"Твій тренер повідомляє: Кількість твоїх тренувань змінено: {change:+d}. Поточна кількість: {new_trainings} ✅"
            if contact.startswith("@"):
                clean_contact = contact.lstrip("@")
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Відправити клієнту", url=f"https://t.me/{clean_contact}?text={msg}")]
                ])
                response = f"Натисніть кнопку, щоб відправити повідомлення:\n{msg}"
                print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Sending response: {response}")
                await message.answer(response, reply_markup=keyboard)
            else:
                response = f"Скопіюйте повідомлення та відправте клієнту через контакт {contact}:\n{msg}"
                print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Sending response: {response}")
                await message.answer(response)

        response = f"Кількість тренувань для {client_name} змінено на {new_trainings}."
        print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Sending response: {response}")
        await message.answer(response)
        await state.clear()
    except ValueError:
        response = "Будь ласка, введіть число для кількості тренувань."
        print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Sending response: {response}")
        await message.answer(response)

# Обробник кнопки "🗑"
@router.callback_query(F.data.startswith("delete_"))
async def delete_client_inline(callback: types.CallbackQuery):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        del user_clients[client_name]
        data = load_data()
        data[str(user_id)] = user_clients
        save_data(data)

        # Оновлення таблиці
        response = "Список твоїх клієнтів:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for name, data in user_clients.items():
            contact = data["contact"]
            if contact.startswith("@"):
                contact = f"[{contact}](tg://user?id={contact})"
            else:
                contact = f"📞 {contact}"
            response += f"👤 {name} | 🏋️‍♂️ Тренування: {data['trainings']} | {contact}\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="⬅️", callback_data=f"minus_{name}"),
                InlineKeyboardButton(text=f"{name}: {data['trainings']} 📝", callback_data=f"change_{name}"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        print(f"[DELETE_CLIENT] Updating table: {response}")
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="Markdown")
        response = f"Клієнта {client_name} видалено!"
        print(f"[DELETE_CLIENT] Sending response: {response}")
        await callback.message.answer(response)
    await callback.answer()

# Обробник кнопки "ℹ️"
@router.callback_query(F.data.startswith("info_"))
async def client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        await state.update_data(client_name=client_name)
        response = f"Введіть вік клієнта {client_name}:"
        print(f"[CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
        await state.set_state(ClientStates.client_info_age)
    await callback.answer()

@router.message(StateFilter(ClientStates.client_info_age))
async def process_client_info_age(message: Message, state: FSMContext):
    age = message.text.strip()
    await state.update_data(age=age)
    response = "Введіть вагу клієнта (кг):"
    print(f"[PROCESS_CLIENT_INFO_AGE] Sending response: {response}")
    await message.answer(response)
    await state.set_state(ClientStates.client_info_weight)

@router.message(StateFilter(ClientStates.client_info_weight))
async def process_client_info_weight(message: Message, state: FSMContext):
    weight = message.text.strip()
    await state.update_data(weight=weight)
    response = "Введіть результати клієнта (наприклад, прогрес у вправах):"
    print(f"[PROCESS_CLIENT_INFO_WEIGHT] Sending response: {response}")
    await message.answer(response)
    await state.set_state(ClientStates.client_info_results)

@router.message(StateFilter(ClientStates.client_info_results))
async def process_client_info_results(message: Message, state: FSMContext):
    results = message.text.strip()
    await state.update_data(results=results)
    response = "Введіть додаткову інформацію (якщо є):"
    print(f"[PROCESS_CLIENT_INFO_RESULTS] Sending response: {response}")
    await message.answer(response)
    await state.set_state(ClientStates.client_info_additional)

@router.message(StateFilter(ClientStates.client_info_additional))
async def process_client_info_additional(message: Message, state: FSMContext):
    additional = message.text.strip()
    data = await state.get_data()
    client_name = data["client_name"]
    user_id = message.from_user.id
    user_clients = load_clients(user_id)

    # Формуємо профіль
    profile = {
        "age": data["age"],
        "weight": data["weight"],
        "results": data["results"],
        "additional": additional
    }
    await state.update_data(temp_profile=profile)

    # Показуємо анкету та кнопки для дій
    response = f"Анкета клієнта {client_name}:\n"
    response += f"Вік: {profile['age']}\n"
    response += f"Вага: {profile['weight']} кг\n"
    response += f"Результати: {profile['results']}\n"
    response += f"Додатково: {profile['additional']}\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Зберегти", callback_data=f"save_info_{client_name}")],
        [InlineKeyboardButton(text="Редагувати", callback_data=f"edit_info_{client_name}")],
        [InlineKeyboardButton(text="Видалити", callback_data=f"delete_info_{client_name}")],
        [InlineKeyboardButton(text="Додати нову інформацію", callback_data=f"add_new_info_{client_name}")],
        [InlineKeyboardButton(text="Аналізувати результати", callback_data=f"analyze_info_{client_name}")]
    ])
    print(f"[PROCESS_CLIENT_INFO_ADDITIONAL] Sending response: {response}")
    await message.answer(response, reply_markup=keyboard)
    # Не очищаємо стан, щоб зберегти temp_profile для подальших дій

# Обробник кнопки "Зберегти"
@router.callback_query(F.data.startswith("save_info_"))
async def save_client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[2]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    data = await state.get_data()
    profile = data.get("temp_profile")

    if client_name in user_clients and profile:
        # Зберігаємо з поточною датою
        current_date = datetime.now().strftime("%Y-%m-%d")
        user_clients[client_name]["archive"].append({
            "date": current_date,
            "profile": profile
        })
        save_client(user_id, client_name, user_clients[client_name])
        response = f"Дані для {client_name} збережено за {current_date}!"
        print(f"[SAVE_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
    await state.clear()
    await callback.answer()

# Обробник кнопки "Редагувати"
@router.callback_query(F.data.startswith("edit_info_"))
async def edit_client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[2]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    
    if client_name in user_clients and user_clients[client_name]["archive"]:
        await state.update_data(client_name=client_name)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for entry in user_clients[client_name]["archive"]:
            date = entry["date"]
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=date, callback_data=f"edit_date_{client_name}_{date}")
            ])
        response = "Виберіть дату для редагування:"
        print(f"[EDIT_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response, reply_markup=keyboard)
        await state.set_state(ClientStates.select_date_for_edit)
    else:
        response = f"Немає даних для редагування для {client_name}."
        print(f"[EDIT_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
        await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("edit_date_"))
async def select_date_for_edit(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[2]
    date = callback.data.split("_")[3]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    
    # Зберігаємо дату для редагування
    await state.update_data(edit_date=date)
    
    # Показуємо поточні дані за цю дату
    entry = next((e for e in user_clients[client_name]["archive"] if e["date"] == date), None)
    if entry:
        profile = entry["profile"]
        response = f"Редагування даних для {client_name} за {date}:\n"
        response += f"Вік: {profile['age']}\n"
        response += f"Вага: {profile['weight']} кг\n"
        response += f"Результати: {profile['results']}\n"
        response += f"Додатково: {profile['additional']}\n"
        response += "Введіть новий вік:"
        print(f"[SELECT_DATE_FOR_EDIT] Sending response: {response}")
        await callback.message.answer(response)
        await state.set_state(ClientStates.edit_client_info_age)
    await callback.answer()

@router.message(StateFilter(ClientStates.edit_client_info_age))
async def edit_client_info_age(message: Message, state: FSMContext):
    age = message.text.strip()
    await state.update_data(age=age)
    response = "Введіть нову вагу (кг):"
    print(f"[EDIT_CLIENT_INFO_AGE] Sending response: {response}")
    await message.answer(response)
    await state.set_state(ClientStates.edit_client_info_weight)

@router.message(StateFilter(ClientStates.edit_client_info_weight))
async def edit_client_info_weight(message: Message, state: FSMContext):
    weight = message.text.strip()
    await state.update_data(weight=weight)
    response = "Введіть нові результати (наприклад, прогрес у вправах):"
    print(f"[EDIT_CLIENT_INFO_WEIGHT] Sending response: {response}")
    await message.answer(response)
    await state.set_state(ClientStates.edit_client_info_results)

@router.message(StateFilter(ClientStates.edit_client_info_results))
async def edit_client_info_results(message: Message, state: FSMContext):
    results = message.text.strip()
    await state.update_data(results=results)
    response = "Введіть нову додаткову інформацію (якщо є):"
    print(f"[EDIT_CLIENT_INFO_RESULTS] Sending response: {response}")
    await message.answer(response)
    await state.set_state(ClientStates.edit_client_info_additional)

@router.message(StateFilter(ClientStates.edit_client_info_additional))
async def edit_client_info_additional(message: Message, state: FSMContext):
    additional = message.text.strip()
    data = await state.get_data()
    client_name = data["client_name"]
    edit_date = data["edit_date"]
    user_id = message.from_user.id
    user_clients = load_clients(user_id)

    # Оновлюємо запис за вибраною датою
    profile = {
        "age": data["age"],
        "weight": data["weight"],
        "results": data["results"],
        "additional": additional
    }
    for entry in user_clients[client_name]["archive"]:
        if entry["date"] == edit_date:
            entry["profile"] = profile
            break
    save_client(user_id, client_name, user_clients[client_name])

    response = f"Дані для {client_name} за {edit_date} оновлено!"
    print(f"[EDIT_CLIENT_INFO_ADDITIONAL] Sending response: {response}")
    await message.answer(response)
    await state.clear()

# Обробник кнопки "Видалити"
@router.callback_query(F.data.startswith("delete_info_"))
async def delete_client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[2]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    
    if client_name in user_clients and user_clients[client_name]["archive"]:
        await state.update_data(client_name=client_name)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for entry in user_clients[client_name]["archive"]:
            date = entry["date"]
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=date, callback_data=f"delete_date_{client_name}_{date}")
            ])
        response = "Виберіть дату для видалення:"
        print(f"[DELETE_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response, reply_markup=keyboard)
        await state.set_state(ClientStates.select_date_for_delete)
    else:
        response = f"Немає даних для видалення для {client_name}."
        print(f"[DELETE_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
        await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("delete_date_"))
async def select_date_for_delete(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[2]
    date = callback.data.split("_")[3]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)

    # Видаляємо запис за вибраною датою
    user_clients[client_name]["archive"] = [e for e in user_clients[client_name]["archive"] if e["date"] != date]
    save_client(user_id, client_name, user_clients[client_name])

    response = f"Дані для {client_name} за {date} видалено!"
    print(f"[SELECT_DATE_FOR_DELETE] Sending response: {response}")
    await callback.message.answer(response)
    await state.clear()
    await callback.answer()

# Обробник кнопки "Додати нову інформацію"
@router.callback_query(F.data.startswith("add_new_info_"))
async def add_new_client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[3]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        await state.update_data(client_name=client_name)
        response = f"Введіть вік клієнта {client_name}:"
        print(f"[ADD_NEW_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
        await state.set_state(ClientStates.client_info_age)
    await callback.answer()

# Обробник кнопки "Аналізувати результати"
@router.callback_query(F.data.startswith("analyze_info_"))
async def analyze_client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[2]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    
    if client_name in user_clients and user_clients[client_name]["archive"]:
        # Сортуємо записи за датою
        entries = sorted(user_clients[client_name]["archive"], key=lambda x: x["date"])
        
        # Аналіз за тиждень (останні 7 днів)
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        week_entries = [e for e in entries if e["date"] >= week_ago]
        week_analysis = "Аналіз за останній тиждень:\n"
        if len(week_entries) >= 2:
            old_weight = float(week_entries[0]["profile"]["weight"])
            new_weight = float(week_entries[-1]["profile"]["weight"])
            weight_change = new_weight - old_weight
            week_analysis += f"Зміна ваги: {weight_change:+.1f} кг\n"
            week_analysis += f"Результати на початку: {week_entries[0]['profile']['results']}\n"
            week_analysis += f"Результати в кінці: {week_entries[-1]['profile']['results']}\n"
        else:
            week_analysis += "Недостатньо даних для аналізу за тиждень.\n"

        # Аналіз за місяць (останні 30 днів)
        month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        month_entries = [e for e in entries if e["date"] >= month_ago]
        month_analysis = "Аналіз за останній місяць:\n"
        if len(month_entries) >= 2:
            old_weight = float(month_entries[0]["profile"]["weight"])
            new_weight = float(month_entries[-1]["profile"]["weight"])
            weight_change = new_weight - old_weight
            month_analysis += f"Зміна ваги: {weight_change:+.1f} кг\n"
            month_analysis += f"Результати на початку: {month_entries[0]['profile']['results']}\n"
            month_analysis += f"Результати в кінці: {month_entries[-1]['profile']['results']}\n"
        else:
            month_analysis += "Недостатньо даних для аналізу за місяць.\n"

        response = f"Аналіз результатів для {client_name}:\n\n{week_analysis}\n{month_analysis}"
        print(f"[ANALYZE_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
    else:
        response = f"Немає даних для аналізу для {client_name}."
        print(f"[ANALYZE_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
    await state.clear()
    await callback.answer()

# Обробник кнопки "📈 Відслідковування показників клієнтів"
@router.message(F.text == "📈 Відслідковування показників клієнтів")
async def track_client_metrics(message: Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        response = "У вас немає доступу до цієї функції."
        print(f"[TRACK_CLIENT_METRICS] Sending response: {response}")
        await message.answer(response)
        return
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if not user_clients:
        response = "Список клієнтів порожній."
        print(f"[TRACK_CLIENT_METRICS] Sending response: {response}")
        await message.answer(response)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for client_name in user_clients.keys():
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=client_name, callback_data=f"track_{client_name}")
        ])
    response = "Оберіть клієнта для відслідковування показників:"
    print(f"[TRACK_CLIENT_METRICS] Sending response: {response}")
    await message.answer(response, reply_markup=keyboard)
    await state.set_state(ClientStates.select_client_for_tracking)

@router.callback_query(F.data.startswith("track_"))
async def track_selected_client(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    
    if client_name in user_clients:
        if user_clients[client_name]["archive"]:
            # Сортуємо записи за датою
            entries = sorted(user_clients[client_name]["archive"], key=lambda x: x["date"])
            
            # Показуємо всі записи
            response = f"Дані для {client_name}:\n\n"
            for entry in entries:
                date = entry["date"]
                profile = entry["profile"]
                response += f"Дата: {date}\n"
                response += f"Вік: {profile['age']}\n"
                response += f"Вага: {profile['weight']} кг\n"
                response += f"Результати: {profile['results']}\n"
                response += f"Додатково: {profile['additional']}\n\n"
            
            # Аналіз за тиждень
            week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            week_entries = [e for e in entries if e["date"] >= week_ago]
            week_analysis = "Аналіз за останній тиждень:\n"
            if len(week_entries) >= 2:
                old_weight = float(week_entries[0]["profile"]["weight"])
                new_weight = float(week_entries[-1]["profile"]["weight"])
                weight_change = new_weight - old_weight
                week_analysis += f"Зміна ваги: {weight_change:+.1f} кг\n"
                week_analysis += f"Результати на початку: {week_entries[0]['profile']['results']}\n"
                week_analysis += f"Результати в кінці: {week_entries[-1]['profile']['results']}\n"
            else:
                week_analysis += "Недостатньо даних для аналізу за тиждень.\n"

            # Аналіз за місяць
            month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            month_entries = [e for e in entries if e["date"] >= month_ago]
            month_analysis = "Аналіз за останній місяць:\n"
            if len(month_entries) >= 2:
                old_weight = float(month_entries[0]["profile"]["weight"])
                new_weight = float(month_entries[-1]["profile"]["weight"])
                weight_change = new_weight - old_weight
                month_analysis += f"Зміна ваги: {weight_change:+.1f} кг\n"
                month_analysis += f"Результати на початку: {month_entries[0]['profile']['results']}\n"
                month_analysis += f"Результати в кінці: {month_entries[-1]['profile']['results']}\n"
            else:
                month_analysis += "Недостатньо даних для аналізу за місяць.\n"

            response += f"\n{week_analysis}\n{month_analysis}"
            print(f"[TRACK_SELECTED_CLIENT] Sending response: {response}")
            await callback.message.answer(response)
        else:
            response = f"Інформації про {client_name} немає. Будь ласка, заповніть анкету результатів."
            print(f"[TRACK_SELECTED_CLIENT] Sending response: {response}")
            await callback.message.answer(response)
    await state.clear()
    await callback.answer()

# Обробник команди /update
@router.message(Command("update"))
async def update_bot(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        response = "У вас немає доступу до цієї функції."
        print(f"[UPDATE] Sending response: {response}")
        await message.answer(response)
        return

    response = "Оновлення бота..."
    print(f"[UPDATE] Sending response: {response}")
    await message.answer(response)

    # Завантажуємо новий код із GitHub
    url = "https://raw.githubusercontent.com/bohdan123/telegram-bot-code/main/bot.py"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            response = f"Помилка при завантаженні коду: {response.status_code} {response.reason}"
            print(f"[UPDATE] Sending response: {response}")
            await message.answer(response)
            return

        # Зберігаємо новий код
        with open("/app/bot.py", "w") as f:
            f.write(response.text)

        response = "Код оновлено! Перезапускаю бота..."
        print(f"[UPDATE] Sending response: {response}")
        await message.answer(response)
        
        # Перезапускаємо бота
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        response = f"Помилка при оновленні: {e}"
        print(f"[UPDATE] Sending response: {response}")
        await message.answer(response)

# FastAPI ендпоінт
@app.get("/")
async def root():
    return {"message": "Bot is running"}

# Головна функція
async def main():
    print("Починаємо ініціалізацію бота...")
    dp.include_router(router)
    
    # Перевірка статусу вебхука
    print("Перевіряємо статус вебхука...")
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url:
        print(f"Вебхук активний: {webhook_info.url}. Видаляємо...")
        await bot.delete_webhook(drop_pending_updates=True)
        print("Вебхук видалено успішно.")
    else:
        print("Вебхук не активний, продовжуємо...")

    print("Запускаємо polling у фоновому режимі...")
    polling_task = asyncio.create_task(dp.start_polling(bot))
    print("Polling запущено.")

    print("Запускаємо FastAPI-сервер...")
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

    await polling_task

if __name__ == "__main__":
    print("Запускаємо бота...")
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Помилка при запуску бота: {e}")
