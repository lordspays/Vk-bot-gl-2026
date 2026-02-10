from bot.core.config import settings
from bot.db import get_player


async def is_admin(user_id: int) -> bool:
    if user_id in settings.ADMIN_USERS:
        return True

    player = await get_player(user_id)
    if player and player.get("admin_level", 0) > 0:
        return True
    return False