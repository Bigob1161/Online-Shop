"""
Управляющие классы (control) диаграммы классов:
  «Авторизация», «Работа со списками товаров и сотрудников», «Оформление заказа»,
  «Подбор товаров по заказу», «Распределение заказов», «Слежение за доставкой», «Доставка заказа».
Здесь реализована вся логика, описанная диаграммами деятельности, последовательности и состояний,
включая альтернативные потоки (ошибки ввода, нехватка товара, занятый курьер, отказ, возврат оплаты).
"""
import re
import secrets
import string
from datetime import datetime, timedelta

from storage import check_password, now
from entities import *


class UserError(Exception):
    """Ошибка, текст которой показывается пользователю."""


def need(cond, text):
    if not cond:
        raise UserError(text)


class Messenger:
    """Уведомления и сообщения между участниками процесса."""

    def __init__(self, st):
        self.st = st

    def send(self, to, text, order=None, sender='Система', kind='info'):
        m = {'id': self.st.next_id('message'), 'time': now(), 'to': to, 'text': text,
             'order': order, 'from': sender, 'kind': kind}
        self.st.messages.append(m)
        return m

    def for_user(self, user, since=0):
        keys = (user['login'], '@' + user['role'])
        return [m for m in self.st.messages if m['to'] in keys and m['id'] > since]


# ============================================================================ Авторизация
class Authorization:
    """«control» Авторизация: Логин, Пароль, Роль."""

    def __init__(self, st):
        self.users = UserList(st)
        self.sessions = {}

    def check_login(self, login, password):
        """Проверить логин и пароль()"""
        need(login.strip() and password, 'Введите логин и пароль.')
        u = self.users.find(login)
        if not u or not check_password(password, u['password']):
            raise UserError('Неверный логин или пароль.\nПроверьте раскладку клавиатуры и попробуйте ещё раз.')
        return self.open_subsystem(u)

    def open_subsystem(self, u):
        """Открыть подсистему по роли()"""
        token = secrets.token_hex(16)
        self.sessions[token] = u['login']
        return {'token': token, 'role': u['role'], 'fio': u['fio'], 'login': u['login'],
                'contacts': u['contacts']}

    def check_unique_login(self, login):
        """Проверить уникальность логина()"""
        return self.users.find(login) is None

    def register(self, fio, contacts, login, password, password2):
        """Регистрация нового пользователя (подсистема «Пользователь»)."""
        fio, contacts, login = fio.strip(), contacts.strip(), login.strip()
        need(fio and contacts and login and password, 'Не все поля заполнены.\nЗаполните ФИО, контактные данные, логин и пароль.')
        need(len(fio.split()) >= 2, 'Укажите фамилию и имя полностью.')
        need(re.fullmatch(r'[A-Za-z0-9_.\-]{3,30}', login), 'Логин должен состоять из латинских букв, цифр, точки, дефиса или подчёркивания (от 3 до 30 символов).')
        need(len(password) >= 6, 'Пароль должен содержать не менее 6 символов.')
        need(password == password2, 'Пароли не совпадают.')
        need(self.check_unique_login(login), 'Логин «%s» уже занят. Придумайте другой логин.' % login)
        u = self.users.add_user(fio, contacts, ROLE_CLIENT, login, password)
        return self.open_subsystem(u)

    def user_by_token(self, token):
        login = self.sessions.get(token)
        u = self.users.find(login) if login else None
        if not u:
            raise UserError('Сеанс завершён. Войдите в систему заново.')
        return u


# ============================================================ Работа со списками (администратор)
class ListsManager:
    """«control» Работа со списками товаров и сотрудников: Выбранный товар, Выбранный сотрудник."""

    def __init__(self, st):
        self.st = st
        self.products = ProductList(st)
        self.users = UserList(st)

    # ----- товары
    def check_product(self, d, pid=None):
        """Проверить данные товара()"""
        name = (d.get('name') or '').strip()
        cat = (d.get('category') or '').strip()
        need(name and cat, 'Заполните наименование и категорию товара.')
        try:
            price = float(str(d.get('price')).replace(',', '.'))
            qty = int(d.get('qty'))
        except (TypeError, ValueError):
            raise UserError('Цена и количество должны быть числами.')
        need(price > 0, 'Цена должна быть больше нуля.')
        need(qty >= 0, 'Количество не может быть отрицательным.')
        same = self.products.find_by_name(name)
        need(same is None or same['id'] == pid, 'Товар «%s» уже есть в каталоге.' % name)
        return name, price, qty, cat

    def add_product(self, d):
        name, price, qty, cat = self.check_product(d)
        return self.products.add_product(name, price, qty, cat)

    def update_product(self, pid, d):
        need(self.products.get(pid), 'Товар не найден.')
        name, price, qty, cat = self.check_product(d, pid)
        return self.products.update_product(pid, name=name, price=price, qty=qty, category=cat)

    def unfinished_orders(self, pid=None, courier=None):
        """Проверить незавершённые заказы()"""
        res = []
        for o in self.st.orders:
            if o['status'] in FINISHED:
                continue
            if pid is not None and any(i['product_id'] == pid and i['status'] != POS_EXCLUDED for i in o['items']):
                res.append(o['number'])
            if courier is not None and o['courier'] == courier:
                res.append(o['number'])
        return res

    def delete_product(self, pid):
        need(self.products.get(pid), 'Товар не найден.')
        nums = self.unfinished_orders(pid=pid)
        need(not nums, 'Товар не может быть удалён: он входит в незавершённые заказы № %s.' % ', '.join(map(str, nums)))
        self.products.delete_product(pid)

    # ----- сотрудники
    def check_employee(self, d, login=None):
        """Проверить данные сотрудника()"""
        fio, contacts, role = (d.get('fio') or '').strip(), (d.get('contacts') or '').strip(), d.get('role')
        need(fio and contacts and role, 'Не все поля заполнены. Укажите ФИО, должность и контактные данные.')
        need(role in ROLES_STAFF, 'Выберите должность из списка.')
        if login is None:
            for u in self.users.staff():
                need(u['fio'].lower() != fio.lower() or u['contacts'] != contacts,
                     'Сотрудник «%s» уже зарегистрирован в системе.' % fio)
        return fio, contacts, role

    def make_credentials(self, fio):
        """Сформировать логин и пароль()"""
        tr = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
                      ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's',
                       't', 'u', 'f', 'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))
        parts = fio.lower().split()
        base = ''.join(tr.get(ch, ch) for ch in parts[0]) if parts else 'user'
        if len(parts) > 1:
            base += '.' + tr.get(parts[1][0], parts[1][0])
        base = re.sub(r'[^a-z0-9.]', '', base) or 'user'
        login, n = base, 1
        while self.users.find(login):
            n += 1
            login = '%s%d' % (base, n)
        alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(alphabet) for _ in range(8))
        return login, password

    def add_employee(self, d):
        fio, contacts, role = self.check_employee(d)
        login, password = self.make_credentials(fio)
        self.users.add_user(fio, contacts, role, login, password)
        return {'login': login, 'password': password, 'fio': fio, 'role': role}

    def update_employee(self, login, d, admin_login):
        u = self.users.find(login)
        need(u and u['role'] in ROLES_STAFF, 'Сотрудник не найден.')
        fio, contacts, role = self.check_employee(d, login)
        if u['role'] == 'Курьер' and role != 'Курьер':
            nums = self.unfinished_orders(courier=login)
            need(not nums, 'Нельзя сменить должность: у курьера есть незавершённые заказы № %s.' % ', '.join(map(str, nums)))
        need(not (login == admin_login and role != 'Администратор'), 'Нельзя снять права администратора с самого себя.')
        self.users.update_user(login, fio=fio, contacts=contacts, role=role)
        res = {'login': login, 'password': None}
        if d.get('new_password'):
            pw = self.make_credentials(fio)[1]
            self.users.update_user(login, password=pw)
            res['password'] = pw
        return res

    def delete_employee(self, login, admin_login):
        u = self.users.find(login)
        need(u and u['role'] in ROLES_STAFF, 'Сотрудник не найден.')
        need(login != admin_login, 'Нельзя удалить собственную учётную запись.')
        nums = self.unfinished_orders(courier=login)
        need(not nums, 'Удаление невозможно: у сотрудника есть незавершённые заказы № %s.' % ', '.join(map(str, nums)))
        self.users.delete_user(login)


# ======================================================================== Оформление заказа
class Checkout:
    """«control» Оформление заказа: Адрес доставки, Итоговая стоимость."""

    DECLINE_CARDS = {'4000000000000002'}   # учебная карта для проверки сценария «Оплата не прошла»

    def __init__(self, st, msg):
        self.st = st
        self.products = ProductList(st)
        self.orders = Order(st)
        self.msg = msg

    def analogs(self, p, need_qty=1):
        return [x for x in self.st.products if x['category'] == p['category'] and x['id'] != p['id'] and x['qty'] >= need_qty]

    def check_stock(self, pid, qty):
        """Проверить наличие товара()"""
        p = self.products.get(pid)
        need(p, 'Товар не найден в каталоге.')
        return {'ok': p['qty'] >= qty, 'available': p['qty'], 'product': p,
                'analogs': self.analogs(p, qty)}

    @staticmethod
    def calc_cost(items):
        """Рассчитать стоимость()"""
        return round(sum(i['price'] * i['qty'] for i in items), 2)

    @staticmethod
    def check_address(address, phone):
        """Проверить адрес доставки()"""
        need(address.strip(), 'Не заполнен адрес доставки.')
        need(len(address.strip()) >= 8, 'Укажите адрес полностью: город, улица, дом, квартира.')
        need(re.sub(r'\D', '', phone or '').__len__() >= 10, 'Укажите телефон получателя (не менее 10 цифр).')

    def create_order(self, client, cart, address, recipient, phone, date, comment):
        need(cart, 'Корзина пуста. Добавьте товары из каталога.')
        self.check_address(address, phone)
        need((recipient or '').strip(), 'Укажите получателя заказа.')
        try:
            d = datetime.strptime(date, '%d.%m.%Y').date()
        except (TypeError, ValueError):
            raise UserError('Укажите дату доставки.')
        need(d >= datetime.now().date(), 'Дата доставки не может быть в прошлом.')
        # повторная проверка наличия всех товаров корзины
        items, missing = [], []
        for c in cart:
            r = self.check_stock(int(c['product_id']), int(c['qty']))
            if not r['ok']:
                missing.append('«%s» (в наличии %d шт.)' % (r['product']['name'], r['available']))
            items.append(OrderItem.new(r['product'], int(c['qty'])))
        need(not missing, 'Товар закончился на складе: %s.\nУдалите товар из корзины или замените аналогичным.' % ', '.join(missing))
        for i in items:   # резервирование товаров
            self.products.get(i['product_id'])['qty'] -= i['qty']
        o = self.orders.create(client, items, address.strip(), recipient.strip(), phone.strip(), date, (comment or '').strip())
        return o

    @staticmethod
    def luhn(num):
        total, alt = 0, False
        for ch in reversed(num):
            d = int(ch)
            if alt:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
            alt = not alt
        return total % 10 == 0

    def pay(self, client, number, card, exp, cvv, holder):
        """Провести оплату()"""
        o = self.orders.get(number)
        need(o and o['client'] == client['login'], 'Заказ не найден.')
        need(o['pay_status'] == PAY_NO and o['status'] == ST_NEW, 'Заказ уже оплачен или отменён.')
        num = re.sub(r'\D', '', card or '')
        need(len(num) == 16, 'Номер карты должен содержать 16 цифр.')
        need(self.luhn(num), 'Номер карты введён с ошибкой. Проверьте цифры.')
        m = re.fullmatch(r'\s*(\d{2})\s*/\s*(\d{2})\s*', exp or '')
        need(m and 1 <= int(m.group(1)) <= 12, 'Срок действия карты укажите в формате ММ/ГГ.')
        month, year = int(m.group(1)), 2000 + int(m.group(2))
        today = datetime.now()
        need((year, month) >= (today.year, today.month), 'Срок действия карты истёк.')
        need(re.fullmatch(r'\d{3}', cvv or ''), 'CVC/CVV — три цифры на обратной стороне карты.')
        need((holder or '').strip(), 'Укажите имя владельца карты.')
        if num in self.DECLINE_CARDS:
            self.orders.log(o, 'Попытка оплаты отклонена банком')
            raise UserError('Оплата не прошла: банк отклонил операцию.\nПроверьте баланс карты или используйте другую карту.')
        self.orders.pay(o, num[-4:])
        self.msg.send('@Кладовщик', 'Новый оплаченный заказ № %d ожидает сборки.' % o['number'], o['number'])
        self.msg.send('@Диспетчер', 'Поступил новый заказ № %d (оплачен).' % o['number'], o['number'])
        return o

    def cancel_by_client(self, client, number, reason):
        o = self.orders.get(number)
        need(o and o['client'] == client['login'], 'Заказ не найден.')
        need(o['status'] in (ST_NEW, ST_PAID, ST_PICKING),
             'Заказ уже передан в доставку и не может быть отменён через программу. Откажитесь от заказа при получении.')
        return cancel_order(self.st, self.msg, o, reason or 'Клиент отказался от заказа')


def cancel_order(st, msg, o, reason):
    """Отмена заказа: возврат товаров на склад и возврат оплаты клиенту."""
    orders, products = Order(st), ProductList(st)
    for i in o['items']:
        if i['status'] != POS_EXCLUDED:
            p = products.get(i['product_id'])
            if p:
                p['qty'] += i['qty']
    refunded = orders.refund(o, reason='отмена заказа')
    if o['courier'] and not busy_orders(st, o['courier'], exclude=o['number']):
        Courier(st).set_status(o['courier'], COURIER_FREE)
    orders.set_status(o, ST_CANCELLED, 'Заказ отменён: %s. Товары возвращены на склад.' % reason)
    txt = 'Заказ № %d отменён (%s).' % (o['number'], reason)
    if refunded:
        txt += ' Оплата %s возвращена на карту •••• %s.' % (money(refunded), o['card'])
    msg.send(o['client'], txt, o['number'])
    msg.send('@Диспетчер', txt, o['number'])
    return {'refunded': refunded}


def busy_orders(st, courier, exclude=None):
    return [o['number'] for o in st.orders if o['courier'] == courier and o['status'] in (ST_HANDED, ST_ON_WAY)
            and o['number'] != exclude]


# ================================================================== Подбор товаров по заказу
class Picking:
    """«control» Подбор товаров по заказу: Номер заказа, Недостающий товар."""

    def __init__(self, st, msg):
        self.st, self.msg = st, msg
        self.orders = Order(st)
        self.products = ProductList(st)

    def list_orders(self):
        return [o for o in self.st.orders if o['status'] in (ST_PAID, ST_PICKING)]

    def open(self, number):
        o = self.orders.get(number)
        need(o and o['status'] in (ST_PAID, ST_PICKING), 'Заказ недоступен для сборки.')
        if o['status'] == ST_PAID:
            self.orders.set_status(o, ST_PICKING, 'Кладовщик начал сборку заказа')
        return o

    def _item(self, number, idx):
        o = self.orders.get(number)
        need(o and o['status'] == ST_PICKING, 'Сначала откройте заказ для сборки.')
        need(0 <= idx < len(o['items']), 'Позиция не найдена.')
        return o, o['items'][idx]

    def check_stock(self, number, idx):
        """Проверить наличие на складе() — товара достаточно: позиция отбирается."""
        o, it = self._item(number, idx)
        need(it['status'] == POS_WAIT, 'Эта позиция уже обработана.')
        OrderItem.mark_picked(it)
        self.orders.log(o, 'Позиция «%s» отобрана со склада' % it['name'])
        return o

    def appeal(self, number, idx, available, comment, sender):
        """Отправить обращение диспетчеру() — товара не хватает."""
        o, it = self._item(number, idx)
        need(it['status'] == POS_WAIT, 'По этой позиции уже принято решение или она отобрана.')
        need(0 <= int(available) < it['qty'], 'Укажите, сколько единиц фактически есть на складе (меньше, чем в заказе).')
        it['status'] = POS_SHORT
        it['note'] = 'На складе %d из %d шт.' % (int(available), it['qty'])
        a = {'id': self.st.next_id('appeal'), 'time': now(), 'order': o['number'], 'idx': idx,
             'product': it['name'], 'product_id': it['product_id'], 'need': it['qty'], 'available': int(available),
             'comment': comment.strip(), 'from': sender['fio'], 'status': 'Открыто', 'decision': ''}
        self.st.appeals.append(a)
        self.orders.log(o, 'Нехватка товара «%s»: %s. Обращение к диспетчеру' % (it['name'], it['note']))
        self.msg.send('@Диспетчер', 'Кладовщик: не хватает товара «%s» в заказе № %d (на складе %d из %d шт.). Требуется решение.'
                      % (it['name'], o['number'], int(available), it['qty']), o['number'], sender['fio'], 'warn')
        return a

    def check_all(self, number):
        """Проверить все позиции() и присвоить статус «Собран»."""
        o = self.orders.get(number)
        need(o and o['status'] == ST_PICKING, 'Заказ не находится на сборке.')
        rest = [i['name'] for i in o['items'] if i['status'] in (POS_WAIT, POS_SHORT)]
        need(not rest, 'Не все позиции обработаны: %s.' % ', '.join('«%s»' % r for r in rest))
        need(any(i['status'] == POS_PICKED for i in o['items']), 'В заказе не осталось ни одной позиции. Обратитесь к диспетчеру для отмены заказа.')
        self.orders.set_status(o, ST_ASSEMBLED, 'Заказ собран и передан диспетчеру')
        self.msg.send('@Диспетчер', 'Заказ № %d собран и ожидает назначения курьера.' % o['number'], o['number'])
        self.msg.send(o['client'], 'Ваш заказ № %d собран. Скоро курьер отправится к вам.' % o['number'], o['number'])
        return o


# ================================================================== Распределение заказов
class Distribution:
    """«control» Распределение заказов: Выбранный заказ, Выбранный курьер."""

    def __init__(self, st, msg):
        self.st, self.msg = st, msg
        self.orders = Order(st)
        self.couriers = Courier(st)
        self.products = ProductList(st)

    def assembled(self):
        return [o for o in self.st.orders if o['status'] == ST_ASSEMBLED]

    def free_couriers(self):
        """Найти свободных курьеров()"""
        return [c for c in self.couriers.all() if c.get('status') == COURIER_FREE]

    def check_courier(self, login):
        """Проверить доступность курьера()"""
        c = self.couriers.find(login)
        need(c, 'Курьер не найден.')
        need(c.get('status') == COURIER_FREE and not busy_orders(self.st, login),
             'Курьер %s занят. Выберите другого курьера.' % c['fio'])
        return c

    def assign(self, number, login, date=None):
        o = self.orders.get(number)
        need(o and o['status'] in (ST_ASSEMBLED, ST_NOT_DELIVERED), 'Заказ недоступен для назначения курьера.')
        need(self.free_couriers(), 'Нет свободных курьеров. Заказ остаётся в очереди.')
        c = self.check_courier(login)
        if date:
            o['delivery_date'] = date
        self.orders.assign_courier(o, c)
        self.orders.set_status(o, ST_HANDED, 'Передан в доставку курьеру %s, дата доставки %s' % (c['fio'], o['delivery_date']))
        self.couriers.set_status(login, COURIER_BUSY)
        self.msg.send(login, 'Вам назначен новый заказ № %d. Адрес: %s.' % (o['number'], o['address']), o['number'], 'Диспетчер')
        self.msg.send(o['client'], 'Заказ № %d передан курьеру %s. Дата доставки: %s.' % (o['number'], c['fio'], o['delivery_date']), o['number'])
        return o

    # ----- решения по обращениям кладовщика
    def decide(self, appeal_id, decision, replacement_id=None, qty=None):
        a = next((x for x in self.st.appeals if x['id'] == appeal_id), None)
        need(a and a['status'] == 'Открыто', 'Обращение не найдено или уже обработано.')
        o = self.orders.get(a['order'])
        it = o['items'][a['idx']]
        p = self.products.get(a['product_id'])
        old_cost = o['cost']
        if decision == 'reduce':
            q = int(qty if qty is not None else a['available'])
            need(1 <= q <= a['available'], 'Новое количество должно быть от 1 до %d.' % a['available'])
            if p:
                p['qty'] = a['available'] - q   # фактический остаток на складе
            OrderItem.change_qty(it, q)
            text = 'количество товара «%s» уменьшено до %d шт.' % (it['name'], q)
        elif decision == 'exclude':
            if p:
                p['qty'] = a['available']
            OrderItem.exclude(it)
            text = 'позиция «%s» исключена из заказа' % it['name']
        elif decision == 'replace':
            r = self.products.get(int(replacement_id or 0))
            need(r and r['id'] != a['product_id'], 'Выберите товар для замены.')
            need(r['qty'] >= it['qty'], 'Товара «%s» недостаточно на складе (в наличии %d шт.).' % (r['name'], r['qty']))
            if p:
                p['qty'] = a['available']
            r['qty'] -= it['qty']
            OrderItem.exclude(it)
            new = OrderItem.new(r, it['qty'])
            new['price'] = min(r['price'], it['price'])   # замена по цене исходного товара
            new['note'] = 'Замена товара «%s»' % it['name']
            o['items'].append(new)
            text = 'товар «%s» заменён на «%s»' % (it['name'], r['name'])
        else:
            raise UserError('Выберите решение.')
        self.orders.recalc(o)
        a['status'] = 'Решено'
        a['decision'] = text
        self.orders.log(o, 'Решение диспетчера: ' + text)
        diff = round(old_cost - o['cost'], 2)
        extra = ''
        if diff > 0 and o['pay_status'] == PAY_YES:
            self.orders.refund(o, diff, 'изменение состава заказа')
            extra = ' Разница %s возвращена на карту.' % money(diff)
        self.msg.send('@Кладовщик', 'Решение по заказу № %d: %s. Обновите список товаров заказа.' % (o['number'], text), o['number'], 'Диспетчер')
        self.msg.send(o['client'], 'Состав заказа № %d изменён: %s.%s' % (o['number'], text, extra), o['number'], 'Диспетчер')
        return o

    # ----- возвращённые заказы
    def returned(self):
        return [o for o in self.st.orders if o['status'] == ST_NOT_DELIVERED]

    def cancel(self, number, reason):
        o = self.orders.get(number)
        need(o and o['status'] not in FINISHED, 'Заказ не найден или уже завершён.')
        need(o['status'] not in (ST_HANDED, ST_ON_WAY), 'Заказ находится у курьера. Дождитесь его возврата.')
        return cancel_order(self.st, self.msg, o, reason or 'отменён диспетчером')


# ================================================================== Слежение за доставкой
class Tracking:
    """«control» Слежение за доставкой: Статус заказа, Местоположение курьера."""

    LOST_AFTER = timedelta(minutes=30)

    def __init__(self, st, msg):
        self.st, self.msg = st, msg
        self.orders = Order(st)
        self.couriers = Courier(st)

    def in_delivery(self):
        return [o for o in self.st.orders if o['status'] in (ST_HANDED, ST_ON_WAY)]

    def get_status(self, number):
        """Получить статус заказа() и Получить местоположение курьера()"""
        o = self.orders.get(number)
        need(o, 'Заказ не найден.')
        c = self.couriers.find(o['courier']) if o['courier'] else None
        loc, lost = '', True
        if c and c.get('location') and c.get('location_time'):
            t = datetime.strptime(c['location_time'], '%d.%m.%Y %H:%M')
            lost = datetime.now() - t > self.LOST_AFTER
            loc = '%s (обновлено %s)' % (c['location'], c['location_time'])
        return {'order': o, 'courier': UserList.public(c) if c else None, 'location': loc, 'lost': lost}

    def message_client(self, number, text, sender):
        """Отправить сообщение клиенту()"""
        o = self.orders.get(number)
        need(o, 'Заказ не найден.')
        need(text.strip(), 'Введите текст сообщения.')
        self.msg.send(o['client'], 'Сообщение по заказу № %d: %s' % (o['number'], text.strip()), o['number'], 'Диспетчер ' + sender['fio'], 'chat')
        self.orders.log(o, 'Диспетчер отправил сообщение клиенту')

    def message_courier(self, login, text, sender, number=None):
        c = self.couriers.find(login)
        need(c, 'Курьер не найден.')
        need(text.strip(), 'Введите текст сообщения.')
        self.msg.send(login, text.strip(), number, 'Диспетчер ' + sender['fio'], 'chat')

    def reassign(self, number, login):
        o = self.orders.get(number)
        need(o and o['status'] in (ST_HANDED, ST_ON_WAY), 'Заказ не находится в доставке.')
        need(o['courier'] != login, 'Заказ уже назначен этому курьеру.')
        c = Distribution(self.st, self.msg).check_courier(login)
        old = o['courier']
        self.orders.assign_courier(o, c)
        self.orders.set_status(o, ST_HANDED, 'Заказ переназначен курьеру %s' % c['fio'])
        self.couriers.set_status(login, COURIER_BUSY)
        if old and not busy_orders(self.st, old):
            self.couriers.set_status(old, COURIER_FREE)
        if old:
            self.msg.send(old, 'Заказ № %d переназначен другому курьеру.' % o['number'], o['number'], 'Диспетчер', 'warn')
        self.msg.send(login, 'Вам назначен заказ № %d. Адрес: %s.' % (o['number'], o['address']), o['number'], 'Диспетчер')
        return o


# ======================================================================== Доставка заказа
class Delivery:
    """«control» Доставка заказа: Номер заказа, Статус заказа."""

    def __init__(self, st, msg):
        self.st, self.msg = st, msg
        self.orders = Order(st)
        self.couriers = Courier(st)

    def my_orders(self, courier):
        return [o for o in self.st.orders if o['courier'] == courier['login'] and o['status'] in (ST_HANDED, ST_ON_WAY)]

    def history(self, courier):
        return [o for o in self.st.orders if o['courier'] == courier['login'] and o['status'] not in (ST_HANDED, ST_ON_WAY)][-30:]

    def _own(self, courier, number, statuses):
        o = self.orders.get(number)
        need(o and o['courier'] == courier['login'], 'Заказ вам не назначен.')
        need(o['status'] in statuses, 'Действие недоступно для заказа в статусе «%s».' % o['status'])
        return o

    def notify_dispatcher(self, text, number, courier, kind='info'):
        """Уведомить диспетчера()"""
        self.msg.send('@Диспетчер', text, number, 'Курьер ' + courier['fio'], kind)

    def accept(self, courier, number):
        o = self._own(courier, number, (ST_HANDED,))
        self.change_status(o, ST_ON_WAY, 'Курьер принял заказ, заказ в пути')
        self.msg.send(o['client'], 'Курьер %s везёт ваш заказ № %d.' % (courier['fio'], o['number']), o['number'])
        return o

    def reject(self, courier, number, reason):
        o = self._own(courier, number, (ST_HANDED,))
        need(reason.strip(), 'Укажите причину отказа.')
        o['courier'], o['courier_fio'] = '', ''
        self.change_status(o, ST_ASSEMBLED, 'Курьер %s отклонил заказ: %s. Заказ возвращён в очередь' % (courier['fio'], reason))
        if not busy_orders(self.st, courier['login']):
            self.couriers.set_status(courier['login'], COURIER_FREE)
        self.notify_dispatcher('Курьер отклонил заказ № %d (%s). Заказ возвращён в очередь на распределение.' % (o['number'], reason),
                               o['number'], courier, 'warn')
        return o

    def change_status(self, o, status, text):
        """Изменить статус заказа()"""
        self.orders.set_status(o, status, text)

    def delivered(self, courier, number):
        o = self._own(courier, number, (ST_ON_WAY,))
        self.change_status(o, ST_DELIVERED, 'Заказ вручён получателю')
        if not busy_orders(self.st, courier['login']):
            self.couriers.set_status(courier['login'], COURIER_FREE)
        self.notify_dispatcher('Заказ № %d доставлен и вручён получателю.' % o['number'], o['number'], courier, 'ok')
        self.msg.send(o['client'], 'Заказ № %d доставлен. Спасибо за покупку!' % o['number'], o['number'], kind='ok')
        return o

    def not_delivered(self, courier, number, reason, action):
        o = self._own(courier, number, (ST_ON_WAY,))
        need(reason, 'Укажите причину.')
        if action == 'later':
            self.orders.log(o, 'Не удалось вручить (%s). Курьер повторит попытку позже' % reason)
            self.notify_dispatcher('Заказ № %d: не удалось вручить (%s). Курьер повторит попытку позже.' % (o['number'], reason),
                                   o['number'], courier, 'warn')
            return o
        o['fail_reason'] = reason
        self.change_status(o, ST_NOT_DELIVERED, 'Не доставлен: %s. Заказ возвращается на склад и диспетчеру' % reason)
        if not busy_orders(self.st, courier['login']):
            self.couriers.set_status(courier['login'], COURIER_FREE)
        self.notify_dispatcher('Заказ № %d не доставлен (%s). Заказ возвращён, требуется решение: повторная доставка или отмена.'
                               % (o['number'], reason), o['number'], courier, 'warn')
        self.msg.send(o['client'], 'Не удалось вручить заказ № %d (%s). Диспетчер свяжется с вами.' % (o['number'], reason), o['number'], kind='warn')
        return o

    def redeliver(self, number, date, courier_login):
        """Повторить доставку / Назначить новую дату доставки (решение диспетчера)."""
        o = self.orders.get(number)
        need(o and o['status'] == ST_NOT_DELIVERED, 'Заказ не находится среди возвращённых.')
        try:
            d = datetime.strptime(date, '%d.%m.%Y').date()
        except (TypeError, ValueError):
            raise UserError('Укажите новую дату доставки.')
        need(d >= datetime.now().date(), 'Дата доставки не может быть в прошлом.')
        o['fail_reason'] = ''
        return Distribution(self.st, self.msg).assign(number, courier_login, date)
