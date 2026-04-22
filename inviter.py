"""
Telegram Inviter - Инвайт участников в группу через несколько аккаунтов
"""
import asyncio
import csv
import os
import random
from datetime import datetime, timedelta
from telethon import TelegramClient, errors
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.types import InputPeerUser
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')
TARGET_GROUP_ID = os.getenv('TARGET_GROUP_ID', '')

class TelegramInviter:
    def __init__(self):
        if not API_ID or not API_HASH or not PHONE:
            raise ValueError("Необходимо настроить API_ID, API_HASH и PHONE в .env файле")
        
        self.client = TelegramClient('inviter_session', API_ID, API_HASH)
        self.success_count = 0
        self.error_count = 0
        self.flood_wait_count = 0
    
    async def start(self):
        await self.client.start(phone=PHONE)
        print(f"✓ Авторизация успешна: {PHONE}")
    
    async def add_members(self, members_file, target_group, delay_range=(30, 60)):
        """
        Добавление участников в группу
        
        Args:
            members_file: CSV файл со списком участников (из parser.py)
            target_group: username или ID целевой группы
            delay_range: диапазон задержки между добавлениями (мин, макс) в секундах
        """
        print(f"Загрузка участников из файла: {members_file}")
        
        if not os.path.exists(members_file):
            print(f"❌ Файл {members_file} не найден")
            return
        
        members = []
        with open(members_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['id']:  # Пропускаем пустые строки
                    members.append(row)
        
        if not members:
            print("❌ Нет участников для добавления")
            return
        
        print(f"Найдено {len(members)} участников для добавления")
        
        try:
            entity = await self.client.get_entity(target_group)
            print(f"✓ Целевая группа найдена: {entity.title}")
        except Exception as e:
            print(f"❌ Ошибка при поиске целевой группы: {e}")
            return
        
        print(f"\nНачинаю инвайт участников...")
        print(f"Задержка между добавлениями: {delay_range[0]}-{delay_range[1]} сек")
        print("-" * 60)
        
        for i, member in enumerate(members, 1):
            try:
                user_id = int(member['id'])
                username = member.get('username', '')
                
                # Пропускаем пользователей без username (их нельзя добавить через инвайт)
                if not username:
                    print(f"[{i}/{len(members)}] Пропущено: нет username (ID: {user_id})")
                    continue
                
                # Получаем объект пользователя
                try:
                    user = await self.client.get_entity(username)
                except ValueError:
                    print(f"[{i}/{len(members)}] Пропущено: пользователь @{username} не найден")
                    self.error_count += 1
                    continue
                
                # Попытка добавления в группу
                try:
                    await self.client(AddChatUserRequest(
                        chat_id=entity.id,
                        user_id=user.id,
                        fwd_limit=0
                    ))
                    
                    self.success_count += 1
                    print(f"[{i}/{len(members)}] ✓ Добавлен: @{username}")
                    
                except errors.FloodWaitError as e:
                    wait_time = e.seconds
                    self.flood_wait_count += 1
                    print(f"[{i}/{len(members)}] ⏳ FloodWait: ожидание {wait_time} секунд")
                    
                    # Ждем указанное время плюс случайная задержка
                    await asyncio.sleep(wait_time + random.randint(5, 10))
                    
                    # Повторная попытка
                    try:
                        await self.client(AddChatUserRequest(
                            chat_id=entity.id,
                            user_id=user.id,
                            fwd_limit=0
                        ))
                        self.success_count += 1
                        print(f"[{i}/{len(members)}] ✓ Добавлен после ожидания: @{username}")
                    except Exception as retry_error:
                        print(f"[{i}/{len(members)}] ❌ Ошибка после ожидания: {retry_error}")
                        self.error_count += 1
                    
                except errors.UserPrivacyRestrictedError:
                    print(f"[{i}/{len(members)}] ❌ Приватность: @{username} запретил добавление")
                    self.error_count += 1
                    
                except errors.UserNotMutualContactError:
                    print(f"[{i}/{len(members)}] ❌ Не контакт: @{username} не является контактом")
                    self.error_count += 1
                    
                except errors.UserAlreadyParticipantError:
                    print(f"[{i}/{len(members)}] ⚠ Уже участник: @{username}")
                    
                except errors.UserIsBotError:
                    print(f"[{i}/{len(members)}] ❌ Бот: @{username} является ботом")
                    self.error_count += 1
                    
                except Exception as e:
                    print(f"[{i}/{len(members)}] ❌ Ошибка: {e}")
                    self.error_count += 1
                
                # Случайная задержка между добавлениями
                if i < len(members):
                    delay = random.randint(delay_range[0], delay_range[1])
                    print(f"   → Ожидание {delay} сек...")
                    await asyncio.sleep(delay)
                
            except KeyboardInterrupt:
                print("\n\n⚠ Прервано пользователем")
                break
            except Exception as e:
                print(f"[{i}/{len(members)}] ❌ Критическая ошибка: {e}")
                self.error_count += 1
                continue
        
        # Итоговая статистика
        print("\n" + "=" * 60)
        print("ИТОГИ:")
        print(f"✓ Успешно добавлено: {self.success_count}")
        print(f"❌ Ошибок: {self.error_count}")
        print(f"⏳ FloodWait ожиданий: {self.flood_wait_count}")
        print(f"📊 Всего обработано: {self.success_count + self.error_count}")
        print("=" * 60)
    
    async def close(self):
        await self.client.disconnect()


async def main():
    print("Telegram Inviter - Инвайт участников в группу")
    print("=" * 60)
    
    inviter = TelegramInviter()
    
    try:
        await inviter.start()
        
        # Запрос файла с участниками
        members_file = input("\nВведите путь к CSV файлу с участниками (по умолчанию parsed_members.csv): ").strip()
        if not members_file:
            members_file = 'parsed_members.csv'
        
        # Запрос целевой группы
        target_group = input("Введите username или ID целевой группы: ").strip()
        if not target_group:
            if TARGET_GROUP_ID:
                target_group = TARGET_GROUP_ID
                print(f"Используется группа из .env: {target_group}")
            else:
                print("❌ Целевая группа не указана. Выход.")
                return
        
        # Запрос диапазона задержки
        delay_input = input("Диапазон задержки в секундах (мин-макс, по умолчанию 30-60): ").strip()
        if delay_input and '-' in delay_input:
            try:
                min_delay, max_delay = map(int, delay_input.split('-'))
                delay_range = (min_delay, max_delay)
            except ValueError:
                delay_range = (30, 60)
        else:
            delay_range = (30, 60)
        
        # Запуск инвайта
        await inviter.add_members(members_file, target_group, delay_range)
        
        print("\n✓ Инвайт завершен!")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
    finally:
        await inviter.close()


if __name__ == '__main__':
    asyncio.run(main())
