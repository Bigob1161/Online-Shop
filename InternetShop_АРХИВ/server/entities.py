"""
Классы-сущности (entity) диаграммы классов:
  «Список пользователей», «Курьер», «Список товаров», «Позиция заказа», «Заказ».
Каждый класс работает с соответствующей таблицей в оперативной памяти (см. storage.py).
"""
from storage import now, hash_password

# Значения статусов (см. диаграмму состояний объекта «Заказ»)
ST_NEW = 'Оформлен'
ST_PAID = 'Оплачен'
ST_PICKING = 'Сборка'
ST_ASSEMBLED = 'Собран'
ST_HANDED = 'Передан в доставку'
ST_ON_WAY = 'В пути'
ST_DELIVERED = 'Доставлен'
ST_NOT_DELIVERED = 'Не доставлен'
ST_CANCELLED = 'Отменён'
FINISHED = (ST_DELIVERED, ST_CANCELLED)

PAY_NO = 'Не оплачен'
PAY_YES = 'Оплачен'
PAY_REFUND = 'Возвращён'

POS_WAIT = 'Ожидает отбора'
POS_PICKED = 'Отобрана'
POS_SHORT = 'Нехватка: ждёт решения диспетчера'
POS_EXCLUDED = 'Исключена'

COURIER_FREE = 'Свободен'
COURIER_BUSY = 'Занят'

ROLES_STAFF = ('Администратор', 'Кладовщик', 'Диспетчер', 'Курьер')
ROLE_CLIENT = 'Клиент'


class UserList:
    """«entity» Список пользователей: ФИО, Контакты, Роль, Логин, Пароль."""

    def __init__(self, st):
        self.st = st

    def find(self, login):
        login = (login or '').strip().lower()
        for u in self.st.users:
            if u['login'].lower() == login:
                return u
        return None

    def add_user(self, fio, contacts, role, login, password):
        """Добавить пользователя()"""
        u = {'login': login.strip(), 'password': hash_password(password), 'fio': fio.strip(),
             'role': role, 'contacts': contacts.strip(), 'created': now()}
        if role == 'Курьер':
            u.update({'status': COURIER_FREE, 'location': '', 'location_time': ''})
        self.st.users.append(u)
        return u

    def update_user(self, login, **fields):
        """Изменить данные пользователя()"""
        u = self.find(login)
        for k, v in fields.items():
            if k == 'password':
                u['password'] = hash_password(v)
            else:
                u[k] = v
        if u['role'] == 'Курьер':
            u.setdefault('status', COURIER_FREE)
            u.setdefault('location', '')
            u.setdefault('location_time', '')
        return u

    def delete_user(self, login):
        """Удалить пользователя()"""
        u = self.find(login)
        self.st.users.remove(u)

    def staff(self):
        return [u for u in self.st.users if u['role'] in ROLES_STAFF]

    @staticmethod
    def public(u):
        d = {k: v for k, v in u.items() if k != 'password'}
        return d


class Courier:
    """«entity» Курьер: ФИО, Статус, Местоположение (хранится в списке пользователей)."""

    def __init__(self, st):
        self.st = st

    def all(self):
        return [u for u in self.st.users if u['role'] == 'Курьер']

    def find(self, login):
        for u in self.all():
            if u['login'] == login:
                return u
        return None

    def set_status(self, login, status):
        """Изменить статус()"""
        c = self.find(login)
        if c:
            c['status'] = status

    def update_location(self, login, location):
        """Обновить местоположение()"""
        c = self.find(login)
        c['location'] = location.strip()
        c['location_time'] = now()


class ProductList:
    """«entity» Список товаров: Наименование, Цена, Количество, Категория."""

    def __init__(self, st):
        self.st = st

    def get(self, pid):
        for p in self.st.products:
            if p['id'] == pid:
                return p
        return None

    def find_by_name(self, name):
        name = name.strip().lower()
        for p in self.st.products:
            if p['name'].lower() == name:
                return p
        return None

    def add_product(self, name, price, qty, category):
        """Добавить товар()"""
        p = {'id': self.st.next_id('product'), 'name': name.strip(), 'price': float(price),
             'qty': int(qty), 'category': category.strip()}
        self.st.products.append(p)
        return p

    def update_product(self, pid, **fields):
        """Изменить товар()"""
        p = self.get(pid)
        p.update(fields)
        return p

    def delete_product(self, pid):
        """Удалить товар()"""
        self.st.products.remove(self.get(pid))


class OrderItem:
    """«entity» Позиция заказа: Товар, Количество, Статус позиции. (Хранится внутри заказа.)"""

    @staticmethod
    def new(product, qty):
        return {'product_id': product['id'], 'name': product['name'], 'price': product['price'],
                'qty': int(qty), 'status': POS_WAIT, 'note': ''}

    @staticmethod
    def mark_picked(item):
        """Отметить отобранной()"""
        item['status'] = POS_PICKED

    @staticmethod
    def change_qty(item, qty):
        """Изменить количество()"""
        item['qty'] = int(qty)
        item['status'] = POS_WAIT

    @staticmethod
    def exclude(item):
        """Исключить позицию()"""
        item['status'] = POS_EXCLUDED


class Order:
    """«entity» Заказ: Номер, Клиент, Адрес доставки, Стоимость, Статус, Статус оплаты, Курьер.
    Заказ состоит из позиций заказа (композиция)."""

    def __init__(self, st):
        self.st = st

    def get(self, number):
        for o in self.st.orders:
            if o['number'] == int(number):
                return o
        return None

    def create(self, client, items, address, recipient, phone, date, comment):
        """Создать заказ()"""
        o = {'number': self.st.next_id('order'), 'created': now(), 'client': client['login'],
             'client_fio': client['fio'], 'recipient': recipient, 'phone': phone, 'address': address,
             'delivery_date': date, 'comment': comment, 'items': items, 'cost': 0.0,
             'status': ST_NEW, 'pay_status': PAY_NO, 'paid_sum': 0.0, 'refund_sum': 0.0, 'card': '',
             'courier': '', 'courier_fio': '', 'fail_reason': '', 'history': []}
        self.recalc(o)
        self.log(o, 'Заказ оформлен клиентом')
        self.st.orders.append(o)
        return o

    @staticmethod
    def recalc(o):
        o['cost'] = round(sum(i['price'] * i['qty'] for i in o['items'] if i['status'] != POS_EXCLUDED), 2)
        return o['cost']

    @staticmethod
    def log(o, text):
        o['history'].append({'time': now(), 'text': text})

    def pay(self, o, card_last4):
        """Оплатить заказ()"""
        o['pay_status'] = PAY_YES
        o['paid_sum'] = o['cost']
        o['card'] = card_last4
        self.set_status(o, ST_PAID, 'Заказ оплачен картой •••• %s, сумма %s' % (card_last4, money(o['cost'])))

    def refund(self, o, amount=None, reason=''):
        """Вернуть оплату()"""
        if o['pay_status'] != PAY_YES:
            return 0
        amount = round(o['paid_sum'] - o['refund_sum'] if amount is None else amount, 2)
        if amount <= 0:
            return 0
        o['refund_sum'] = round(o['refund_sum'] + amount, 2)
        if o['refund_sum'] >= o['paid_sum'] - 0.001:
            o['pay_status'] = PAY_REFUND
        self.log(o, 'Возврат оплаты клиенту: %s%s' % (money(amount), (' (' + reason + ')') if reason else ''))
        return amount

    def assign_courier(self, o, courier):
        """Назначить курьера()"""
        o['courier'] = courier['login']
        o['courier_fio'] = courier['fio']

    def set_status(self, o, status, text=None):
        """Изменить статус()"""
        o['status'] = status
        self.log(o, text or ('Статус заказа: «%s»' % status))


def money(v):
    s = '{:,.2f}'.format(float(v)).replace(',', ' ').replace('.', ',')
    if s.endswith(',00'):
        s = s[:-3]
    return s + ' ₽'
