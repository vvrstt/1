import asyncio
import csv
import random
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest, GetParticipantsRequest
from telethon.tl.types import InputUser, ChannelParticipantsSearch
from database import DB_NAME, init_db
from manager import get_all_accounts, get_all_proxies

# Инициализация БД при старте
init_db()

async def invite_users():
    """Инвайт пользователей в группу через выбранные аккаунты."""
    accounts = get_all_accounts()
    if not accounts:
        print("❌ Нет добавленных аккаунтов. Запустите manager.py для добавления.")
        return
    
    proxies = get_all_proxies()
    
    # Выбор файла с пользователями
    print("\n📂 Доступные файлы с пользователями:")
    import os
    csv_files = [f for f in os.listdir('.') if f.startswith('parsed_users_') and f.endswith('.csv')]
    if not csv_files:
        print("❌ Нет файлов parsed_users_*.csv. Сначала запустите парсер.")
        return
    
    for i, f in enumerate(csv_files, 1):
        print(f"{i}. {f}")
    
    try:
        file_idx = int(input("\nВыберите номер файла: ")) - 1
        if file_idx < 0 or file_idx >= len(csv_files):
            print("❌ Неверный номер.")
            return
        csv_file = csv_files[file_idx]
    except ValueError:
        print("❌ Введите число.")
        return
    
    # Загрузка пользователей из CSV
    users_to_invite = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['user_id']:
                users_to_invite.append({
                    'user_id': int(row['user_id']),
                    'username': row['username']
                })
    
    print(f"📊 Загружено {len(users_to_invite)} пользователей из {csv_file}")
    
    # Выбор аккаунтов для инвайта
    print("\n📋 Доступные аккаунты:")
    for i, (phone, api_id, api_hash, session) in enumerate(accounts, 1):
        print(f"{i}. {phone}")
    
    print("\nВыберите аккаунты для инвайта (через запятую, например: 1,2,3 или все - нажмите Enter)")
    acc_input = input("Номера аккаунтов: ").strip()
    
    if acc_input:
        try:
            selected_indices = [int(x.strip()) - 1 for x in acc_input.split(',')]
            selected_accounts = [accounts[i] for i in selected_indices if 0 <= i < len(accounts)]
        except (ValueError, IndexError):
            print("❌ Неверный формат. Будут использованы все аккаунты.")
            selected_accounts = accounts
    else:
        selected_accounts = accounts
    
    if not selected_accounts:
        print("❌ Нет выбранных аккаунтов.")
        return
    
    target_link = input("\nВведите ссылку на группу, куда добавлять пользователей: ").strip()
    if not target_link:
        print("❌ Ссылка обязательна.")
        return
    
    # Настройки инвайта
    try:
        delay_min = int(input("Минимальная задержка между действиями (сек): ") or "5")
        delay_max = int(input("Максимальная задержка между действиями (сек): ") or "10")
        max_per_account = int(input("Максимум пользователей на аккаунт (0 = без лимита): ") or "50")
    except ValueError:
        delay_min, delay_max, max_per_account = 5, 10, 50
    
    success_count = 0
    error_count = 0
    user_index = 0
    
    for acc_idx, (phone, api_id, api_hash, session_name) in enumerate(selected_accounts):
        print(f"\n{'='*60}")
        print(f"🔄 Работа с аккаунтом: {phone}")
        print(f"{'='*60}")
        
        # Настройка прокси
        proxy = None
        if proxies and len(proxies) >= acc_idx + 1:
            ptype, ip, port, user, pwd = proxies[acc_idx % len(proxies)]
            if ptype == 'socks5':
                proxy = {'proxy_type': 'socks5', 'addr': ip, 'port': port, 'username': user, 'password': pwd}
            elif ptype == 'http':
                proxy = {'proxy_type': 'http', 'addr': ip, 'port': port, 'username': user, 'password': pwd}
            elif ptype == 'mtproto':
                proxy = {'proxy_type': 'mtproto', 'addr': ip, 'port': port, 'secret': pwd or ''}
        
        client = TelegramClient(session_name, int(api_id), api_hash, proxy=proxy)
        
        try:
            await client.start(phone)
            print(f"✅ Аккаунт {phone} авторизован.")
            
            entity = await client.get_entity(target_link)
            print(f"🎯 Целевая группа: {entity.title}")
            
            count_for_account = 0
            limit_reached = False
            
            while user_index < len(users_to_invite):
                if max_per_account > 0 and count_for_account >= max_per_account:
                    print(f"⚠️ Достигнут лимит {max_per_account} для этого аккаунта.")
                    limit_reached = True
                    break
                
                user_data = users_to_invite[user_index]
                user_index += 1
                
                try:
                    user = await client.get_entity(user_data['user_id'])
                    await client(InviteToChannelRequest(entity, [user]))
                    
                    success_count += 1
                    count_for_account += 1
                    print(f"✅ Добавлен: {user_data['username'] or user_data['user_id']} ({success_count})")
                    
                except Exception as e:
                    error_count += 1
                    err_msg = str(e)
                    if "FLOOD_WAIT" in err_msg:
                        print(f"⏸️ FLOOD_WAIT! Пауза 10 минут...")
                        await asyncio.sleep(600)
                        continue
                    elif "USER_PRIVACY_RESTRICTED" in err_msg:
                        print(f"⚠️ Приватность пользователя ограничена.")
                    elif "USER_ALREADY_PARTICIPANT" in err_msg:
                        print(f"ℹ️ Пользователь уже в группе.")
                    else:
                        print(f"❌ Ошибка: {err_msg}")
                
                # Случайная задержка
                delay = random.uniform(delay_min, delay_max)
                await asyncio.sleep(delay)
            
            if limit_reached:
                continue
                
        except Exception as e:
            print(f"❌ Ошибка с аккаунтом {phone}: {e}")
        finally:
            await client.disconnect()
    
    print(f"\n{'='*60}")
    print(f"📊 ИТОГИ:")
    print(f"✅ Успешно: {success_count}")
    print(f"❌ Ошибки: {error_count}")
    print(f"📁 Файл: {csv_file}")
    print(f"{'='*60}")

if __name__ == "__main__":
    print("=== TELEGRAM INVITER ===")
    print("Инвайт пользователей из спаршенного файла")
    asyncio.run(invite_users())
