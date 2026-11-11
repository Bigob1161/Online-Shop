"""Соединение клиентской части с сервером по протоколу TCP/IP (JSON-строки)."""
import json
import os
import socket

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client_config.json')


class ApiError(Exception):
    """Ошибка, которую нужно показать пользователю."""


class Connection:
    def __init__(self):
        self.host, self.port = '127.0.0.1', 5050
        self.token = None
        self.user = None
        self.load_config()

    def load_config(self):
        try:
            with open(CONFIG, encoding='utf-8') as f:
                c = json.load(f)
            self.host, self.port = c.get('host', self.host), int(c.get('port', self.port))
        except (OSError, ValueError):
            pass

    def save_config(self, host, port):
        self.host, self.port = host.strip(), int(port)
        with open(CONFIG, 'w', encoding='utf-8') as f:
            json.dump({'host': self.host, 'port': self.port}, f, ensure_ascii=False, indent=2)

    def request(self, cmd, **params):
        params['cmd'] = cmd
        if self.token:
            params['token'] = self.token
        data = (json.dumps(params, ensure_ascii=False) + '\n').encode('utf-8')
        try:
            with socket.create_connection((self.host, self.port), timeout=6) as s:
                s.sendall(data)
                buf = b''
                while not buf.endswith(b'\n'):
                    chunk = s.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
        except OSError:
            raise ApiError('Нет связи с сервером (%s:%s).\n\nПроверьте, что сервер запущен и компьютер подключён к сети. '
                           'Адрес сервера можно изменить в окне входа: «Настройки подключения».' % (self.host, self.port))
        try:
            resp = json.loads(buf.decode('utf-8'))
        except ValueError:
            raise ApiError('Сервер прислал некорректный ответ. Повторите попытку.')
        if not resp.get('ok'):
            raise ApiError(resp.get('error') or 'Неизвестная ошибка.')
        return resp.get('data')


api = Connection()
