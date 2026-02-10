from datetime import datetime

from loguru import logger
from vkbottle import BaseMiddleware, BaseReturnManager
from vkbottle.bot import Message
from vkbottle_types.objects import UsersFields

from bot.core.loader import bot
from bot.db import create_player, get_player, unban_player


class RegistrationMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        player = await get_player(self.event.from_id)
        if player and player.get("is_banned", 0) == 1:
            ban_reason = player.get("ban_reason", "Не указана")
            ban_until = player.get("ban_until")

            if ban_until:
                try:
                    ban_until_date = datetime.fromisoformat(ban_until)
                    if datetime.now() > ban_until_date:
                        await unban_player(self.event.from_id, 0)
                    else:
                        days_left = (ban_until_date - datetime.now()).days
                        await self.event.answer(
                            f"🚫 Вы заблокированы!\n📝 Причина: {ban_reason}\n⏳ Срок: {days_left} дней\n📅 До: {ban_until_date.strftime('%d.%m.%Y')}"
                        )
                except:
                    pass
            else:
                await self.event.answer(
                    f"🚫 Вы заблокированы навсегда!\n📝 Причина: {ban_reason}"
                )

            self.stop("User is banned")

        if not player:
            logger.info(f"Creating new player with id {self.event.from_id}")
            await create_player(self.event.from_id, str(self.event.from_id))


class BotMessageReturnHandler(BaseReturnManager):
    @BaseReturnManager.instance_of(str)
    async def str_handler(self, value: str, message: Message, _: dict):
        # TODO: Currently ignoring formatting. How do we use it with vkbottle's formatting system?
        value = value.replace("", "").replace("", "").replace("", "").replace("", "")
        await message.answer(value)
