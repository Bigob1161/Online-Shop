"""
«boundary» Окно администратора.
Таблицы «Список товаров» и «Список сотрудников», кнопки «Добавить / Изменить / Удалить товар»,
«Добавить / Изменить / Удалить сотрудника». Диаграммы деятельности «Составление списка товаров»
и «Составление списка сотрудников».
"""
from PyQt5.QtWidgets import QWidget, QComboBox, QSpinBox, QDoubleSpinBox, QApplication

from net import api, ApiError
from ui import *

ROLES = ['Кладовщик', 'Диспетчер', 'Курьер', 'Администратор']


class ProductDialog(FormDialog):
    def __init__(self, parent, categories, p=None):
        super().__init__(parent, 'Изменение товара' if p else 'Новый товар',
                         'Измените данные и нажмите «Сохранить».' if p else 'Заполните данные товара.')
        self.p = p
        self.name = self.add('Наименование', line(p['name'] if p else '', 'Например: Смартфон Galaxy A35'))
        self.cat = self.add('Категория', QComboBox())
        self.cat.setEditable(True)
        self.cat.addItems(categories)
        self.cat.setCurrentText(p['category'] if p else '')
        self.cat.lineEdit().setPlaceholderText('Выберите или введите новую')
        self.price = self.add('Цена, ₽', QDoubleSpinBox())
        self.price.setRange(0, 10000000)
        self.price.setDecimals(2)
        self.price.setGroupSeparatorShown(True)
        self.price.setValue(p['price'] if p else 0)
        self.qty = self.add('Количество на складе', QSpinBox())
        self.qty.setRange(0, 1000000)
        self.qty.setValue(p['qty'] if p else 0)
        self.saved = None

    def on_ok(self):
        data = {'name': self.name.text(), 'category': self.cat.currentText(), 'price': self.price.value(), 'qty': self.qty.value()}
        try:
            # Проверить данные товара() -> Сохранение товара в каталоге
            if self.p:
                self.saved = api.request('product_update', id=self.p['id'], data=data)
            else:
                self.saved = api.request('product_add', data=data)
        except ApiError as e:
            return self.show_error(str(e))   # альтернативный поток: сообщение об ошибке, повторный ввод
        self.accept()


class EmployeeDialog(FormDialog):
    def __init__(self, parent, e=None):
        super().__init__(parent, 'Изменение данных сотрудника' if e else 'Новый сотрудник',
                         'Измените должность и контактные данные.' if e else
                         'После сохранения система сама сформирует логин и пароль сотрудника.')
        self.e = e
        self.fio = self.add('ФИО', line(e['fio'] if e else '', 'Фамилия Имя Отчество'))
        self.role = self.add('Должность', QComboBox())
        self.role.addItems(ROLES)
        if e:
            self.role.setCurrentText(e['role'])
        self.contacts = self.add('Контакты', line(e['contacts'] if e else '', 'Телефон, e-mail'))
        self.newpw = QCheckBox('Выдать новый пароль')
        if e:
            self.add('Пароль', self.newpw)
        self.result_data = None

    def on_ok(self):
        data = {'fio': self.fio.text(), 'role': self.role.currentText(), 'contacts': self.contacts.text(),
                'new_password': self.newpw.isChecked()}
        try:
            if self.e:
                self.result_data = api.request('employee_update', login=self.e['login'], data=data)
            else:
                self.result_data = api.request('employee_add', data=data)
        except ApiError as e:
            return self.show_error(str(e))
        self.accept()


class CredentialsDialog(FormDialog):
    """Вывод логина и пароля на экран."""

    def __init__(self, parent, fio, login, password):
        super().__init__(parent, 'Учётная запись создана' if password else 'Готово',
                         'Передайте эти данные сотруднику %s. Пароль показывается только один раз.' % fio, ok_text='Готово')
        self.cancel.hide()
        l1 = self.add('Логин', line(login))
        l1.setReadOnly(True)
        l2 = self.add('Пароль', line(password))
        l2.setReadOnly(True)
        self.lay.insertWidget(self.lay.count() - 2, btn('Скопировать логин и пароль', 'secondary',
                              lambda: QApplication.clipboard().setText('Логин: %s\nПароль: %s' % (login, password))))


class AdminWindow(BaseWindow):
    def __init__(self):
        super().__init__('Подсистема администратора')
        self.products, self.staff = [], []
        nav_layout(self, [('Список товаров', self.build_products()), ('Список сотрудников', self.build_staff())])

    # ------------------------------------------------------------------ товары
    def build_products(self):
        self.psearch = line('', 'Поиск по названию или категории')
        self.psearch.textChanged.connect(self.fill_products)
        self.ptable = Table(['Наименование', 'Категория', 'Цена', 'Количество'])
        self.ptable.doubleClicked.connect(self.edit_product)
        return vbox(page_header('Список товаров', 'Каталог интернет-магазина. Изменения сразу становятся видны покупателям.'),
                    hbox(self.psearch, btn('Добавить товар', 'primary', self.add_product),
                         btn('Изменить товар', 'secondary', self.edit_product), btn('Удалить товар', 'danger', self.delete_product)),
                    self.ptable, hbox(label('', 'hint'), 'stretch', btn('Сохранить данные', 'secondary', self.save)), spacing=12)

    def fill_products(self):
        q = self.psearch.text().strip().lower()
        data = [p for p in self.products if not q or q in p['name'].lower() or q in p['category'].lower()]
        self.ptable.set_rows([[p['name'], p['category'], money(p['price']), p['qty']] for p in data], data, key=lambda p: p['id'])

    def categories(self):
        return sorted({p['category'] for p in self.products})

    def add_product(self):
        d = ProductDialog(self, self.categories())
        if d.exec_():
            info(self, 'Товар «%s» успешно добавлен.' % d.saved['name'])
            self.refresh()

    def edit_product(self, *_):
        p = self.ptable.current()
        if not p:
            return warn(self, 'Выберите товар в списке.')
        d = ProductDialog(self, self.categories(), p)
        if d.exec_():
            info(self, 'Данные товара обновлены.')
            self.refresh()

    def delete_product(self):
        p = self.ptable.current()
        if not p:
            return warn(self, 'Выберите товар для удаления.')
        # Запрос подтверждения удаления (проверка незавершённых заказов выполняется сервером)
        if not ask(self, 'Удалить товар «%s» из каталога?' % p['name'], 'Удалить', 'Отказ'):
            return
        if call(self, 'product_delete', id=p['id']) is not None:
            info(self, 'Товар удалён.')
            self.refresh()

    # ------------------------------------------------------------------ сотрудники
    def build_staff(self):
        self.stable = Table(['ФИО', 'Должность', 'Контакты', 'Логин', 'Статус'])
        self.stable.doubleClicked.connect(self.edit_employee)
        return vbox(page_header('Список сотрудников', 'Сотрудники получают логин и пароль от администратора.'),
                    hbox('stretch', btn('Добавить сотрудника', 'primary', self.add_employee),
                         btn('Изменить сотрудника', 'secondary', self.edit_employee),
                         btn('Удалить сотрудника', 'danger', self.delete_employee)),
                    self.stable, hbox('stretch', btn('Сохранить данные', 'secondary', self.save)), spacing=12)

    def fill_staff(self):
        self.stable.set_rows([[e['fio'], e['role'], e['contacts'], e['login'], e.get('status', '—')] for e in self.staff],
                             self.staff, key=lambda e: e['login'])

    def add_employee(self):
        d = EmployeeDialog(self)
        if d.exec_():
            r = d.result_data
            CredentialsDialog(self, r['fio'], r['login'], r['password']).exec_()
            self.refresh()

    def edit_employee(self, *_):
        e = self.stable.current()
        if not e:
            return warn(self, 'Выберите сотрудника в списке.')
        d = EmployeeDialog(self, e)
        if d.exec_():
            if d.result_data.get('password'):
                CredentialsDialog(self, e['fio'], e['login'], d.result_data['password']).exec_()
            else:
                info(self, 'Данные сотрудника обновлены, права доступа изменены в соответствии с должностью.')
            self.refresh()

    def delete_employee(self):
        e = self.stable.current()
        if not e:
            return warn(self, 'Выберите сотрудника для удаления.')
        if not ask(self, 'Удалить учётную запись сотрудника %s (%s)?' % (e['fio'], e['role']), 'Удалить', 'Отказ'):
            return
        if call(self, 'employee_delete', login=e['login']) is not None:
            info(self, 'Сотрудник удалён.')
            self.refresh()

    # ------------------------------------------------------------------ общее
    def refresh(self):
        self.products = api.request('products') or []
        self.staff = api.request('employees') or []
        self.fill_products()
        self.fill_staff()

    def save(self):
        r = call(self, 'save')
        if r:
            info(self, 'Данные сохранены в файлы (%s).' % r['time'])
