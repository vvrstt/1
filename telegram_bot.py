"""
Telegram Inviter & Parser

Функционал:
1. Парсер участников из групп/каналов с сортировкой по времени последней активности
2. Инвайтер для добавления участников в целевую группу через аккаунты Telegram

Требования:
- Python 3.8+
- Telethon
- Аккаунты в формате сессий (.session) или через API ID/Hash

Установка зависимостей:
    pip install telethon python-dotenv

Настройка:
    Скопируйте .env.example в .env и заполните данные
"""

import asyncio
import os
import csv
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from telethon import TelegramClient
from telethon.tl.types import User, ChannelParticipantsRecent
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types.messages import ChannelParticipants
from telethon.errors import FloodWaitError, PeerFloodError, UserPrivacyRestrictedError
from telethon.tl.functions.messages import AddChatUserRequest, ImportChatInviteRequest
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")
SESSION_NAME = os.getenv("SESSION_NAME", "my_session")

# Пути к файлам
ACCOUNTS_FILE = "accounts.csv"  # Файл со списком аккаунтов (phone, api_id, api_hash, session_file)
PARSED_USERS_FILE = "parsed_users.csv"  # Файл для сохранения спарсенных пользователей


class TelegramParser:
    """Парсер участников телеграм групп/каналов"""
    
    def __init__(self, api_id: int, api_hash: str, phone: str, session_name: str = "parser_session"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.client: Optional[TelegramClient] = None
    
    async def start(self):
        """Инициализация клиента"""
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await self.client.start(phone=self.phone)
        print(f"[Parser] Авторизация успешна: {self.phone}")
    
    async def stop(self):
        """Закрытие клиента"""
        if self.client:
            await self.client.disconnect()
    
    async def parse_members(self, chat_link: str, limit: int = 1000) -> List[Dict]:
        """
        Парсинг участников группы/канала
        
        Args:
            chat_link: Ссылка на группу/канал или username
            limit: Максимальное количество участников для парсинга
            
        Returns:
            Список словарей с информацией о пользователях
        """
        if not self.client:
            raise Exception("Клиент не инициализирован. Вызовите start()")
        
        participants = []
        
        try:
            # Получаем информацию о чате
            entity = await self.client.get_entity(chat_link)
            print(f"[Parser] Парсинг участников из: {entity.title}")
            
            # Запрашиваем участников
            offset = 0
            batch_size = 100
            
            while len(participants) < limit:
                result = await self.client(GetParticipantsRequest(
                    channel=entity,
                    filter=ChannelParticipantsRecent(),
                    offset=offset,
                    limit=batch_size,
                    hash=0
                ))
                
                if not result.users:
                    break
                
                for user in result.users:
                    if isinstance(user, User) and not user.bot and not user.deleted:
                        # Получаем время последней активности
                        last_seen = None
                        status_emoji = "unknown"
                        
                        if hasattr(user, 'status') and user.status:
                            status_type = type(user.status).__name__
                            
                            if status_type == 'UserStatusOnline':
                                last_seen = datetime.now()
                                status_emoji = "🟢 online"
                            elif status_type == 'UserStatusOffline':
                                last_seen = user.status.was_online
                                status_emoji = "⚫ offline"
                            elif status_type == 'UserStatusRecently':
                                last_seen = datetime.now()  # Примерное время
                                status_emoji = "🟡 recently"
                            elif status_type == 'UserStatusLastWeek':
                                last_seen = datetime.now()  # Примерное время
                                status_emoji = "🟠 last week"
                            elif status_type == 'UserStatusLastMonth':
                                last_seen = datetime.now()  # Примерное время
                                status_emoji = "🔴 last month"
                        
                        participant = {
                            'user_id': user.id,
                            'username': user.username or '',
                            'first_name': user.first_name or '',
                            'last_name': user.last_name or '',
                            'phone': user.phone or '',
                            'last_seen': last_seen,
                            'status': status_emoji,
                            'is_bot': user.bot,
                            'is_deleted': user.deleted
                        }
                        participants.append(participant)
                
                offset += batch_size
                
                if len(result.users) < batch_size:
                    break
                
                print(f"[Parser] Спарсено: {len(participants)} участников...")
                
        except Exception as e:
            print(f"[Parser] Ошибка при парсинге: {e}")
        
        return participants
    
    def sort_by_activity(self, participants: List[Dict], reverse: bool = True) -> List[Dict]:
        """
        Сортировка участников по времени последней активности
        
        Args:
            participants: Список участников
            reverse: True - от новых к старым, False - наоборот
            
        Returns:
            Отсортированный список
        """
        def get_sort_key(user):
            if user['last_seen'] is None:
                return datetime.min
            return user['last_seen']
        
        sorted_list = sorted(participants, key=get_sort_key, reverse=reverse)
        return sorted_list
    
    async def save_to_csv(self, participants: List[Dict], filename: str = PARSED_USERS_FILE):
        """Сохранение результатов в CSV"""
        if not participants:
            print("[Parser] Нет данных для сохранения")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['user_id', 'username', 'first_name', 'last_name', 
                         'phone', 'last_seen', 'status', 'is_bot', 'is_deleted']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for user in participants:
                row = user.copy()
                if row['last_seen']:
                    row['last_seen'] = row['last_seen'].strftime('%Y-%m-%d %H:%M:%S')
                writer.writerow(row)
        
        print(f"[Parser] Сохранено {len(participants)} пользователей в {filename}")


class TelegramInviter:
    """Инвайтер для добавления участников в группу"""
    
    def __init__(self, accounts: List[Dict]):
        """
        Args:
            accounts: Список аккаунтов в формате:
                     [{'phone': '+7xxx', 'api_id': xxx, 'api_hash': 'xxx', 'session': 'file.session'}, ...]
        """
        self.accounts = accounts
        self.clients: List[Tuple[TelegramClient, Dict]] = []
    
    async def add_account(self, phone: str, api_id: int, api_hash: str, session_name: str):
        """Добавление аккаунта в пул"""
        account = {
            'phone': phone,
            'api_id': api_id,
            'api_hash': api_hash,
            'session': session_name
        }
        self.accounts.append(account)
    
    async def initialize_accounts(self):
        """Инициализация всех аккаунтов"""
        for acc in self.accounts:
            try:
                client = TelegramClient(acc['session'], acc['api_id'], acc['api_hash'])
                await client.connect()
                
                if not await client.is_user_authorized():
                    print(f"[Inviter] Аккаунт {acc['phone']} не авторизован. Требуется вход.")
                    await client.start(phone=acc['phone'])
                
                me = await client.get_me()
                print(f"[Inviter] Аккаунт готов: @{me.username} ({me.first_name})")
                
                self.clients.append((client, acc))
                
            except Exception as e:
                print(f"[Inviter] Ошибка инициализации аккаунта {acc['phone']}: {e}")
    
    async def close_accounts(self):
        """Закрытие всех соединений"""
        for client, _ in self.clients:
            await client.disconnect()
        self.clients.clear()
    
    async def invite_users(self, target_chat: str, users: List[Dict], 
                          delay_between_invites: float = 30.0,
                          max_invites_per_account: int = 50) -> Dict:
        """
        Приглашение пользователей в целевую группу
        
        Args:
            target_chat: Username или ссылка на целевую группу
            users: Список пользователей для инвайта (с полями user_id, username)
            delay_between_invites: Задержка между приглашениями (сек)
            max_invites_per_account: Максимум приглашений на один аккаунт
            
        Returns:
            Статистика инвайта
        """
        stats = {
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        if not self.clients:
            print("[Inviter] Нет авторизованных аккаунтов")
            return stats
        
        try:
            target_entity = await self.clients[0][0].get_entity(target_chat)
            print(f"[Inviter] Целевая группа: {target_entity.title}")
        except Exception as e:
            print(f"[Inviter] Ошибка получения целевой группы: {e}")
            return stats
        
        current_account_idx = 0
        invites_per_account = {i: 0 for i in range(len(self.clients))}
        
        for user in users:
            # Проверка лимита на аккаунт
            if invites_per_account[current_account_idx] >= max_invites_per_account:
                current_account_idx = (current_account_idx + 1) % len(self.clients)
                if invites_per_account[current_account_idx] >= max_invites_per_account:
                    print("[Inviter] Все аккаунты исчерпали лимит приглашений")
                    break
            
            client, acc = self.clients[current_account_idx]
            
            try:
                # Попытка пригласить по user_id
                if user.get('user_id'):
                    await client(AddChatUserRequest(
                        chat_id=target_entity.id,
                        user_id=user['user_id'],
                        fwd_limit=0
                    ))
                # Или по username
                elif user.get('username'):
                    user_entity = await client.get_entity(user['username'])
                    await client(AddChatUserRequest(
                        chat_id=target_entity.id,
                        user_id=user_entity.id,
                        fwd_limit=0
                    ))
                else:
                    print(f"[Inviter] Пропуск: нет user_id или username")
                    stats['failed'] += 1
                    continue
                
                stats['success'] += 1
                invites_per_account[current_account_idx] += 1
                print(f"[Inviter] Успешно: @{user.get('username', user.get('user_id'))} "
                      f"(аккаунт: {acc['phone']}, всего: {stats['success']})")
                
            except FloodWaitError as e:
                wait_time = e.seconds
                print(f"[Inviter] FloodWait: ожидание {wait_time} сек")
                await asyncio.sleep(wait_time)
                continue
                
            except UserPrivacyRestrictedError:
                stats['failed'] += 1
                stats['errors'].append(f"Privacy restricted: {user.get('username')}")
                print(f"[Inviter] Приватность: @{user.get('username')} нельзя пригласить")
                
            except PeerFloodError:
                print(f"[Inviter] SPAM блок на аккаунте {acc['phone']}")
                current_account_idx = (current_account_idx + 1) % len(self.clients)
                continue
                
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"{type(e).__name__}: {user.get('username')}")
                print(f"[Inviter] Ошибка: {e}")
            
            # Переход к следующему аккаунту для распределения нагрузки
            current_account_idx = (current_account_idx + 1) % len(self.clients)
            
            # Задержка между приглашениями
            await asyncio.sleep(delay_between_invites)
        
        return stats


async def main_parser_example():
    """Пример использования парсера"""
    parser = TelegramParser(API_ID, API_HASH, PHONE, SESSION_NAME)
    
    try:
        await parser.start()
        
        # Парсинг участников из группы
        chat_link = input("Введите ссылку на группу для парсинга: ")
        limit = int(input("Максимальное количество участников (по умолчанию 1000): ") or "1000")
        
        participants = await parser.parse_members(chat_link, limit)
        print(f"\n[Parser] Всего найдено: {len(participants)} активных участников")
        
        # Сортировка по активности
        sorted_participants = parser.sort_by_activity(participants, reverse=True)
        
        print("\n=== Топ-10 по активности ===")
        for i, user in enumerate(sorted_participants[:10], 1):
            seen = user['last_seen'].strftime('%Y-%m-%d %H:%M:%S') if user['last_seen'] else 'N/A'
            print(f"{i}. @{user['username'] or user['user_id']} - {seen} {user['status']}")
        
        # Сохранение в CSV
        await parser.save_to_csv(sorted_participants)
        
    finally:
        await parser.stop()


async def main_inviter_example():
    """Пример использования инвайтера"""
    # Загрузка аккаунтов из файла или создание списка
    accounts = []
    
    # Пример: добавление аккаунтов вручную
    # accounts = [
    #     {'phone': '+79991234567', 'api_id': 12345, 'api_hash': 'abc123', 'session': 'account1.session'},
    #     {'phone': '+79997654321', 'api_id': 67890, 'api_hash': 'def456', 'session': 'account2.session'},
    # ]
    
    inviter = TelegramInviter(accounts)
    
    try:
        await inviter.initialize_accounts()
        
        if not inviter.clients:
            print("[Inviter] Добавьте хотя бы один аккаунт")
            return
        
        # Загрузка пользователей из CSV
        users_to_invite = []
        if os.path.exists(PARSED_USERS_FILE):
            with open(PARSED_USERS_FILE, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    users_to_invite.append({
                        'user_id': int(row['user_id']) if row['user_id'] else None,
                        'username': row['username'] or None
                    })
            print(f"[Inviter] Загружено {len(users_to_invite)} пользователей из {PARSED_USERS_FILE}")
        else:
            print(f"[Inviter] Файл {PARSED_USERS_FILE} не найден. Сначала запустите парсер.")
            return
        
        target_chat = input("Введите username целевой группы (без @): ")
        
        stats = await inviter.invite_users(
            target_chat=f"@{target_chat}",
            users=users_to_invite,
            delay_between_invites=30.0,
            max_invites_per_account=50
        )
        
        print(f"\n=== Результаты инвайта ===")
        print(f"Успешно: {stats['success']}")
        print(f"Неудачно: {stats['failed']}")
        if stats['errors']:
            print("Ошибки:")
            for err in stats['errors'][:10]:
                print(f"  - {err}")
    
    finally:
        await inviter.close_accounts()


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════╗
║         Telegram Inviter & Parser                         ║
║  Выбор режима:                                            ║
║    1 - Парсер участников с сортировкой по активности      ║
║    2 - Инвайтер пользователей в группу                    ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    mode = input("Выберите режим (1 или 2): ").strip()
    
    if mode == "1":
        asyncio.run(main_parser_example())
    elif mode == "2":
        asyncio.run(main_inviter_example())
    else:
        print("Неверный выбор режима")
