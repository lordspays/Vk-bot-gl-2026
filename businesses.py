from bot.utils import format_number
from vkbottle.bot import BotLabeler, Message

from bot.core.config import settings
from bot.db import (
    buy_business,
    create_player,
    get_player,
    get_player_clan,
    upgrade_business,
)
from bot.services.clans import (
    calculate_business_income_with_clan,
    get_clan_bonuses,
)


business_labeler = BotLabeler()
business_labeler.vbml_ignore_case = True


# ======================
# БИЗНЕС КОМАНДЫ
# ======================


@business_labeler.message(text=["б", "/б"])
async def show_all_businesses_handler(message: Message):
    """Показать все бизнесы игрока"""
    user_id = message.from_id
    player = await get_player(user_id)

    if not player:
        player = await create_player(user_id, str(message.from_id))

    business_list = []
    total_clan_income = 0

    for business_id, business in settings.BUSINESSES.items():
        business_level = player.get(f"business_{business_id}_level", 0)
        if business_level > 0:
            income = (
                business["base_income"]
                + (business_level - 1) * business["income_increase"]
            )
            business_list.append(
                f"{business_id}. ✅ {business['name']}\n   ⏳ Доход: {format_number(income)} магнезии/час"
            )

            # Рассчитываем доход для клана
            clan = await get_player_clan(user_id)
            if clan:
                clan_bonuses = get_clan_bonuses(clan["level"])
                clan_income = income * clan_bonuses["business_bonus_percent"] / 100
                total_clan_income += clan_income

    if not business_list:
        return "📊 ВАШИ БИЗНЕСЫ\n\nУ вас пока нет бизнесов! 🏢\n\n💡 Посмотреть доступные бизнесы: /б магазин"

    clan_info = ""
    clan = await get_player_clan(user_id)
    if clan:
        clan_info = f"\n🏰 Ваш клан: [{clan['tag']}] {clan['name']}\n💰 В казну клана: ~{format_number(total_clan_income)} магнезии/час"

    info_text = (
        "📊 ВАШИ БИЗНЕСЫ\n\n"
        "🏢 Купленные бизнесы:\n\n"
        + "\n\n".join(business_list)
        + f"{clan_info}\n\n"
        f"💎 Общий баланс магнезии: {format_number(player['magnesia'])} банок\n"
        f"💰 Общий баланс монет: {format_number(player['balance'])} монет\n\n"
        f"📝 Для просмотра бизнеса: /б [номер]"
    )

    return info_text


@business_labeler.message(text=["б <business_id> купить", "/б <business_id> купить"])
async def buy_business_handler(message: Message, business_id: str):
    """Покупка бизнеса"""
    try:
        business_id = int(business_id)
    except ValueError:
        return "❌ Номер бизнеса должен быть числом!"

    if business_id not in settings.BUSINESSES:
        return "❌ Бизнес не найден!"

    user_id = message.from_id
    player = await get_player(user_id)

    if not player:
        player = await create_player(user_id, str(message.from_id))

    business = settings.BUSINESSES[business_id]
    business_level = player.get(f"business_{business_id}_level", 0)

    if business_level > 0:
        return "❌ Вы уже владеете этим бизнесом!"

    if business["currency"] == "монет":
        if player["balance"] < business["base_price"]:
            return f"❌ Недостаточно монет! Нужно {format_number(business['base_price'])} 💰"
    else:
        if player["magnesia"] < business["base_price"]:
            return f"❌ Недостаточно банок магнезии! Нужно {format_number(business['base_price'])} 💎"

    await buy_business(user_id, business_id, business)

    # Информация о бонусе клана
    clan = await get_player_clan(user_id)
    clan_bonus_text = ""
    if clan:
        clan_bonuses = get_clan_bonuses(clan['level'])
        clan_bonus_text = f"\n🏰 Бонус клана: +{clan_bonuses['business_bonus_percent']}% в казну клана"
    
    return (
        f'{business["name"].split()[0]} Бизнес куплен!'
        f'\n\n{business["name"]}'
        f'\n💵 Стоимость: {format_number(business["base_price"])} {business["currency"]}'
        f'\n🏋️‍♂️ Доход: {business["base_income"]} банок магнезии в час{clan_bonus_text}'
    )


@business_labeler.message(text=["б <cmd_args> улучшить", "/б <cmd_args> улучшить"])
async def upgrade_business_handler(message: Message, cmd_args: str):
    """Улучшение бизнеса"""
    parts = cmd_args.strip().split()

    if len(parts) < 2:
        return

    try:
        business_id = int(parts[0])
        upgrade_num = int(parts[1])
    except ValueError:
        return "❌ Номер бизнеса и улучшения должны быть числами!"

    if business_id not in settings.BUSINESSES:
        return "❌ Бизнес не найден!"

    if upgrade_num < 1 or upgrade_num > 5:
        return "❌ Номер улучшения должен быть от 1 до 5!"

    user_id = message.from_id
    player = await get_player(user_id)

    if not player:
        player = await create_player(user_id, str(message.from_id))

    business = settings.BUSINESSES[business_id]
    business_level = player.get(f"business_{business_id}_level", 0)

    if business_level == 0:
        return "❌ Вы не владеете этим бизнесом!"

    upgrades = player.get(f"business_{business_id}_upgrades", {})
    completed_upgrades = sum(1 for v in upgrades.values() if v > 0)

    upgrade_price = business["upgrade_price"] + completed_upgrades * 50

    if business["upgrade_currency"] == "монет":
        if player["balance"] < upgrade_price:
            return f"❌ Недостаточно монет! Нужно {format_number(upgrade_price)} 💰"
    else:
        if player["magnesia"] < upgrade_price:
            return f"❌ Недостаточно банок магнезии! Нужно {format_number(upgrade_price)} 💎"

    await upgrade_business(user_id, business_id, upgrade_num, upgrade_price)

    upgrade_info = business["upgrades"][upgrade_num]
    new_level = upgrades.get(str(upgrade_num), 0) + 1

    message_text = (
        f"{upgrade_info['emoji']} Улучшение #{upgrade_num} завершено!\n\n"
        f"✅ {upgrade_info['name']}\n"
        f"📈 Новый уровень: {new_level}\n"
        f"💰 Потрачено: {format_number(upgrade_price)} {business['upgrade_currency']}\n"
        f"🏗️ Улучшено этапов: {completed_upgrades + 1}/5\n"
        f"🏢 Уровень бизнеса: {business_level}"
    )

    if completed_upgrades + 1 >= 5:
        message_text += f"\n\n🎉 ВСЕ 5 УЛУЧШЕНИЙ ЗАВЕРШЕНЫ!\n🏢 Уровень бизнеса повышен до {business_level + 1}\n💎 Доход увеличен до {business['base_income'] + business_level * business['income_increase']} банок магнезии в час!"

    return message_text


@business_labeler.message(text=["б магазин", "/б магазин", "б купить", "/б купить"])
async def show_business_shop_handler(message: Message):
    """Магазин бизнесов"""
    user_id = message.from_id
    player = await get_player(user_id)

    if not player:
        player = await create_player(user_id, str(message.from_id))

    shop_items = []
    for business_id, business in settings.BUSINESSES.items():
        business_level = player.get(f"business_{business_id}_level", 0)

        if business_level > 0:
            status = "✅ Куплен"
        else:
            status = "❌ Не куплен"

        shop_items.append(
            f"{business_id}. {business['name']}\n"
            f"   💰 Цена: {format_number(business['base_price'])} {business['currency']}\n"
            f"   ⏳ Доход: {business['base_income']} банок магнезии/час\n"
            f"   📈 Улучшение: {format_number(business['upgrade_price'])} {business['upgrade_currency']}/уровень\n"
            f"   {status}"
        )

    info_text = (
        "📊 СИСТЕМА БИЗНЕСОВ GYM LEGEND\n\n"
        "🏢 Доступные бизнесы:\n\n"
        + "\n\n".join(shop_items)
        + f"\n\n💰 Ваш баланс: {format_number(player['balance'])} монет\n"
        f"💎 Накоплено магнезии: {format_number(player['magnesia'])} банок\n\n"
        f"📝 Команды:\n"
        f"• /б [номер] - посмотреть бизнес\n"
        f"• /б [номер] купить - купить бизнес\n"
        f"• /б магазин - магазин бизнесов"
    )

    return info_text


@business_labeler.message(text=["б <business_id>", "/б <business_id>"])
async def get_business_info_handler(message: Message, business_id: str):
    """Информация о бизнесе"""
    try:
        business_id = int(business_id)
    except ValueError:
        return "❌ Номер бизнеса должен быть числом!"

    if business_id not in settings.BUSINESSES:
        return "❌ Бизнес не найден!"

    user_id = message.from_id
    player = await get_player(user_id)

    if not player:
        player = await create_player(user_id, str(message.from_id))

    business = settings.BUSINESSES[business_id]
    business_level = player.get(f"business_{business_id}_level", 0)
    upgrades = player.get(f"business_{business_id}_upgrades", {})

    if business_level == 0:
        return f"❌ Вы не владеете бизнесом #{business_id}!\n💡 Купите его: /б {business_id} купить"

    # Базовый доход бизнеса
    base_income = (
        business["base_income"] + (business_level - 1) * business["income_increase"]
    )

    # Рассчитываем доход с учетом клана
    income_calculation = await calculate_business_income_with_clan(
        player, business_id, base_income
    )

    completed_upgrades = sum(1 for v in upgrades.values() if v > 0)

    upgrade_text = ""
    for i in range(1, 6):
        level = upgrades.get(str(i), 0)
        upgrade_info = business["upgrades"][i]
        upgrade_text += f"\n{upgrade_info['emoji']} {i}. {upgrade_info['name']} (Уровень {level})"

    next_upgrade_price = business["upgrade_price"] + completed_upgrades * 50

    # Формируем информационное сообщение
    info_parts = [
        f"📊 БИЗНЕС #{business_id}",
        "",
        f"✅ {business['name']}",
        "",
        f"⏳ Базовый доход: {format_number(base_income)} банок магнезии/час",
    ]

    clan = await get_player_clan(user_id)
    if clan:
        clan_bonuses = get_clan_bonuses(clan["level"])
        info_parts.extend(
            [
                f"🏰 Ваш клан: [{clan['tag']}] {clan['name']}",
                f"⭐ Бонус клана: +{clan_bonuses['business_bonus_percent']}% к доходу",
                "",
                "📊 Распределение дохода:",
                f"├─ 👤 Вам: {format_number(income_calculation['player_income'])} магнезии/час",
                f"└─ 🏦 В казну клана: {format_number(income_calculation['clan_income'])} магнезии/час",
            ]
        )
    else:
        info_parts.append(
            f"👤 Ваш доход: {format_number(income_calculation['player_income'])} магнезии/час"
        )

    info_parts.extend(
        [
            "",
            f"📊 Уровень бизнеса: {business_level}",
            f"🏗️ Улучшено этапов: {completed_upgrades}/5",
            "",
            f"{upgrade_text}",
            "",
            f"🕐 Накоплено магнезии: {format_number(player['magnesia'])} банок",
            f"💰 Следующее улучшение: {format_number(next_upgrade_price)} {business['upgrade_currency']}",
            "",
            f"💡 Для улучшения: /б {business_id} [1-5] улучшить",
        ]
    )

    return "\n".join(info_parts)
