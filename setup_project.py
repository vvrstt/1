import os
import shutil

def setup():
    # Создаем папки
    dirs = ['accounts', 'parsed_data', 'logs']
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)
            print(f"Папка {d} создана.")
        else:
            print(f"Папка {d} уже существует.")

    # Создаем .env файл, если нет
    if not os.path.exists('.env'):
        with open('.env', 'w', encoding='utf-8') as f:
            f.write("""API_ID=ваш_api_id
API_HASH=ваш_api_hash
PHONE_NUMBER=+79990000000
""")
        print("Файл .env создан. Заполните его своими данными.")
    else:
        print("Файл .env уже существует.")

    # Создаем requirements.txt
    if not os.path.exists('requirements.txt'):
        with open('requirements.txt', 'w', encoding='utf-8') as f:
            f.write("""telethon==1.34.0
pandas==2.0.0
python-dateutil==2.8.2
""")
        print("Файл requirements.txt создан.")

    # Копируем основные скрипты (заглушки), если их нет
    files_to_create = {
        'parser.py': '# Скрипт парсера будет здесь\n# См. инструкцию ниже',
        'inviter.py': '# Скрипт инвайтера будет здесь\n# См. инструкцию ниже'
    }

    for filename, content in files_to_create.items():
        if not os.path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Файл {filename} создан.")
        else:
            print(f"Файл {filename} уже существует.")

if __name__ == '__main__':
    setup()
    print("\nНастройка завершена! Теперь установите зависимости:")
    print("pip install -r requirements.txt")
