from datetime import datetime

from bot.utils import format_number
from vkbottle.bot import BotLabeler, Message

from bot.db import count_promo_uses, get_player, get_promo_info, use_promo_code
from bot.services.users import is_admin

promocode_labeler = BotLabeler()
promocode_labeler.vbml_ignore_case = True


@promocode_labeler.message(text=["промоинфо", "/промоинфо"])
async def promo_info_empty_handler(message: Message, code: str):
    """Информация о промокоде"""
    return "❌ Укажите код промокода!\n📝 Использование: /промоинфо [код]"


@promocode_labeler.message(text=["промоинфо <code>", "/промоинфо <code>"])
async def promo_info_handler(message: Message, code: str):
    """Информация о промокоде"""
    code = code.upper()
    promo_info = await get_promo_info(code)

    if not promo_info:
        return f"❌ Промокод {code} не найден!"

    # Получаем информацию о создателе
    creator = await get_player(promo_info["created_by"])
    creator_name = creator["username"] if creator else f"ID: {promo_info['created_by']}"

    # Форматируем даты
    created_at = datetime.fromisoformat(promo_info["created_at"]).strftime(
        "%d.%m.%Y %H:%M"
    )

    expires_text = "⏳ Срок: Не ограничен"
    if promo_info["expires_at"]:
        expires_date = datetime.fromisoformat(promo_info["expires_at"])
        expires_text = f"⏳ Срок: до {expires_date.strftime('%d.%m.%Y')}"

        if datetime.now() > expires_date:
            expires_text += " ⚠️ Истек"

    status = "✅ Активен" if promo_info["is_active"] == 1 else "❌ Неактивен"

    info_text = (
        f"🎫 ИНФОРМАЦИЯ О ПРОМОКОДЕ\n\n"
        f"🔑 Код: {promo_info['code']}\n"
        f"📊 Статус: {status}\n\n"
        f"🎯 Использования:\n"
        f"├─ Всего: {promo_info['uses_total']}\n"
        f"├─ Осталось: {promo_info['uses_left']}\n"
        f"└─ Использовано: {promo_info['uses_total'] - promo_info['uses_left']}\n\n"
        f"💰 Награда: {format_number(promo_info['reward_amount'])} {promo_info['reward_type']}\n\n"
        f"👤 Создатель: {creator_name}\n"
        f"📅 Создан: {created_at}\n"
        f"{expires_text}\n\n"
        f"💡 Для активации: /промо {promo_info['code']}"
    )

    # Если администратор - показываем дополнительную информацию
    if await is_admin(message.from_id):
        total_uses = await count_promo_uses(code)

        recent_users = await count_promo_uses(code, 5)

        users_text = "Нет использований"
        if recent_users:
            user_names = []
            for user_id in recent_users:
                user = await get_player(user_id[0])
                if user:
                    user_names.append(user["username"])
            users_text = ", ".join(user_names[:5])
            if total_uses > 5:
                users_text += f" и еще {total_uses - 5}"

        info_text += (
            f"\n\n📊 Статистика (только для админов):\n"
            f"👥 Всего активаций: {total_uses}\n"
            f"👤 Последние активаторы: {users_text}"
        )

    return info_text


@promocode_labeler.message(text=["промо", "/промо"])
async def use_promo_empty_handler(message: Message, code: str):
    """Использование промокода"""
    return "❌ Укажите код промокода!\n📝 Использование: /промо [код]"


@promocode_labeler.message(text=["промо <code>", "/промо <code>"])
async def use_promo_handler(message: Message, code: str):
    """Использование промокода"""
    code = code.upper()
    result = await use_promo_code(message.from_id, code)

    if result["success"]:
        player = await get_player(message.from_id)

        if result["reward_type"] == "монеты":
            new_balance = player["balance"]
            reward_text = f"💰 {format_number(result['reward_amount'])} монет\n📈 Новый баланс: {format_number(new_balance)} монет"
        else:
            new_magnesia = player["magnesia"]
            reward_text = f"💎 {format_number(result['reward_amount'])} банок магнезии\n📈 Новый баланс: {format_number(new_magnesia)} банок"

        return (
            f"🎉 Промокод активирован!\n\n"
            f"🔑 Код: {code}\n"
            f"🎁 Получено: {reward_text}\n\n"
            f"✅ Награда успешно зачислена на ваш счет!"
        )
    else:
        return (
            f"❌ Не удалось активировать промокод\n\n"
            f"🔑 Код: {code}\n"
            f"📝 Причина: {result['error']}"
        )
