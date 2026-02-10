from bot.utils import format_number
from vkbottle.bot import BotLabeler, Message

from bot.core.config import settings
from bot.db import (
    create_player,
    get_player,
    get_top_balance,
    get_top_earners,
    get_top_lifts,
)

top_labeler = BotLabeler()
top_labeler.vbml_ignore_case = True


@top_labeler.message(text=["топ", "/топ"])
async def get_top_list_handler(message: Message):
    """Список топов"""
    user_id = message.from_id
    player = await get_player(user_id)

    if not player:
        player = await create_player(user_id, str(message.from_id))

    top_text = (
        "🏆 Система ТОПа Gym Legend\n\n"
        "📊 Доступные рейтинги:\n\n"
        "💰 /топ монет - топ игроков по балансу\n"
        "💪 /топ поднятий - топ по количеству поднятий\n"
        "📈 /топ заработка - топ по общему заработку\n"
        "🏰 /к топ - топ кланов\n\n"
        f"💪 Ваши показатели:\n"
        f"💰 Баланс: {format_number(player['balance'])} монет\n"
        f"💪 Поднятий: {format_number(player['total_lifts'])}\n"
        f"🏋️‍♂️ Гантеля: {player['dumbbell_name']}\n\n"
        "Выберите нужный топ из списка выше!"
    )

    return top_text


@top_labeler.message(text=["топ монет", "/топ монет"])
async def get_top_balance_handler(message: Message):
    """Топ по монетам"""
    top_players = await get_top_balance(10)

    if not top_players:
        return "🏆 Топ пока пуст. Будьте первым!"

    top_text = "🏆 ТОП по монетам:\n\n"

    for i, (user_id, username, balance, dumbbell_name) in enumerate(top_players, 1):
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "🔸"))
        top_text += f"{medal} {i}. [id{user_id}|{username}]\n"
        top_text += f"   💰 {format_number(balance)} монет | 🏋️‍♂️ {dumbbell_name}\n\n"

    await message.answer(top_text, disable_mentions=True)


@top_labeler.message(text=["топ поднятий", "/топ поднятий"])
async def get_top_lifts_handler(message: Message):
    """Топ по поднятиям"""
    top_players = await get_top_lifts(10)

    if not top_players:
        return "🏆 Топ пока пуст. Будьте первым!"

    top_text = "💪 ТОП по поднятиям:\n\n"

    for i, (user_id, username, total_lifts, dumbbell_name) in enumerate(top_players, 1):
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "🔸"))
        top_text += f"{medal} {i}. [id{user_id}|{username}]\n"
        top_text += (
            f"   💪 {format_number(total_lifts)} поднятий | 🏋️‍♂️ {dumbbell_name}\n\n"
        )

    await message.answer(top_text, disable_mentions=True)


@top_labeler.message(text=["топ заработка", "/топ заработка"])
async def get_top_earners_handler(message: Message):
    """Топ по заработку"""
    top_players = await get_top_earners(10)

    if not top_players:
        return "🏆 Топ пока пуст. Будьте первым!"

    top_text = "💰 ТОП по заработку:\n\n"

    for i, (user_id, username, dumbbell_name, dumbbell_level, total_earned) in enumerate(
        top_players, 1
    ):
        medal = "🥇" if i == 1 else ("🥈" if i == 2 else ("🥉" if i == 3 else "🔸"))
        dumbbell_info = settings.DUMBBELL_LEVELS.get(
            dumbbell_level, {"income_per_use": 1}
        )
        income_per_lift = dumbbell_info["income_per_use"]

        top_text += f"{medal} {i}. [id{user_id}|{username}]\n"
        top_text += f"   💰 {format_number(total_earned)} монет | 🏋️‍♂️ {dumbbell_name}\n"
        top_text += f"   📈 {income_per_lift} монет/подход\n\n"

    await message.answer(top_text, disable_mentions=True)
