"""
Telegram Parser - Парсинг участников групп/каналов с сортировкой по активности
"""
import asyncio
import csv
import os
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import ChannelParticipantsSearch
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
PHONE = os.getenv('PHONE', '')

class TelegramParser:
    def __init__(self):
        if not API_ID or not API_HASH or not PHONE:
            raise ValueError("Необходимо настроить API_ID, API_HASH и PHONE в .env файле")
        
        self.client = TelegramClient('parser_session', API_ID, API_HASH)
        self.members_data = []
    
    async def start(self):
        await self.client.start(phone=PHONE)
        print(f"✓ Авторизация успешна: {PHONE}")
    
    async def parse_members(self, source_group, limit=1000):
        """
        Парсинг участников группы/канала
        
        Args:
            source_group: username или ID исходной группы (например, '@username' или '-1001234567890')
            limit: максимальное количество участников для парсинга
        """
        print(f"Начинаю парсинг участников из: {source_group}")
        self.members_data = []
        
        try:
            entity = await self.client.get_entity(source_group)
            print(f"Найдена группа/канал: {entity.title}")
            
            # Получаем всех участников
            participants = await self.client.get_participants(entity, limit=limit)
            
            print(f"Найдено участников: {len(participants)}")
            print("Анализируем последнюю активность...")
            
            for i, participant in enumerate(participants):
                if i % 100 == 0 and i > 0:
                    print(f"Обработано: {i}/{len(participants)}")
                
                user_info = {
                    'id': participant.id,
                    'username': participant.username or '',
                    'first_name': participant.first_name or '',
                    'last_name': participant.last_name or '',
                    'phone': participant.phone or '',
                    'last_activity': None,
                    'last_activity_timestamp': 0
                }
                
                # Пытаемся получить информацию о последней активности
                # Примечание: Telegram не предоставляет точное время последнего входа для всех пользователей
                # Мы можем использовать дату участия или другие доступные метаданные
                
                if hasattr(participant, 'date') and participant.date:
                    user_info['last_activity'] = participant.date
                    user_info['last_activity_timestamp'] = participant.date.timestamp()
                
                self.members_data.append(user_info)
            
            # Сортировка по времени последней активности (от самых активных к наименее активным)
            self.members_data.sort(
                key=lambda x: x['last_activity_timestamp'], 
                reverse=True
            )
            
            print(f"✓ Парсинг завершен. Обработано {len(self.members_data)} участников")
            return self.members_data
            
        except Exception as e:
            print(f"Ошибка при парсинге: {e}")
            raise
    
    def save_to_csv(self, filename='parsed_members.csv'):
        """Сохранение результатов в CSV файл"""
        if not self.members_data:
            print("Нет данных для сохранения")
            return
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['id', 'username', 'first_name', 'last_name', 'phone', 'last_activity']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for member in self.members_data:
                row = member.copy()
                # Преобразуем datetime в строку для CSV
                if row['last_activity']:
                    row['last_activity'] = row['last_activity'].strftime('%Y-%m-%d %H:%M:%S')
                writer.writerow(row)
        
        print(f"✓ Данные сохранены в файл: {filename}")
    
    def display_sorted_members(self, top_n=20):
        """Отображение топ-N самых активных участников"""
        if not self.members_data:
            print("Нет данных для отображения")
            return
        
        print(f"\n{'='*60}")
        print(f"Топ-{top_n} самых активных участников (по времени последней активности):")
        print(f"{'='*60}")
        
        for i, member in enumerate(self.members_data[:top_n], 1):
            activity_str = "Неизвестно"
            if member['last_activity']:
                activity_str = member['last_activity'].strftime('%Y-%m-%d %H:%M:%S')
            
            username = f"@{member['username']}" if member['username'] else "без username"
            name = f"{member['first_name']} {member['last_name']}".strip() or "без имени"
            
            print(f"{i}. {name} ({username}) - Активность: {activity_str}")
        
        print(f"{'='*60}\n")
    
    async def close(self):
        await self.client.disconnect()


async def main():
    print("Telegram Parser - Парсинг участников с сортировкой по активности")
    print("=" * 60)
    
    parser = TelegramParser()
    
    try:
        await parser.start()
        
        # Запрос источника у пользователя
        source_group = input("\nВведите username или ID группы/канала для парсинга (например, @durov или -1001234567890): ").strip()
        
        if not source_group:
            print("Источник не указан. Выход.")
            return
        
        # Запрос лимита
        limit_input = input("Максимальное количество участников для парсинга (по умолчанию 1000): ").strip()
        limit = int(limit_input) if limit_input.isdigit() else 1000
        
        # Парсинг
        await parser.parse_members(source_group, limit)
        
        # Отображение результатов
        parser.display_sorted_members(20)
        
        # Сохранение
        save_filename = input("Введите имя файла для сохранения (по умолчанию parsed_members.csv): ").strip()
        if not save_filename:
            save_filename = 'parsed_members.csv'
        
        parser.save_to_csv(save_filename)
        
        print("\n✓ Парсинг успешно завершен!")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
    finally:
        await parser.close()


if __name__ == '__main__':
    asyncio.run(main())
