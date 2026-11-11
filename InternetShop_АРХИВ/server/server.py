"""
Серверная часть информационной системы «Интернет-магазин. Доставка товаров».

Запуск:  python server.py            (порт по умолчанию 5050)
         python server.py 6000       (другой порт)

Клиенты (client.py) подключаются к серверу по сети по протоколу TCP/IP.
Обмен — JSON-сообщения, одна строка на запрос и одна строка на ответ.
При запуске данные считываются из файлов в память, при остановке (Ctrl+C или закрытие окна)
записываются обратно; кроме того, после каждого изменения файлы создаются заново,
чтобы данные не потерялись при внезапном отключении питания.
"""
import json
import os
import signal
import socket
import socketserver
import sys
import threading
import atexit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage import Storage, now
from entities import *
from controls import (UserError, Messenger, Authorization, ListsManager, Checkout, Picking,
                      Distribution, Tracking, Delivery)

HOST = '0.0.0.0'
PORT = 5050


def pub_order(o):
    return o


class App:
    """Ядро сервера: таблицы в памяти + управляющие классы."""

    def __init__(self, data_dir=None):
        self.st = Storage(data_dir) if data_dir else Storage()
        self.st.load()
        self.lock = threading.RLock()
        self.msg = Messenger(self.st)
        self.auth = Authorization(self.st)
        self.lists = ListsManager(self.st)
        self.checkout = Checkout(self.st, self.msg)
        self.picking = Picking(self.st, self.msg)
        self.distr = Distribution(self.st, self.msg)
        self.track = Tracking(self.st, self.msg)
        self.deliv = Delivery(self.st, self.msg)
        self.couriers = Courier(self.st)
        self.orders = Order(self.st)

    # роль -> разрешённые команды
    ROLE_CMDS = {
        'Администратор': {'products', 'product_add', 'product_update', 'product_delete', 'employees',
                          'employee_add', 'employee_update', 'employee_delete', 'save', 'all_orders'},
        'Кладовщик': {'products', 'wh_orders', 'wh_open', 'wh_pick', 'wh_shortage', 'wh_done', 'wh_message', 'order'},
        'Диспетчер': {'products', 'assembled', 'couriers', 'free_couriers', 'assign', 'in_delivery', 'track',
                      'msg_client', 'msg_courier', 'reassign', 'appeals', 'decide', 'returned', 'redeliver',
                      'cancel_order', 'all_orders', 'order'},
        'Курьер': {'my_tasks', 'accept', 'reject', 'set_location', 'delivered', 'not_delivered', 'courier_info', 'msg_dispatcher'},
        'Клиент': {'products', 'check_stock', 'create_order', 'pay', 'my_orders', 'client_cancel', 'msg_dispatcher'},
    }
    PUBLIC = {'ping', 'login', 'register'}
    CHANGING = {'register', 'product_add', 'product_update', 'product_delete', 'employee_add', 'employee_update',
                'employee_delete', 'create_order', 'pay', 'client_cancel', 'wh_open', 'wh_pick', 'wh_shortage',
                'wh_done', 'wh_message', 'assign', 'msg_client', 'msg_courier', 'reassign', 'decide', 'redeliver',
                'cancel_order', 'accept', 'reject', 'set_location', 'delivered', 'not_delivered', 'msg_dispatcher', 'save'}

    def handle(self, req):
        cmd = req.get('cmd')
        with self.lock:
            try:
                if cmd in self.PUBLIC:
                    data = getattr(self, 'c_' + cmd)(req)
                else:
                    user = self.auth.user_by_token(req.get('token'))
                    if cmd == 'notifications':
                        data = self.c_notifications(req, user)
                    elif cmd == 'logout':
                        self.auth.sessions.pop(req.get('token'), None)
                        data = True
                    else:
                        if cmd not in self.ROLE_CMDS.get(user['role'], ()):
                            raise UserError('Эта операция недоступна для вашей роли.')
                        data = getattr(self, 'c_' + cmd)(req, user)
                if cmd in self.CHANGING:
                    self.st.save()
                return {'ok': True, 'data': data}
            except UserError as e:
                return {'ok': False, 'error': str(e)}
            except Exception as e:   # непредвиденная ошибка — не роняем сервер
                import traceback
                traceback.print_exc()
                return {'ok': False, 'error': 'Внутренняя ошибка сервера: %s' % e}

    # ------------------------------------------------------------ общие команды
    def c_ping(self, r):
        return {'time': now()}

    def c_login(self, r):
        return self.auth.check_login(r.get('login', ''), r.get('password', ''))

    def c_register(self, r):
        return self.auth.register(r.get('fio', ''), r.get('contacts', ''), r.get('login', ''),
                                  r.get('password', ''), r.get('password2', ''))

    def c_notifications(self, r, u):
        return self.msg.for_user(u, int(r.get('since', 0)))

    def c_products(self, r, u):
        return self.st.products

    def c_order(self, r, u):
        o = self.orders.get(r['number'])
        if not o:
            raise UserError('Заказ не найден.')
        return o

    def c_all_orders(self, r, u):
        return self.st.orders

    def c_msg_dispatcher(self, r, u):
        text = (r.get('text') or '').strip()
        if not text:
            raise UserError('Введите текст сообщения.')
        n = r.get('number')
        self.msg.send('@Диспетчер', text, n, '%s %s' % (u['role'], u['fio']), 'chat')
        return True

    # ---------------------------------------------------------- администратор
    def c_product_add(self, r, u):
        return self.lists.add_product(r['data'])

    def c_product_update(self, r, u):
        return self.lists.update_product(int(r['id']), r['data'])

    def c_product_delete(self, r, u):
        self.lists.delete_product(int(r['id']))
        return True

    def c_employees(self, r, u):
        return [UserList.public(x) for x in self.lists.users.staff()]

    def c_employee_add(self, r, u):
        return self.lists.add_employee(r['data'])

    def c_employee_update(self, r, u):
        return self.lists.update_employee(r['login'], r['data'], u['login'])

    def c_employee_delete(self, r, u):
        self.lists.delete_employee(r['login'], u['login'])
        return True

    def c_save(self, r, u):
        return {'time': now()}

    # ------------------------------------------------------------------ клиент
    def c_check_stock(self, r, u):
        res = self.checkout.check_stock(int(r['product_id']), int(r.get('qty', 1)))
        return res

    def c_create_order(self, r, u):
        return self.checkout.create_order(u, r.get('cart', []), r.get('address', ''), r.get('recipient', ''),
                                          r.get('phone', ''), r.get('date', ''), r.get('comment', ''))

    def c_pay(self, r, u):
        return self.checkout.pay(u, int(r['number']), r.get('card'), r.get('exp'), r.get('cvv'), r.get('holder'))

    def c_my_orders(self, r, u):
        return [o for o in self.st.orders if o['client'] == u['login']]

    def c_client_cancel(self, r, u):
        return self.checkout.cancel_by_client(u, int(r['number']), r.get('reason', ''))

    # --------------------------------------------------------------- кладовщик
    def c_wh_orders(self, r, u):
        return self.picking.list_orders()

    def c_wh_open(self, r, u):
        return self.picking.open(int(r['number']))

    def c_wh_pick(self, r, u):
        return self.picking.check_stock(int(r['number']), int(r['idx']))

    def c_wh_shortage(self, r, u):
        return self.picking.appeal(int(r['number']), int(r['idx']), int(r['available']), r.get('comment', ''), u)

    def c_wh_done(self, r, u):
        return self.picking.check_all(int(r['number']))

    def c_wh_message(self, r, u):
        return self.c_msg_dispatcher(r, u)

    # --------------------------------------------------------------- диспетчер
    def c_assembled(self, r, u):
        return self.distr.assembled()

    def c_couriers(self, r, u):
        res = []
        for c in self.couriers.all():
            d = UserList.public(c)
            d['orders'] = [o['number'] for o in self.st.orders if o['courier'] == c['login'] and o['status'] in (ST_HANDED, ST_ON_WAY)]
            res.append(d)
        return res

    def c_free_couriers(self, r, u):
        return [UserList.public(c) for c in self.distr.free_couriers()]

    def c_assign(self, r, u):
        return self.distr.assign(int(r['number']), r['courier'])

    def c_in_delivery(self, r, u):
        return self.track.in_delivery()

    def c_track(self, r, u):
        return self.track.get_status(int(r['number']))

    def c_msg_client(self, r, u):
        self.track.message_client(int(r['number']), r.get('text', ''), u)
        return True

    def c_msg_courier(self, r, u):
        self.track.message_courier(r['courier'], r.get('text', ''), u, r.get('number'))
        return True

    def c_reassign(self, r, u):
        return self.track.reassign(int(r['number']), r['courier'])

    def c_appeals(self, r, u):
        return [a for a in self.st.appeals if a['status'] == 'Открыто' or r.get('all')]

    def c_decide(self, r, u):
        return self.distr.decide(int(r['id']), r.get('decision'), r.get('replacement'), r.get('qty'))

    def c_returned(self, r, u):
        return self.distr.returned()

    def c_redeliver(self, r, u):
        return self.deliv.redeliver(int(r['number']), r.get('date'), r.get('courier'))

    def c_cancel_order(self, r, u):
        return self.distr.cancel(int(r['number']), r.get('reason', ''))

    # ------------------------------------------------------------------- курьер
    def c_courier_info(self, r, u):
        return UserList.public(u)

    def c_my_tasks(self, r, u):
        return {'active': self.deliv.my_orders(u), 'history': self.deliv.history(u), 'me': UserList.public(u)}

    def c_accept(self, r, u):
        return self.deliv.accept(u, int(r['number']))

    def c_reject(self, r, u):
        return self.deliv.reject(u, int(r['number']), r.get('reason', ''))

    def c_set_location(self, r, u):
        loc = (r.get('location') or '').strip()
        if not loc:
            raise UserError('Введите текущее местоположение (адрес или ориентир).')
        self.couriers.update_location(u['login'], loc)
        return UserList.public(u)

    def c_delivered(self, r, u):
        return self.deliv.delivered(u, int(r['number']))

    def c_not_delivered(self, r, u):
        return self.deliv.not_delivered(u, int(r['number']), r.get('reason', ''), r.get('action', 'return'))


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        while True:
            line = self.rfile.readline()
            if not line:
                break
            try:
                req = json.loads(line.decode('utf-8'))
                resp = self.server.app.handle(req)
            except json.JSONDecodeError:
                resp = {'ok': False, 'error': 'Неверный формат запроса.'}
            self.wfile.write((json.dumps(resp, ensure_ascii=False) + '\n').encode('utf-8'))
            self.wfile.flush()


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def local_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    ips.add('127.0.0.1')
    return sorted(ips)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    app = App()
    srv = Server((HOST, port), Handler)
    srv.app = app

    def stop(*_):
        with app.lock:
            app.st.save()
        print('\nДанные сохранены в файлы. Сервер остановлен.')
        os._exit(0)

    atexit.register(lambda: app.st.save())
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, stop)
    print('=' * 64)
    print('  Сервер интернет-магазина запущен')
    print('  Порт: %d' % port)
    print('  Адрес для подключения с других компьютеров: %s' % ', '.join(local_ips()))
    print('  Данные: %s' % app.st.data_dir)
    print('  Чтобы остановить сервер и сохранить данные, нажмите Ctrl+C')
    print('=' * 64)
    srv.serve_forever()


if __name__ == '__main__':
    main()
