"""
Gym Legend - Игровой бот для ВК
Полная версия с административной системой, системой силы, бизнесами, промокодами, переводом денег и кланами
С ОБНОВЛЕННОЙ СИСТЕМОЙ КЛАНОВ

Bot rewritten by F1zzTao (https://github.com/F1zzTao)
"""

from __future__ import annotations

from bot.db import create_tables
from bot.middlewares.register import RegistrationMiddleware, BotMessageReturnHandler
from loguru import logger

from bot.core.loader import bot
from bot.handlers import get_handlers_labelers


async def on_startup() -> None:
    logger.info("bot starting...")

    await create_tables()

    bot.labeler.load(get_handlers_labelers())
    bot.labeler.message_view.register_middleware(RegistrationMiddleware)
    bot.labeler.message_view.handler_return_manager = BotMessageReturnHandler()

    logger.info("Gym Legend Bot is running!")


async def on_shutdown() -> None:
    logger.info("bot stopping...")

    """
    await dp.storage.close()
    await dp.fsm.storage.close()

    await bot.session.close()
    """

    logger.info("bot stopped")


def main() -> None:
    logger.add(
        "logs/vk_bot.log",
        level="DEBUG",
        format="{time} | {level} | {module}:{function}:{line} | {message}",
        rotation="100 KB",
        compression="zip",
    )

    bot.loop_wrapper.on_startup.append(on_startup())
    bot.loop_wrapper.on_shutdown.append(on_shutdown())

    bot.run_forever()


if __name__ == "__main__":
    main()