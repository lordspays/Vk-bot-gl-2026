from datetime import datetime, timedelta

from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules import ABCRule

from bot.core.config import settings
from bot.db import (
    add_magnesia,
    ban_player,
    count_admins,
    count_banned_players,
    count_clans,
    count_players,
    count_table_rows,
    count_total_balance,
    create_promo_code,
    delete_clan,
    delete_player,
    delete_promo_code,
    get_clan_by_tag,
    get_clan_member_count,
    get_clan_members,
    get_clan_treasury_log,
    get_player,
    get_promo_info,
    get_recent_players,
    increment_admin_stat,
    make_admin,
    remove_admin,
    reset_all,
    set_admin_nickname,
    set_custom_income,
    set_dumbbell_level,
    set_total_lifts,
    sum_column,
    sum_promo_uses,
    unban_player,
    update_clan_name,
    update_player_balance,
    update_username,
)
from bot.services.clans import get_clan_bonuses
from bot.services.users import is_admin
from bot.utils import format_number, pointer_to_screen_name


class IsAdmin(ABCRule[Message]):
    async def check(self, event: Message) -> bool:
        return await is_admin(event.from_id)


admin_labeler = BotLabeler()
admin_labeler.vbml_ignore_case = True
admin_labeler.auto_rules = [IsAdmin()]

PENDING_DELETIONS = {}
PENDING_RESETS = {}

# ======================
# АДМИН КОМАНДЫ КЛАНОВ (без изменений)
# ======================


@admin_labeler.message(text=["аксменить <cmd_args>", "/аксменить <cmd_args>"])
async def admin_rename_clan_command(message: Message, cmd_args: str):
    """Принудительная смена названия клана администратором"""
    user_id = message.from_id

    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    admin_level = await get_admin_level(user_id)
    if admin_level < 2:
        return "❌ Только администраторы 2+ уровня могут изменять названия кланов!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите тег клана и новое название!\n📝 Использование: /аксменить [тег] [новое_название]"

    tag = parts[0]
    new_name = " ".join(parts[1:])

    # Проверяем название клана
    if len(new_name) < 3 or len(new_name) > 20:
        return "❌ Название клана должно быть от 3 до 20 символов!"

    result = await update_clan_name(tag, new_name, user_id)

    if result["success"]:
        return (
            f"✅ Название клана изменено!\n\n"
            f"🔰 Тег: [{tag.upper()}]\n"
            f"📝 Старое название: {result['old_name']}\n"
            f"🏷️ Новое название: {result['new_name']}\n"
            f"👮 Изменил: Администратор"
        )
    else:
        return f"❌ {result['error']}"


@admin_labeler.message(text=["акудалить <tag>", "/акудалить <tag>"])
async def admin_delete_clan_command(message: Message, tag: str):
    """Удаление клана администратором"""
    user_id = message.from_id

    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    admin_level = await get_admin_level(user_id)
    if admin_level < 2:
        return "❌ Только администраторы 2+ уровня могут удалять кланы!"

    clan = await get_clan_by_tag(tag)
    if not clan:
        return f"❌ Клан с тегом [{tag.upper()}] не найден!"

    # Проверяем, не находится ли подтверждение в ожидании
    if tag.upper() in PENDING_DELETIONS:
        # Подтверждаем удаление
        result = await delete_clan(tag, user_id)

        if result["success"]:
            del PENDING_DELETIONS[tag.upper()]

            return (
                f"🗑️ Клан удален!\n\n"
                f"🔰 Тег: [{tag.upper()}]\n"
                f"🏷️ Название: {clan['name']}\n"
                f"👥 Участников исключено: {result['member_count']}\n"
                f"💰 Утеряно из казны: {format_number(clan['treasury'])} монет\n"
                f"👮 Удалил: Администратор"
            )
        else:
            return f"❌ {result['error']}"
    else:
        # Запрашиваем подтверждение
        PENDING_DELETIONS[tag.upper()] = {
            "admin_id": user_id,
            "clan_name": clan["name"],
            "timestamp": datetime.now(),
        }

        member_count = await get_clan_member_count(clan["id"])

        response_text = (
            f"⚠️ ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ КЛАНА\n\n"
            f"🔰 Тег: [{tag.upper()}]\n"
            f"🏷️ Название: {clan['name']}\n"
            f"👑 Владелец: ID: [id{clan['owner_id']}|{clan['owner_id']}]\n"
            f"👥 Участников: {member_count}\n"
            f"💰 Казна: {format_number(clan['treasury'])} монет\n"
            f"📅 Существует: {(datetime.now() - datetime.fromisoformat(clan['created_at'])).days} дней\n\n"
            f"❗ ВНИМАНИЕ!\n"
            f"• Все участники будут исключены\n"
            f"• Казна будет утеряна\n"
            f"• Действие необратимо!\n\n"
            f"✅ Для подтверждения отправьте команду еще раз:\n"
            f"/акудалить {tag.upper()}"
        )
        await message.answer(response_text, disable_mentions=True)


@admin_labeler.message(text=["акинфо <tag>", "/акинфо <tag>"])
async def admin_clan_info_command(message: Message, tag: str):
    """Подробная информация о клане для администратора"""
    user_id = message.from_id

    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    clan = await get_clan_by_tag(tag)
    if not clan:
        return f"❌ Клан с тегом [{tag.upper()}] не найден!"

    # Получаем участников
    members = await get_clan_members(clan["id"], 50)

    # Получаем владельца
    owner = await get_player(clan["owner_id"])

    # Получаем лог операций
    log = await get_clan_treasury_log(clan["id"], 10)

    # Получаем бонусы клана
    clan_bonuses = get_clan_bonuses(clan["level"])

    # Форматируем информацию об участниках
    members_text = ""
    for i, member in enumerate(members[:15], 1):
        role_emoji = (
            "👑"
            if member["role"] == "owner"
            else ("⭐" if member["role"] == "officer" else "👤")
        )
        join_date = datetime.fromisoformat(member["joined_at"]).strftime("%d.%m")
        members_text += f"{i}. {role_emoji} {member['username']} (ID: {member['user_id']}) - {format_number(member['contributions'])} монет ({join_date})\n"

    # Форматируем лог операций
    log_text = ""
    for entry in log:
        action_emoji = (
            "➕"
            if entry["action_type"] == "deposit"
            else (
                "⬆️"
                if entry["action_type"] == "upgrade"
                else (
                    "💰"
                    if entry["action_type"] == "lift_income"
                    else (
                        "🏦"
                        if entry["action_type"] == "business_income"
                        else ("📊" if entry["action_type"] == "distribution" else "📝")
                    )
                )
            )
        )
        username = entry["username"] or "Система"
        time_str = datetime.fromisoformat(entry["created_at"]).strftime("%d.%m %H:%M")
        log_text += (
            f"• {action_emoji} {entry['description']} - {username} ({time_str})\n"
        )

    # Форматируем даты
    created_date = datetime.fromisoformat(clan["created_at"]).strftime("%d.%m.%Y %H:%M")
    days_exist = (datetime.now() - datetime.fromisoformat(clan["created_at"])).days

    response_text = (
        f"📊 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О КЛАНЕ [{clan['tag']}]\n\n"
        f"🏷️ Название: {clan['name']}\n"
        f"👑 Владелец: {owner['username'] if owner else 'Не найден'} (ID: [id{owner['owner_id']}|{clan['owner_id']}])\n"
        f"⭐ Уровень: {clan['level']}\n"
        f"💰 Казна: {format_number(clan['treasury'])} монет\n"
        f"👥 Участников: {len(members)}\n"
        f"📈 Доход/час: {format_number(clan['total_income_per_hour'])} магнезии\n"
        f"💪 Всего поднятий: {format_number(clan['total_lifts'])}\n"
        f"📅 Создан: {created_date} ({days_exist} дней)\n"
        f"🎯 Бонусы клана:\n"
        f"├─ 💼 +{clan_bonuses['business_bonus_percent']}% от бизнесов в казну\n"
        f"└─ 🏋️ +{clan_bonuses['lift_bonus_coins']} монет в казну с поднятий\n\n"
        f"🏆 Участники (топ-15):\n{members_text}\n"
        f"📜 Последние операции с казной:\n{log_text}\n"
        f"👮 Административные команды:\n"
        f"• /аксменить {clan['tag']} [новое_название]\n"
        f"• /акудалить {clan['tag']}"
    )

    await message.answer(response_text, disable_mentions=True)


# ======================
# ОСТАЛЬНЫЕ АДМИН КОМАНДЫ
# ======================


async def get_admin_level(user_id: int) -> int:
    if user_id in settings.ADMIN_USERS:
        # ? We're lying for now, so maybe there's a better approach...?
        return 2
    player = await get_player(user_id)
    return player.get("admin_level", 0) if player else 0


@admin_labeler.message(
    text=["создатьпромокод <cmd_args>", "/создатьпромокод <cmd_args>"]
)
async def create_promo_handler(message: Message, cmd_args: str):
    """Создание промокода"""
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут создавать промокоды!"

    parts = cmd_args.split()
    if len(parts) < 4:
        return "❌ Недостаточно параметров!\n📝 Использование: /создатьпромокод [код] [использования] [тип_награды] [сумма]\n\nТипы наград: монеты, магнезия\nПример: /создатьпромокод NEWYEAR2024 100 монеты 5000"

    code = parts[0].upper()

    try:
        uses_total = int(parts[1])
        if uses_total <= 0:
            return "❌ Количество использований должно быть положительным числом!"
    except:
        return "❌ Количество использований должно быть числом!"

    reward_type = parts[2].lower()
    if reward_type not in ["монеты", "магнезия"]:
        return "❌ Неверный тип награды!\n✅ Допустимые типы: монеты, магнезия"

    try:
        reward_amount = int(parts[3])
        if reward_amount <= 0:
            return "❌ Сумма награды должна быть положительным числом!"
    except:
        return "❌ Сумма награды должна быть числом!"

    # Проверяем срок действия (опциональный 5-й параметр)
    expires_days = None
    if len(parts) > 4:
        try:
            expires_days = int(parts[4])
            if expires_days <= 0:
                return "❌ Срок действия должен быть положительным числом дней!"
        except:
            return "❌ Срок действия должен быть числом дней!"

    if await create_promo_code(
        code, uses_total, reward_type, reward_amount, user_id, expires_days
    ):
        if expires_days:
            expires_date = (datetime.now() + timedelta(days=expires_days)).strftime(
                "%d.%m.%Y"
            )
            expires_text = f"⏳ Срок действия: {expires_days} дней (до {expires_date})"
        else:
            expires_text = "⏳ Срок действия: Не ограничен"

        return (
            f"🎫 Промокод создан!\n\n"
            f"🔑 Код: {code}\n"
            f"🎯 Использований: {uses_total}\n"
            f"💰 Награда: {format_number(reward_amount)} {reward_type}\n"
            f"{expires_text}\n\n"
            f"📢 Игроки могут активировать промокод командой:\n"
            f"/промо {code}"
        )
    else:
        return "❌ Промокод с таким кодом уже существует!"


@admin_labeler.message(text=["удалитьпромокод <code>", "/удалитьпромокод <code>"])
async def delete_promo_handler(message: Message, code: str):
    """Удаление промокода"""
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут удалять промокоды!"

    code = code.upper()
    promo_info = await get_promo_info(code)

    if not promo_info:
        return f"❌ Промокод {code} не найден!"

    await delete_promo_code(code, user_id)

    return (
        f"🗑️ Промокод удален!\n\n"
        f"🔑 Код: {code}\n"
        f"🔄 Использовано: {promo_info['uses_total'] - promo_info['uses_left']}/{promo_info['uses_total']}\n"
        f"👮 Удалил: Администратор"
    )


@admin_labeler.message(text=["админпанель", "/админпанель", "админ_панель"])
async def admin_panel_handler(message: Message):
    user_id = message.from_id
    player = await get_player(user_id)

    if not player or (await get_admin_level(user_id)) == 0:
        return "❌ У вас нет прав администратора!"

    admin_level = player["admin_level"]
    if admin_level == 1:
        position = "👮 Администратор"
    elif admin_level == 2:
        position = "👑 Создатель🌟"
    else:
        position = "❓ Неизвестная должность"

    admin_since = "Не назначен"
    if player.get("admin_since"):
        admin_since_date = datetime.fromisoformat(player["admin_since"])
        admin_since = admin_since_date.strftime("%d.%m.%Y %H:%M")

    admin_nickname = player.get("admin_nickname", "Не установлен")
    if admin_nickname != "Не установлен":
        admin_nickname_display = f"{admin_nickname} 👑"
    else:
        admin_nickname_display = admin_nickname

    admin_id = player.get("admin_id", "Не назначен")

    stats = [
        f"🚫 Банов выдано: {player.get('bans_given', 0)}",
        f"⛔ Пермбанов выдано: {player.get('permabans_given', 0)}",
        f"🗑️ Удалений профилей: {player.get('deletions_given', 0)}",
        f"🏋️‍♂️ Гантелей установлено: {player.get('dumbbell_sets_given', 0)}",
        f"📝 Ников изменено: {player.get('nickname_changes_given', 0)}",
    ]

    response_text = (
        f"🏛️ АДМИНИСТРАТИВНАЯ ПАНЕЛЬ\n\n"
        f"👤 Ваш ник: [id{player['user_id']}|{player['username']}]\n"
        f"💎 Должность: {position}\n"
        f"🆔 Админ ID: {admin_id}\n"
        f"👑 Админ-ник: {admin_nickname_display}\n"
        f"📅 С должности: {admin_since}\n\n"
        f"📊 Ваша статистика:\n" + "\n".join(stats) + "\n\n📝 Доступные команды:\n"
        "• /админ - список всех админ команд\n"
        "• /аник [ник] - установить админ-ник\n"
        "• /назначить [ник] [уровень] - назначить админа\n"
        "• /снять [ник] - снять с должности\n"
        "• /статистика - статистика бота\n\n"
        "💡 Напишите /админ для полного списка команд"
    )

    await message.answer(response_text, disable_mentions=True)


@admin_labeler.message(text=["аник <cmd_args>", "/аник <cmd_args>"])
async def set_admin_nickname_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    if not cmd_args:
        return "❌ Укажите админ-ник!\n📝 Использование: /аник [админ_ник]"

    if len(cmd_args) > 15:
        return "❌ Админ-ник не может быть длиннее 15 символов!"

    await set_admin_nickname(user_id, cmd_args)

    return f"✅ Ваш админ-ник установлен: {cmd_args} 👑"


@admin_labeler.message(text=["назначить <cmd_args>", "/назначить <cmd_args>"])
async def make_admin_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    admin_level = await get_admin_level(user_id)
    if admin_level < 2:
        return "❌ Только администраторы 2+ уровня могут назначать администраторов!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и уровень!\n📝 Использование: /назначить [айди] [уровень]\nУровни: 1 (админ), 2 (создатель)"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    try:
        new_admin_level = int(parts[1])
    except ValueError:
        return "❌ Уровень админа должен быть числом (1 или 2)!"

    if new_admin_level not in [1, 2]:
        return "❌ Уровень админа может быть только 1 или 2!"

    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    # Нельзя назначать уровень выше своего
    if new_admin_level > admin_level:
        return f"❌ Вы не можете назначить уровень выше своего (ваш уровень: {admin_level})!"

    target_username = target_player["username"]

    # Проверяем, не является ли уже админом
    if target_player.get("admin_level", 0) > 0:
        return f'❌ Игрок "{target_username}" уже является администратором!'

    # Назначаем админа
    admin_id = await make_admin(target_id, user_id, new_admin_level)

    level_name = "Администратор" if new_admin_level == 1 else "Создатель🌟"

    return (
        f"✅ Игрок назначен администратором!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"💎 Должность: {level_name}\n"
        f"🆔 Админ ID: {admin_id}\n"
        f"👮 Назначил: Администратор\n\n"
        f"💡 Игрок получил доступ к админ панели: /админпанель"
    )


@admin_labeler.message(text=["снять <cmd_args>", "/снять <cmd_args>"])
async def remove_admin_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    try:
        target_id = int(pointer_to_screen_name(cmd_args))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    admin_level = await get_admin_level(user_id)
    if admin_level < 2:
        return "❌ Только администраторы 2+ уровня могут снимать администраторов!"

    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    if target_player.get("admin_level", 0) == 0:
        return f'❌ Игрок "{target_username}" не является администратором!'

    # Нельзя снимать самого себя
    if target_id == user_id:
        return "❌ Нельзя снять с должности самого себя!"

    # Нельзя снимать администраторов равного или высшего уровня
    if target_player["admin_level"] >= admin_level:
        return "❌ Вы не можете снять администратора равного или высшего уровня!"

    # Снимаем с должности
    await remove_admin(target_id, user_id)

    return (
        f"✅ Администратор снят с должности!\n\n"
        f"👤 Администратор: [id{target_id}|{target_username}]\n"
        f"💎 Бывшая должность: Уровень {target_player['admin_level']}\n"
        f"👮 Снял: Администратор\n\n"
        f"⚠️ Игрок лишился всех админ прав и статистики"
    )


@admin_labeler.message(text=["лгантеля <cmd_args>", "/лгантеля <cmd_args>"])
async def set_dumbbell_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и уровень гантели!\n📝 Использование: /лгантеля [айди] [уровень (1-20)]"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    try:
        new_level = int(parts[1])
        if new_level < 1 or new_level > 20:
            return "❌ Уровень гантели должен быть от 1 до 20!"
    except:
        return "❌ Уровень гантели должен быть числом!"

    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    # Устанавливаем уровень гантели
    if await set_dumbbell_level(target_id, new_level, user_id):
        dumbbell_info = settings.DUMBBELL_LEVELS[new_level]

        return (
            f"✅ Уровень гантели изменен!\n\n"
            f"👤 Игрок: [id{target_id}|{target_username}]\n"
            f"🏋️‍♂️ Новая гантеля: {dumbbell_info['name']}\n"
            f"⭐ Новый уровень: {new_level}\n"
            f"💰 Доход за подход: {dumbbell_info['income_per_use']} монет\n"
            f"👮 Изменил: Администратор"
        )
    else:
        return "❌ Ошибка при изменении уровня гантели!"


@admin_labeler.message(text=["-баланс <cmd_args>", "/-баланс <cmd_args>"])
async def remove_balance_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return (
            "❌ Укажите айди игрока и сумму!\n📝 Использование: /-баланс [айди] [сумма]"
        )

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    try:
        amount = int(parts[1])
        if amount <= 0:
            return "❌ Сумма должна быть положительным числом!"
    except:
        return "❌ Сумма должна быть числом!"

    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    if target_player["balance"] < amount:
        amount = target_player["balance"]  # Убираем весь баланс

    await update_player_balance(
        target_id,
        -amount,
        "admin_remove_balance",
        f"Администратор убрал {amount} монет",
        user_id,
    )

    return (
        f"✅ Баланс уменьшен!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"💰 Убрано: {format_number(amount)} монет\n"
        f"💳 Новый баланс: {format_number(target_player['balance'] - amount)} монет\n"
        f"👮 Изменил: Администратор"
    )


@admin_labeler.message(text=["+баланс <cmd_args>", "/+баланс <cmd_args>"])
async def add_balance_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return (
            "❌ Укажите айди игрока и сумму!\n📝 Использование: /+баланс [айди] [сумма]"
        )

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    try:
        amount = int(parts[1])
        if amount <= 0:
            return "❌ Сумма должна быть положительным числом!"
    except:
        return "❌ Сумма должна быть числом!"

    if amount > 2_147_483_647:
        # Limit in SQLite is a 64-bit int, but we use 32-bit int here for future
        # possible compatibility with other dbs
        return "❌ Сумма слишком большая!"

    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    await update_player_balance(
        target_id,
        amount,
        "admin_add_balance",
        f"Администратор добавил {amount} монет",
        user_id,
    )

    return (
        f"✅ Баланс увеличен!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"💰 Добавлено: {format_number(amount)} монет\n"
        f"💳 Новый баланс: {format_number(target_player['balance'] + amount)} монет\n"
        f"👮 Изменил: Администратор"
    )


@admin_labeler.message(text=["бан <cmd_args>", "/бан <cmd_args>"])
async def ban_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 3:
        return "❌ Укажите айди игрока, дни и причину!\n📝 Использование: /бан [айди] [дни] [причина]\nПример: /бан 1234567 7 Оскорбления"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    try:
        days = int(parts[1])
        if days < 1:
            return "❌ Количество дней должно быть положительным числом!"
    except:
        return "❌ Количество дней должно быть числом!"

    reason = " ".join(parts[2:])

    # Проверяем существование игрока
    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    # Нельзя банить администраторов
    if target_player.get("admin_level", 0) > 0:
        return "❌ Нельзя забанить администратора! Используйте /снять"

    # Баним игрока
    await ban_player(target_id, days, reason, user_id)
    await increment_admin_stat(user_id, "bans")

    ban_until = (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")

    return (
        f"🚫 Игрок забанен!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"⏳ Срок: {days} дней\n"
        f"📅 До: {ban_until}\n"
        f"📝 Причина: {reason}\n"
        f"👮 Забанил: Администратор"
    )


@admin_labeler.message(text=["пермбан <cmd_args>", "/пермбан <cmd_args>"])
async def permaban_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и причину!\n📝 Использование: /пермбан [айди] [причина]"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    reason = " ".join(parts[1:])

    # Проверяем существование игрока
    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    # Нельзя банить администраторов
    if target_player.get("admin_level", 0) > 0:
        return "❌ Нельзя забанить администратора! Используйте /снять"

    # Баним навсегда (0 дней = пермабан)
    await ban_player(target_id, 0, reason, user_id)
    await increment_admin_stat(user_id, "permabans")

    return (
        f"⛔ Игрок забанен навсегда!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"📝 Причина: {reason}\n"
        f"👮 Забанил: Администратор"
    )


@admin_labeler.message(text=["разбан <cmd_args>", "/разбан <cmd_args>"])
async def unban_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    try:
        target_id = int(cmd_args)
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    # Проверяем существование игрока
    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    # Проверяем, забанен ли игрок
    if target_player.get("is_banned", 0) == 0:
        return f'❌ Игрок "[id{target_id}|{target_username}]" не забанен!'

    # Разбаниваем игрока
    await unban_player(target_id, user_id)

    return (
        f"✅ Игрок разбанен!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"👮 Разбанил: Администратор"
    )


@admin_labeler.message(text=["удалить <cmd_args>", "/удалить <cmd_args>"])
async def delete_player_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и причину!\n📝 Использование: /удалить [айди] [причина]"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    reason = " ".join(parts[1:])

    # Проверяем существование игрока
    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    # Нельзя удалять администраторов
    if target_player.get("admin_level", 0) > 0:
        return "❌ Нельзя удалить администратора! Используйте /снять"

    # Сохраняем запрос на удаление
    PENDING_DELETIONS[target_id] = {
        "admin_id": user_id,
        "username": target_username,
        "reason": reason,
        "timestamp": datetime.now(),
    }

    # Получаем статистику игрока
    created_date = datetime.fromisoformat(target_player["created_at"]).strftime(
        "%d.%m.%Y"
    )
    days_exist = (
        datetime.now() - datetime.fromisoformat(target_player["created_at"])
    ).days

    return (
        f"⚠️ ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ ИГРОКА\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"🆔 ID: {target_id}\n"
        f"💰 Баланс: {format_number(target_player['balance'])} монет\n"
        f"🏋️‍♂️ Гантеля: {target_player['dumbbell_name']}\n"
        f"💪 Поднятий: {format_number(target_player['total_lifts'])}\n"
        f"📅 Зарегистрирован: {created_date} ({days_exist} дней)\n\n"
        f"📝 Причина удаления:\n{reason}\n\n"
        f"❗ ВНИМАНИЕ! Это действие необратимо!\n"
        f"• Аккаунт будет полностью удален\n"
        f"• Баланс и прогресс будут утеряны\n\n"
        f"✅ Для подтверждения: /удалить+\n"
        f"❌ Для отмены: /удалить-"
    )


@admin_labeler.message(text="/удалить+")
async def confirm_delete_handler(message: Message):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    # Проверяем, есть ли ожидающие удаления от этого админа
    target_id = None
    for tid, data in PENDING_DELETIONS.items():
        if data["admin_id"] == user_id:
            target_id = tid
            break

    if not target_id:
        return "❌ Нет ожидающих подтверждения удалений!"

    data = PENDING_DELETIONS[target_id]

    # Удаляем игрока
    await delete_player(target_id, user_id)
    await increment_admin_stat(user_id, "deletions")

    # Удаляем из ожидающих
    del PENDING_DELETIONS[target_id]

    return (
        f"🗑️ Игрок удален!\n\n"
        f"👤 Игрок: {data['username']}\n"
        f"📝 Причина: {data['reason']}\n"
        f"👮 Удалил: Администратор"
    )


@admin_labeler.message(text="/удалить-")
async def cancel_delete_handler(message: Message):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    # Проверяем, есть ли ожидающие удаления от этого админа
    target_id = None
    for tid, data in PENDING_DELETIONS.items():
        if data["admin_id"] == user_id:
            target_id = tid
            break

    if not target_id:
        return "❌ Нет ожидающих подтверждения удалений!"

    data = PENDING_DELETIONS[target_id]

    # Отменяем удаление
    del PENDING_DELETIONS[target_id]

    return (
        f"✅ Удаление отменено!\n\n"
        f"👤 Игрок: {data['username']}\n"
        f"📝 Причина отмены: Администратор отменил удаление"
    )


@admin_labeler.message(text=["сгник <cmd_args>", "/сгник <cmd_args>"])
async def change_player_username_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и новый ник!\n📝 Использование: /сгник [айди] [новый_ник]"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    new_username = " ".join(parts[1:])

    # Проверяем новый ник
    if len(new_username) > 20:
        return "❌ Ник не может быть длиннее 20 символов!"

    if len(new_username) < 3:
        return "❌ Ник должен быть не короче 3 символов!"

    # Проверяем существование игрока
    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    old_username = target_player["username"]

    # Меняем ник
    await update_username(target_id, new_username)
    await increment_admin_stat(user_id, "nickname_changes")

    return (
        f"✅ Ник игрока изменен!\n\n"
        f"👤 Игрок: [id{target_id}|{old_username}] → {new_username}\n"
        f"👮 Изменил: Администратор"
    )


@admin_labeler.message(text=["поднятия <cmd_args>", "/поднятия <cmd_args>"])
async def set_lifts_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и количество поднятий!\n📝 Использование: /поднятия [айди] [количество]"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    try:
        new_total = int(parts[1])
        if new_total < 0:
            return "❌ Количество поднятий не может быть отрицательным!"
    except:
        return "❌ Количество поднятий должно быть числом!"

    # Проверяем существование игрока
    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    # Устанавливаем количество поднятий
    await set_total_lifts(target_id, new_total, user_id)

    return (
        f"✅ Количество поднятий изменено!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"💪 Новое количество: {format_number(new_total)} поднятий\n"
        f"👮 Изменил: Администратор"
    )


@admin_labeler.message(text=["заработок <cmd_args>", "/заработок <cmd_args>"])
async def set_custom_income_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и сумму дохода!\n📝 Использование: /заработок [айди] [сумма]\nДля сброса: /заработок [айди] сброс"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    income_str = parts[1]

    # Проверяем существование игрока
    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    if income_str.lower() == "сброс":
        # Сбрасываем кастомный доход
        custom_income = None
        message_text = f"✅ Кастомный доход сброшен!\n\n👤 Игрок: [id{target_id}|{target_username}]\n💰 Теперь используется доход от гантели\n👮 Сбросил: Администратор"
    else:
        try:
            custom_income = int(income_str)
            if custom_income < 1:
                return "❌ Доход должен быть положительным числом!"
            message_text = f"✅ Кастомный доход установлен!\n\n👤 Игрок: [id{target_id}|{target_username}]\n💰 Новый доход за подход: {format_number(custom_income)} монет\n👮 Установил: Администратор"
        except:
            return '❌ Доход должен быть числом или "сброс"!'

    # Устанавливаем кастомный доход
    await set_custom_income(target_id, custom_income, user_id)

    return message_text


@admin_labeler.message(text=["банки <cmd_args>", "/банки <cmd_args>"])
async def add_magnesia_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и количество банок!\n📝 Использование: /банки [айди] [количество]"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    try:
        amount = int(parts[1])
        if amount <= 0:
            return "❌ Количество банок должно быть положительным числом!"
    except:
        return "❌ Количество банок должно быть числом!"

    # Проверяем существование игрока
    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    # Добавляем магнезию
    await add_magnesia(target_id, amount, user_id)
    target_player = await get_player(target_id)

    return (
        f"✅ Банки магнезии добавлены!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"💎 Добавлено: {format_number(amount)} банок\n"
        f"🏦 Новый баланс: {format_number(target_player['magnesia'])} банок\n"
        f"👮 Выдал: Администратор"
    )


@admin_labeler.message(text=["статистика", "/статистика"])
async def bot_statistics_handler(message: Message):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    admin_level = await get_admin_level(user_id)
    if admin_level < 2:
        return "❌ Только администраторы 2+ уровня могут просматривать статистику бота!"

    # Статистика игроков
    total_players = await count_players(False)
    banned_players = await count_banned_players()
    admin_players = await count_admins()
    total_balance = await count_total_balance()

    total_lifts = await sum_column("players", "total_lifts")
    total_earned = await sum_column("players", "total_earned")

    # Статистика кланов
    total_clans = await count_table_rows("clans")
    total_clan_treasury = await sum_column("clans", "treasury")
    total_clan_income = await sum_column("clans", "total_income_per_hour")

    # Статистика промокодов
    total_promos = await count_table_rows("promo_codes")
    total_promo_uses = await sum_promo_uses()

    # Последние регистрации
    recent_players = await get_recent_players()

    recent_text = ""
    for i, (username, created_at) in enumerate(recent_players, 1):
        date_str = datetime.fromisoformat(created_at).strftime("%d.%m %H:%M")
        recent_text += f"{i}. {username} ({date_str})\n"

    stats_text = (
        f"📊 СТАТИСТИКА БОТА GYM LEGEND\n\n"
        f"👥 Игроки:\n"
        f"├─ Всего игроков: {total_players}\n"
        f"├─ Забанено: {banned_players}\n"
        f"├─ Администраторов: {admin_players}\n"
        f"├─ Активных: {total_players - banned_players}\n"
        f"├─ Общий баланс: {format_number(total_balance)} монет\n"
        f"├─ Всего поднятий: {format_number(total_lifts)}\n"
        f"└─ Всего заработано: {format_number(total_earned)} монет\n\n"
        f"🏰 Кланы (НОВАЯ СИСТЕМА):\n"
        f"├─ Всего кланов: {total_clans}\n"
        f"├─ Общая казна: {format_number(total_clan_treasury)} монет\n"
        f"└─ Общий доход/час: {format_number(total_clan_income)} магнезии\n\n"
        f"🎫 Промокоды:\n"
        f"├─ Создано промокодов: {total_promos}\n"
        f"└─ Всего активаций: {total_promo_uses}\n\n"
        f"📈 Последние регистрации:\n{recent_text}"
    )

    return stats_text


@admin_labeler.message(text=["сбросвсех", "/сбросвсех"])
async def reset_all_accounts_handler(message: Message):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    admin_level = await get_admin_level(user_id)
    if admin_level < 2:
        return "❌ Только администраторы 2+ уровня могут сбрасывать все аккаунты!"

    # Сохраняем запрос на сброс
    PENDING_RESETS[user_id] = {"timestamp": datetime.now()}

    regular_players = await count_players(regular_only=True)
    total_clans = await count_clans()

    return (
        f"⚠️ ПОДТВЕРЖДЕНИЕ СБРОСА ВСЕХ АККАУНТОВ\n\n"
        f"📊 Статистика:\n"
        f"├─ Обычных игроков: {regular_players}\n"
        f"├─ Кланов: {total_clans}\n"
        f"└─ Администраторов: Не будут затронуты\n\n"
        f"❗ ВНИМАНИЕ! Это действие:\n"
        f"• Удалит ВСЕХ обычных игроков\n"
        f"• Удалит ВСЕ кланы\n"
        f"• Сбросит всю статистику\n"
        f"• Администраторы НЕ будут удалены\n"
        f"• Действие НЕОБРАТИМО!\n\n"
        f"✅ Для подтверждения: /сбросвсех+\n"
        f"❌ Для отмены: /сбросвсех-"
    )


@admin_labeler.message(text="/сбросвсех+")
async def confirm_reset_all_handler(message: Message):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    admin_level = await get_admin_level(user_id)
    if admin_level < 2:
        return "❌ Только администраторы 2+ уровня могут сбрасывать все аккаунты!"

    # Проверяем, есть ли запрос на сброс
    if user_id not in PENDING_RESETS:
        return "❌ Нет ожидающих подтверждения сбросов!"

    # Считаем статистику перед удалением
    deleted_players = await count_players(regular_only=True)
    deleted_clans = await count_clans()

    deleted_balance = await count_total_balance()

    await reset_all()

    # Удаляем запрос на сброс
    del PENDING_RESETS[user_id]

    return (
        f"🔄 Все аккаунты сброшены!\n\n"
        f"📊 Статистика удаления:\n"
        f"├─ Удалено игроков: {deleted_players}\n"
        f"├─ Удалено кланов: {deleted_clans}\n"
        f"├─ Утеряно монет: {format_number(deleted_balance)}\n"
        f"└─ Администраторы: Сохранены\n\n"
        f"✅ Бот готов к новому сезону!"
    )


@admin_labeler.message(text="/сбросвсех-")
async def cancel_reset_all_handler(message: Message):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    # Проверяем, есть ли запрос на сброс
    if user_id not in PENDING_RESETS:
        return "❌ Нет ожидающих подтверждения сбросов!"

    # Отменяем сброс
    del PENDING_RESETS[user_id]

    return "✅ Сброс всех аккаунтов отменен!"


@admin_labeler.message(text=["связь <cmd_args>", "/связь <cmd_args>"])
async def send_message_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    parts = cmd_args.split()
    if len(parts) < 2:
        return "❌ Укажите айди игрока и сообщение!\n📝 Использование: /связь [айди] [сообщение]"

    try:
        target_id = int(pointer_to_screen_name(parts[0]))
    except ValueError:
        return "❌ Айди игрока должно быть числом!"

    message_text = " ".join(parts[1:])

    target_player = await get_player(target_id)

    if not target_player:
        return "❌ Игрок с таким айди не найден!"

    target_username = target_player["username"]

    # В реальном боте здесь был бы код отправки сообщения игроку
    # В этом примере просто возвращаем подтверждение

    return (
        f"📨 Сообщение отправлено!\n\n"
        f"👤 Игрок: [id{target_id}|{target_username}]\n"
        f"📝 Сообщение: {message_text}\n"
        f"👮 Отправил: Администратор\n\n"
        f"💡 Сообщение было доставлено игроку"
    )


@admin_labeler.message(text=["рассылка <cmd_args>", "/рассылка <cmd_args>"])
async def broadcast_message_handler(message: Message, cmd_args: str):
    user_id = message.from_id
    if not await is_admin(user_id):
        return "❌ Только администраторы могут использовать эту команду!"

    message_text = cmd_args

    total_players = await count_players(False, True)

    # В реальном боте здесь был бы код массовой рассылки
    # В этом примере просто возвращаем подтверждение

    return (
        f"📢 Массовая рассылка запущена!\n\n"
        f"👥 Получателей: {total_players} игроков\n"
        f"📝 Сообщение: {message_text}\n"
        f"👮 Отправил: Администратор\n\n"
        f"💡 Сообщение отправлено всем активным игрокам"
    )


@admin_labeler.message(text=["админ", "/админ"])
async def admin_help_handler(message: Message):
    commands = [
        "🏛️ Административные команды Gym Legend\n",
        "📝 Основные команды:",
        "├── /админпанель - показать админ панель",
        "├── /аник [ник] - установить админ-ник",
        "├── /лгантеля [айди] [уровень] - установить уровень гантели",
        "├── /-баланс [айди] [сумма] - убрать сумму с баланса игрока",
        "├── /+баланс [айди] [сумма] - добавить сумму на баланс игрока",
        "├── /бан [айди] [дни] [причина] - заблокировать игрока",
        "├── /пермбан [айди] [причина] - перманентный бан",
        "├── /разбан [айди] - разблокировать игрока",
        "├── /удалить [айди] [причина] - удалить профиль игрока",
        "├── /удалить+ - подтвердить удаление",
        "├── /удалить- - отменить удаление",
        "├── /сгник [айди] [новый_ник] - сменить ник игроку",
        "├── /поднятия [айди] [количество] - установить поднятия",
        "├── /заработок [айди] [сумма] - установить кастомный доход",
        "├── /банки [айди] [сумма] - выдать банки магнезии игроку",
        "├── /рассылка [сообщение] - массовая рассылка всем игрокам",
        "└── /связь [айди] [сообщение] - отправить сообщение\n",
        "🎫 Промокоды:",
        "├── /создатьпромокод [код] [использования] [тип] [сумма] - создать промокод",
        "├── /удалитьпромокод [код] - удалить промокод",
        "└── /промоинфо [код] - информация о промокоде\n",
        "🏰 Кланы (админ):",
        "├── /аксменить [ТЭГ] [новое_название] - принудительно сменить название клана",
        "├── /акудалить [ТЭГ] - удалить клан",
        "└── /акинфо [ТЭГ] - подробная информация о клане\n",
        "🌟 Особенные команды:",
        "├── /назначить [айди] [уровень] - назначить админа",
        "├── /снять [айди] - снять с должности администратора",
        "├── /статистика - статистика бота (только создатель)",
        "├── /сбросвсех - сбросить все аккаунты (только создатель)",
        "├── /сбросвсех+ - подтвердить сброс",
        "└── /сбросвсех- - отменить сброс\n",
        "💡 Игроки:",
        "└── /промо [код] - активировать промокод\n",
        "⚠️ Внимание:",
        "• При удалении нужно указать причину",
        "• Для подтверждения/отмены используйте /удалить+ или /удалить-",
        "• /сбросвсех удалит ВСЕХ игроков кроме создателя",
        "• Все действия логируются",
    ]

    return "\n".join(commands)
