import re
from datetime import datetime

from vkbottle.bot import BotLabeler, Message

from bot.core.config import settings
from bot.db import (
    create_player,
    get_player,
    get_player_clan,
    update_player_balance,
    update_username,
)
from bot.services.clans import (
    get_clan_bonuses,
)
from bot.utils import format_number, pointer_to_screen_name

user_labeler = BotLabeler()
user_labeler.vbml_ignore_case = True


# ======================
# КОМАНДА ПЕРЕВОДА ДЕНЕГ
# ======================


@user_labeler.message(
    text=[
        "перевод <cmd_args>",
        "перевести <cmd_args>",
        "/перевод <cmd_args>",
        "/перевести <cmd_args>",
    ]
)
async def transfer_money_handler(message: Message, cmd_args: str):
    """Перевод денег другому игроку"""
    parts = cmd_args.strip().split()

    if len(parts) < 2:
        return "❌ Укажите айди игрока и сумму перевода!\n📝 Использование: /перевод [айди] [сумма]"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    amount_str = parts[1]
    user_id = message.from_id

    try:
        amount = int(amount_str)
        if amount <= 0:
            return "❌ Сумма перевода должна быть положительным числом!"
    except ValueError:
        return "❌ Сумма перевода должна быть числом!"

    player = await get_player(user_id)

    # Проверяем баланс игрока
    if player["balance"] < amount:
        return f"❌ Недостаточно средств для перевода!\n💰 Нужно: {format_number(amount)} монет\n💳 У вас: {format_number(player['balance'])} монет"

    # Минимальная сумма перевода
    if amount < 10:
        return "❌ Минимальная сумма перевода - 10 монет!"

    target_player = await get_player(target_id)

    if not target_player:
        return '❌ Игрок с таким айди не найден!'

    target_username = target_player["username"]

    # Проверяем, не забанен ли получатель
    if target_player.get("is_banned", 0) == 1:
        return "❌ Нельзя переводить деньги забаненному игроку!"

    # Комиссия 5%
    commission = max(1, int(amount * 0.05))
    net_amount = amount - commission

    try:
        # Снимаем деньги у отправителя
        await update_player_balance(
            user_id,
            -amount,
            "money_transfer_sent",
            f"Перевод игроку {target_username}",
            None,
            target_id,
        )

        # Зачисляем деньги получателю (за вычетом комиссии)
        await update_player_balance(
            target_id,
            net_amount,
            "money_transfer_received",
            f"Перевод от игрока {player['username']}",
            None,
            user_id,
        )

        response_text = (
            f"💸 Перевод выполнен успешно!\n\n"
            f"👤 Отправитель: [id{player['user_id']}|{player['username']}]\n"
            f"👥 Получатель: [id{target_id}|{target_username}]\n"
            f"💰 Сумма: {format_number(amount)} монет\n"
            f"📊 Комиссия (5%): {format_number(commission)} монет\n"
            f"💳 Зачислено: {format_number(net_amount)} монет\n"
            f"🏦 Ваш баланс: {format_number(player['balance'] - amount)} монет\n\n"
            f"✅ Деньги успешно переведены!"
        )
        await message.answer(response_text, disable_mentions=True)
    except Exception as e:
        return f"❌ Ошибка при выполнении перевода: {str(e)}"


# ======================
# ОБЫЧНЫЕ КОМАНДЫ
# ======================


@user_labeler.message(text=["начать", "/начать"])
async def welcome_handler(message: Message):
    """Приветственное сообщение"""
    user_id = message.from_id

    player = await get_player(user_id)
    if not player:
        player = await create_player(user_id, str(user_id))

    welcome_text = (
        "🔥 Привет! Ты попал в Gym Legend 😩🤟"
        + "\n\n💪 Здесь ты можешь стать легендой фитнес-индустрии!"
        + f"\n👤 Твой ник: [id{user_id}|{player['username']}]"
        + f"\n💰 Стартовый баланс: {format_number(player['balance'])} монет"
        + f"\n🏋️‍♂️ Стартовая гантеля: {player['dumbbell_name']}"
        + "\n\n🏋️‍♂️ Как играть:"
        + "\n1. Качайся с гантелями (/поднять)"
        + "\n2. Прокачивай гантели (/прокачаться)"
        + "\n3. Открой бизнес (/б магазин)"
        + "\n4. Создай или вступи в клан (/к создать)"
        + "\n5. Соревнуйся с другими (/топ)"
        + "\n\n📝 Напиши команду /помощь, чтобы узнать все команды"
    )

    await message.answer(welcome_text, disable_mentions=True)


@user_labeler.message(text=["профиль", "/профиль"])
async def get_profile_handler(message: Message):
    """Профиль игрока"""
    user_id = message.from_id
    player = await get_player(user_id)

    if not player:
        return "❌ Игрок не найден"

    if player.get("custom_income") is not None:
        income_per_use = player["custom_income"]
        income_note = f"💰 Доход за подход: {income_per_use} монет ⚡\n"
    else:
        dumbbell_info = settings.DUMBBELL_LEVELS[player["dumbbell_level"]]
        income_per_use = dumbbell_info["income_per_use"]
        income_note = f"💰 Доход за подход: {income_per_use} монет\n"

    # Добавляем информацию о бонусах клана
    clan = await get_player_clan(user_id)
    clan_info = ""
    clan_bonus_text = ""
    if clan:
        clan_bonuses = get_clan_bonuses(clan["level"])
        clan_info = f"🏰 Клан: [{clan['tag']}] {clan['name']}\n"
        clan_bonus_text = (
            f"🏰 Бонус клана: +{clan_bonuses['lift_bonus_coins']} монет за поднятие\n"
        )

    created_date = datetime.fromisoformat(player["created_at"]).strftime("%d.%m.%Y")

    admin_level = player.get("admin_level", 0)
    if admin_level > 0:
        privileges = "💎 Админ"
    else:
        privileges = "💎 Игрок"

    profile_text = (
        f"👤 Профиль игрока #{player['user_id']}\n\n"
        f"💪 Ник: [id{player['user_id']}|{player['username']}]\n"
        f"💎 Привилегии: {privileges}\n"
        f"{clan_info}"
        f"💰 Баланс: {format_number(player['balance'])} монет\n"
        f"💪 Сила: {format_number(player['power'])}\n"
        f"🏋️‍♂️ Гантеля: {player['dumbbell_name']}\n"
        f"⭐ Уровень гантели: {player['dumbbell_level']}\n"
        f"{income_note}"
        f"{clan_bonus_text}"
        f"💪 Поднятий гантели: {format_number(player['total_lifts'])}\n"
        f"💎 Банки магнезии: {format_number(player['magnesia'])} банок\n"
        f"📅 Дата регистрации: {created_date}"
    )

    await message.answer(profile_text, disable_mentions=True)


@user_labeler.message(text=["баланс", "/баланс"])
async def get_balance_handler(message: Message):
    """Баланс игрока"""
    user_id = message.from_id
    player = await get_player(user_id)

    return f"💰 Ваш баланс: {format_number(player['balance'])} монет"


@user_labeler.message(text=["помощь", "/помощь"])
async def get_help_handler(message: Message):
    """Справка по командам"""
    commands = [
        "🏋️‍♂️ Gym Legend - Доступные команды:\n",
        "📊 Профиль и информация:",
        "├── /профиль - ваш профиль",
        "├── /баланс - текущий баланс\n",
        "💪 Гантели:",
        "├── /гантеля - информация о гантеле",
        "├── /поднять - поднять гантелю (обновленная система!)",
        "├── /прокачаться - улучшить гантелю",
        "└── /магазин - магазин гантелей\n",
        "🏢 Бизнес системы:",
        "├── /б - список ваших бизнесов",
        "├── /б [номер] - информация о бизнесе",
        "├── /б магазин - магазин бизнесов",
        "├── /б [номер] купить - купить бизнес",
        "└── /б [номер] [1-5] улучшить - улучшить бизнес\n",
        "🏰 Кланы (НОВАЯ СИСТЕМА):",
        "├── /к создать [ТЭГ] [название] - создать клан (1000 монет)",
        "├── /к улучшить - улучшить уровень клана",
        "├── /к казна - посмотреть казну клана",
        "├── /к профиль - информация о клане",
        "├── /к топ - топ кланов",
        "├── /к положить [сумма] - положить деньги в казну",
        "└── /к распределить всем [сумма] - распределить казну\n",
        "💸 Перевод денег:",
        "├── /перевод [айди] [сумма] - перевести деньги",
        "└── /перевести [айди] [сумма] - перевести деньги\n",
        "🎫 Промокоды:",
        "└── /промо [код] - активировать промокод\n",
        "🏆 Рейтинги:",
        "├── /топ - общий список рейтингов",
        "├── /топ монет - топ по балансу",
        "├── /топ поднятий - топ по поднятиям",
        "└── /топ заработка - топ по заработку\n",
        "💡 Особенности новой системы кланов:",
        "• Бонусы клана идут в казну",
        "• Игроки получают бонус за поднятия",
        "• Казна клана распределяется между участниками",
        "• Бизнесы приносят доход в казну клана",
    ]

    return "\n".join(commands)


@user_labeler.message(text=["магазин", "/магазин"])
async def get_dumbbell_shop_handler(message: Message):
    """Магазин гантелей"""
    user_id = message.from_id
    player = await get_player(user_id)

    if not player:
        player = await create_player(user_id, str(message.from_id))

    current_level = player["dumbbell_level"]

    shop_items = []
    for level in range(1, 21):
        dumbbell = settings.DUMBBELL_LEVELS[level]

        if level == current_level:
            prefix = "✅ "
        elif level < current_level:
            prefix = "✔️ "
        else:
            prefix = "🔘 "

        if level == current_level:
            suffix = " (Ваш текущий)"
        elif player["balance"] >= dumbbell["price"]:
            suffix = " 🔥"
        else:
            suffix = " ⏳"

        shop_items.append(
            f"{prefix}Уровень {level}: {dumbbell['name']}\n"
            f"   ⚖️ Вес: {dumbbell['weight']} | "
            f"💰 Доход: {dumbbell['income_per_use']} монет | "
            f"💪 Сила: {dumbbell['power_per_use']} | "
            f"💵 Цена: {format_number(dumbbell['price'])} монет{suffix}"
        )

    shop_text = (
        "🏪 Магазин гантелей\n\n"
        "💪 Как прокачаться:\n"
        "1. Накапливайте монеты (/поднять)\n"
        "2. Купите улучшение (/прокачаться)\n"
        "3. Получайте больше дохода!\n\n"
        "📊 Доступные гантели:\n"
        + "\n".join(shop_items)
        + f"\n\n💰 Ваш баланс: {format_number(player['balance'])} монет\n"
        f"🏋️‍♂️ Текущая гантеля: {player['dumbbell_name']}"
    )

    return shop_text


@user_labeler.message(text=["гник <cmd_args>", "/гник <cmd_args>"])
async def change_username_handler(message: Message, cmd_args: str):
    """Изменить ник"""
    user_id = message.from_id
    new_username = cmd_args.strip()

    if not new_username:
        return "❌ Укажите новый ник!\n📝 Использование: /гник [новый_ник]"

    if len(new_username) > 20:
        return "❌ Ник не может быть длиннее 20 символов!"

    if len(new_username) < 3:
        return "❌ Ник должен быть не короче 3 символов!"

    if re.search(r'[@#$%^&*()+=|\\<>{}[\]:;"\'?/~`]', new_username):
        return "❌ Ник не может содержать специальные символы!\n✅ Разрешены: буквы, цифры, пробелы, дефисы, подчеркивания"

    if new_username != new_username.strip():
        return "❌ Ник не может начинаться или заканчиваться пробелом!"

    if "  " in new_username:
        return "❌ Ник не может содержать несколько пробелов подряд!"

    if not re.match(r"^[a-zA-Zа-яА-ЯёЁ0-9 _-]+$", new_username):
        return "❌ Ник содержит недопустимые символы!\n✅ Разрешены: буквы, цифры, пробелы, дефисы, подчеркивания"

    await update_username(user_id, new_username)

    return f"✅ Ваш ник изменен на: {new_username}"
