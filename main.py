import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import asyncio
import threading
import os
import csv
import sqlite3
from datetime import datetime
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch, UserStatusRecently, UserStatusLastMonth, UserStatusLastWeek
from telethon.tl.functions.messages import AddChatUserRequest, ImportChatInviteRequest
import aiohttp
import socks

# Настройки внешнего вида
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DB_NAME = "data.db"

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME)
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.migrate_database()  # Добавляем недостающие колонки если их нет

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                api_id INTEGER,
                api_hash TEXT,
                session_string TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS proxies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proxy_type TEXT,
                host TEXT,
                port INTEGER,
                username TEXT,
                password TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def migrate_database(self):
        """Добавляет отсутствующие колонки в существующие таблицы"""
        # Проверяем таблицу accounts
        self.cursor.execute("PRAGMA table_info(accounts)")
        columns = {col[1] for col in self.cursor.fetchall()}
        
        if 'session_string' not in columns:
            print("Добавление колонки session_string в таблицу accounts...")
            self.cursor.execute("ALTER TABLE accounts ADD COLUMN session_string TEXT")
            self.conn.commit()
        
        if 'api_id' not in columns:
            self.cursor.execute("ALTER TABLE accounts ADD COLUMN api_id INTEGER")
            self.conn.commit()
            
        if 'api_hash' not in columns:
            self.cursor.execute("ALTER TABLE accounts ADD COLUMN api_hash TEXT")
            self.conn.commit()

        # Проверяем таблицу proxies
        self.cursor.execute("PRAGMA table_info(proxies)")
        proxy_columns = {col[1] for col in self.cursor.fetchall()}
        
        if 'host' not in proxy_columns and 'ip' in proxy_columns:
            # Переименовываем ip в host для совместимости
            try:
                self.cursor.execute("ALTER TABLE proxies RENAME COLUMN ip TO host")
                self.conn.commit()
            except:
                pass  # Если не получается, пробуем добавить новую колонку
        elif 'host' not in proxy_columns:
            self.cursor.execute("ALTER TABLE proxies ADD COLUMN host TEXT")
            self.conn.commit()

    def add_account(self, phone, api_id, api_hash, session_string):
        self.cursor.execute("INSERT INTO accounts (phone, api_id, api_hash, session_string) VALUES (?, ?, ?, ?)",
                            (phone, api_id, api_hash, session_string))
        self.conn.commit()

    def get_accounts(self):
        self.cursor.execute("SELECT id, phone, api_id, api_hash, session_string FROM accounts")
        return self.cursor.fetchall()

    def delete_account(self, acc_id):
        self.cursor.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
        self.conn.commit()

    def add_proxy(self, p_type, host, port, username, password):
        self.cursor.execute("INSERT INTO proxies (proxy_type, host, port, username, password) VALUES (?, ?, ?, ?, ?)",
                            (p_type, host, port, username, password))
        self.conn.commit()

    def get_proxies(self):
        self.cursor.execute("SELECT id, proxy_type, host, port, username, password FROM proxies")
        return self.cursor.fetchall()

    def delete_proxy(self, p_id):
        self.cursor.execute("DELETE FROM proxies WHERE id = ?", (p_id,))
        self.conn.commit()

db = Database()

class TelegramToolGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Telegram Parser & Inviter Manager")
        self.geometry("900x700")

        # Сетка главного окна
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Табы
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        self.tab_accounts = self.tabview.add("Аккаунты")
        self.tab_proxies = self.tabview.add("Прокси")
        self.tab_parser = self.tabview.add("Парсер")
        self.tab_inviter = self.tabview.add("Инвайтер")

        self.setup_accounts_tab()
        self.setup_proxies_tab()
        self.setup_parser_tab()
        self.setup_inviter_tab()

    # --- Вкладка Аккаунты ---
    def setup_accounts_tab(self):
        frame = ctk.CTkFrame(self.tab_accounts)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Форма добавления
        lbl_title = ctk.CTkLabel(frame, text="Добавление аккаунта", font=ctk.CTkFont(size=16, weight="bold"))
        lbl_title.pack(pady=10)

        self.ent_phone = ctk.CTkEntry(frame, placeholder_text="Номер телефона (+7...)")
        self.ent_phone.pack(pady=5, fill="x", padx=20)

        self.ent_api_id = ctk.CTkEntry(frame, placeholder_text="API ID")
        self.ent_api_id.pack(pady=5, fill="x", padx=20)

        self.ent_api_hash = ctk.CTkEntry(frame, placeholder_text="API Hash")
        self.ent_api_hash.pack(pady=5, fill="x", padx=20)

        btn_add = ctk.CTkButton(frame, text="Добавить аккаунт (запрос кода)", command=self.add_account_thread)
        btn_add.pack(pady=10)

        # Список аккаунтов
        self.acc_listbox = ctk.CTkScrollableFrame(frame)
        self.acc_listbox.pack(fill="both", expand=True, padx=20, pady=10)
        
        btn_refresh = ctk.CTkButton(frame, text="Обновить список", command=self.refresh_accounts)
        btn_refresh.pack(pady=5)

        self.refresh_accounts()

    def add_account_thread(self):
        phone = self.ent_phone.get()
        api_id = self.ent_api_id.get()
        api_hash = self.ent_api_hash.get()

        if not phone or not api_id or not api_hash:
            messagebox.showerror("Ошибка", "Заполните все поля")
            return

        def run_auth():
            try:
                client = TelegramClient(StringSession(), int(api_id), api_hash)
                # Запуск в том же потоке не блокирует GUI, так как connect синхронен здесь, но лучше через async loop
                # Для простоты используем синхронный вызов внутри потока
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def auth_process():
                    await client.connect()
                    if not await client.is_user_authorized():
                        sent = await client.send_code_request(phone)
                        code = input(f"Введите код для {phone}: ") # В консоли, т.к. GUI сложно сделать ввод кода безопасно без доп окон
                        # Для полноценного GUI нужно модальное окно ввода кода. 
                        # Упростим: просим пользователя ввести код в консоль или сразу сессию.
                        # ПЕРЕДЕЛАЕМ: Сделаем запрос сессии напрямую, чтобы не мучить консолью.
                        pass 
                    return client.session.save()

                # Так как ввод кода в консоль неудобен при запущенном GUI, 
                # предложим пользователю создать сессию через отдельный скрипт или введем поле для кода.
                # РЕШЕНИЕ: Добавим поле для кода подтверждения в интерфейс.
                pass
            except Exception as e:
                print(e)

        # Упрощенная логика: пока просто сохраняем данные, а авторизацию делаем при первом запуске инструмента
        # Или просим ввести строку сессии, если она уже есть.
        # ДАВАЙТЕ СДЕЛАЕМ ПРОЩЕ: Поле для ввода кода появится после нажатия кнопки? 
        # Нет, это сложно. Давайте сделаем так: Пользователь вводит данные, мы пытаемся авторизовать.
        # Если нужен код - пишем в лог (которого нет). 
        # ЛУЧШИЙ ВАРИАНТ ДЛЯ ГУИ: Два шага. 1. Сохранить данные. 2. Кнопка "Авторизовать".
        
        # Пока реализуем простое добавление данных, а авторизацию проведем при старте парсера/инвайтера.
        # Но Telethon требует сессию. 
        # Давайте сделаем так: При нажатии "Добавить" создаем клиент, запрашиваем код через простой Toplevel.
        
        self.auth_dialog = ctk.CTkToplevel(self)
        self.auth_dialog.title("Авторизация")
        self.auth_dialog.geometry("400x300")
        
        ctk.CTkLabel(self.auth_dialog, text=f"Отправка кода на {phone}...").pack(pady=10)
        
        async def start_auth():
            client = TelegramClient(StringSession(), int(api_id), api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                try:
                    await client.send_code_request(phone)
                    ctk.CTkLabel(self.auth_dialog, text="Введите код из СМС/Telegram:").pack(pady=5)
                    ent_code = ctk.CTkEntry(self.auth_dialog)
                    ent_code.pack(pady=5)
                    
                    def submit_code():
                        code = ent_code.get()
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            async def sign_in():
                                await client.sign_in(phone, code)
                                return client.session.save()
                            session_str = loop.run_until_complete(sign_in())
                            db.add_account(phone, api_id, api_hash, session_str)
                            messagebox.showinfo("Успех", "Аккаунт добавлен!")
                            self.auth_dialog.destroy()
                            self.refresh_accounts()
                        except errors.SessionPasswordNeededError:
                            messagebox.showinfo("2FA", "Нужен пароль двухфакторной аутентификации")
                            # Тут нужна еще одна ступень, упростим для примера
                        except Exception as e:
                            messagebox.showerror("Ошибка", str(e))
                    
                    ctk.CTkButton(self.auth_dialog, text="Войти", command=submit_code).pack(pady=10)
                except Exception as e:
                    messagebox.showerror("Ошибка отправки кода", str(e))
            else:
                session_str = client.session.save()
                db.add_account(phone, api_id, api_hash, session_str)
                messagebox.showinfo("Успех", "Аккаунт уже авторизован и добавлен!")
                self.auth_dialog.destroy()
                self.refresh_accounts()
            await client.disconnect()

        # Запуск асинхронного процесса в отдельном потоке
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(start_auth())
            loop.close()
        
        threading.Thread(target=run_loop, daemon=True).start()

    def refresh_accounts(self):
        for widget in self.acc_listbox.winfo_children():
            widget.destroy()
        
        accounts = db.get_accounts()
        if not accounts:
            ctk.CTkLabel(self.acc_listbox, text="Нет аккаунтов").pack(pady=10)
            return

        for acc in accounts:
            row = ctk.CTkFrame(self.acc_listbox)
            row.pack(fill="x", padx=5, pady=2)
            ctk.CTkLabel(row, text=f"{acc[1]} (ID: {acc[2]})").pack(side="left", padx=10)
            btn_del = ctk.CTkButton(row, text="X", width=30, fg_color="red", 
                                    command=lambda i=acc[0]: self.delete_account(i))
            btn_del.pack(side="right", padx=5)

    def delete_account(self, acc_id):
        if messagebox.askyesno("Подтверждение", "Удалить аккаунт?"):
            db.delete_account(acc_id)
            self.refresh_accounts()

    # --- Вкладка Прокси ---
    def setup_proxies_tab(self):
        frame = ctk.CTkFrame(self.tab_proxies)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Добавление прокси", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        self.proxy_type = ctk.CTkComboBox(frame, values=["SOCKS5", "HTTP", "MTProto"])
        self.proxy_type.pack(pady=5, fill="x", padx=20)
        self.proxy_type.set("SOCKS5")

        self.ent_host = ctk.CTkEntry(frame, placeholder_text="Хост (IP)")
        self.ent_host.pack(pady=5, fill="x", padx=20)

        self.ent_port = ctk.CTkEntry(frame, placeholder_text="Порт")
        self.ent_port.pack(pady=5, fill="x", padx=20)

        self.ent_p_user = ctk.CTkEntry(frame, placeholder_text="Логин (необязательно)")
        self.ent_p_user.pack(pady=5, fill="x", padx=20)

        self.ent_p_pass = ctk.CTkEntry(frame, placeholder_text="Пароль (необязательно)")
        self.ent_p_pass.pack(pady=5, fill="x", padx=20)

        ctk.CTkButton(frame, text="Добавить прокси", command=self.add_proxy).pack(pady=10)

        self.proxy_listbox = ctk.CTkScrollableFrame(frame)
        self.proxy_listbox.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkButton(frame, text="Обновить список", command=self.refresh_proxies).pack(pady=5)
        self.refresh_proxies()

    def add_proxy(self):
        p_type = self.proxy_type.get()
        host = self.ent_host.get()
        port = self.ent_port.get()
        user = self.ent_p_user.get()
        pwd = self.ent_p_pass.get()

        if not host or not port:
            messagebox.showerror("Ошибка", "Хост и порт обязательны")
            return
        
        try:
            db.add_proxy(p_type, host, int(port), user if user else None, pwd if pwd else None)
            messagebox.showinfo("Успех", "Прокси добавлено")
            self.refresh_proxies()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def refresh_proxies(self):
        for widget in self.proxy_listbox.winfo_children():
            widget.destroy()
        
        proxies = db.get_proxies()
        if not proxies:
            ctk.CTkLabel(self.proxy_listbox, text="Нет прокси").pack(pady=10)
            return

        for p in proxies:
            row = ctk.CTkFrame(self.proxy_listbox)
            row.pack(fill="x", padx=5, pady=2)
            info = f"{p[1]}://{p[2]}:{p[3]}"
            ctk.CTkLabel(row, text=info).pack(side="left", padx=10)
            btn_del = ctk.CTkButton(row, text="X", width=30, fg_color="red", 
                                    command=lambda i=p[0]: self.delete_proxy(i))
            btn_del.pack(side="right", padx=5)

    def delete_proxy(self, p_id):
        if messagebox.askyesno("Подтверждение", "Удалить прокси?"):
            db.delete_proxy(p_id)
            self.refresh_proxies()

    # --- Вкладка Парсер ---
    def setup_parser_tab(self):
        frame = ctk.CTkFrame(self.tab_parser)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Настройки парсера", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # Выбор аккаунта
        ctk.CTkLabel(frame, text="Аккаунт для парсинга:").pack(anchor="w", padx=20)
        self.parser_acc_var = ctk.StringVar()
        self.parser_acc_menu = ctk.CTkOptionMenu(frame, variable=self.parser_acc_var)
        self.parser_acc_menu.pack(fill="x", padx=20, pady=5)
        self.update_acc_menus()

        # Ссылка
        self.ent_parse_link = ctk.CTkEntry(frame, placeholder_text="Ссылка на группу/канал (https://t.me/...)")
        self.ent_parse_link.pack(fill="x", padx=20, pady=5)

        # Фильтр активности
        ctk.CTkLabel(frame, text="Фильтр активности:").pack(anchor="w", padx=20)
        self.parse_filter = ctk.CTkComboBox(frame, values=["Все", "Недавно был", "Был в течение месяца", "Был в течение недели"])
        self.parse_filter.pack(fill="x", padx=20, pady=5)
        self.parse_filter.set("Все")

        self.btn_start_parse = ctk.CTkButton(frame, text="Запустить парсер", command=self.start_parser_thread, fg_color="green")
        self.btn_start_parse.pack(pady=20)

        self.parse_log = ctk.CTkTextbox(frame, height=200)
        self.parse_log.pack(fill="both", expand=True, padx=20, pady=10)

    def update_acc_menus(self):
        accounts = db.get_accounts()
        acc_names = [f"{a[1]} (ID: {a[2]})" for a in accounts]
        
        # Обновляем меню в парсере
        current = self.parser_acc_var.get()
        self.parser_acc_menu.configure(values=acc_names)
        if acc_names and current not in acc_names:
            self.parser_acc_var.set(acc_names[0])

        # Обновляем меню в инвайтере (если нужно, вызовем там отдельно)
        if hasattr(self, 'inviter_acc_menu'):
             curr_inv = self.inviter_acc_var.get()
             self.inviter_acc_menu.configure(values=acc_names)
             if acc_names and curr_inv not in acc_names:
                 self.inviter_acc_var.set(acc_names[0])

    def log_parse(self, msg):
        self.parse_log.insert("end", msg + "\n")
        self.parse_log.see("end")

    def start_parser_thread(self):
        acc_name = self.parser_acc_var.get()
        link = self.ent_parse_link.get()
        filter_mode = self.parse_filter.get()

        if not acc_name or not link:
            messagebox.showerror("Ошибка", "Выберите аккаунт и введите ссылку")
            return

        # Находим аккаунт в БД
        accs = db.get_accounts()
        target_acc = None
        for a in accs:
            if f"{a[1]} (ID: {a[2]})" == acc_name:
                target_acc = a
                break
        
        if not target_acc:
            return

        threading.Thread(target=self.run_parser, args=(target_acc, link, filter_mode), daemon=True).start()

    def run_parser(self, account, link, filter_mode):
        async def parse_task():
            api_id, api_hash, session_str = account[2], account[3], account[4]
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            
            # Прокси (берем первый попавшийся для примера, можно добавить выбор)
            proxies = db.get_proxies()
            if proxies:
                p = proxies[0]
                proxy_conn = (p[1], p[2], int(p[3]), True, p[4], p[5]) if p[4] else (p[1], p[2], int(p[3]), True)
                # Упрощенно для Telethon
                if p[1] == "SOCKS5":
                    await client.connect(proxy=(socks.SOCKS5, p[2], int(p[3]), True, p[4], p[5]))
                elif p[1] == "HTTP":
                    await client.connect(proxy=(socks.HTTP, p[2], int(p[3]), True, p[4], p[5]))
            else:
                await client.connect()

            self.log_parse(f"Подключено как {account[1]}")
            
            try:
                if "/joinchat/" in link or "t.me/+/" in link:
                    entity = await client(ImportChatInviteRequest(link.split('/')[-1]))
                else:
                    entity = await client.get_entity(link)
                
                self.log_parse(f"Парсим участников: {entity.title}")
                
                all_participants = []
                offset = 0
                limit = 100
                
                while True:
                    participants = await client(GetParticipantsRequest(
                        entity, ChannelParticipantsSearch(''), offset, limit, hash=0
                    ))
                    if not participants.users:
                        break
                    
                    all_participants.extend(participants.users)
                    offset += limit
                    self.log_parse(f"Найдено: {len(all_participants)}")
                    await asyncio.sleep(1) # Анти-спам

                # Обработка и сортировка
                results = []
                now = datetime.now()
                
                for user in all_participants:
                    if user.deleted: continue
                    if user.bot: continue
                    
                    status = getattr(user, 'status', None)
                    last_seen = None
                    sort_key = 999999 # Default far future

                    if isinstance(status, UserStatusRecently):
                        last_seen = "Recently"
                        sort_key = 0
                    elif isinstance(status, UserStatusLastWeek):
                        last_seen = "Last Week"
                        sort_key = 1
                    elif isinstance(status, UserStatusLastMonth):
                        last_seen = "Last Month"
                        sort_key = 2
                    elif status:
                        last_seen = str(status.was_online) if hasattr(status, 'was_online') else "Long ago"
                        sort_key = 3
                    else:
                        last_seen = "Unknown"
                        sort_key = 4

                    # Фильтрация
                    if filter_mode == "Недавно был" and sort_key > 0: continue
                    if filter_mode == "Был в течение недели" and sort_key > 1: continue
                    if filter_mode == "Был в течение месяца" and sort_key > 2: continue

                    results.append({
                        'id': user.id,
                        'username': user.username or "",
                        'first_name': user.first_name or "",
                        'last_name': user.last_name or "",
                        'last_seen': last_seen,
                        'sort_key': sort_key
                    })

                # Сортировка
                results.sort(key=lambda x: x['sort_key'])

                filename = f"parsed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=['id', 'username', 'first_name', 'last_name', 'last_seen'])
                    writer.writeheader()
                    writer.writerows(results)

                self.log_parse(f"Готово! Сохранено в {filename} ({len(results)} чел.)")
                messagebox.showinfo("Успех", f"Парсинг завершен!\nФайл: {filename}")

            except Exception as e:
                self.log_parse(f"Ошибка: {str(e)}")
            finally:
                await client.disconnect()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(parse_task())
        loop.close()

    # --- Вкладка Инвайтер ---
    def setup_inviter_tab(self):
        frame = ctk.CTkFrame(self.tab_inviter)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="Настройки инвайтера", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # Выбор файла
        btn_file = ctk.CTkButton(frame, text="Выбрать CSV файл", command=self.select_csv)
        btn_file.pack(pady=5)
        self.lbl_csv_file = ctk.CTkLabel(frame, text="Файл не выбран")
        self.lbl_csv_file.pack(pady=5)
        self.csv_path = None

        # Выбор аккаунтов (можно несколько, но для простоты возьмем один или рандом)
        ctk.CTkLabel(frame, text="Аккаунт для инвайта:").pack(anchor="w", padx=20)
        self.inviter_acc_var = ctk.StringVar()
        self.inviter_acc_menu = ctk.CTkOptionMenu(frame, variable=self.inviter_acc_var)
        self.inviter_acc_menu.pack(fill="x", padx=20, pady=5)
        self.update_acc_menus()

        self.ent_target_link = ctk.CTkEntry(frame, placeholder_text="Ссылка на вашу группу (куда инвайтить)")
        self.ent_target_link.pack(fill="x", padx=20, pady=5)

        self.ent_delay_min = ctk.CTkEntry(frame, placeholder_text="Мин. задержка (сек)", width=100)
        self.ent_delay_min.pack(side="left", padx=20, pady=5)
        self.ent_delay_min.insert(0, "10")
        
        self.ent_delay_max = ctk.CTkEntry(frame, placeholder_text="Макс. задержка (сек)", width=100)
        self.ent_delay_max.pack(side="left", padx=20, pady=5)
        self.ent_delay_max.insert(0, "30")

        self.btn_start_invite = ctk.CTkButton(frame, text="Запустить инвайтер", command=self.start_inviter_thread, fg_color="orange")
        self.btn_start_invite.pack(pady=20)

        self.invite_log = ctk.CTkTextbox(frame, height=200)
        self.invite_log.pack(fill="both", expand=True, padx=20, pady=10)

    def select_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if path:
            self.csv_path = path
            self.lbl_csv_file.configure(text=os.path.basename(path))

    def log_invite(self, msg):
        self.invite_log.insert("end", msg + "\n")
        self.invite_log.see("end")

    def start_inviter_thread(self):
        if not self.csv_path:
            messagebox.showerror("Ошибка", "Выберите CSV файл")
            return
        
        acc_name = self.inviter_acc_var.get()
        target_link = self.ent_target_link.get()
        
        if not acc_name or not target_link:
            messagebox.showerror("Ошибка", "Выберите аккаунт и целевую группу")
            return

        try:
            d_min = float(self.ent_delay_min.get())
            d_max = float(self.ent_delay_max.get())
        except:
            messagebox.showerror("Ошибка", "Неверный формат задержки")
            return

        accs = db.get_accounts()
        target_acc = None
        for a in accs:
            if f"{a[1]} (ID: {a[2]})" == acc_name:
                target_acc = a
                break
        
        if not target_acc:
            return

        # Чтение пользователей
        users = []
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['username']: # Только юзернеймы
                    users.append(row['username'])

        threading.Thread(target=self.run_inviter, args=(target_acc, target_link, users, d_min, d_max), daemon=True).start()

    def run_inviter(self, account, target_link, users, d_min, d_max):
        async def invite_task():
            api_id, api_hash, session_str = account[2], account[3], account[4]
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            
            # Подключение с прокси (аналогично парсеру)
            proxies = db.get_proxies()
            if proxies:
                p = proxies[0]
                if p[1] == "SOCKS5":
                    await client.connect(proxy=(socks.SOCKS5, p[2], int(p[3]), True, p[4], p[5]))
                elif p[1] == "HTTP":
                    await client.connect(proxy=(socks.HTTP, p[2], int(p[3]), True, p[4], p[5]))
            else:
                await client.connect()

            self.log_invite(f"Подключено как {account[1]}")

            try:
                if "/joinchat/" in target_link or "t.me/+/" in target_link:
                    entity = await client(ImportChatInviteRequest(target_link.split('/')[-1]))
                else:
                    entity = await client.get_entity(target_link)
                
                self.log_invite(f"Начинаем инвайт в: {entity.title}")
                
                success_count = 0
                error_count = 0

                for user in users:
                    try:
                        await client(AddChatUserRequest(entity.id, await client.get_input_entity(user), 0))
                        self.log_invite(f"+ Добавлен: @{user}")
                        success_count += 1
                    except errors.FloodWaitError as e:
                        self.log_invite(f"⚠️ FloodWait: ждем {e.seconds} сек")
                        await asyncio.sleep(e.seconds)
                        # Повторная попытка
                        try:
                            await client(AddChatUserRequest(entity.id, await client.get_input_entity(user), 0))
                            self.log_invite(f"+ Добавлен (повтор): @{user}")
                            success_count += 1
                        except:
                            error_count += 1
                    except errors.UserPrivacyRestrictedError:
                        self.log_invite(f"❌ Приватность: @{user}")
                        error_count += 1
                    except errors.UserAlreadyParticipantError:
                        self.log_invite(f"🔁 Уже в группе: @{user}")
                    except Exception as e:
                        self.log_invite(f"❌ Ошибка: @{user} - {str(e)}")
                        error_count += 1

                    delay = random.uniform(d_min, d_max)
                    self.log_invite(f"Пауза {delay:.1f} сек...")
                    await asyncio.sleep(delay)

                self.log_invite(f"✅ Завершено. Успешно: {success_count}, Ошибок: {error_count}")

            except Exception as e:
                self.log_invite(f"Критическая ошибка: {str(e)}")
            finally:
                await client.disconnect()

        import random
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(invite_task())
        loop.close()

if __name__ == "__main__":
    app = TelegramToolGUI()
    app.mainloop()