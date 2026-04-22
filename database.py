import sqlite3
import os
from datetime import datetime

DB_NAME = "data.db"

def init_db():
    """Создает таблицы базы данных, если они не существуют."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица аккаунтов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL UNIQUE,
            api_id INTEGER NOT NULL,
            api_hash TEXT NOT NULL,
            session_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица прокси
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proxies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proxy_type TEXT NOT NULL, -- mtproto, socks5, http
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            username TEXT,
            password TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица спаршенных пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            last_seen TIMESTAMP,
            source_group TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("База данных инициализирована.")

if __name__ == "__main__":
    init_db()
