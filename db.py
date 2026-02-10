import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiosqlite

from bot.core.config import settings

# Основная таблица игроков
SQL_PLAYERS_TABLE = """
    CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 1,
        power INTEGER DEFAULT 0,
        magnesia INTEGER DEFAULT 0,
        last_dumbbell_use TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_new INTEGER DEFAULT 1,
        dumbbell_level INTEGER DEFAULT 1,
        dumbbell_name TEXT DEFAULT 'Гантеля 1кг',
        total_lifts INTEGER DEFAULT 0,
        total_earned INTEGER DEFAULT 0,
        custom_income INTEGER DEFAULT NULL,
        admin_level INTEGER DEFAULT 0,
        admin_nickname TEXT DEFAULT NULL,
        admin_since TIMESTAMP DEFAULT NULL,
        admin_id TEXT DEFAULT NULL,
        bans_given INTEGER DEFAULT 0,
        permabans_given INTEGER DEFAULT 0,
        deletions_given INTEGER DEFAULT 0,
        dumbbell_sets_given INTEGER DEFAULT 0,
        nickname_changes_given INTEGER DEFAULT 0,
        is_banned INTEGER DEFAULT 0,
        ban_reason TEXT,
        ban_until TIMESTAMP DEFAULT NULL,
        business_1_level INTEGER DEFAULT 0,
        business_1_upgrades TEXT DEFAULT '{}',
        business_2_level INTEGER DEFAULT 0,
        business_2_upgrades TEXT DEFAULT '{}',
        business_3_level INTEGER DEFAULT 0,
        business_3_upgrades TEXT DEFAULT '{}',
        clan_id INTEGER DEFAULT NULL,
        used_promo_codes TEXT DEFAULT '[]'
    )
"""

# Таблица транзакций
SQL_TRANSACTIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        amount INTEGER,
        description TEXT,
        admin_id INTEGER DEFAULT NULL,
        target_user_id INTEGER DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

# Таблица использований гантелей
SQL_DUMBBELL_USES_TABLE = """
    CREATE TABLE IF NOT EXISTS dumbbell_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        dumbbell_level INTEGER,
        income INTEGER,
        power_gained INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES players (user_id)
    )
"""

# Таблица админ действий
SQL_ADMIN_ACTIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS admin_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action_type TEXT,
        target_user_id INTEGER,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

# Таблица промокодов
SQL_PROMO_CODES_TABLE = """
    CREATE TABLE IF NOT EXISTS promo_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        uses_total INTEGER DEFAULT 1,
        uses_left INTEGER DEFAULT 1,
        reward_type TEXT NOT NULL,
        reward_amount INTEGER NOT NULL,
        created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP DEFAULT NULL,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (created_by) REFERENCES players (user_id)
    )
"""

# Таблица использований промокодов
SQL_PROMO_USES_TABLE = """
    CREATE TABLE IF NOT EXISTS promo_uses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        promo_code TEXT NOT NULL,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES players (user_id),
        FOREIGN KEY (promo_code) REFERENCES promo_codes (code)
    )
"""

# Таблица кланов
SQL_CLANS_TABLE = """
    CREATE TABLE IF NOT EXISTS clans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        owner_id INTEGER NOT NULL,
        level INTEGER DEFAULT 1,
        treasury INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_income_per_hour INTEGER DEFAULT 0,
        total_lifts INTEGER DEFAULT 0,
        FOREIGN KEY (owner_id) REFERENCES players (user_id)
    )
"""

# Таблица участников кланов
SQL_CLAN_MEMBERS_TABLE = """
    CREATE TABLE IF NOT EXISTS clan_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clan_id INTEGER NOT NULL,
        user_id INTEGER UNIQUE NOT NULL,
        role TEXT DEFAULT 'member',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        contributions INTEGER DEFAULT 0,
        FOREIGN KEY (clan_id) REFERENCES clans (id),
        FOREIGN KEY (user_id) REFERENCES players (user_id)
    )
"""

# Таблица лога казны клана
SQL_CLAN_TREASURY_LOG_TABLE = """
    CREATE TABLE IF NOT EXISTS clan_treasury_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clan_id INTEGER NOT NULL,
        user_id INTEGER,
        action_type TEXT,
        amount INTEGER,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (clan_id) REFERENCES clans (id),
        FOREIGN KEY (user_id) REFERENCES players (user_id)
    )
"""

# Таблица приглашений в кланы
SQL_CLAN_INVITES_TABLE = """
    CREATE TABLE IF NOT EXISTS clan_invites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clan_id INTEGER NOT NULL,
        inviter_id INTEGER NOT NULL,
        invitee_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        FOREIGN KEY (clan_id) REFERENCES clans (id),
        FOREIGN KEY (inviter_id) REFERENCES players (user_id),
        FOREIGN KEY (invitee_id) REFERENCES players (user_id)
    )
"""


async def create_tables() -> None:
    """Create all database tables if they don't exist"""
    # Creating database file if it doesn't exist
    with open(settings.database_path, "a"):
        pass

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(SQL_PLAYERS_TABLE)
        await db.execute(SQL_TRANSACTIONS_TABLE)
        await db.execute(SQL_DUMBBELL_USES_TABLE)
        await db.execute(SQL_ADMIN_ACTIONS_TABLE)
        await db.execute(SQL_PROMO_CODES_TABLE)
        await db.execute(SQL_PROMO_USES_TABLE)
        await db.execute(SQL_CLANS_TABLE)
        await db.execute(SQL_CLAN_MEMBERS_TABLE)
        await db.execute(SQL_CLAN_TREASURY_LOG_TABLE)
        await db.execute(SQL_CLAN_INVITES_TABLE)
        await db.commit()


async def initialize_admin_ids() -> bool:
    """Initialize admin IDs for existing admins without an ID"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            'SELECT user_id, admin_since FROM players WHERE admin_level > 0 AND (admin_id IS NULL OR admin_id = "") ORDER BY admin_since ASC'
        ) as cur:
            admins = await cur.fetchall()

        current_id = 1000
        for admin in admins:
            user_id = admin[0]
            await db.execute(
                "UPDATE players SET admin_id = ? WHERE user_id = ?",
                (str(current_id), user_id),
            )
            current_id += 1

        await db.commit()
        return True


async def get_player(user_id: int) -> Optional[Dict[str, Any]]:
    """Get player data by user_id"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            """
            SELECT user_id, username, balance, power, magnesia, last_dumbbell_use, is_new,
                   dumbbell_level, dumbbell_name, total_lifts, total_earned,
                   custom_income, admin_level, admin_nickname, admin_since,
                   admin_id, bans_given, permabans_given, deletions_given,
                   dumbbell_sets_given, nickname_changes_given,
                   is_banned, ban_reason, ban_until, created_at,
                   business_1_level, business_1_upgrades,
                   business_2_level, business_2_upgrades,
                   business_3_level, business_3_upgrades,
                   clan_id, used_promo_codes
            FROM players WHERE user_id = ?
        """,
            (user_id,),
        ) as cur:
            row = await cur.fetchone()

        if not row:
            return

        business_1_upgrades = row[26] if row[26] else "{}"
        business_2_upgrades = row[28] if row[28] else "{}"
        business_3_upgrades = row[30] if row[30] else "{}"
        used_promo_codes = row[32] if row[32] else "[]"

        return {
            "user_id": row[0],
            "username": row[1],
            "balance": row[2],
            "power": row[3],
            "magnesia": row[4],
            "last_dumbbell_use": row[5],
            "is_new": row[6],
            "dumbbell_level": row[7],
            "dumbbell_name": row[8],
            "total_lifts": row[9],
            "total_earned": row[10],
            "custom_income": row[11],
            "admin_level": row[12],
            "admin_nickname": row[13],
            "admin_since": row[14],
            "admin_id": row[15],
            "bans_given": row[16],
            "permabans_given": row[17],
            "deletions_given": row[18],
            "dumbbell_sets_given": row[19],
            "nickname_changes_given": row[20],
            "is_banned": row[21],
            "ban_reason": row[22],
            "ban_until": row[23],
            "created_at": row[24],
            "business_1_level": row[25] or 0,
            "business_1_upgrades": json.loads(business_1_upgrades),
            "business_2_level": row[27] or 0,
            "business_2_upgrades": json.loads(business_2_upgrades),
            "business_3_level": row[29] or 0,
            "business_3_upgrades": json.loads(business_3_upgrades),
            "clan_id": row[31],
            "used_promo_codes": json.loads(used_promo_codes),
        }


async def create_player(user_id: int, username: str) -> Optional[Dict[str, Any]]:
    """Create a new player"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """INSERT OR IGNORE INTO players 
               (user_id, username, dumbbell_level, dumbbell_name) 
               VALUES (?, ?, 1, 'Гантеля 1кг')""",
            (user_id, username),
        )
        await db.commit()
    return await get_player(user_id)


async def update_username(user_id: int, new_username: str) -> bool:
    """Update player username"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET username = ? WHERE user_id = ?", (new_username, user_id)
        )
        await db.commit()
    return True


async def update_player_balance(
    user_id: int,
    amount: int,
    transaction_type: str,
    description: str,
    admin_id: Optional[int] = None,
    target_user_id: Optional[int] = None,
) -> bool:
    """Update player balance and log transaction"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET balance = balance + ? WHERE user_id = ?",
            (amount, user_id),
        )

        await db.execute(
            """INSERT INTO transactions (user_id, type, amount, description, admin_id, target_user_id) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, transaction_type, amount, description, admin_id, target_user_id),
        )

        if amount > 0:
            await db.execute(
                "UPDATE players SET total_earned = total_earned + ? WHERE user_id = ?",
                (amount, user_id),
            )

        await db.commit()
    return True


async def set_player_balance(user_id: int, new_balance: int, admin_id: int) -> bool:
    """Set player balance to a specific value"""
    player = await get_player(user_id)
    old_balance = player["balance"] if player else 0

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET balance = ? WHERE user_id = ?", (new_balance, user_id)
        )
        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (
                admin_id,
                "set_balance",
                user_id,
                f"Изменение баланса: {old_balance} -> {new_balance}",
            ),
        )
        await db.commit()
    return True


async def add_power(user_id: int, amount: int) -> bool:
    """Add power to player"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET power = power + ? WHERE user_id = ?", (amount, user_id)
        )
        await db.commit()
    return True


async def set_power(user_id: int, new_power: int, admin_id: int) -> bool:
    """Set player power to a specific value"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET power = ? WHERE user_id = ?", (new_power, user_id)
        )
        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (admin_id, "set_power", user_id, f"Установлена сила: {new_power}"),
        )
        await db.commit()
    return True


async def add_magnesia(
    user_id: int, amount: int, admin_id: Optional[int] = None
) -> bool:
    """Add magnesia to player"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET magnesia = magnesia + ? WHERE user_id = ?",
            (amount, user_id),
        )

        if admin_id:
            await db.execute(
                """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
                   VALUES (?, ?, ?, ?)""",
                (
                    admin_id,
                    "add_magnesia",
                    user_id,
                    f"Добавлено банок магнезии: {amount}",
                ),
            )

        await db.commit()
    return True


async def update_dumbbell_level(
    user_id: int, new_level: int, dumbbell_name: str
) -> bool:
    """Update player dumbbell level"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET dumbbell_level = ?, dumbbell_name = ? WHERE user_id = ?",
            (new_level, dumbbell_name, user_id),
        )
        await db.commit()
    return True


async def set_dumbbell_level(user_id: int, new_level: int, admin_id: int) -> bool:
    """Set player dumbbell level to a specific value"""
    if new_level not in settings.DUMBBELL_LEVELS:
        return False

    dumbbell_info = settings.DUMBBELL_LEVELS[new_level]

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET dumbbell_level = ?, dumbbell_name = ? WHERE user_id = ?",
            (new_level, dumbbell_info["name"], user_id),
        )

        await db.execute(
            "UPDATE players SET dumbbell_sets_given = dumbbell_sets_given + 1 WHERE user_id = ?",
            (admin_id,),
        )

        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (
                admin_id,
                "set_dumbbell_level",
                user_id,
                f"Установлен уровень гантели: {new_level}",
            ),
        )

        await db.commit()
    return True


async def update_dumbbell_use_time(user_id: int) -> bool:
    """Update the last dumbbell use time"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET last_dumbbell_use = ? WHERE user_id = ?",
            (datetime.now().isoformat(), user_id),
        )
        await db.commit()
    return True


async def increment_total_lifts(user_id: int) -> bool:
    """Increment total lifts counter"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET total_lifts = total_lifts + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()
    return True


async def set_total_lifts(user_id: int, new_total: int, admin_id: int) -> bool:
    """Set total lifts to a specific value"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET total_lifts = ? WHERE user_id = ?", (new_total, user_id)
        )
        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (
                admin_id,
                "set_total_lifts",
                user_id,
                f"Установлено поднятий: {new_total}",
            ),
        )
        await db.commit()
    return True


async def set_custom_income(
    user_id: int, custom_income: Optional[int], admin_id: int
) -> bool:
    """Set custom income for player"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET custom_income = ? WHERE user_id = ?",
            (custom_income, user_id),
        )
        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (
                admin_id,
                "set_custom_income",
                user_id,
                f"Установлен кастомный доход: {custom_income}",
            ),
        )
        await db.commit()
    return True


async def buy_business(
    user_id: int, business_id: int, business_info: Dict[str, Any]
) -> bool:
    """Buy a business for player"""
    async with aiosqlite.connect(settings.database_path) as db:
        if business_info["currency"] == "монет":
            await db.execute(
                "UPDATE players SET balance = balance - ? WHERE user_id = ?",
                (business_info["base_price"], user_id),
            )
        else:
            await db.execute(
                "UPDATE players SET magnesia = magnesia - ? WHERE user_id = ?",
                (business_info["base_price"], user_id),
            )

        column = f"business_{business_id}_level"
        await db.execute(
            f"UPDATE players SET {column} = 1 WHERE user_id = ?", (user_id,)
        )

        await db.commit()
    return True


async def upgrade_business(
    user_id: int, business_id: int, upgrade_num: int, price: int
) -> bool:
    """Upgrade a business"""
    player = await get_player(user_id)
    if not player:
        return False

    upgrades_column = f"business_{business_id}_upgrades"
    current_upgrades = player[upgrades_column]

    if str(upgrade_num) not in current_upgrades:
        current_upgrades[str(upgrade_num)] = 1
    else:
        current_upgrades[str(upgrade_num)] += 1

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            f"UPDATE players SET {upgrades_column} = ? WHERE user_id = ?",
            (json.dumps(current_upgrades), user_id),
        )

        business_info = settings.BUSINESSES[business_id]
        if business_info["upgrade_currency"] == "монет":
            await db.execute(
                "UPDATE players SET balance = balance - ? WHERE user_id = ?",
                (price, user_id),
            )
        else:
            await db.execute(
                "UPDATE players SET magnesia = magnesia - ? WHERE user_id = ?",
                (price, user_id),
            )

        level_column = f"business_{business_id}_level"
        completed_upgrades = sum(1 for v in current_upgrades.values() if v > 0)

        if completed_upgrades >= 5:
            await db.execute(
                f"UPDATE players SET {level_column} = {level_column} + 1 WHERE user_id = ?",
                (user_id,),
            )
            for key in current_upgrades:
                current_upgrades[key] = 0
            await db.execute(
                f"UPDATE players SET {upgrades_column} = ? WHERE user_id = ?",
                (json.dumps(current_upgrades), user_id),
            )

        await db.commit()
    return True


async def make_admin(user_id: int, admin_id: int, admin_level: int = 1) -> str:
    """Make a player an admin"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            'SELECT MAX(CAST(admin_id AS INTEGER)) FROM players WHERE admin_id IS NOT NULL AND admin_id != ""'
        ) as cur:
            result = await cur.fetchone()

        if result[0] is None:
            new_admin_id = 1000
        else:
            new_admin_id = int(result[0]) + 1

        await db.execute(
            """UPDATE players 
               SET admin_level = ?, admin_since = ?, admin_id = ?
               WHERE user_id = ?""",
            (admin_level, datetime.now().isoformat(), str(new_admin_id), user_id),
        )

        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (
                admin_id,
                "make_admin",
                user_id,
                f"Назначение администратора уровня {admin_level} с ID {new_admin_id}",
            ),
        )

        await db.commit()
    return str(new_admin_id)


async def remove_admin(user_id: int, admin_id: int) -> bool:
    """Remove admin status from player"""
    player_data = await get_player(user_id)
    if not player_data:
        return False

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """UPDATE players 
               SET admin_level = 0, admin_nickname = NULL, admin_since = NULL, admin_id = NULL,
                   bans_given = 0, permabans_given = 0, deletions_given = 0,
                   dumbbell_sets_given = 0, nickname_changes_given = 0
               WHERE user_id = ?""",
            (user_id,),
        )

        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (
                admin_id,
                "remove_admin",
                user_id,
                f"Снятие с должности администратора: {player_data['username']}",
            ),
        )

        await db.commit()
    return True


async def set_admin_nickname(user_id: int, nickname: str) -> bool:
    """Set admin nickname"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET admin_nickname = ? WHERE user_id = ?",
            (nickname, user_id),
        )
        await db.commit()
    return True


async def ban_player(user_id: int, days: int, reason: str, admin_id: int) -> bool:
    """Ban a player"""
    if days == 0:
        ban_until = None
    else:
        ban_until = (datetime.now() + timedelta(days=days)).isoformat()

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET is_banned = 1, ban_reason = ?, ban_until = ? WHERE user_id = ?",
            (reason, ban_until, user_id),
        )

        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (admin_id, "ban", user_id, f"Бан: {days} дней, причина: {reason}"),
        )

        await db.commit()
    return True


async def unban_player(user_id: int, admin_id: int) -> bool:
    """Unban a player"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "UPDATE players SET is_banned = 0, ban_reason = NULL, ban_until = NULL WHERE user_id = ?",
            (user_id,),
        )
        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (admin_id, "unban", user_id, "Разбан игрока"),
        )
        await db.commit()
    return True


async def delete_player(user_id: int, admin_id: int) -> bool:
    """Delete a player"""
    player_data = await get_player(user_id)
    if not player_data:
        return False

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute("DELETE FROM transactions WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM dumbbell_uses WHERE user_id = ?", (user_id,))
        await db.execute("DELETE FROM players WHERE user_id = ?", (user_id,))

        await db.execute(
            """INSERT INTO admin_actions (admin_id, action_type, target_user_id, details) 
               VALUES (?, ?, ?, ?)""",
            (
                admin_id,
                "delete_player",
                user_id,
                f"Удален игрок: {player_data['username']}",
            ),
        )

        await db.commit()
    return True


async def log_dumbbell_use(
    user_id: int, dumbbell_level: int, income: int, power_gained: int
) -> bool:
    """Log dumbbell use"""
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            """INSERT INTO dumbbell_uses (user_id, dumbbell_level, income, power_gained) 
               VALUES (?, ?, ?, ?)""",
            (user_id, dumbbell_level, income, power_gained),
        )
        await db.commit()
    return True


async def increment_admin_stat(user_id: int, stat_name: str) -> bool:
    """Increment admin statistic"""
    stats_map = {
        "bans": "bans_given",
        "permabans": "permabans_given",
        "deletions": "deletions_given",
        "dumbbell_sets": "dumbbell_sets_given",
        "nickname_changes": "nickname_changes_given",
    }

    if stat_name in stats_map:
        column = stats_map[stat_name]
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                f"UPDATE players SET {column} = {column} + 1 WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
    return True


async def get_top_balance(limit: int = 10) -> List[Tuple]:
    """Get top players by balance"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT user_id, username, balance, dumbbell_name FROM players WHERE is_banned = 0 ORDER BY balance DESC LIMIT ?",
            (limit,),
        ) as cur:
            return await cur.fetchall()


async def get_top_lifts(limit: int = 10) -> List[Tuple]:
    """Get top players by total lifts"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT user_id, username, total_lifts, dumbbell_name FROM players WHERE is_banned = 0 ORDER BY total_lifts DESC LIMIT ?",
            (limit,),
        ) as cur:
            return await cur.fetchall()


async def get_top_earners(limit: int = 10) -> List[Tuple]:
    """Get top players by total earned"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT user_id, username, dumbbell_name, dumbbell_level, total_earned FROM players WHERE is_banned = 0 ORDER BY total_earned DESC LIMIT ?",
            (limit,),
        ) as cur:
            return await cur.fetchall()


# ==============================
# ФУНКЦИИ ДЛЯ ПРОМОКОДОВ
# ==============================


async def create_promo_code(
    code: str,
    uses_total: int,
    reward_type: str,
    reward_amount: int,
    created_by: int,
    expires_days: Optional[int] = None,
) -> bool:
    """Create a promo code"""
    if expires_days:
        expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
    else:
        expires_at = None

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                """
                INSERT INTO promo_codes (code, uses_total, uses_left, reward_type, reward_amount, created_by, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    code,
                    uses_total,
                    uses_total,
                    reward_type,
                    reward_amount,
                    created_by,
                    expires_at,
                ),
            )

            await db.execute(
                """
                INSERT INTO admin_actions (admin_id, action_type, target_user_id, details)
                VALUES (?, ?, ?, ?)
            """,
                (
                    created_by,
                    "create_promo",
                    0,
                    f"Создан промокод: {code}, награда: {reward_amount} {reward_type}",
                ),
            )

            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        return False


async def delete_promo_code(code: str, admin_id: int) -> bool:
    """Delete a promo code"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT code FROM promo_codes WHERE code = ?", (code,)
        ) as cur:
            result = await cur.fetchone()

        if not result:
            return False

        await db.execute("DELETE FROM promo_codes WHERE code = ?", (code,))

        await db.execute(
            """
            INSERT INTO admin_actions (admin_id, action_type, target_user_id, details)
            VALUES (?, ?, ?, ?)
        """,
            (admin_id, "delete_promo", 0, f"Удален промокод: {code}"),
        )

        await db.commit()
    return True


async def get_promo_info(code: str) -> Optional[Dict[str, Any]]:
    """Get promo code information"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            """
            SELECT code, uses_total, uses_left, reward_type, reward_amount, 
                   created_by, created_at, expires_at, is_active
            FROM promo_codes WHERE code = ?
        """,
            (code,),
        ) as cur:
            row = await cur.fetchone()

        if row:
            return {
                "code": row[0],
                "uses_total": row[1],
                "uses_left": row[2],
                "reward_type": row[3],
                "reward_amount": row[4],
                "created_by": row[5],
                "created_at": row[6],
                "expires_at": row[7],
                "is_active": row[8],
            }
        return None


async def use_promo_code(user_id: int, code: str) -> Dict[str, Any]:
    """Use a promo code"""
    # Check if promo exists
    promo_info = await get_promo_info(code)
    if not promo_info:
        return {"success": False, "error": "Промокод не найден"}

    # Check if promo is active
    if promo_info["is_active"] == 0:
        return {"success": False, "error": "Промокод неактивен"}

    # Check expiration
    if promo_info["expires_at"]:
        expires_at = datetime.fromisoformat(promo_info["expires_at"])
        if datetime.now() > expires_at:
            return {"success": False, "error": "Срок действия промокода истек"}

    # Check remaining uses
    if promo_info["uses_left"] <= 0:
        return {"success": False, "error": "Лимит использований исчерпан"}

    async with aiosqlite.connect(settings.database_path) as db:
        # Check if player already used this promo
        async with db.execute(
            "SELECT used_promo_codes FROM players WHERE user_id = ?", (user_id,)
        ) as cur:
            result = await cur.fetchone()

        used_codes = json.loads(result[0] if result[0] else "[]")

        if code in used_codes:
            return {"success": False, "error": "Вы уже использовали этот промокод"}

        # Decrease remaining uses
        await db.execute(
            "UPDATE promo_codes SET uses_left = uses_left - 1 WHERE code = ?", (code,)
        )

        # Give reward
        if promo_info["reward_type"] == "монеты":
            await db.execute(
                "UPDATE players SET balance = balance + ? WHERE user_id = ?",
                (promo_info["reward_amount"], user_id),
            )
        elif promo_info["reward_type"] == "магнезия":
            await db.execute(
                "UPDATE players SET magnesia = magnesia + ? WHERE user_id = ?",
                (promo_info["reward_amount"], user_id),
            )

        # Add promo to used codes
        used_codes.append(code)
        await db.execute(
            "UPDATE players SET used_promo_codes = ? WHERE user_id = ?",
            (json.dumps(used_codes), user_id),
        )

        # Log usage
        await db.execute(
            """
            INSERT INTO promo_uses (user_id, promo_code)
            VALUES (?, ?)
        """,
            (user_id, code),
        )

        await db.commit()

    return {
        "success": True,
        "reward_type": promo_info["reward_type"],
        "reward_amount": promo_info["reward_amount"],
    }


async def get_all_promo_codes() -> List[Dict[str, Any]]:
    """Get all promo codes"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute("""
            SELECT code, uses_total, uses_left, reward_type, reward_amount, 
                   created_at, expires_at, is_active
            FROM promo_codes ORDER BY created_at DESC
        """) as cur:
            rows = await cur.fetchall()

    promos = []
    for row in rows:
        promos.append(
            {
                "code": row[0],
                "uses_total": row[1],
                "uses_left": row[2],
                "reward_type": row[3],
                "reward_amount": row[4],
                "created_at": row[5],
                "expires_at": row[6],
                "is_active": row[7],
            }
        )
    return promos


# ==============================
# ФУНКЦИИ ДЛЯ КЛАНОВ
# ==============================


async def create_clan(tag: str, name: str, owner_id: int) -> Dict[str, Any]:
    """Create a clan"""
    async with aiosqlite.connect(settings.database_path) as db:
        # Check tag uniqueness
        async with db.execute(
            "SELECT id FROM clans WHERE tag = ?", (tag.upper(),)
        ) as cur:
            if await cur.fetchone():
                return {"success": False, "error": "Клан с таким тегом уже существует"}

        # Check name uniqueness
        async with db.execute("SELECT id FROM clans WHERE name = ?", (name,)) as cur:
            if await cur.fetchone():
                return {
                    "success": False,
                    "error": "Клан с таким названием уже существует",
                }

        # Check if player is already in a clan
        async with db.execute(
            "SELECT clan_id FROM players WHERE user_id = ?", (owner_id,)
        ) as cur:
            player_data = await cur.fetchone()

        if player_data and player_data[0]:
            return {"success": False, "error": "Вы уже состоите в клане"}

        try:
            # Create clan
            SQL_CREATE_CLAN = """
                INSERT INTO clans (tag, name, owner_id, level, treasury)
                VALUES (?, ?, ?, 1, 0)
            """
            async with db.execute(
                SQL_CREATE_CLAN, (tag.upper(), name, owner_id)
            ) as cur:
                clan_id = cur.lastrowid

            # Add owner as member
            await db.execute(
                """
                INSERT INTO clan_members (clan_id, user_id, role, contributions)
                VALUES (?, ?, 'owner', 0)
            """,
                (clan_id, owner_id),
            )

            # Update player's clan_id
            await db.execute(
                "UPDATE players SET clan_id = ? WHERE user_id = ?", (clan_id, owner_id)
            )

            await db.commit()
            return {
                "success": True,
                "clan_id": clan_id,
                "tag": tag.upper(),
                "name": name,
            }
        except Exception as e:
            return {"success": False, "error": f"Ошибка при создании клана: {str(e)}"}


async def get_clan_by_tag(tag: str) -> Optional[Dict[str, Any]]:
    """Get clan by tag"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            """
            SELECT id, tag, name, owner_id, level, treasury, created_at,
                   total_income_per_hour, total_lifts
            FROM clans WHERE tag = ?
        """,
            (tag.upper(),),
        ) as cur:
            row = await cur.fetchone()

        if row:
            return {
                "id": row[0],
                "tag": row[1],
                "name": row[2],
                "owner_id": row[3],
                "level": row[4],
                "treasury": row[5],
                "created_at": row[6],
                "total_income_per_hour": row[7],
                "total_lifts": row[8],
            }
        return None


async def get_clan_by_id(clan_id: int) -> Optional[Dict[str, Any]]:
    """Get clan by ID"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            """
            SELECT id, tag, name, owner_id, level, treasury, created_at,
                   total_income_per_hour, total_lifts
            FROM clans WHERE id = ?
        """,
            (clan_id,),
        ) as cur:
            row = await cur.fetchone()

        if row:
            return {
                "id": row[0],
                "tag": row[1],
                "name": row[2],
                "owner_id": row[3],
                "level": row[4],
                "treasury": row[5],
                "created_at": row[6],
                "total_income_per_hour": row[7],
                "total_lifts": row[8],
            }
        return None


async def get_player_clan(user_id: int) -> Optional[Dict[int, Any]]:
    """Get player's clan"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT clan_id FROM players WHERE user_id = ?", (user_id,)
        ) as cur:
            result = await cur.fetchone()

        if result and result[0]:
            return await get_clan_by_id(result[0])
        return None


async def get_clan_members(clan_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """Get clan members"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            """
            SELECT cm.user_id, p.username, cm.role, cm.contributions, cm.joined_at
            FROM clan_members cm
            JOIN players p ON cm.user_id = p.user_id
            WHERE cm.clan_id = ?
            ORDER BY 
                CASE cm.role 
                    WHEN 'owner' THEN 1
                    WHEN 'officer' THEN 2
                    ELSE 3 
                END,
                cm.contributions DESC
            LIMIT ?
        """,
            (clan_id, limit),
        ) as cur:
            rows = await cur.fetchall()

    members = []
    for row in rows:
        members.append(
            {
                "user_id": row[0],
                "username": row[1],
                "role": row[2],
                "contributions": row[3],
                "joined_at": row[4],
            }
        )
    return members


async def get_member_clan_role(user_id: int, clan_id: int):
    """Get player's clan"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT role FROM clan_members WHERE user_id = ? AND clan_id = ?", (user_id, clan_id)
        ) as cur:
            result = await cur.fetchone()
        return result


async def get_clan_member_count(clan_id: int) -> int:
    """Get clan member count"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM clan_members WHERE clan_id = ?", (clan_id,)
        ) as cur:
            result = await cur.fetchone()
    return result[0]


async def deposit_to_clan_treasury(user_id: int, amount: int) -> Dict[str, Any]:
    """Deposit money to clan treasury"""
    player = await get_player(user_id)
    if not player or not player["clan_id"]:
        return {"success": False, "error": "Вы не состоите в клане"}

    if player["balance"] < amount:
        return {"success": False, "error": "Недостаточно средств на балансе"}

    if amount <= 0:
        return {"success": False, "error": "Сумма должна быть положительной"}

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            # Deduct from player
            await db.execute(
                "UPDATE players SET balance = balance - ? WHERE user_id = ?",
                (amount, user_id),
            )

            # Add to clan treasury
            await db.execute(
                "UPDATE clans SET treasury = treasury + ? WHERE id = ?",
                (amount, player["clan_id"]),
            )

            # Increase player contribution
            await db.execute(
                "UPDATE clan_members SET contributions = contributions + ? WHERE user_id = ? AND clan_id = ?",
                (amount, user_id, player["clan_id"]),
            )

            # Log operation
            await db.execute(
                """
                INSERT INTO clan_treasury_log (clan_id, user_id, action_type, amount, description)
                VALUES (?, ?, 'deposit', ?, ?)
            """,
                (
                    player["clan_id"],
                    user_id,
                    amount,
                    f"Игрок {player['username']} внес {amount} монет в казну",
                ),
            )

            await db.commit()
            return {
                "success": True,
                "new_balance": player["balance"] - amount,
                "new_treasury": None,
            }
    except Exception as e:
        return {"success": False, "error": f"Ошибка при внесении средств: {str(e)}"}


async def upgrade_clan(clan_id: int) -> Dict[str, Any]:
    """Upgrade clan level"""
    clan = await get_clan_by_id(clan_id)
    if not clan:
        return {"success": False, "error": "Клан не найден"}

    # Calculate upgrade cost
    upgrade_cost = settings.CLAN_UPGRADE_BASE_COST * clan["level"]

    if clan["treasury"] < upgrade_cost:
        return {
            "success": False,
            "error": f"Недостаточно средств в казне. Нужно {upgrade_cost} монет",
        }

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            # Deduct from treasury
            await db.execute(
                "UPDATE clans SET treasury = treasury - ?, level = level + 1 WHERE id = ?",
                (upgrade_cost, clan_id),
            )

            # Log operation
            await db.execute(
                """
                INSERT INTO clan_treasury_log (clan_id, action_type, amount, description)
                VALUES (?, 'upgrade', ?, ?)
            """,
                (
                    clan_id,
                    upgrade_cost,
                    f"Улучшение клана до уровня {clan['level'] + 1}",
                ),
            )

            await db.commit()
            return {
                "success": True,
                "new_level": clan["level"] + 1,
                "cost": upgrade_cost,
            }
    except Exception as e:
        return {"success": False, "error": f"Ошибка при улучшении клана: {str(e)}"}


async def get_clan_treasury_log(clan_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get clan treasury log"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            """
            SELECT ctl.action_type, ctl.amount, ctl.description, ctl.created_at, p.username
            FROM clan_treasury_log ctl
            LEFT JOIN players p ON ctl.user_id = p.user_id
            WHERE ctl.clan_id = ?
            ORDER BY ctl.created_at DESC
            LIMIT ?
        """,
            (clan_id, limit),
        ) as cur:
            rows = await cur.fetchall()

    log = []
    for row in rows:
        log.append(
            {
                "action_type": row[0],
                "amount": row[1],
                "description": row[2],
                "created_at": row[3],
                "username": row[4],
            }
        )
    return log


async def get_top_clans(limit: int = 10) -> List[Dict[str, Any]]:
    """Get top clans"""
    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(
            """
            SELECT c.tag, c.name, c.level, c.treasury, c.total_income_per_hour,
                   COUNT(cm.id) as member_count
            FROM clans c
            LEFT JOIN clan_members cm ON c.id = cm.clan_id
            GROUP BY c.id
            ORDER BY c.total_income_per_hour DESC, c.treasury DESC
            LIMIT ?
        """,
            (limit,),
        ) as cur:
            rows = await cur.fetchall()

    clans = []
    for row in rows:
        clans.append(
            {
                "tag": row[0],
                "name": row[1],
                "level": row[2],
                "treasury": row[3],
                "total_income_per_hour": row[4],
                "member_count": row[5] or 0,
            }
        )
    return clans


async def delete_clan(tag: str, admin_id: int) -> Dict[str, Any]:
    """Delete a clan"""
    clan = await get_clan_by_tag(tag)
    if not clan:
        return {"success": False, "error": "Клан не найден"}

    try:
        async with aiosqlite.connect(settings.database_path) as db:
            # Get all clan members
            async with db.execute(
                "SELECT user_id FROM clan_members WHERE clan_id = ?", (clan["id"],)
            ) as cur:
                members = await cur.fetchall()

            # Reset clan_id for all members
            for member in members:
                await db.execute(
                    "UPDATE players SET clan_id = NULL WHERE user_id = ?", (member[0],)
                )

            # Delete members
            await db.execute(
                "DELETE FROM clan_members WHERE clan_id = ?", (clan["id"],)
            )

            # Delete treasury log
            await db.execute(
                "DELETE FROM clan_treasury_log WHERE clan_id = ?", (clan["id"],)
            )

            # Delete clan
            await db.execute("DELETE FROM clans WHERE id = ?", (clan["id"],))

            # Log admin action
            await db.execute(
                """
                INSERT INTO admin_actions (admin_id, action_type, target_user_id, details)
                VALUES (?, ?, ?, ?)
            """,
                (
                    admin_id,
                    "delete_clan",
                    clan["owner_id"],
                    f"Удален клан: {clan['tag']} {clan['name']}",
                ),
            )

            await db.commit()
            return {
                "success": True,
                "clan_name": clan["name"],
                "member_count": len(members),
            }
    except Exception as e:
        return {"success": False, "error": f"Ошибка при удалении клана: {str(e)}"}


async def update_clan_name(tag: str, new_name: str, admin_id: int) -> Dict[str, Any]:
    """Update clan name"""
    clan = await get_clan_by_tag(tag)
    if not clan:
        return {"success": False, "error": "Клан не найден"}

    try:
        old_name = clan["name"]
        async with aiosqlite.connect(settings.database_path) as db:
            await db.execute(
                "UPDATE clans SET name = ? WHERE id = ?", (new_name, clan["id"])
            )

            # Log admin action
            await db.execute(
                """
                INSERT INTO admin_actions (admin_id, action_type, target_user_id, details)
                VALUES (?, ?, ?, ?)
            """,
                (
                    admin_id,
                    "rename_clan",
                    clan["owner_id"],
                    f"Переименован клан {clan['tag']}: {old_name} -> {new_name}",
                ),
            )

            await db.commit()
            return {"success": True, "old_name": old_name, "new_name": new_name}
    except Exception as e:
        return {"success": False, "error": f"Ошибка при изменении названия: {str(e)}"}


# Other database funcs not part of database class


async def get_players_with_businesses():
    SQL_BUSINESS_PLAYERS = """
        SELECT user_id, 
               COALESCE(business_1_level, 0) as b1_level,
               COALESCE(business_2_level, 0) as b2_level,
               COALESCE(business_3_level, 0) as b3_level,
               clan_id
        FROM players 
        WHERE (business_1_level > 0 OR business_2_level > 0 OR business_3_level > 0)
          AND clan_id IS NOT NULL
    """

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL_BUSINESS_PLAYERS) as cur:
            players = await cur.fetchall()
    return players


async def add_treasury(clan_id, amount: int, add_total_lifts: bool = False) -> None:
    SQL_TREASURY_LOG = "UPDATE clans SET treasury = treasury + ?"
    if add_total_lifts:
        SQL_TREASURY_LOG += ", total_lifts = total_lifts + 1"
    SQL_TREASURY_LOG += " WHERE id = ?"

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(SQL_TREASURY_LOG, (amount, clan_id))
        await db.commit()


async def subtract_treasury(clan_id, amount: int, subtract_total_lifts: bool = False) -> None:
    SQL_TREASURY_LOG = "UPDATE clans SET treasury = treasury - ?"
    if subtract_total_lifts:
        SQL_TREASURY_LOG += ", total_lifts = total_lifts - 1"
    SQL_TREASURY_LOG += " WHERE id = ?"

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(SQL_TREASURY_LOG, (amount, clan_id))
        await db.commit()


async def log_collection(
    clan_id, action_type: str, amount: int, description: str
) -> None:
    SQL_TREASURY_LOG = """
        INSERT INTO clan_treasury_log (clan_id, action_type, amount, description)
        VALUES (?, ?, ?, ?)
    """

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(SQL_TREASURY_LOG, (clan_id, action_type, amount, description))
        await db.commit()


async def log_collection_with_user(
    clan_id, user_id, action_type: str, amount: int, description: str
) -> None:
    SQL_TREASURY_LOG = """
        INSERT INTO clan_treasury_log (clan_id, user_id, action_type, amount, description)
        VALUES (?, ?, ?, ?, ?)
    """

    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            SQL_TREASURY_LOG, (clan_id, user_id, action_type, amount, description)
        )
        await db.commit()


async def count_players(regular_only: bool = True, unbanned_only: bool = False) -> int:
    SQL_COUNT_PLAYERS = "SELECT COUNT(*) FROM players"
    # TODO: Better approach?
    if regular_only or unbanned_only:
        SQL_COUNT_PLAYERS += " WHERE "
        if regular_only:
            SQL_COUNT_PLAYERS += "admin_level = 0 "
        if unbanned_only and regular_only:
            SQL_COUNT_PLAYERS += " AND "
        if unbanned_only:
            SQL_COUNT_PLAYERS += "is_banned = 0 "

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL_COUNT_PLAYERS) as cur:
            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


async def count_banned_players() -> int:
    SQL_COUNT_BANNED = "SELECT COUNT(*) FROM players WHERE is_banned = 1"
    # TODO: Better approach?

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL_COUNT_BANNED) as cur:
            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


async def count_admins() -> int:
    SQL_COUNT_BANNED = "SELECT COUNT(*) FROM players WHERE admin_level > 0"

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL_COUNT_BANNED) as cur:
            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


async def count_clans() -> int:
    SQL_COUNT_CLANS = "SELECT COUNT(*) FROM clans"

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL_COUNT_CLANS) as cur:
            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


async def count_total_balance() -> int:
    SQL_COUNT_BALANCE = "SELECT SUM(balance) FROM players WHERE admin_level = 0"

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL_COUNT_BALANCE) as cur:
            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


# TODO: Add overloads
async def count_promo_uses(code: str, limit: int = 0):
    SQL = "SELECT COUNT(*) FROM promo_uses WHERE promo_code = ?"

    if limit > 0:
        SQL += f" LIMIT {limit}"

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL, (code,)) as cur:
            if limit > 0:
                result = await cur.fetchall()
                return result

            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


async def sum_promo_uses() -> int:
    SQL = "SELECT SUM(uses_total - uses_left) FROM promo_codes"

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL) as cur:
            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


async def get_recent_players(limit: int = 5):
    SQL = "SELECT username, created_at FROM players ORDER BY created_at DESC LIMIT ?"

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL, (limit,)) as cur:
            return await cur.fetchall()


async def sum_column(table: str, column: str) -> int:
    SQL = f"SELECT SUM({column}) FROM {table}"

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL) as cur:
            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


async def count_table_rows(table: str) -> int:
    SQL = f"SELECT COUNT(*) FROM {table}"

    async with aiosqlite.connect(settings.database_path) as db:
        async with db.execute(SQL) as cur:
            result = await cur.fetchone()
            return 0 if not result else 0 if not result[0] else result[0]


async def reset_all() -> None:
    async with aiosqlite.connect(settings.database_path) as db:
        # Удаляем обычных игроков
        await db.execute("DELETE FROM players WHERE admin_level = 0")

        # Удаляем кланы (автоматически удалятся из-за внешних ключей)
        await db.execute("DELETE FROM clans")

        # Очищаем связанные таблицы
        await db.execute("DELETE FROM transactions")
        await db.execute("DELETE FROM dumbbell_uses")
        await db.execute("DELETE FROM promo_uses")
        await db.execute("DELETE FROM clan_members")
        await db.execute("DELETE FROM clan_treasury_log")
        await db.execute("DELETE FROM clan_invites")

        await db.commit()
