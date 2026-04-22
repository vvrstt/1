import asyncio
import os
import csv
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch, UserStatusOffline, UserStatusOnline, UserStatusRecently, UserStatusLastMonth, UserStatusLastWeek
from database import DB_NAME, init_db
from manager import get_all_accounts, get_all_proxies

# Инициализация БД при старте
init_db()

def parse_last_seen(status):
    """Преобразует статус Telegram в дату последнего посещения."""
    if isinstance(status, UserStatusOnline):
        return datetime.now()  # Онлайн сейчас
    elif isinstance(status, UserStatusOffline):
        return status.was_online
    elif isinstance(status, UserStatusRecently):
        return datetime.now() - timedelta(days=1)  # Примерно вчера
    elif isinstance(status, UserStatusLastWeek):
        return datetime.now() - timedelta(weeks=1)
    elif isinstance(status, UserStatusLastMonth):
        return datetime.now() - timedelta(days=30)
    else:
        return None  # Статус скрыт или неизвестен

async def parse_members():
    """Парсинг участников группы/канала с сортировкой по активности."""
    accounts = get_all_accounts()
    if not accounts:
        print("❌ Нет добавленных аккаунтов. Запустите manager.py для добавления.")
        return
    
    proxies = get_all_proxies()
    
    print("\n📋 Доступные аккаунты:")
    for i, (phone, api_id, api_hash, session) in enumerate(accounts, 1):
        print(f"{i}. {phone}")
    
    try:
        acc_idx = int(input("\nВыберите номер аккаунта для парсинга: ")) - 1
        if acc_idx < 0 or acc_idx >= len(accounts):
            print("❌ Неверный номер аккаунта.")
            return
    except ValueError:
        print("❌ Введите число.")
        return
    
    phone, api_id, api_hash, session_name = accounts[acc_idx]
    
    # Настройка прокси (если есть)
    proxy = None
    if proxies:
        use_proxy = input("Использовать прокси? (y/n): ").strip().lower()
        if use_proxy == 'y':
            print("\n📋 Доступные прокси:")
            for i, (ptype, ip, port, user, pwd) in enumerate(proxies, 1):
                print(f"{i}. {ptype.upper()} | {ip}:{port}")
            try:
                proxy_idx = int(input("Выберите номер прокси: ")) - 1
                if 0 <= proxy_idx < len(proxies):
                    ptype, ip, port, user, pwd = proxies[proxy_idx]
                    if ptype == 'socks5':
                        proxy = {
                            'proxy_type': 'socks5',
                            'addr': ip,
                            'port': port,
                            'username': user,
                            'password': pwd
                        }
                    elif ptype == 'http':
                        proxy = {
                            'proxy_type': 'http',
                            'addr': ip,
                            'port': port,
                            'username': user,
                            'password': pwd
                        }
                    elif ptype == 'mtproto':
                        proxy = {
                            'proxy_type': 'mtproto',
                            'addr': ip,
                            'port': port,
                            'secret': pwd or ''
                        }
            except (ValueError, IndexError):
                print("❌ Неверный выбор прокси. Работа без прокси.")
    
    target_link = input("Введите ссылку на группу/канал для парсинга: ").strip()
    if not target_link:
        print("❌ Ссылка обязательна.")
        return
    
    client = TelegramClient(session_name, int(api_id), api_hash, proxy=proxy)
    
    try:
        await client.start(phone)
        print(f"✅ Аккаунт {phone} авторизован.")
        
        entity = await client.get_entity(target_link)
        print(f"🎯 Парсинг участников из: {entity.title}")
        
        all_members = []
        offset = 0
        limit = 100
        
        while True:
            participants = await client(GetParticipantsRequest(
                entity, ChannelParticipantsSearch(''), offset, limit, hash=0
            ))
            if not participants.users:
                break
            
            for user in participants.users:
                if user.deleted:
                    continue
                    
                last_seen = parse_last_seen(user.status)
                all_members.append({
                    'user_id': user.id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'phone': user.phone or '',
                    'last_seen': last_seen,
                    'source_group': entity.title
                })
            
            offset += limit
            print(f"📊 Спаршено: {len(all_members)} участников...")
            
            if len(participants.users) < limit:
                break
        
        # Сортировка по времени последней активности (от новых к старым)
        all_members.sort(key=lambda x: x['last_seen'] or datetime.min, reverse=True)
        
        # Сохранение в CSV
        filename = f"parsed_users_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['user_id', 'username', 'first_name', 'last_name', 'phone', 'last_seen', 'source_group'])
            writer.writeheader()
            for member in all_members:
                row = member.copy()
                row['last_seen'] = member['last_seen'].isoformat() if member['last_seen'] else 'unknown'
                writer.writerow(row)
        
        print(f"\n✅ Парсинг завершен! Сохранено {len(all_members)} участников.")
        print(f"📁 Файл: {filename}")
        print("📊 Участники отсортированы по времени последней активности (от самых активных к наименее активным).")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    print("=== TELEGRAM PARSER ===")
    print("Парсер участников с сортировкой по активности")
    asyncio.run(parse_members())
