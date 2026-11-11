from PyQt5.QtCore import Qt
"""
«boundary» Окно кладовщика.
Таблица «Товары заказа», кнопки «Отметить отобранным», «Связаться с диспетчером», «Заказ собран».
Диаграмма деятельности «Подбор товаров по заказу пользователя».
"""
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSpinBox, QPlainTextEdit, QTextBrowser

from net import api, ApiError
from ui import *


class ShortageDialog(FormDialog):
    def __init__(self, parent, item):
        super().__init__(parent, 'Товара не хватает', 'Позиция «%s», в заказе %d шт. Укажите, сколько фактически есть на складе — '
                         'диспетчер примет решение: замена, уменьшение количества или исключение позиции.'
                         % (item['name'], item['qty']), ok_text='Отправить диспетчеру')
        self.avail = self.add('Есть на складе, шт.', QSpinBox())
        self.avail.setRange(0, item['qty'] - 1)
        self.comment = self.add('Комментарий', line('', 'Например: повреждена упаковка'))


class WarehouseWindow(BaseWindow):
    def __init__(self):
        super().__init__('Подсистема кладовщика')
        self.orders = []
        self.current = None
        nav_layout(self, [('Сборка заказов', self.build())])

    def build(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(18)
        self.olist = Table(['№', 'Дата', 'Позиций', 'Статус'], stretch=1)
        self.olist.doubleClicked.connect(self.open_order)
        left = vbox(page_header('Заказы на сборку', 'Оплаченные заказы, ожидающие подбора товаров.'), self.olist,
                    btn('Открыть заказ', 'primary', self.open_order), spacing=12)
        left.setFixedWidth(380)
        self.title = label('Заказ не выбран', 'h2')
        self.info = label('Откройте заказ из списка слева, чтобы начать сборку.', 'muted', True)
        self.items = Table(['Товар', 'Кол-во', 'Статус позиции', 'Примечание'])
        self.b_pick = btn('Отметить отобранным', 'success', self.pick)
        self.b_short = btn('Товара не хватает', 'danger', self.shortage)
        self.b_call = btn('Связаться с диспетчером', 'secondary', self.call_dispatcher)
        self.b_done = btn('Заказ собран', 'primary', self.done)
        self.items.picked.connect(lambda *_: self.update_buttons())
        right = card(self.title, self.info, self.items, hbox(self.b_pick, self.b_short, 'stretch'), hbox(self.b_call, 'stretch', self.b_done))
        h.addWidget(left)
        h.addWidget(right, 1)
        self.update_buttons()
        return w

    def refresh(self):
        self.orders = api.request('wh_orders') or []
        self.olist.set_rows([[o['number'], o['created'], len(o['items']), o['status']] for o in self.orders], self.orders,
                            key=lambda o: o['number'])
        if self.current:
            try:
                self.current = api.request('order', number=self.current['number'])
            except ApiError:
                self.current = None
            self.show_current()

    def open_order(self, *_):
        o = self.olist.current()
        if not o:
            return warn(self, 'Выберите заказ в списке.')
        r = call(self, 'wh_open', number=o['number'])   # Просмотр списка товаров заказа
        if r:
            self.current = r
            self.refresh()

    def show_current(self):
        o = self.current
        if not o or o['status'] not in ('Сборка',):
            if o and o['status'] == 'Собран':
                self.info.setText('Заказ № %d собран и передан диспетчеру.' % o['number'])
            self.items.set_rows([], [])
            self.update_buttons()
            return
        self.title.setText('Заказ № %d' % o['number'])
        self.info.setText('Получатель: %s · Дата доставки: %s%s' % (o['recipient'], o['delivery_date'],
                          (' · Комментарий: ' + o['comment']) if o['comment'] else ''))
        idx = list(range(len(o['items'])))
        self.items.set_rows([[i['name'], i['qty'], i['status'], i.get('note', '')] for i in o['items']], idx, key=lambda x: x)
        self.update_buttons()

    def update_buttons(self):
        o = self.current
        active = bool(o and o['status'] == 'Сборка')
        i = self.items.current()
        st = o['items'][i]['status'] if (active and i is not None) else None
        self.b_pick.setEnabled(st == 'Ожидает отбора')
        self.b_short.setEnabled(st == 'Ожидает отбора')
        self.b_call.setEnabled(True)
        self.b_done.setEnabled(active)

    def pick(self):
        i = self.items.current()
        if i is None:
            return warn(self, 'Выберите позицию заказа.')
        if call(self, 'wh_pick', number=self.current['number'], idx=i) is not None:   # «товара достаточно»
            self.refresh()

    def shortage(self):
        i = self.items.current()
        if i is None:
            return warn(self, 'Выберите позицию заказа.')
        d = ShortageDialog(self, self.current['items'][i])
        if d.exec_():
            r = call(self, 'wh_shortage', number=self.current['number'], idx=i, available=d.avail.value(), comment=d.comment.text())
            if r is not None:
                info(self, 'Обращение отправлено диспетчеру. Когда он примет решение, список товаров заказа обновится.')
                self.refresh()

    def call_dispatcher(self):
        d = FormDialog(self, 'Связаться с диспетчером', ('По заказу № %d' % self.current['number']) if self.current else '',
                       ok_text='Отправить')
        t = QPlainTextEdit()
        t.setFixedHeight(110)
        t.setPlaceholderText('Текст сообщения')
        d.add('Сообщение', t)
        if d.exec_():
            if call(self, 'wh_message', text=t.toPlainText(), number=self.current['number'] if self.current else None) is not None:
                info(self, 'Сообщение отправлено диспетчеру.')

    def done(self):
        if not self.current:
            return
        # Проверить все позиции(): альтернативный поток «Не все позиции обработаны» — сообщение сервера
        r = call(self, 'wh_done', number=self.current['number'])
        if r is not None:
            info(self, 'Заказ № %d собран и передан диспетчеру.' % r['number'])
            self.current = None
            self.title.setText('Заказ не выбран')
            self.info.setText('Откройте следующий заказ из списка слева.')
            self.refresh()
