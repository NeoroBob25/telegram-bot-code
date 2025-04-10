@router.message(StateFilter(ClientStates.track_client_select))
async def process_track_client_select(message: types.Message, state: FSMContext):
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

    profiles = user_clients[client_name].get("profiles", [])
    if not profiles:
        response = f"Інформації про {client_name} немає. Будь ласка, заповніть анкету результатів."
        print(f"[PROCESS_TRACK_CLIENT_SELECT] Sending response: {response}")
        await message.answer(response)
        print(f"[PROCESS_TRACK_CLIENT_SELECT] Response sent successfully to User ID: {user_id}")
        await state.clear()
        return

    # Зберігаємо client_name у стані (про всяк випадок)
    await state.update_data(client_name=client_name)

    # Відправляємо анкети по одній
    for idx, profile in enumerate(profiles):
        response = f"📊 Показники клієнта {client_name} (Анкета №{idx + 1}):\n\n"
        response += f"📅 Дата: {profile['date']}\n"
        response += f"Вік: {profile['age']}\n"
        response += f"Вага: {profile['weight']} кг\n"
        response += f"Результати: {profile['results']}\n"
        response += f"Додатково: {profile['additional']}\n\n"

        # Використовуємо дату як унікальний ідентифікатор у callback_data
        profile_date = profile['date']
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Редагувати", callback_data=f"edit_info_{client_name}_{profile_date}"),
                InlineKeyboardButton(text=f"Видалити №{idx + 1}", callback_data=f"delete_info_{client_name}_{profile_date}")
            ]
        ])

        print(f"[PROCESS_TRACK_CLIENT_SELECT] Sending profile {idx + 1}: {response}")
        await message.answer(response, reply_markup=keyboard)
        print(f"[PROCESS_TRACK_CLIENT_SELECT] Profile {idx + 1} sent successfully to User ID: {user_id}")

    # Відправляємо статистику окремо
    one_week_ago = datetime.now().date() - timedelta(days=7)
    recent_profiles_week = [p for p in profiles if datetime.strptime(p["date"], "%Y-%m-%d").date() >= one_week_ago]
    one_month_ago = datetime.now().date() - timedelta(days=30)
    recent_profiles_month = [p for p in profiles if datetime.strptime(p["date"], "%Y-%m-%d").date() >= one_month_ago]

    response = f"📈 Статистика для {client_name}:\n\n"
    
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

    print(f"[PROCESS_TRACK_CLIENT_SELECT] Sending statistics: {response}")
    await message.answer(response)
    print(f"[PROCESS_TRACK_CLIENT_SELECT] Statistics sent successfully to User ID: {user_id}")
    await state.clear()

@router.callback_query(F.data.startswith("delete_info_"))
async def delete_client_info(callback: types.CallbackQuery, state: FSMContext):
    try:
        # Розбираємо callback_data: delete_info_{client_name}_{profile_date}
        parts = callback.data.split("_")
        if len(parts) != 4:
            raise ValueError("Некоректний формат callback_data")
        client_name = parts[2]
        profile_date = parts[3]
    except Exception as e:
        response = f"Помилка: Некоректний формат callback_data: {e}"
        print(f"[DELETE_CLIENT_INFO] Error: {response}")
        await callback.message.answer(response)
        await callback.answer()
        return

    user_id = callback.from_user.id
    user_clients = load_clients(user_id)

    print(f"[DELETE_CLIENT_INFO] Attempting to delete profile for client: {client_name}, date: {profile_date}")

    if client_name not in user_clients:
        response = f"Клієнта {client_name} не знайдено."
        print(f"[DELETE_CLIENT_INFO] Error: {response}")
        await callback.message.answer(response)
        await callback.answer()
        return

    profiles = user_clients[client_name].get("profiles", [])
    profile_to_delete = None
    for profile in profiles:
        if profile["date"] == profile_date:
            profile_to_delete = profile
            break

    if not profile_to_delete:
        response = f"Анкету для {client_name} за {profile_date} не знайдено."
        print(f"[DELETE_CLIENT_INFO] Error: {response}")
        await callback.message.answer(response)
        await callback.answer()
        return

    # Видаляємо профіль
    user_clients[client_name]["profiles"] = [p for p in profiles if p["date"] != profile_date]
    save_client(user_id, client_name, user_clients[client_name])

    response = f"Дані для {client_name} за {profile_date} видалено!"
    print(f"[DELETE_CLIENT_INFO] Sending response: {response}")
    await callback.message.answer(response)
    print(f"[DELETE_CLIENT_INFO] Response sent successfully to User ID: {user_id}")
    await callback.answer()
