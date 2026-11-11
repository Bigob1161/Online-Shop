from PyQt5.QtCore import Qt
"""
«boundary» Окно курьера.
Поле «Адрес доставки», Поле «Данные получателя», кнопки «Принять заказ», «Отклонить заказ»,
«Отметить вручение», «Отметить невручение». Диаграмма деятельности «Доставка заказов».
"""
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPlainTextEdit, QTextBrowser, QRadioButton, QButtonGroup, QListWidget, QListWidgetItem

from net import api, ApiError
from ui import *

REASONS = ['Клиента нет на месте', 'Клиент отказался от заказа', 'Клиент отказался от части заказа', 'Неверный адрес']


class NotDeliveredDialog(FormDialog):
    def __init__(self, parent, o):
        super().__init__(parent, 'Не удалось вручить заказ № %d' % o['number'], 'Укажите причину и дальнейшее действие.',
                         ok_text='Подтвердить', width=500)
        self.rg = QButtonGroup(self)
        for i, r in enumerate(REASONS):
            rb = QRadioButton(r)
            self.rg.addButton(rb, i)
            self.form.addRow(rb)
            if i == 0:
                rb.setChecked(True)
        self.form.addRow(label('Что делать с заказом?', 'h2'))
        self.ag = QButtonGroup(self)
        self.later = QRadioButton('Повторить попытку позже (заказ остаётся у меня)')
        self.ret = QRadioButton('Вернуть заказ на склад и диспетчеру')
        self.ag.addButton(self.later, 0)
        self.ag.addButton(self.ret, 1)
        self.ret.setChecked(True)
        self.form.addRow(self.later)
        self.form.addRow(self.ret)

    def values(self):
        return REASONS[self.rg.checkedId()], ('later' if self.later.isChecked() else 'return')


class CourierWindow(BaseWindow):
    def __init__(self):
        super().__init__('Подсистема курьера')
        self.active, self.cur = [], None
        nav_layout(self, [('Мои доставки', self.build()), ('История', self.build_history())])

    def build(self):
        self.status = label('', 'infobanner', True)
        self.loc = line('', 'Где вы сейчас? Например: ул. Ленина, 15')
        self.loc_info = label('', 'hint')
        self.tlist = Table(['№', 'Статус', 'Адрес', 'Дата'], stretch=2)
        self.tlist.picked.connect(self.show_order)
        self.addr = label('', 'h2', True)
        self.recipient = label('', None, True)
        self.detail = QTextBrowser()
        self.detail.setStyleSheet('QTextBrowser { border: none; }')
        self.detail.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.b_accept = btn('Принять заказ', 'success', self.accept)
        self.b_reject = btn('Отклонить заказ', 'danger', self.reject)
        self.b_ok = btn('Отметить вручение', 'success', self.delivered)
        self.b_fail = btn('Отметить невручение', 'danger', self.not_delivered)
        self.b_msg = btn('Написать диспетчеру', 'secondary', self.write)
        right = card(label('Адрес доставки', 'muted'), self.addr, label('Данные получателя', 'muted'), self.recipient, self.detail,
                     hbox(self.b_accept, self.b_reject, 'stretch'), hbox(self.b_ok, self.b_fail, 'stretch'), self.b_msg)
        body = QWidget()
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(18)
        h.addWidget(vbox(label('Назначенные заказы', 'h2'), self.tlist, spacing=8), 2)
        h.addWidget(right, 3)
        self.show_order(None)
        return vbox(page_header('Мои доставки'), self.status,
                    hbox(label('Местоположение:', 'muted'), self.loc, btn('Обновить местоположение', 'secondary', self.set_loc), self.loc_info),
                    body, spacing=12)

    def build_history(self):
        self.htable = Table(['№', 'Статус', 'Адрес', 'Получатель'], stretch=2)
        return vbox(page_header('История доставок'), self.htable, spacing=12)

    def refresh(self):
        r = api.request('my_tasks') or {}
        me = r.get('me', {})
        self.status.setText('Ваш статус: %s. %s' % (me.get('status', ''), 'Новые заказы появятся здесь автоматически.'
                                                    if me.get('status') == 'Свободен' else 'Завершите текущую доставку.'))
        self.loc_info.setText(('обновлено ' + me['location_time']) if me.get('location_time') else 'не указано')
        if not self.loc.hasFocus() and not self.loc.text() and me.get('location'):
            self.loc.setText(me['location'])
        self.active = r.get('active', [])
        self.tlist.set_rows([[o['number'], o['status'], o['address'], o['delivery_date']] for o in self.active], self.active,
                            key=lambda o: o['number'])
        if not self.tlist.current() and self.active:
            self.tlist.selectRow(0)
        self.show_order(self.tlist.current())
        h = r.get('history', [])
        self.htable.set_rows([[o['number'], o['status'], o['address'], o['recipient']] for o in reversed(h)], list(reversed(h)))

    def show_order(self, o):
        self.cur = o
        st = o['status'] if o else None
        self.b_accept.setEnabled(st == 'Передан в доставку')
        self.b_reject.setEnabled(st == 'Передан в доставку')
        self.b_ok.setEnabled(st == 'В пути')
        self.b_fail.setEnabled(st == 'В пути')
        self.b_msg.setEnabled(True)
        if not o:
            self.addr.setText('Нет назначенных заказов')
            self.recipient.setText('')
            self.detail.setHtml('')
            return
        self.addr.setText(o['address'])
        self.recipient.setText('%s, тел. %s' % (o['recipient'], o['phone']))
        hint = 'Подтвердите принятие заказа или откажитесь от него.' if st == 'Передан в доставку' else \
               'После вручения нажмите «Отметить вручение».'
        self.detail.setHtml('<p><b>Заказ № %d</b> · дата доставки %s · <span style="color:%s">%s</span></p>%s'
                            '<table width="100%%" cellpadding="3">%s</table><p>Сумма: <b>%s</b> — <b>оплачен онлайн</b>, '
                            'деньги с клиента брать не нужно.</p><p style="color:#667085">%s</p>'
                            % (o['number'], o['delivery_date'], STATUS_COLORS.get(st, TEXT), st,
                               ('<p>Комментарий: %s</p>' % o['comment']) if o['comment'] else '', order_text(o), money(o['cost']), hint))

    def accept(self):
        if self.cur and call(self, 'accept', number=self.cur['number']):
            info(self, 'Заказ принят, статус «В пути». Доставьте заказ по адресу:\n%s' % self.cur['address'])
            self.refresh()

    def reject(self):
        if not self.cur:
            return
        d = FormDialog(self, 'Отклонение заказа № %d' % self.cur['number'], 'Заказ вернётся в очередь диспетчеру.', ok_text='Отклонить')
        t = d.add('Причина', line('', 'Например: неисправен автомобиль'))
        if d.exec_():
            if call(self, 'reject', number=self.cur['number'], reason=t.text()):
                info(self, 'Заказ возвращён в очередь диспетчеру.')
                self.refresh()

    def delivered(self):
        if self.cur and ask(self, 'Подтвердите, что заказ № %d вручён получателю.' % self.cur['number'], 'Заказ вручён', 'Отмена'):
            if call(self, 'delivered', number=self.cur['number']):
                info(self, 'Заказ доставлен. Диспетчер и клиент получили уведомление.')
                self.refresh()

    def not_delivered(self):
        if not self.cur:
            return
        d = NotDeliveredDialog(self, self.cur)
        if d.exec_():
            reason, action = d.values()
            if call(self, 'not_delivered', number=self.cur['number'], reason=reason, action=action):
                info(self, 'Диспетчер уведомлён.' + (' Повторите попытку позже.' if action == 'later' else
                                                     ' Верните заказ на склад.'))
                self.refresh()

    def set_loc(self):
        if call(self, 'set_location', location=self.loc.text()):
            Toast(self, 'Местоположение передано диспетчеру', 'ok')
            self.refresh()

    def write(self):
        d = FormDialog(self, 'Сообщение диспетчеру', ('По заказу № %d' % self.cur['number']) if self.cur else '', ok_text='Отправить')
        t = QPlainTextEdit()
        t.setFixedHeight(110)
        d.add('Текст', t)
        if d.exec_() and call(self, 'msg_dispatcher', text=t.toPlainText(), number=self.cur['number'] if self.cur else None):
            info(self, 'Сообщение отправлено диспетчеру.')
