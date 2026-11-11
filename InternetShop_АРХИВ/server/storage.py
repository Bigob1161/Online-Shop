"""
Компонент «Хранение данных».

Файл товаров (products.json), файл заказов (orders.json) и файл пользователей (users.json).
При запуске сервера все данные считываются из файлов в оперативную память и хранятся
в форме таблиц (списков словарей). При завершении работы (и после каждого изменения)
файлы не дописываются, а создаются заново на основании данных из таблиц.
"""
import json
import os
import hashlib
import secrets
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
FILES = {
    'users': 'users.json',       # «Файл пользователей»
    'products': 'products.json', # «Файл товаров»
    'orders': 'orders.json',     # «Файл заказов»
}


def hash_password(password, salt=None):
    """Пароли хранятся только в виде хеша (как в реальной организации)."""
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('ascii'), 60000).hex()
    return salt + '$' + h


def check_password(password, stored):
    try:
        salt, _ = stored.split('$', 1)
    except ValueError:
        return False
    return secrets.compare_digest(hash_password(password, salt), stored)


def now():
    return datetime.now().strftime('%d.%m.%Y %H:%M')


class Storage:
    """Таблицы системы в оперативной памяти и операции чтения/записи файлов."""

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.users = []      # таблица «Список пользователей» (включая курьеров)
        self.products = []   # таблица «Список товаров»
        self.orders = []     # таблица «Заказ» (позиции заказа хранятся внутри заказа)
        self.appeals = []    # обращения кладовщика к диспетчеру
        self.messages = []   # уведомления и сообщения пользователям
        self.counters = {'order': 1000, 'product': 0, 'appeal': 0, 'message': 0}

    # ------------------------------------------------------------------ чтение
    def _path(self, key):
        return os.path.join(self.data_dir, FILES[key])

    def _read(self, key, default):
        p = self._path(key)
        if not os.path.exists(p):
            return default
        with open(p, encoding='utf-8') as f:
            return json.load(f)

    def load(self):
        """Считать все файлы в оперативную память. Если файлов нет — создать начальные данные."""
        if not os.path.exists(self._path('users')):
            self.seed()
            self.save()
            return
        u = self._read('users', {})
        self.users = u.get('users', [])
        p = self._read('products', {})
        self.products = p.get('products', [])
        o = self._read('orders', {})
        self.orders = o.get('orders', [])
        self.appeals = o.get('appeals', [])
        self.messages = o.get('messages', [])
        self.counters.update(o.get('counters', {}))
        self.counters['product'] = max([self.counters['product']] + [x['id'] for x in self.products])

    # ------------------------------------------------------------------ запись
    def _write(self, key, data):
        p = self._path(key)
        tmp = p + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)   # файл создаётся заново

    def save(self):
        """Записать таблицы в файлы (файлы создаются заново)."""
        self._write('users', {'users': self.users})
        self._write('products', {'products': self.products})
        self._write('orders', {'orders': self.orders, 'appeals': self.appeals,
                               'messages': self.messages[-2000:], 'counters': self.counters})

    def next_id(self, kind):
        self.counters[kind] += 1
        return self.counters[kind]

    # --------------------------------------------------------- начальные данные
    def seed(self):
        def user(login, password, fio, role, contacts):
            d = {'login': login, 'password': hash_password(password), 'fio': fio, 'role': role,
                 'contacts': contacts, 'created': now()}
            if role == 'Курьер':
                d.update({'status': 'Свободен', 'location': '', 'location_time': ''})
            return d

        self.users = [
            user('admin', 'admin123', 'Смирнова Анна Сергеевна', 'Администратор', '+7 900 100-00-01'),
            user('sklad', 'sklad123', 'Петров Иван Николаевич', 'Кладовщик', '+7 900 100-00-02'),
            user('disp', 'disp123', 'Кузнецова Мария Олеговна', 'Диспетчер', '+7 900 100-00-03'),
            user('kurier1', 'kurier123', 'Иванов Алексей Петрович', 'Курьер', '+7 900 100-00-04'),
            user('kurier2', 'kurier123', 'Сидоров Дмитрий Андреевич', 'Курьер', '+7 900 100-00-05'),
            user('client', 'client123', 'Васильев Сергей Игоревич', 'Клиент', '+7 900 200-00-01, vasiliev@mail.ru'),
        ]
        items = [
            ('Смартфон Galaxy A35', 'Смартфоны', 27990, 12), ('Смартфон Redmi Note 13', 'Смартфоны', 19990, 8),
            ('Смартфон realme 12', 'Смартфоны', 17490, 0), ('Наушники AirDots Pro', 'Аудио', 3490, 25),
            ('Наушники JBL Tune 520', 'Аудио', 4990, 14), ('Портативная колонка JBL Go 3', 'Аудио', 3290, 9),
            ('Ноутбук Vivobook 15', 'Ноутбуки', 54990, 5), ('Ноутбук IdeaPad Slim 3', 'Ноутбуки', 49990, 3),
            ('Мышь беспроводная Logitech M190', 'Аксессуары', 990, 40), ('Клавиатура Defender Dark', 'Аксессуары', 1290, 22),
            ('Зарядное устройство 20 Вт', 'Аксессуары', 1190, 30), ('Кабель USB-C 1 м', 'Аксессуары', 390, 60),
            ('Чайник электрический Polaris', 'Бытовая техника', 2490, 11), ('Пылесос Dreame T20', 'Бытовая техника', 18990, 4),
            ('Фен Dyson Supersonic', 'Бытовая техника', 39990, 2),
        ]
        self.products = []
        for name, cat, price, qty in items:
            self.products.append({'id': self.next_id('product'), 'name': name, 'category': cat,
                                  'price': float(price), 'qty': qty})
        self.orders, self.appeals, self.messages = [], [], []
