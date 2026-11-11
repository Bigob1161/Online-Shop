"""
Клиентская часть информационной системы «Интернет-магазин. Доставка товаров».

Запуск:  python client.py
Окно «Вход в систему» (граничный класс «Вход в систему»): ввод логина и пароля, регистрация,
затем открывается подсистема в соответствии с ролью пользователя.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QSpinBox

from net import api, ApiError
from ui import (setup_app, btn, label, line, hbox, vbox, FormDialog, error, info, app_icon, ACCENT, MUTED)


class SettingsDialog(FormDialog):
    """Настройки подключения к серверу."""

    def __init__(self, parent):
        super().__init__(parent, 'Настройки подключения',
                         'Укажите адрес компьютера, на котором запущен сервер. Если сервер работает на этом же компьютере — 127.0.0.1.')
        self.host = self.add('Адрес сервера', line(api.host, '127.0.0.1'))
        self.port = self.add('Порт', QSpinBox())
        self.port.setRange(1, 65535)
        self.port.setValue(api.port)
        self.test = btn('Проверить связь', 'secondary', self.check)
        self.lay.insertWidget(self.lay.count() - 2, self.test)

    def check(self):
        old = api.host, api.port
        api.host, api.port = self.host.text().strip(), self.port.value()
        try:
            api.request('ping')
            info(self, 'Соединение с сервером установлено.')
        except ApiError as e:
            self.show_error(str(e))
        api.host, api.port = old

    def on_ok(self):
        if not self.host.text().strip():
            return self.show_error('Укажите адрес сервера.')
        api.save_config(self.host.text(), self.port.value())
        self.accept()


class RegisterDialog(FormDialog):
    """Форма регистрации нового пользователя (диаграмма деятельности «Регистрация»)."""

    def __init__(self, parent):
        super().__init__(parent, 'Регистрация', 'Создайте учётную запись, чтобы оформлять заказы с доставкой.',
                         ok_text='Зарегистрироваться', width=480)
        self.fio = self.add('ФИО', line('', 'Иванов Иван Иванович'))
        self.contacts = self.add('Телефон или e-mail', line('', '+7 900 000-00-00'))
        self.login = self.add('Логин', line('', 'латинские буквы и цифры'))
        self.pw = self.add('Пароль', line('', 'не менее 6 символов', True))
        self.pw2 = self.add('Повтор пароля', line('', '', True))
        self.cancel.setText('Выход из формы')
        self.result_user = None

    def on_ok(self):
        # «Проверка корректности и уникальности данных»
        try:
            self.result_user = api.request('register', fio=self.fio.text(), contacts=self.contacts.text(),
                                           login=self.login.text(), password=self.pw.text(), password2=self.pw2.text())
        except ApiError as e:
            # альтернативный поток: «Получение сообщения об ошибке» -> повторный ввод
            self.show_error(str(e))
            return
        self.accept()


class LoginWindow(QWidget):
    """«boundary» Вход в систему: Поле «Логин», Поле «Пароль», Кнопка «Войти», Кнопка «Регистрация»."""

    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.setObjectName('page')
        self.setWindowTitle('Интернет-магазин — Вход в систему')
        self.setWindowIcon(app_icon())
        self.resize(980, 640)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # левая информационная панель
        left = QFrame()
        left.setStyleSheet('QFrame { background: %s; } QLabel { color: white; }' % ACCENT)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(46, 46, 46, 46)
        logo = label('')
        logo.setPixmap(app_icon().pixmap(52, 52))
        lv.addWidget(logo)
        lv.addSpacing(18)
        t = label('Интернет-магазин', None)
        t.setStyleSheet('font-size: 30px; font-weight: 700; color: white;')
        lv.addWidget(t)
        s = label('Заказ, оплата и доставка товаров', None)
        s.setStyleSheet('font-size: 16px; color: #DCE6FF;')
        lv.addWidget(s)
        lv.addStretch(1)
        for line_text in ('Каталог товаров и корзина', 'Безопасная оплата картой', 'Сборка заказа на складе',
                          'Доставка курьером и отслеживание'):
            l = label('—  ' + line_text)
            l.setStyleSheet('font-size: 14px; color: #EEF3FF; padding: 3px 0;')
            lv.addWidget(l)
        root.addWidget(left, 5)
        # форма входа
        right = QWidget()
        right.setObjectName('page')
        rv = QVBoxLayout(right)
        rv.setContentsMargins(70, 40, 70, 30)
        rv.addStretch(1)
        rv.addWidget(label('Вход в систему', 'title'))
        rv.addWidget(label('Введите логин и пароль, выданные администратором, или зарегистрируйтесь как покупатель.', 'muted', True))
        rv.addSpacing(16)
        rv.addWidget(label('Логин', 'muted'))
        self.login = line('', 'Ваш логин')
        rv.addWidget(self.login)
        rv.addSpacing(6)
        rv.addWidget(label('Пароль', 'muted'))
        self.password = line('', 'Ваш пароль', True)
        rv.addWidget(self.password)
        self.err = label('', 'error', True)
        self.err.hide()
        rv.addWidget(self.err)
        rv.addSpacing(10)
        self.enter = btn('Войти', 'primary', self.do_login)
        self.enter.setMinimumHeight(40)
        rv.addWidget(self.enter)
        rv.addSpacing(6)
        reg = btn('Регистрация', 'secondary', self.do_register)
        reg.setMinimumHeight(40)
        rv.addWidget(reg)
        rv.addStretch(1)
        rv.addWidget(hbox(btn('Настройки подключения', 'link', self.do_settings), 'stretch', btn('Выход', 'link', self.close)))
        root.addWidget(right, 6)
        self.login.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self.do_login)

    def set_invalid(self, flag):
        for w in (self.login, self.password):
            w.setProperty('invalid', flag)
            w.style().unpolish(w)
            w.style().polish(w)

    def do_login(self):
        try:
            res = api.request('login', login=self.login.text(), password=self.password.text())
        except ApiError as e:
            # альтернативный поток «Неверные данные»: сообщение об ошибке и повторный ввод
            self.err.setText(str(e))
            self.err.show()
            self.set_invalid(True)
            self.password.clear()
            self.password.setFocus()
            return
        self.err.hide()
        self.set_invalid(False)
        self.password.clear()
        self.open_subsystem(res)

    def open_subsystem(self, res):
        api.token = res['token']
        api.user = res
        self.hide()
        self.on_success(res)

    def do_register(self):
        d = RegisterDialog(self)
        if d.exec_() and d.result_user:
            info(self, 'Учётная запись создана. Добро пожаловать, %s!' % d.result_user['fio'])
            self.open_subsystem(d.result_user)

    def do_settings(self):
        SettingsDialog(self).exec_()


class App:
    def __init__(self):
        self.qt = QApplication(sys.argv)
        setup_app(self.qt)
        self.login = LoginWindow(self.open_role)
        self.window = None
        self.login.show()

    def open_role(self, res):
        """Открыть подсистему в соответствии с ролью."""
        role = res['role']
        if role == 'Администратор':
            from admin_window import AdminWindow as W
        elif role == 'Кладовщик':
            from warehouse_window import WarehouseWindow as W
        elif role == 'Диспетчер':
            from dispatcher_window import DispatcherWindow as W
        elif role == 'Курьер':
            from courier_window import CourierWindow as W
        else:
            from shop_window import ShopWindow as W
        self.window = W()
        self.window.logout.connect(self.back_to_login)
        self.window.show()

    def back_to_login(self):
        self.login.show()
        self.login.login.setFocus()

    def run(self):
        return self.qt.exec_()


if __name__ == '__main__':
    sys.exit(App().run())
