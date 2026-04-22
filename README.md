# README: Telegram Inviter & Parser

## Описание

Инструмент для парсинга участников Telegram групп/каналов и их последующего инвайта в целевые группы.

### Возможности

1. **Парсер**:
   - Извлечение участников из групп и каналов
   - Определение времени последней активности пользователя
   - Сортировка по времени последней активности (онлайн, офлайн, недавно, неделя, месяц)
   - Сохранение результатов в CSV файл

2. **Инвайтер**:
   - Добавление пользователей в целевую группу
   - Поддержка нескольких аккаунтов для распределения нагрузки
   - Автоматическая обработка ошибок (FloodWait, Privacy Restricted, PeerFlood)
   - Настройка задержек между приглашениями

## Установка

```bash
# Установка зависимостей
pip install telethon python-dotenv

# Копирование примера конфигурации
cp .env.example .env

# Редактирование .env с вашими данными
```

## Получение API ключей

1. Перейдите на https://my.telegram.org/apps
2. Войдите под своим номером телефона
3. Создайте новое приложение
4. Скопируйте `API_ID` и `API_HASH` в файл `.env`

## Использование

### Запуск

```bash
python telegram_bot.py
```

Вам будет предложено выбрать режим:
- **1** - Парсер участников с сортировкой по активности
- **2** - Инвайтер пользователей в группу

### Режим 1: Парсер

1. Введите ссылку на группу/канал для парсинга
2. Укажите максимальное количество участников (по умолчанию 1000)
3. Скрипт покажет топ-10 самых активных пользователей
4. Результаты сохраняются в `parsed_users.csv`

### Режим 2: Инвайтер

1. Добавьте аккаунты в код (см. пример в `main_inviter_example()`)
2. Запустите скрипт
3. Введите username целевой группы
4. Скрипт начнет приглашение пользователей из `parsed_users.csv`

## Конфигурация инвайтера

Для работы с несколькими аккаунтами создайте список:

```python
accounts = [
    {
        'phone': '+79991234567',
        'api_id': 12345,
        'api_hash': 'abc123def456',
        'session': 'account1.session'
    },
    {
        'phone': '+79997654321',
        'api_id': 67890,
        'api_hash': 'xyz789uvw012',
        'session': 'account2.session'
    }
]
```

## Параметры настройки

В функции `invite_users()` можно настроить:

- `delay_between_invites` - задержка между приглашениями (сек), по умолчанию 30
- `max_invites_per_account` - лимит приглашений на аккаунт, по умолчанию 50

## Обработка ошибок

Скрипт автоматически обрабатывает:

- **FloodWaitError** - ожидание указанного времени
- **UserPrivacyRestrictedError** - пользователь запретил приглашения
- **PeerFloodError** - временный бан аккаунта на рассылку
- Другие ошибки Telegram API

## Важные замечания

⚠️ **Предупреждение**: Массовый инвайт может привести к блокировке аккаунтов Telegram. Используйте осторожно!

Рекомендации:
- Используйте задержки между приглашениями (30+ секунд)
- Ограничьте количество приглашений на аккаунт (50-100 в день)
- Используйте несколько аккаунтов для больших объемов
- Не инвайтте ботов и удаленные аккаунты

## Структура выходного CSV файла

| Поле | Описание |
|------|----------|
| user_id | ID пользователя в Telegram |
| username | Юзернейм (@username) |
| first_name | Имя |
| last_name | Фамилия |
| phone | Номер телефона (если доступен) |
| last_seen | Время последней активности |
| status | Статус активности (emoji) |
| is_bot | Является ли ботом |
| is_deleted | Удален ли аккаунт |

## Пример использования в коде

```python
import asyncio
from telegram_bot import TelegramParser, TelegramInviter

async def main():
    # Парсинг
    parser = TelegramParser(API_ID, API_HASH, PHONE, "my_session")
    await parser.start()
    
    participants = await parser.parse_members("https://t.me/target_group", 500)
    sorted_users = parser.sort_by_activity(participants, reverse=True)
    await parser.save_to_csv(sorted_users)
    
    await parser.stop()
    
    # Инвайт
    inviter = TelegramInviter(accounts)
    await inviter.initialize_accounts()
    
    stats = await inviter.invite_users(
        target_chat="@my_target_group",
        users=sorted_users,
        delay_between_invites=30.0,
        max_invites_per_account=50
    )
    
    print(f"Успешно: {stats['success']}, Неудачно: {stats['failed']}")
    
    await inviter.close_accounts()

asyncio.run(main())
```

## Лицензия

Используйте на свой страх и риск. Автор не несет ответственности за возможные блокировки аккаунтов.
