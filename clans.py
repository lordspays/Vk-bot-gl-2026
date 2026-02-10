from typing import Any, Dict

from bot.core.config import settings
from bot.db import (
    add_power,
    add_treasury,
    get_clan_by_id,
    get_player,
    get_player_clan,
    get_players_with_businesses,
    increment_total_lifts,
    log_collection,
    log_collection_with_user,
    log_dumbbell_use,
    update_dumbbell_use_time,
    update_player_balance,
)

# ==============================
# ОБНОВЛЕННАЯ СИСТЕМА КЛАНОВ
# ==============================

def get_clan_bonuses(clan_level: int) -> Dict[str, Any]:
    """Получение бонусов клана по уровню"""
    # Базовые бонусы: 5% к бизнесам и +1 монета за поднятие на 1 уровне
    business_bonus_percent = 5 + (clan_level - 1)  # 5% + (уровень-1)%
    lift_bonus_coins = 1 + (clan_level - 1)        # 1 + (уровень-1)
    
    return {
        'business_bonus_percent': business_bonus_percent,
        'lift_bonus_coins': lift_bonus_coins,
        'business_bonus_multiplier': 1 + (business_bonus_percent / 100)  # Множитель для расчетов
    }


async def calculate_business_income_with_clan(player: Dict[str, Any], business_id: int, base_income: int) -> Dict[str, Any]:
    """Расчет дохода от бизнеса с учетом клана (НОВАЯ СИСТЕМА)"""
    clan = await get_player_clan(player['user_id'])
    
    if not clan:
        # Без клана - обычный доход
        return {
            'player_income': base_income,
            'clan_income': 0,
            'total_income': base_income
        }
    
    # Получаем бонусы клана
    clan_bonuses = get_clan_bonuses(clan['level'])
    
    # НОВАЯ СИСТЕМА: процент идет в казну клана
    clan_bonus_amount = base_income * clan_bonuses['business_bonus_percent'] / 100
    
    # Игрок получает только базовый доход
    player_income = base_income
    
    # Клан получает процент в казну
    clan_income = clan_bonus_amount
    
    return {
        'player_income': player_income,
        'clan_income': clan_income,
        'total_income': player_income + clan_income,
        'business_bonus_percent': clan_bonuses['business_bonus_percent'],
        'clan_bonus_amount': clan_bonus_amount
    }


async def calculate_dumbbell_income_with_clan(player: Dict[str, Any], base_income: int, power_gained: int) -> Dict[str, Any]:
    """Расчет дохода от поднятия гантели с учетом клана (НОВАЯ СИСТЕМА)"""
    clan = await get_player_clan(player['user_id'])
    
    if not clan:
        # Без клана - обычный доход
        return {
            'player_income': base_income,
            'clan_income': 0,
            'total_income': base_income,
            'power_gained': power_gained,
            'clan_bonus': 0
        }
    
    # Получаем бонусы клана
    clan_bonuses = get_clan_bonuses(clan['level'])
    
    # Определяем дополнительный бонус в казну клана (зависит от уровня гантели)
    additional_clan_bonus = 0
    if player['dumbbell_level'] <= 4:
        additional_clan_bonus = 1
    elif player['dumbbell_level'] <= 9:
        additional_clan_bonus = 2
    elif player['dumbbell_level'] <= 14:
        additional_clan_bonus = 3
    else:
        additional_clan_bonus = 4
    
    # НОВАЯ СИСТЕМА:
    # 1. Игрок получает: базовый доход + бонус клана
    player_income = base_income + clan_bonuses['lift_bonus_coins']
    
    # 2. Клан получает в казну: бонус клана + дополнительный бонус
    clan_income = clan_bonuses['lift_bonus_coins'] + additional_clan_bonus
    
    return {
        'player_income': player_income,
        'clan_income': clan_income,
        'total_income': player_income + clan_income,
        'power_gained': power_gained,
        'clan_bonus_coins': clan_bonuses['lift_bonus_coins'],
        'additional_clan_bonus': additional_clan_bonus
    }


async def collect_clan_income_hourly():
    """Ежечасный сбор доходов с бизнесов в казну кланов (НОВАЯ СИСТЕМА)"""
    # Получаем всех игроков с бизнесами
    players = await get_players_with_businesses()
    
    total_collected = 0
    clan_collections = {}
    
    for player in players:
        user_id = player[0]
        clan_id = player[4]
        
        if not clan_id:
            continue
        
        # Рассчитываем общий доход от всех бизнесов игрока
        total_business_income = 0
        
        # Бизнес 1
        if player[1] > 0:
            business_income = BUSINESSES[1]['base_income'] + (player[1] - 1) * BUSINESSES[1]['income_increase']
            total_business_income += business_income
        
        # Бизнес 2
        if player[2] > 0:
            business_income = BUSINESSES[2]['base_income'] + (player[2] - 1) * BUSINESSES[2]['income_increase']
            total_business_income += business_income
        
        # Бизнес 3
        if player[3] > 0:
            business_income = BUSINESSES[3]['base_income'] + (player[3] - 1) * BUSINESSES[3]['income_increase']
            total_business_income += business_income
        
        if total_business_income > 0:
            # Получаем клан игрока
            clan = await get_clan_by_id(clan_id)
            if clan:
                clan_bonuses = get_clan_bonuses(clan['level'])
                
                # Процент от дохода идет в казну клана
                clan_income = total_business_income * clan_bonuses['business_bonus_percent'] / 100
                
                # Добавляем в сборы клана
                if clan_id not in clan_collections:
                    clan_collections[clan_id] = 0
                clan_collections[clan_id] += clan_income
                
                total_collected += clan_income
    
    # Зачисляем собранные средства в казну кланов
    for clan_id, amount in clan_collections.items():
        if amount > 0:
            # TODO: Both functions commit on every iteration; can be optimized
            await add_treasury(clan_id, int(amount))
            
            # Логируем сбор
            await log_collection(
                clan_id,
                'business_income',
                int(amount),
                'Ежечасный сбор с бизнесов участников'
            )
    
    #self.db.conn.commit()
    return total_collected


async def process_dumbbell_lift_with_clan(user_id: int) -> Dict[str, Any]:
    """Обработка поднятия гантели с учетом клана (НОВАЯ СИСТЕМА)"""
    player = await get_player(user_id)
    clan = await get_player_clan(user_id)
    
    if player.get('custom_income') is not None:
        base_income = player['custom_income']
        dumbbell_info = {'power_per_use': 1}  # Минимальная сила для кастомного дохода
    else:
        dumbbell_info = settings.DUMBBELL_LEVELS[player['dumbbell_level']]
        base_income = dumbbell_info['income_per_use']
    
    power_gained = dumbbell_info['power_per_use']
    
    # Рассчитываем доход с учетом клана
    income_calculation = await calculate_dumbbell_income_with_clan(player, base_income, power_gained)
    
    # Зачисляем доход игроку
    await update_player_balance(
        user_id,
        income_calculation['player_income'],
        'dumbbell_income',
        f'Подъем гантели {player["dumbbell_name"]} с бонусом клана'
    )
    
    # Зачисляем бонус в казну клана
    if clan and income_calculation['clan_income'] > 0:
        await add_treasury(
            clan['id'],
            income_calculation['clan_income'],
            True
        )
        
        # Логируем вклад в казну
        await log_collection_with_user(
            clan['id'],
            user_id,
            'lift_income',
            income_calculation['clan_income'], 
            f'Бонус от поднятия гантели игроком {player["username"]}'
        )
    
    # Обновляем время последнего поднятия и статистику
    await add_power(user_id, power_gained)
    await update_dumbbell_use_time(user_id)
    await increment_total_lifts(user_id)
    await log_dumbbell_use(user_id, player['dumbbell_level'], 
                           income_calculation['player_income'], power_gained)
    
    return income_calculation