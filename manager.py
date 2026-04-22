import sqlite3
from database import DB_NAME

def add_account(phone, api_id, api_hash):
    """Добавляет аккаунт в базу данных."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    session_name = f"session_{phone.replace('+', '')}"
    
    try:
        cursor.execute('''
            INSERT INTO accounts (phone, api_id, api_hash, session_name)
            VALUES (?, ?, ?, ?)
        ''', (phone, api_id, api_hash, session_name))
        conn.commit()
        print(f"✅ Аккаунт {phone} успешно добавлен!")
        return True
    except sqlite3.IntegrityError:
        print(f"❌ Аккаунт {phone} уже существует в базе.")
        return False
    finally:
        conn.close()

def add_proxy(proxy_type, ip, port, username=None, password=None):
    """Добавляет прокси в базу данных."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO proxies (proxy_type, ip, port, username, password)
            VALUES (?, ?, ?, ?, ?)
        ''', (proxy_type, ip, port, username, password))
        conn.commit()
        print(f"✅ Прокси {ip}:{port} ({proxy_type}) успешно добавлен!")
        return True
    except Exception as e:
        print(f"❌ Ошибка при добавлении прокси: {e}")
        return False
    finally:
        conn.close()

def get_all_accounts():
    """Получает все аккаунты из базы данных."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT phone, api_id, api_hash, session_name FROM accounts')
    accounts = cursor.fetchall()
    conn.close()
    return accounts

def get_all_proxies():
    """Получает все прокси из базы данных."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT proxy_type, ip, port, username, password FROM proxies')
    proxies = cursor.fetchall()
    conn.close()
    return proxies

def delete_account(phone):
    """Удаляет аккаунт из базы данных."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM accounts WHERE phone = ?', (phone,))
        conn.commit()
        print(f"✅ Аккаунт {phone} удален.")
        return True
    except Exception as e:
        print(f"❌ Ошибка при удалении: {e}")
        return False
    finally:
        conn.close()

def delete_proxy(ip, port):
    """Удаляет прокси из базы данных."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM proxies WHERE ip = ? AND port = ?', (ip, port))
        conn.commit()
        print(f"✅ Прокси {ip}:{port} удален.")
        return True
    except Exception as e:
        print(f"❌ Ошибка при удалении: {e}")
        return False
    finally:
        conn.close()

def list_accounts():
    """Выводит список всех аккаунтов."""
    accounts = get_all_accounts()
    if not accounts:
        print("\n📭 Нет сохраненных аккаунтов.")
        return
    
    print("\n📋 Список аккаунтов:")
    print("-" * 60)
    for i, (phone, api_id, api_hash, session) in enumerate(accounts, 1):
        print(f"{i}. Телефон: {phone}")
        print(f"   API ID: {api_id}, API Hash: {api_hash[:10]}...")
        print(f"   Session: {session}")
        print("-" * 60)

def list_proxies():
    """Выводит список всех прокси."""
    proxies = get_all_proxies()
    if not proxies:
        print("\n📭 Нет сохраненных прокси.")
        return
    
    print("\n📋 Список прокси:")
    print("-" * 60)
    for i, (ptype, ip, port, user, pwd) in enumerate(proxies, 1):
        creds = f"{user}:{pwd}" if user and pwd else "без авторизации"
        print(f"{i}. Тип: {ptype.upper()} | {ip}:{port} | {creds}")
        print("-" * 60)

if __name__ == "__main__":
    # Инициализация БД при первом запуске
    from database import init_db
    init_db()
    
    while True:
        print("\n=== МЕНЕДЖЕР АККАУНТОВ И ПРОКСИ ===")
        print("1. Добавить аккаунт")
        print("2. Добавить прокси")
        print("3. Показать аккаунты")
        print("4. Показать прокси")
        print("5. Удалить аккаунт")
        print("6. Удалить прокси")
        print("7. Выход")
        
        choice = input("\nВыберите действие (1-7): ").strip()
        
        if choice == '1':
            phone = input("Введите номер телефона (например, +79991234567): ").strip()
            api_id = input("Введите API ID: ").strip()
            api_hash = input("Введите API Hash: ").strip()
            
            if phone and api_id and api_hash:
                try:
                    add_account(phone, int(api_id), api_hash)
                except ValueError:
                    print("❌ API ID должен быть числом.")
            else:
                print("❌ Все поля обязательны.")
                
        elif choice == '2':
            print("\nТипы прокси: mtproto, socks5, http")
            ptype = input("Введите тип прокси: ").strip().lower()
            ip = input("Введите IP адрес: ").strip()
            port = input("Введите порт: ").strip()
            user = input("Логин (оставьте пустым, если нет): ").strip()
            pwd = input("Пароль (оставьте пустым, если нет): ").strip()
            
            if ptype and ip and port:
                try:
                    add_proxy(ptype, ip, int(port), user if user else None, pwd if pwd else None)
                except ValueError:
                    print("❌ Порт должен быть числом.")
            else:
                print("❌ Тип, IP и порт обязательны.")
                
        elif choice == '3':
            list_accounts()
            
        elif choice == '4':
            list_proxies()
            
        elif choice == '5':
            phone = input("Введите номер телефона для удаления: ").strip()
            if phone:
                delete_account(phone)
                
        elif choice == '6':
            ip = input("Введите IP прокси для удаления: ").strip()
            port = input("Введите порт прокси для удаления: ").strip()
            if ip and port:
                try:
                    delete_proxy(ip, int(port))
                except ValueError:
                    print("❌ Порт должен быть числом.")
                    
        elif choice == '7':
            print("👋 До свидания!")
            break
        else:
            print("❌ Неверный выбор. Попробуйте снова.")
