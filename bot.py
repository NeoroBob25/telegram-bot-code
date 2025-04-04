import json
import os
import asyncio
import logging
import sys
import requests
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
    delete_client = State()
    change_trainings = State()
    change_trainings_count = State()
    client_info_age = State()
    client_info_weight = State()
    client_info_results = State()
    client_info_additional = State()
    confirm_notification = State()

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

    print(f"User ID: {user_id}, Chat ID: {chat_id}, Username: {username}")
    members = load_members()
    if user_id in ALLOWED_USERS:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Додати клієнта")],
                [KeyboardButton(text="Перегляд клієнтів")],
                [KeyboardButton(text="Видалити клієнта")],
                [KeyboardButton(text="📝Змінити кількість тренувань")],
            ],
            resize_keyboard=True
        )
        await message.answer("Вітаю, Богдане! Ось доступні дії:", reply_markup=keyboard)
        if user_id not in members:
            members[user_id] = {"chat_id": chat_id, "interacted": True, "role": "admin"}
            save_member(user_id, members[user_id])
    else:
        await message.answer("У вас немає доступу до бота.")

# Обробник "Додати клієнта"
@router.message(F.text == "Додати клієнта")
async def add_client(message: Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас немає доступу до цієї функції.")
        return
    await message.answer("Введіть ім'я клієнта:")
    await state.set_state(ClientStates.add_client_name)

@router.message(StateFilter(ClientStates.add_client_name))
async def process_client_name(message: Message, state: FSMContext):
    client_name = message.text.strip()
    await state.update_data(client_name=client_name)
    await message.answer("Введіть кількість тренувань:")
    await state.set_state(ClientStates.add_client_trainings)

@router.message(StateFilter(ClientStates.add_client_trainings))
async def process_client_trainings(message: Message, state: FSMContext):
    try:
        trainings = int(message.text.strip())
        await state.update_data(trainings=trainings)
        await message.answer("Введіть контакт клієнта (юзернейм Telegram або номер телефону):")
        await state.set_state(ClientStates.add_client_contact)
    except ValueError:
        await message.answer("Будь ласка, введіть число для кількості тренувань.")

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
    await message.answer(f"Клієнта {client_name} додано! Кількість тренувань: {trainings}, Контакт: {contact}")
    await state.clear()

# Обробник "Перегляд клієнтів"
@router.message(F.text == "Перегляд клієнтів")
async def view_clients(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас немає доступу до цієї функції.")
        return
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if not user_clients:
        await message.answer("Список клієнтів порожній.")
        return

    response = "Список твоїх клієнтів:\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for client_name, client_data in user_clients.items():
        response += f"{client_name} | Тренувань: {client_data['trainings']}\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="⬅️", callback_data=f"minus_{client_name}"),
            InlineKeyboardButton(text=f"{client_data['trainings']}", callback_data="noop"),
            InlineKeyboardButton(text="➡️", callback_data=f"plus_{client_name}"),
            InlineKeyboardButton(text="🗑", callback_data=f"delete_{client_name}"),
            InlineKeyboardButton(text="ℹ️", callback_data=f"info_{client_name}")
        ])
    await message.answer(response, reply_markup=keyboard)

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
            await state.update_data(client_name=client_name, message_text=msg, change=change, new_trainings=new_trainings)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Відправити", callback_data="send_notification")]
            ])
            await callback.message.answer(f"Повідомлення для {client_name}:\n{msg}", reply_markup=keyboard)

        # Оновлення таблиці
        response = "Список твоїх клієнтів:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for name, data in user_clients.items():
            response += f"{name} | Тренувань: {data['trainings']}\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="⬅️", callback_data=f"minus_{name}"),
                InlineKeyboardButton(text=f"{data['trainings']}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        await callback.message.edit_text(response, reply_markup=keyboard)
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
            await state.update_data(client_name=client_name, message_text=msg, change=change, new_trainings=new_trainings)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Відправити", callback_data="send_notification")]
            ])
            await callback.message.answer(f"Повідомлення для {client_name}:\n{msg}", reply_markup=keyboard)

        # Оновлення таблиці
        response = "Список твоїх клієнтів:\n\n"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for name, data in user_clients.items():
            response += f"{name} | Тренувань: {data['trainings']}\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="⬅️", callback_data=f"minus_{name}"),
                InlineKeyboardButton(text=f"{data['trainings']}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        await callback.message.edit_text(response, reply_markup=keyboard)
    await callback.answer()

# Обробник відправки повідомлення
@router.callback_query(F.data == "send_notification")
async def send_notification(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client_name = data["client_name"]
    message_text = data["message_text"]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    contact = user_clients[client_name]["contact"]

    if contact and contact.startswith("@"):
        try:
            chat = await bot.get_chat(contact)
            await bot.send_message(chat.id, message_text)
            await callback.message.edit_text(f"Повідомлення для {client_name} відправлено!")
        except Exception as e:
            await callback.message.edit_text(f"Не вдалося надіслати повідомлення клієнту: {e}")
    else:
        await callback.message.edit_text("Контакт не підтримується для надсилання.")
    await state.clear()
    await callback.answer()

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
            response += f"{name} | Тренувань: {data['trainings']}\n"
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text="⬅️", callback_data=f"minus_{name}"),
                InlineKeyboardButton(text=f"{data['trainings']}", callback_data="noop"),
                InlineKeyboardButton(text="➡️", callback_data=f"plus_{name}"),
                InlineKeyboardButton(text="🗑", callback_data=f"delete_{name}"),
                InlineKeyboardButton(text="ℹ️", callback_data=f"info_{name}")
            ])
        await callback.message.edit_text(response, reply_markup=keyboard)
        await callback.message.answer(f"Клієнта {client_name} видалено!")
    await callback.answer()

# Обробник кнопки "ℹ️"
@router.callback_query(F.data.startswith("info_"))
async def client_info(callback: types.CallbackQuery, state: FSMContext):
    client_name = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        await state.update_data(client_name=client_name)
        await callback.message.answer(f"Введіть вік клієнта {client_name}:")
        await state.set_state(ClientStates.client_info_age)
    await callback.answer()

@router.message(StateFilter(ClientStates.client_info_age))
async def process_client_info_age(message: Message, state: FSMContext):
    age = message.text.strip()
    await state.update_data(age=age)
    await message.answer("Введіть вагу клієнта (кг):")
    await state.set_state(ClientStates.client_info_weight)

@router.message(StateFilter(ClientStates.client_info_weight))
async def process_client_info_weight(message: Message, state: FSMContext):
    weight = message.text.strip()
    await state.update_data(weight=weight)
    await message.answer("Введіть результати клієнта (наприклад, прогрес у вправах):")
    await state.set_state(ClientStates.client_info_results)

@router.message(StateFilter(ClientStates.client_info_results))
async def process_client_info_results(message: Message, state: FSMContext):
    results = message.text.strip()
    await state.update_data(results=results)
    await message.answer("Введіть додаткову інформацію (якщо є):")
    await state.set_state(ClientStates.client_info_additional)

@router.message(StateFilter(ClientStates.client_info_additional))
async def process_client_info_additional(message: Message, state: FSMContext):
    additional = message.text.strip()
    data = await state.get_data()
    client_name = data["client_name"]
    user_id = message.from_user.id
    user_clients = load_clients(user_id)

    # Оновлюємо профіль клієнта
    profile = {
        "age": data["age"],
        "weight": data["weight"],
        "results": data["results"],
        "additional": additional
    }
    user_clients[client_name]["profile"] = profile

    # Додаємо до архіву
    user_clients[client_name]["archive"].append({
        "timestamp": message.date.isoformat(),
        "profile": profile
    })

    # Аналіз (зміна ваги)
    analysis = ""
    if len(user_clients[client_name]["archive"]) > 1:
        old_weight = float(user_clients[client_name]["archive"][-2]["profile"]["weight"])
        new_weight = float(profile["weight"])
        weight_change = new_weight - old_weight
        analysis = f"Зміна ваги: {weight_change:+.1f} кг\n"

    save_client(user_id, client_name, user_clients[client_name])

    # Показуємо анкету
    response = f"Анкета клієнта {client_name}:\n"
    response += f"Вік: {profile['age']}\n"
    response += f"Вага: {profile['weight']} кг\n"
    response += f"Результати: {profile['results']}\n"
    response += f"Додатково: {profile['additional']}\n"
    response += analysis
    await message.answer(response)
    await state.clear()

# Обробник "Видалити клієнта"
@router.message(F.text == "Видалити клієнта")
async def delete_client(message: Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас немає доступу до цієї функції.")
        return
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if not user_clients:
        await message.answer("Список клієнтів порожній.")
        return
    response = "Оберіть клієнта для видалення:\n"
    for client_name in user_clients.keys():
        response += f"- {client_name}\n"
    await message.answer(response)
    await state.set_state(ClientStates.delete_client)

@router.message(StateFilter(ClientStates.delete_client))
async def process_delete_client(message: Message, state: FSMContext):
    client_name = message.text.strip()
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if client_name in user_clients:
        del user_clients[client_name]
        data = load_data()
        data[str(user_id)] = user_clients
        save_data(data)
        await message.answer(f"Клієнта {client_name} видалено!")
    else:
        await message.answer("Такого клієнта не знайдено.")
    await state.clear()

# Обробник "📝Змінити кількість тренувань"
@router.message(F.text == "📝Змінити кількість тренувань")
async def change_trainings(message: Message, state: FSMContext):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас немає доступу до цієї функції.")
        return
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if not user_clients:
        await message.answer("Список клієнтів порожній.")
        return
    response = "Оберіть клієнта для зміни кількості тренувань:\n"
    for client_name in user_clients.keys():
        response += f"- {client_name}\n"
    await message.answer(response)
    await state.set_state(ClientStates.change_trainings)

@router.message(StateFilter(ClientStates.change_trainings))
async def process_change_trainings(message: Message, state: FSMContext):
    client_name = message.text.strip()
    user_id = message.from_user.id
    user_clients = load_clients(user_id)
    if client_name not in user_clients:
        await message.answer("Такого клієнта не знайдено.")
        await state.clear()
        return

    await state.update_data(client_name=client_name)
    await message.answer(f"Введіть нову кількість тренувань для {client_name} (поточна: {user_clients[client_name]['trainings']}):")
    await state.set_state(ClientStates.change_trainings_count)

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
            await state.update_data(client_name=client_name, message_text=msg, change=change, new_trainings=new_trainings)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Відправити", callback_data="send_notification")]
            ])
            await message.answer(f"Повідомлення для {client_name}:\n{msg}", reply_markup=keyboard)

        await message.answer(f"Кількість тренувань для {client_name} змінено на {new_trainings}.")
        await state.clear()
    except ValueError:
        await message.answer("Будь ласка, введіть число для кількості тренувань.")

# Обробник команди /update
@router.message(Command("update"))
async def update_bot(message: Message):
    if message.from_user.id not in ALLOWED_USERS:
        await message.answer("У вас немає доступу до цієї функції.")
        return

    await message.answer("Оновлення бота...")

    # Завантажуємо новий код із GitHub
    url = "https://raw.githubusercontent.com/bohdan123/telegram-bot-code/main/bot.py"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            await message.answer(f"Помилка при завантаженні коду: {response.status_code} {response.reason}")
            return

        # Зберігаємо новий код
        with open("/app/bot.py", "w") as f:
            f.write(response.text)

        await message.answer("Код оновлено! Перезапускаю бота...")
        
        # Перезапускаємо бота
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        await message.answer(f"Помилка при оновленні: {e}")

# FastAPI ендпоінт
@app.get("/")
async def root():
    return {"message": "Bot is running"}

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
