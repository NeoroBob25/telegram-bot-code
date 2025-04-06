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
    client_info_date = State()
    track_client_select = State()
    edit_client_info_select_date = State()
    edit_client_info_field = State()
    delete_client_info_select_date = State()
    add_new_client_info_date = State()

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
        print(f"[START] Response sent successfully to User ID: {user_id}")
        if user_id not in members:
            members[user_id] = {"chat_id": chat_id, "interacted": True, "role": "admin"}
            save_member(user_id, members[user_id])
    else:
        response = "У вас немає доступу до бота."
        print(f"[START] Sending response: {response}")
        await message.answer(response)
        print(f"[START] Response sent successfully to User ID: {user_id}")

# Обробник "Додати клієнта"
@router.message(F.text == "Додати клієнта")
async def add_client(message: Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        response = "У вас немає доступу до цієї функції."
        print(f"[ADD_CLIENT] Sending response: {response}")
        await message.answer(response)
        print(f"[ADD_CLIENT] Response sent successfully to User ID: {message.from_user.id}")
        return
    response = "Введіть ім'я клієнта:"
    print(f"[ADD_CLIENT] Sending response: {response}")
    await message.answer(response)
    print(f"[ADD_CLIENT] Response sent successfully to User ID: {message.from_user.id}")
    await state.set_state(ClientStates.add_client_name)

@router.message(StateFilter(ClientStates.add_client_name))
async def process_client_name(message: Message, state: FSMContext):
    client_name = message.text.strip()
    await state.update_data(client_name=client_name)
    response = "Введіть кількість тренувань:"
    print(f"[PROCESS_CLIENT_NAME] Sending response: {response}")
    await message.answer(response)
    print(f"[PROCESS_CLIENT_NAME] Response sent successfully to User ID: {message.from_user.id}")
    await state.set_state(ClientStates.add_client_trainings)

@router.message(StateFilter(ClientStates.add_client_trainings))
async def process_client_trainings(message: Message, state: FSMContext):
    try:
        trainings = int(message.text.strip())
        await state.update_data(trainings=trainings)
        response = "Введіть контакт клієнта (юзернейм Telegram або номер телефону):"
        print(f"[PROCESS_CLIENT_TRAININGS] Sending response: {response}")
        await message.answer(response)
        print(f"[PROCESS_CLIENT_TRAININGS] Response sent successfully to User ID: {message.from_user.id}")
        await state.set_state(ClientStates.add_client_contact)
    except ValueError:
        response = "Будь ласка, введіть число для кількості тренувань."
        print(f"[PROCESS_CLIENT_TRAININGS] Sending response: {response}")
        await message.answer(response)
        print(f"[PROCESS_CLIENT_TRAININGS] Response sent successfully to User ID: {message.from_user.id}")

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
        "profiles": [],
        "archive": []
    }
    save_client(user_id, client_name, user_clients[client_name])
    response = f"Клієнта {client_name} додано! Кількість тренувань: {trainings}, Контакт: {contact}"
    print(f"[PROCESS_CLIENT_CONTACT] Sending response: {response}")
    await message.answer(response)
    print(f"[PROCESS_CLIENT_CONTACT] Response sent successfully to User ID: {user_id}")
    await state.clear()

# Обробник "Перегляд клієнтів"
@router.message(F.text == "Перегляд клієнтів")
async def view_clients(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        response = "У вас немає доступу до цієї функції."
        print(f"[VIEW_CLIENTS] Sending response: {response}")
        await message.answer(response)
        print(f"[VIEW_CLIENTS] Response sent successfully to User ID: {message.from_user.id}")
        return
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if not user_clients:
        response = "Список клієнтів порожній."
        print(f"[VIEW_CLIENTS] Sending response: {response}")
        await message.answer(response)
        print(f"[VIEW_CLIENTS] Response sent successfully to User ID: {user_id}")
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
            InlineKeyboardButton(text="📝", callback_data=f"change_{client_name}"),
            InlineKeyboardButton(text=f"{client_name}: {client_data['trainings']}", callback_data="noop"),
            InlineKeyboardButton(text="➡️", callback_data=f"plus_{client_name}"),
            InlineKeyboardButton(text="🗑", callback_data=f"delete_{client_name}"),
            InlineKeyboardButton(text="ℹ️", callback_data=f"info_{client_name}")
        ])
    print(f"[VIEW_CLIENTS] Sending response: {response}")
    await message.answer(response, reply_markup=keyboard, parse_mode="Markdown")
    print(f"[VIEW_CLIENTS] Response sent successfully to User ID: {user_id}")

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
                print(f"[MINUS_TRAINING] Response sent successfully to User ID: {user_id}")
            else:
                response = f"Скопіюйте повідомлення та відправте клієнту через контакт {contact}:\n{msg}"
                print(f"[MINUS_TRAINING] Sending response: {response}")
                await callback.message.answer(response)
                print(f"[MINUS_TRAINING] Response sent successfully to User ID: {user_id}")

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
                InlineKeyboardButton(text="📝", callback_data=f"change_{name}"),
                InlineKeyboardButton(text=f"{name}: {data['trainings']}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        print(f"[MINUS_TRAINING] Updating table: {response}")
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="Markdown")
        print(f"[MINUS_TRAINING] Table updated successfully for User ID: {user_id}")
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
                print(f"[PLUS_TRAINING] Response sent successfully to User ID: {user_id}")
            else:
                response = f"Скопіюйте повідомлення та відправте клієнту через контакт {contact}:\n{msg}"
                print(f"[PLUS_TRAINING] Sending response: {response}")
                await callback.message.answer(response)
                print(f"[PLUS_TRAINING] Response sent successfully to User ID: {user_id}")

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
                InlineKeyboardButton(text="📝", callback_data=f"change_{name}"),
                InlineKeyboardButton(text=f"{name}: {data['trainings']}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        print(f"[PLUS_TRAINING] Updating table: {response}")
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="Markdown")
        print(f"[PLUS_TRAINING] Table updated successfully for User ID: {user_id}")
    await callback.answer()

# Обробник кнопки "📝" у таблиці
@router.callback_query(F.data.startswith("change_"))
async def change_trainings_inline(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        await state.update_data(client_name=client_name)
        response = f"Введіть нову кількість тренувань для {client_name} (поточна: {user_clients[client_name]['trainings']}):"
        print(f"[CHANGE_TRAININGS_INLINE] Sending response: {response}")
        await callback.message.answer(response)
        print(f"[CHANGE_TRAININGS_INLINE] Response sent successfully to User ID: {user_id}")
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
                print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Response sent successfully to User ID: {user_id}")
            else:
                response = f"Скопіюйте повідомлення та відправте клієнту через контакт {contact}:\n{msg}"
                print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Sending response: {response}")
                await message.answer(response)
                print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Response sent successfully to User ID: {user_id}")

        response = f"Кількість тренувань для {client_name} змінено на {new_trainings}."
        print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Sending response: {response}")
        await message.answer(response)
        print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Response sent successfully to User ID: {user_id}")

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
                InlineKeyboardButton(text="📝", callback_data=f"change_{name}"),
                InlineKeyboardButton(text=f"{name}: {data['trainings']}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        await message.answer(response, reply_markup=keyboard, parse_mode="Markdown")
        print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Table updated successfully for User ID: {user_id}")

        await state.clear()
    except ValueError:
        response = "Будь ласка, введіть число для кількості тренувань."
        print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Sending response: {response}")
        await message.answer(response)
        print(f"[PROCESS_CHANGE_TRAININGS_COUNT] Response sent successfully to User ID: {user_id}")

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
                InlineKeyboardButton(text="📝", callback_data=f"change_{name}"),
                InlineKeyboardButton(text=f"{name}: {data['trainings']}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        print(f"[DELETE_CLIENT] Updating table: {response}")
        await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="Markdown")
        print(f"[DELETE_CLIENT] Table updated successfully for User ID: {user_id}")
        response = f"Клієнта {client_name} видалено!"
        print(f"[DELETE_CLIENT] Sending response: {response}")
        await callback.message.answer(response)
        print(f"[DELETE_CLIENT] Response sent successfully to User ID: {user_id}")
    await callback.answer()

# Обробник кнопки "ℹ️"
@router.callback_query(F.data.startswith("info_"))
async def client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        await state.update_data(client_name=client_name)
        response = f"Введіть дату для анкети клієнта {client_name} (формат: РРРР-ММ-ДД, наприклад, 2025-04-06). Залиште порожнім для сьогоднішньої дати:"
        print(f"[CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
        print(f"[CLIENT_INFO] Response sent successfully to User ID: {user_id}")
        await state.set_state(ClientStates.client_info_date)
    await callback.answer()

@router.message(StateFilter(ClientStates.client_info_date))
async def process_client_info_date(message: Message, state: FSMContext):
    date_input = message.text.strip()
    if date_input:
        try:
            selected_date = datetime.strptime(date_input, "%Y-%m-%d").date()
        except ValueError:
            response = "Неправильний формат дати. Використовуйте РРРР-ММ-ДД (наприклад, 2025-04-06)."
            print(f"[CLIENT_INFO_DATE] Sending response: {response}")
            await message.answer(response)
            print(f"[CLIENT_INFO_DATE] Response sent successfully to User ID: {message.from_user.id}")
            return
    else:
        selected_date = datetime.now().date()
    
    await state.update_data(selected_date=selected_date.isoformat())
    response = f"Введіть вік клієнта:"
    print(f"[CLIENT_INFO_DATE] Sending response: {response}")
    await message.answer(response)
    print(f"[CLIENT_INFO_DATE] Response sent successfully to User ID: {message.from_user.id}")
    await state.set_state(ClientStates.client_info_age)

@router.message(StateFilter(ClientStates.client_info_age))
async def process_client_info_age(message: Message, state: FSMContext):
    age = message.text.strip()
    await state.update_data(age=age)
    response = "Введіть вагу клієнта (кг):"
    print(f"[PROCESS_CLIENT_INFO_AGE] Sending response: {response}")
    await message.answer(response)
    print(f"[PROCESS_CLIENT_INFO_AGE] Response sent successfully to User ID: {message.from_user.id}")
    await state.set_state(ClientStates.client_info_weight)

@router.message(StateFilter(ClientStates.client_info_weight))
async def process_client_info_weight(message: Message, state: FSMContext):
    weight = message.text.strip()
    await state.update_data(weight=weight)
    response = "Введіть результати клієнта (наприклад, прогрес у вправах, заміри тіла):"
    print(f"[PROCESS_CLIENT_INFO_WEIGHT] Sending response: {response}")
    await message.answer(response)
    print(f"[PROCESS_CLIENT_INFO_WEIGHT] Response sent successfully to User ID: {message.from_user.id}")
    await state.set_state(ClientStates.client_info_results)

@router.message(StateFilter(ClientStates.client_info_results))
async def process_client_info_results(message: Message, state: FSMContext):
    results = message.text.strip()
    await state.update_data(results=results)
    response = "Введіть додаткову інформацію (якщо є):"
    print(f"[PROCESS_CLIENT_INFO_RESULTS] Sending response: {response}")
    await message.answer(response)
    print(f"[PROCESS_CLIENT_INFO_RESULTS] Response sent successfully to User ID: {message.from_user.id}")
    await state.set_state(ClientStates.client_info_additional)

@router.message(StateFilter(ClientStates.client_info_additional))
async def process_client_info_additional(message: Message, state: FSMContext):
    additional = message.text.strip()
    data = await state.get_data()
    client_name = data["client_name"]
    selected_date = data["selected_date"]
    user_id = message.from_user.id
    user_clients = load_clients(user_id)

    # Формуємо профіль
    profile = {
        "date": selected_date,
        "age": data["age"],
        "weight": data["weight"],
        "results": data["results"],
        "additional": additional
    }

    # Зберігаємо профіль у списку profiles
    if "profiles" not in user_clients[client_name]:
        user_clients[client_name]["profiles"] = []
    
    # Перевіряємо, чи є профіль із такою датою
    for i, existing_profile in enumerate(user_clients[client_name]["profiles"]):
        if existing_profile["date"] == selected_date:
            user_clients[client_name]["profiles"][i] = profile
            break
    else:
        user_clients[client_name]["profiles"].append(profile)

    # Сортуємо профілі за датою
    user_clients[client_name]["profiles"].sort(key=lambda x: x["date"])

    save_client(user_id, client_name, user_clients[client_name])

    # Показуємо анкету та пропонуємо дії
    response = f"Анкета клієнта {client_name} за {selected_date}:\n"
    response += f"Вік: {profile['age']}\n"
    response += f"Вага: {profile['weight']} кг\n"
    response += f"Результати: {profile['results']}\n"
    response += f"Додатково: {profile['additional']}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Зберегти", callback_data=f"save_info_{client_name}_{selected_date}")],
        [InlineKeyboardButton(text="Редагувати", callback_data=f"edit_info_{client_name}_{selected_date}")],
        [InlineKeyboardButton(text="Видалити", callback_data=f"delete_info_{client_name}_{selected_date}")],
        [InlineKeyboardButton(text="Додати нову інформацію", callback_data=f"add_new_info_{client_name}")],
        [InlineKeyboardButton(text="Аналізувати результати", callback_data=f"analyze_info_{client_name}")]
    ])

    print(f"[PROCESS_CLIENT_INFO_ADDITIONAL] Sending response: {response}")
    await message.answer(response, reply_markup=keyboard)
    print(f"[PROCESS_CLIENT_INFO_ADDITIONAL] Response sent successfully to User ID: {user_id}")
    await state.clear()

# Обробник кнопки "Зберегти"
@router.callback_query(F.data.startswith("save_info_"))
async def save_client_info(callback: types.CallbackQuery):
    _, client_name, selected_date = callback.data.split("_", 2)
    user_id = callback.from_user.id
    response = f"Дані для {client_name} за {selected_date} збережено!"
    print(f"[SAVE_CLIENT_INFO] Sending response: {response}")
    await callback.message.answer(response)
    print(f"[SAVE_CLIENT_INFO] Response sent successfully to User ID: {user_id}")
    await callback.answer()

# Обробник кнопки "Редагувати"
@router.callback_query(F.data.startswith("edit_info_"))
async def edit_client_info(callback: types.CallbackQuery, state: FSMContext):
    _, client_name, selected_date = callback.data.split("_", 2)
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    
    profiles = user_clients[client_name]["profiles"]
    profile_to_edit = next((p for p in profiles if p["date"] == selected_date), None)
    
    if profile_to_edit:
        response = f"Яке поле хочете відредагувати для {client_name} за {selected_date}?\n"
        response += "Доступні поля: Вік, Вага, Результати, Додатково"
        await state.update_data(client_name=client_name, selected_date=selected_date)
        print(f"[EDIT_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
        print(f"[EDIT_CLIENT_INFO] Response sent successfully to User ID: {user_id}")
        await state.set_state(ClientStates.edit_client_info_field)
    await callback.answer()

@router.message(StateFilter(ClientStates.edit_client_info_field))
async def process_edit_client_info_field(message: Message, state: FSMContext):
    field = message.text.strip().lower()
    data = await state.get_data()
    client_name = data["client_name"]
    selected_date = data["selected_date"]
    
    if field not in ["вік", "вага", "результати", "додатково"]:
        response = "Невірне поле. Виберіть: Вік, Вага, Результати, Додатково."
        print(f"[PROCESS_EDIT_CLIENT_INFO_FIELD] Sending response: {response}")
        await message.answer(response)
        print(f"[PROCESS_EDIT_CLIENT_INFO_FIELD] Response sent successfully to User ID: {message.from_user.id}")
        return
    
    await state.update_data(field_to_edit=field)
    response = f"Введіть нове значення для поля '{field}' для {client_name} за {selected_date}:"
    print(f"[PROCESS_EDIT_CLIENT_INFO_FIELD] Sending response: {response}")
    await message.answer(response)
    print(f"[PROCESS_EDIT_CLIENT_INFO_FIELD] Response sent successfully to User ID: {message.from_user.id}")
    await state.set_state(ClientStates.edit_client_info_select_date)

@router.message(StateFilter(ClientStates.edit_client_info_select_date))
async def process_edit_client_info_value(message: Message, state: FSMContext):
    new_value = message.text.strip()
    data = await state.get_data()
    client_name = data["client_name"]
    selected_date = data["selected_date"]
    field = data["field_to_edit"]
    user_id = message.from_user.id
    user_clients = load_clients(user_id)

    profiles = user_clients[client_name]["profiles"]
    for profile in profiles:
        if profile["date"] == selected_date:
            if field == "вік":
                profile["age"] = new_value
            elif field == "вага":
                profile["weight"] = new_value
            elif field == "результати":
                profile["results"] = new_value
            elif field == "додатково":
                profile["additional"] = new_value
            break

    save_client(user_id, client_name, user_clients[client_name])

    response = f"Дані для {client_name} за {selected_date} оновлено!\n"
    response += f"Вік: {profile['age']}\n"
    response += f"Вага: {profile['weight']} кг\n"
    response += f"Результати: {profile['results']}\n"
    response += f"Додатково: {profile['additional']}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Зберегти", callback_data=f"save_info_{client_name}_{selected_date}")],
        [InlineKeyboardButton(text="Редагувати", callback_data=f"edit_info_{client_name}_{selected_date}")],
        [InlineKeyboardButton(text="Видалити", callback_data=f"delete_info_{client_name}_{selected_date}")],
        [InlineKeyboardButton(text="Додати нову інформацію", callback_data=f"add_new_info_{client_name}")],
        [InlineKeyboardButton(text="Аналізувати результати", callback_data=f"analyze_info_{client_name}")]
    ])

    print(f"[PROCESS_EDIT_CLIENT_INFO_VALUE] Sending response: {response}")
    await message.answer(response, reply_markup=keyboard)
    print(f"[PROCESS_EDIT_CLIENT_INFO_VALUE] Response sent successfully to User ID: {user_id}")
    await state.clear()

# Обробник кнопки "Видалити"
@router.callback_query(F.data.startswith("delete_info_"))
async def delete_client_info(callback: types.CallbackQuery):
    _, client_name, selected_date = callback.data.split("_", 2)
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)

    profiles = user_clients[client_name]["profiles"]
    user_clients[client_name]["profiles"] = [p for p in profiles if p["date"] != selected_date]
    save_client(user_id, client_name, user_clients[client_name])

    response = f"Дані для {client_name} за {selected_date} видалено!"
    print(f"[DELETE_CLIENT_INFO] Sending response: {response}")
    await callback.message.answer(response)
    print(f"[DELETE_CLIENT_INFO] Response sent successfully to User ID: {user_id}")
    await callback.answer()

# Обробник кнопки "Додати нову інформацію"
@router.callback_query(F.data.startswith("add_new_info_"))
async def add_new_client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_", 3)[3]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        await state.update_data(client_name=client_name)
        response = f"Введіть дату для нової анкети клієнта {client_name} (формат: РРРР-ММ-ДД, наприклад, 2025-04-06). Залиште порожнім для сьогоднішньої дати:"
        print(f"[ADD_NEW_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
        print(f"[ADD_NEW_CLIENT_INFO] Response sent successfully to User ID: {user_id}")
        await state.set_state(ClientStates.add_new_client_info_date)
    await callback.answer()

@router.message(StateFilter(ClientStates.add_new_client_info_date))
async def process_add_new_client_info_date(message: Message, state: FSMContext):
    date_input = message.text.strip()
    if date_input:
        try:
            selected_date = datetime.strptime(date_input, "%Y-%m-%d").date()
        except ValueError:
            response = "Неправильний формат дати. Використовуйте РРРР-ММ-ДД (наприклад, 2025-04-06)."
            print(f"[ADD_NEW_CLIENT_INFO_DATE] Sending response: {response}")
            await message.answer(response)
            print(f"[ADD_NEW_CLIENT_INFO_DATE] Response sent successfully to User ID: {message.from_user.id}")
            return
    else:
        selected_date = datetime.now().date()
    
    await state.update_data(selected_date=selected_date.isoformat())
    response = "Введіть вік клієнта:"
    print(f"[ADD_NEW_CLIENT_INFO_DATE] Sending response: {response}")
    await message.answer(response)
    print(f"[ADD_NEW_CLIENT_INFO_DATE] Response sent successfully to User ID: {message.from_user.id}")
    await state.set_state(ClientStates.client_info_age)

# Обробник кнопки "Аналізувати результати"
@router.callback_query(F.data.startswith("analyze_info_"))
async def analyze_client_info(callback: types.CallbackQuery):
    client_name = callback.data.split("_", 2)[2]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    
    profiles = user_clients[client_name]["profiles"]
    if not profiles:
        response = f"Інформації про {client_name} немає. Будь ласка, заповніть анкету результатів."
        print(f"[ANALYZE_CLIENT_INFO] Sending response: {response}")
        await callback.message.answer(response)
        print(f"[ANALYZE_CLIENT_INFO] Response sent successfully to User ID: {user_id}")
        await callback.answer()
        return

    # Аналіз за останні 7 днів
    one_week_ago = datetime.now().date() - timedelta(days=7)
    recent_profiles_week = [p for p in profiles if datetime.strptime(p["date"], "%Y-%m-%d").date() >= one_week_ago]
    
    # Аналіз за останні 30 днів
    one_month_ago = datetime.now().date() - timedelta(days=30)
    recent_profiles_month = [p for p in profiles if datetime.strptime(p["date"], "%Y-%m-%d").date() >= one_month_ago]

    response = f"Аналіз результатів для {client_name}:\n\n"

    # Аналіз за тиждень
    if recent_profiles_week:
        response += "📅 За останні 7 днів:\n"
        if len(recent_profiles_week) > 1:
            first_week = recent_profiles_week[0]
            last_week = recent_profiles_week[-1]
            try:
                weight_change_week = float(last_week["weight"]) - float(first_week["weight"])
                response += f"Зміна ваги: {weight_change_week:+.1f} кг\n"
            except (ValueError, TypeError):
                response += "Зміна ваги: дані недоступні\n"
            response += f"Останні результати: {last_week['results']}\n"
        else:
            response += "Недостатньо даних для аналізу за тиждень.\n"
    else:
        response += "📅 За останні 7 днів: даних немає.\n"

    # Аналіз за місяць
    if recent_profiles_month:
        response += "\n📅 За останні 30 днів:\n"
        if len(recent_profiles_month) > 1:
            first_month = recent_profiles_month[0]
            last_month = recent_profiles_month[-1]
            try:
                weight_change_month = float(last_month["weight"]) - float(first_month["weight"])
                response += f"Зміна ваги: {weight_change_month:+.1f} кг\n"
            except (ValueError, TypeError):
                response += "Зміна ваги: дані недоступні\n"
            response += f"Останні результати: {last_month['results']}\n"
        else:
            response += "Недостатньо даних для аналізу за місяць.\n"
    else:
        response += "\n📅 За останні 30 днів: даних немає.\n"

    print(f"[ANALYZE_CLIENT_INFO] Sending response: {response}")
    await callback.message.answer(response)
    print(f"[ANALYZE_CLIENT_INFO] Response sent successfully to User ID: {user_id}")
    await callback.answer()

# Обробник "📈 Відслідковування показників клієнтів"
@router.message(F.text == "📈 Відслідковування показників клієнтів")
async def track_client_progress(message: Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        response = "У вас немає доступу до цієї функції."
        print(f"[TRACK_CLIENT_PROGRESS] Sending response: {response}")
        await message.answer(response)
        print(f"[TRACK_CLIENT_PROGRESS] Response sent successfully to User ID: {message.from_user.id}")
        return
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if not user_clients:
        response = "Список клієнтів порожній."
        print(f"[TRACK_CLIENT_PROGRESS] Sending response: {response}")
        await message.answer(response)
        print(f"[TRACK_CLIENT_PROGRESS] Response sent successfully to User ID: {user_id}")
        return

    response = "Оберіть клієнта для перегляду показників:\n"
    for client_name in user_clients.keys():
        response += f"- {client_name}\n"
    print(f"[TRACK_CLIENT_PROGRESS] Sending response: {response}")
    await message.answer(response)
    print(f"[TRACK_CLIENT_PROGRESS] Response sent successfully to User ID: {user_id}")
    await state.set_state(ClientStates.track_client_select)

@router.message(StateFilter(ClientStates.track_client_select))
async def process_track_client_select(message: Message, state: FSMContext):
    client_name = message.text.strip()
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if client_name not in user_clients:
        response = "Такого клієнта не знайдено."
        print(f"[PROCESS_TRACK_CLIENT_SELECT] Sending response: {response}")
        await message.answer(response)
        print(f"[PROCESS_TRACK_CLIENT_SELECT] Response sent successfully to User ID: {user_id}")
        await state.clear()
        return

    profiles = user_clients[client_name]["profiles"]
    if not profiles:
        response = f"Інформації про {client_name} немає. Будь ласка, заповніть анкету результатів."
        print(f"[PROCESS_TRACK_CLIENT_SELECT] Sending response: {response}")
        await message.answer(response)
        print(f"[PROCESS_TRACK_CLIENT_SELECT] Response sent successfully to User ID: {user_id}")
        await state.clear()
        return

    response = f"📊 Показники клієнта {client_name}:\n\n"
    for profile in profiles:
        response += f"📅 Дата: {profile['date']}\n"
        response += f"Вік: {profile['age']}\n"
        response += f"Вага: {profile['weight']} кг\n"
        response += f"Результати: {profile['results']}\n"
        response += f"Додатково: {profile['additional']}\n\n"

    # Аналіз за тиждень і місяць
    one_week_ago = datetime.now().date() - timedelta(days=7)
    recent_profiles_week = [p for p in profiles if datetime.strptime(p["date"], "%Y-%m-%d").date() >= one_week_ago]
    one_month_ago = datetime.now().date() - timedelta(days=30)
    recent_profiles_month = [p for p in profiles if datetime.strptime(p["date"], "%Y-%m-%d").date() >= one_month_ago]

    response += "📈 Статистика:\n"
    
    if recent_profiles_week:
        response += "За останні 7 днів:\n"
        if len(recent_profiles_week) > 1:
            first_week = recent_profiles_week[0]
            last_week = recent_profiles_week[-1]
            try:
                weight_change_week = float(last_week["weight"]) - float(first_week["weight"])
                response += f"Зміна ваги: {weight_change_week:+.1f} кг\n"
            except (ValueError, TypeError):
                response += "Зміна ваги: дані недоступні\n"
            response += f"Останні результати: {last_week['results']}\n"
        else:
            response += "Недостатньо даних для аналізу за тиждень.\n"
    else:
        response += "За останні 7 днів: даних немає.\n"

    if recent_profiles_month:
        response += "\nЗа останні 30 днів:\n"
        if len(recent_profiles_month) > 1:
            first_month = recent_profiles_month[0]
            last_month = recent_profiles_month[-1]
            try:
                weight_change_month = float(last_month["weight"]) - float(first_month["weight"])
                response += f"Зміна ваги: {weight_change_month:+.1f} кг\n"
            except (ValueError, TypeError):
                response += "Зміна ваги: дані недоступні\n"
            response += f"Останні результати: {last_month['results']}\n"
        else:
            response += "Недостатньо даних для аналізу за місяць.\n"
    else:
        response += "\nЗа останні 30 днів: даних немає.\n"

    print(f"[PROCESS_TRACK_CLIENT_SELECT] Sending response: {response}")
    await message.answer(response)
    print(f"[PROCESS_TRACK_CLIENT_SELECT] Response sent successfully to User ID: {user_id}")
    await state.clear()

# Обробник команди /update
@router.message(Command("update"))
async def update_bot(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        response = "У вас немає доступу до цієї функції."
        print(f"[UPDATE] Sending response: {response}")
        await message.answer(response)
        print(f"[UPDATE] Response sent successfully to User ID: {message.from_user.id}")
        return

    response = "Оновлення бота..."
    print(f"[UPDATE] Sending response: {response}")
    await message.answer(response)
    print(f"[UPDATE] Response sent successfully to User ID: {message.from_user.id}")

    # Завантажуємо новий код із GitHub
    url = "https://raw.githubusercontent.com/bohdan123/telegram-bot-code/main/bot.py"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            response = f"Помилка при завантаженні коду: {response.status_code} {response.reason}"
            print(f"[UPDATE] Sending response: {response}")
            await message.answer(response)
            print(f"[UPDATE] Response sent successfully to User ID: {message.from_user.id}")
            return

        # Зберігаємо новий код
        with open("/app/bot.py", "w") as f:
            f.write(response.text)

        response = "Код оновлено! Перезапускаю бота..."
        print(f"[UPDATE] Sending response: {response}")
        await message.answer(response)
        print(f"[UPDATE] Response sent successfully to User ID: {message.from_user.id}")
        
        # Перезапускаємо бота
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        response = f"Помилка при оновленні: {e}"
        print(f"[UPDATE] Sending response: {response}")
        await message.answer(response)
        print(f"[UPDATE] Response sent successfully to User ID: {message.from_user.id}")

# FastAPI ендпоінт
@app.get("/")
async def root():
    return {"message": "Bot is running"}

# Головна функція
async def main():
    print("Починаємо ініціалізацію бота...")
    dp.include_router(router)
    
    # Перевірка статусу вебхука з кількома спробами
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            print(f"Перевіряємо статус вебхука (спроба {attempt + 1}/{max_attempts})...")
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                print(f"Вебхук активний: {webhook_info.url}. Видаляємо...")
                await bot.delete_webhook(drop_pending_updates=True)
                print("Вебхук видалено успішно.")
            else:
                print("Вебхук не активний, продовжуємо...")
                break
        except Exception as e:
            print(f"Помилка при перевірці/видаленні вебхука: {e}")
            if attempt == max_attempts - 1:
                print("Не вдалося видалити вебхук після кількох спроб. Зупиняємо бота.")
                raise Exception("Не вдалося видалити вебхук. Перевірте токен і налаштування Telegram.")
            await asyncio.sleep(2)  # Чекаємо перед наступною спробою

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
        raise
