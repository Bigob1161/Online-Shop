from PyQt5.QtCore import Qt
"""
«boundary» Окно диспетчера.
Таблицы «Собранные заказы», «Свободные курьеры», «Заказы в доставке»,
кнопки «Назначить курьера», «Связаться с клиентом».
Диаграммы деятельности «Распределение заказов для доставки курьером», «Слежение за доставкой заказов»,
а также решения по обращениям кладовщика и по возвращённым заказам (общая диаграмма деятельности).
"""
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QComboBox, QSpinBox, QPlainTextEdit, QTextBrowser,
                             QRadioButton, QButtonGroup)

from net import api, ApiError
from ui import *


def text_dialog(parent, title, subtitle, placeholder, ok='Отправить'):
    d = FormDialog(parent, title, subtitle, ok_text=ok)
    t = QPlainTextEdit()
    t.setPlaceholderText(placeholder)
    t.setFixedHeight(110)
    d.add('Сообщение', t)
    return t.toPlainText() if d.exec_() else None


class CourierPick(FormDialog):
    """Выбор курьера (и при необходимости новой даты доставки)."""

    def __init__(self, parent, title, couriers, with_date=False, date=None):
        super().__init__(parent, title, 'Выберите свободного курьера.', ok_text='Назначить')
        self.combo = self.add('Курьер', QComboBox())
        for c in couriers:
            self.combo.addItem('%s — %s' % (c['fio'], c.get('status', '')), c['login'])
        self.date = self.add('Новая дата доставки', date_edit(date)) if with_date else None

    def courier(self):
        return self.combo.currentData()


class DecisionDialog(FormDialog):
    """Принятие решения по позиции (замена / уменьшение / исключение)."""

    def __init__(self, parent, appeal, products):
        super().__init__(parent, 'Решение по заказу № %d' % appeal['order'],
                         'Не хватает товара «%s»: на складе %d из %d шт.%s' % (
                             appeal['product'], appeal['available'], appeal['need'],
                             ('\nКомментарий кладовщика: ' + appeal['comment']) if appeal['comment'] else ''),
                         ok_text='Принять решение', width=540)
        self.a = appeal
        self.g = QButtonGroup(self)
        self.r_replace = QRadioButton('Заменить аналогичным товаром')
        self.r_reduce = QRadioButton('Уменьшить количество')
        self.r_excl = QRadioButton('Исключить позицию из заказа')
        for i, r in enumerate((self.r_replace, self.r_reduce, self.r_excl)):
            self.g.addButton(r, i)
        cur = next((p for p in products if p['id'] == appeal['product_id']), None)
        cat = cur['category'] if cur else ''
        self.repl = QComboBox()
        cand = sorted([p for p in products if p['id'] != appeal['product_id'] and p['qty'] >= appeal['need']],
                      key=lambda p: (p['category'] != cat, p['name']))
        for p in cand:
            self.repl.addItem('%s · %s · в наличии %d шт.' % (p['name'], money(p['price']), p['qty']), p['id'])
        self.qty = QSpinBox()
        self.qty.setRange(1, max(1, appeal['available']))
        self.qty.setValue(max(1, appeal['available']))
        self.qty.setSuffix(' шт.')
        self.form.addRow(self.r_replace)
        self.add('Товар для замены', self.repl)
        self.form.addRow(self.r_reduce)
        self.add('Новое количество', self.qty)
        self.form.addRow(self.r_excl)
        if not cand:
            self.r_replace.setEnabled(False)
            self.repl.setEnabled(False)
        if appeal['available'] < 1:
            self.r_reduce.setEnabled(False)
            self.qty.setEnabled(False)
        (self.r_replace if cand else (self.r_reduce if appeal['available'] else self.r_excl)).setChecked(True)
        self.lay.insertWidget(self.lay.count() - 2, label('При уменьшении суммы заказа разница автоматически возвращается клиенту. '
                                                          'Замена выполняется по цене исходного товара.', 'hint', True))
        self.done_order = None

    def on_ok(self):
        k = self.g.checkedId()
        dec = ['replace', 'reduce', 'exclude'][k]
        try:
            self.done_order = api.request('decide', id=self.a['id'], decision=dec, replacement=self.repl.currentData(),
                                          qty=self.qty.value())
        except ApiError as e:
            return self.show_error(str(e))
        self.accept()


class DispatcherWindow(BaseWindow):
    def __init__(self):
        super().__init__('Подсистема диспетчера')
        self.couriers, self.products = [], []
        self.only_free = False
        self.all = []
        self.track = None
        b = nav_layout(self, [('Распределение заказов', self.build_distr()), ('Слежение за доставкой', self.build_track()),
                              ('Обращения кладовщика', self.build_appeals()), ('Возвращённые заказы', self.build_returned()),
                              ('Все заказы', self.build_all())])
        self.nav = b

    # ------------------------------------------------------------ распределение
    def build_distr(self):
        self.asm = Table(['№', 'Получатель', 'Адрес', 'Дата доставки', 'Сумма'], stretch=2)
        self.ctable = Table(['Курьер', 'Статус', 'Заказы', 'Местоположение'], stretch=0)
        self.ctitle = label('Курьеры', 'h2')
        self.b_find = btn('Найти свободных курьеров', 'secondary', self.find_free)
        left = vbox(label('Собранные заказы', 'h2'), self.asm, spacing=8)
        right = vbox(self.ctitle, self.ctable, hbox(self.b_find, 'stretch'), spacing=8)
        body = QWidget()
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(18)
        h.addWidget(left, 1)
        h.addWidget(right, 1)
        return vbox(page_header('Распределение заказов для доставки курьером',
                                'Выберите собранный заказ, найдите свободного курьера и нажмите «Назначить курьера».'),
                    body, hbox('stretch', btn('Назначить курьера', 'primary', self.assign)), spacing=12)

    def fill_couriers(self):
        data = [c for c in self.couriers if not self.only_free or c['status'] == 'Свободен']
        self.ctable.set_rows([[c['fio'], c['status'], ', '.join(map(str, c.get('orders', []))) or '—',
                               c.get('location') or 'нет данных'] for c in data], data, key=lambda c: c['login'])
        self.ctitle.setText('Свободные курьеры' if self.only_free else 'Курьеры')
        self.b_find.setText('Показать всех курьеров' if self.only_free else 'Найти свободных курьеров')

    def find_free(self):
        # Найти свободных курьеров(): альтернативный поток «Нет свободных курьеров»
        self.only_free = not self.only_free
        self.fill_couriers()
        if self.only_free and not any(c['status'] == 'Свободен' for c in self.couriers):
            warn(self, 'Нет свободных курьеров. Заказ остаётся в очереди — назначьте курьера, когда он освободится.')

    def assign(self):
        o = self.asm.current()
        if not o:
            return warn(self, 'Выберите заказ в таблице «Собранные заказы».')
        c = self.ctable.current()
        if not c:
            free = [x for x in self.couriers if x['status'] == 'Свободен']
            if not free:
                return warn(self, 'Нет свободных курьеров. Заказ № %d остаётся в очереди.' % o['number'])
            return warn(self, 'Выберите курьера в таблице справа.')
        if c['status'] != 'Свободен':
            return warn(self, 'Курьер %s занят. Выберите другого курьера.' % c['fio'], 'Курьер занят')
        r = call(self, 'assign', number=o['number'], courier=c['login'])
        if r:
            info(self, 'Заказ № %d передан в доставку. Курьер %s получил уведомление.' % (o['number'], c['fio']))
            self.refresh()

    # ------------------------------------------------------------ слежение
    def build_track(self):
        self.dtable = Table(['№', 'Статус', 'Курьер', 'Адрес', 'Дата доставки'], stretch=3)
        self.dtable.picked.connect(self.show_track)
        self.banner = label('', 'banner', True)
        self.banner.hide()
        self.tinfo = QTextBrowser()
        self.tinfo.setStyleSheet('QTextBrowser { border: none; }')
        self.tinfo.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.b_client = btn('Связаться с клиентом', 'primary', self.contact_client)
        self.b_courier = btn('Связаться с курьером', 'secondary', self.contact_courier)
        self.b_reassign = btn('Переназначить заказ другому курьеру', 'secondary', self.reassign)
        right = card(label('Статус и местоположение курьера', 'h2'), self.banner, self.tinfo, self.b_client, self.b_courier, self.b_reassign)
        right.setFixedWidth(420)
        body = QWidget()
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(18)
        h.addWidget(vbox(label('Заказы в доставке', 'h2'), self.dtable, spacing=8), 1)
        h.addWidget(right)
        self.show_track(None)
        return vbox(page_header('Слежение за доставкой заказов', 'Выберите заказ, чтобы увидеть статус доставки и местоположение курьера.'),
                    body, spacing=12)

    def show_track(self, o):
        for b in (self.b_client, self.b_courier, self.b_reassign):
            b.setEnabled(bool(o))
        self.banner.hide()
        if not o:
            self.tinfo.setHtml('<p style="color:#667085">Выберите заказ в таблице.</p>')
            self.track = None
            return
        try:
            t = api.request('track', number=o['number'])   # Получить статус заказа(), Получить местоположение курьера()
        except ApiError as e:
            self.tinfo.setPlainText(str(e))
            return
        self.track = t
        if t['lost']:
            # альтернативный поток «Связь потеряна»
            self.banner.setText('Нет данных о местоположении курьера. Свяжитесь с курьером напрямую или назначьте заказ другому курьеру.')
            self.banner.show()
        c = t['courier'] or {}
        oo = t['order']
        self.tinfo.setHtml('<h3>Заказ № %d</h3><p><b style="color:%s">%s</b></p><p>Курьер: %s<br>Телефон курьера: %s<br>'
                           'Местоположение: %s</p><p>Получатель: %s, %s<br>Адрес: %s</p><p style="color:#667085">%s</p>'
                           % (oo['number'], STATUS_COLORS.get(oo['status'], TEXT), oo['status'], c.get('fio', '—'),
                              c.get('contacts', '—'), t['location'] or 'нет данных', oo['recipient'], oo['phone'], oo['address'],
                              '<br>'.join('%s — %s' % (x['time'], x['text']) for x in reversed(oo['history'][-6:]))))

    def contact_client(self):
        o = self.dtable.current()
        if not o:
            return
        t = text_dialog(self, 'Связаться с клиентом', 'Заказ № %d, получатель %s, %s' % (o['number'], o['recipient'], o['phone']),
                        'Например: курьер задерживается на 20 минут')
        if t is not None and call(self, 'msg_client', number=o['number'], text=t) is not None:
            info(self, 'Сообщение отправлено клиенту.')

    def contact_courier(self, *_, order=None):
        o = order or self.dtable.current()
        if not o or not o['courier']:
            return
        t = text_dialog(self, 'Связаться с курьером', '%s · заказ № %d' % (o['courier_fio'], o['number']),
                        'Например: сообщите своё местоположение')
        if t is not None and call(self, 'msg_courier', courier=o['courier'], text=t, number=o['number']) is not None:
            info(self, 'Сообщение отправлено курьеру.')

    def reassign(self):
        o = self.dtable.current()
        if not o:
            return
        free = [c for c in self.couriers if c['status'] == 'Свободен' and c['login'] != o['courier']]
        if not free:
            return warn(self, 'Нет свободных курьеров для переназначения.')
        d = CourierPick(self, 'Назначение заказа другому курьеру', free)
        if d.exec_() and call(self, 'reassign', number=o['number'], courier=d.courier()):
            info(self, 'Заказ № %d назначен другому курьеру.' % o['number'])
            self.refresh()

    # ------------------------------------------------------------ обращения
    def build_appeals(self):
        self.atable = Table(['№ заказа', 'Время', 'Товар', 'Нужно', 'На складе', 'Комментарий'], stretch=2)
        self.atable.doubleClicked.connect(self.decide)
        return vbox(page_header('Обращения кладовщика', 'Кладовщику не хватает товара. Примите решение: замена, уменьшение количества или исключение позиции.'),
                    self.atable, hbox('stretch', btn('Принять решение по позиции', 'primary', self.decide)), spacing=12)

    def decide(self, *_):
        a = self.atable.current()
        if not a:
            return warn(self, 'Выберите обращение.')
        d = DecisionDialog(self, a, self.products)
        if d.exec_():
            info(self, 'Решение принято. Состав заказа обновлён, кладовщик и клиент получили уведомления.')
            self.refresh()

    # ------------------------------------------------------------ возвраты
    def build_returned(self):
        self.rtable = Table(['№', 'Получатель', 'Адрес', 'Причина', 'Оплата'], stretch=3)
        return vbox(page_header('Возвращённые заказы', 'Заказы, которые не удалось вручить. Назначьте новую дату доставки или отмените заказ.'),
                    self.rtable, hbox('stretch', btn('Отменить заказ', 'danger', self.cancel_returned),
                                      btn('Повторить доставку', 'primary', self.redeliver)), spacing=12)

    def redeliver(self):
        o = self.rtable.current()
        if not o:
            return warn(self, 'Выберите заказ.')
        free = [c for c in self.couriers if c['status'] == 'Свободен']
        if not free:
            return warn(self, 'Нет свободных курьеров. Заказ остаётся в очереди.')
        d = CourierPick(self, 'Повторная доставка заказа № %d' % o['number'], free, with_date=True)
        if d.exec_():
            r = call(self, 'redeliver', number=o['number'], courier=d.courier(), date=d.date.date().toString('dd.MM.yyyy'))
            if r:
                info(self, 'Назначена повторная доставка на %s.' % r['delivery_date'])
                self.refresh()

    def cancel_returned(self):
        o = self.rtable.current()
        if not o:
            return warn(self, 'Выберите заказ.')
        self.cancel_order(o)

    def cancel_order(self, o):
        txt = 'Отменить заказ № %d?\nТовары будут возвращены на склад.' % o['number']
        if o['pay_status'] == 'Оплачен':
            txt += '\nКлиенту будет возвращено %s.' % money(o['paid_sum'] - o['refund_sum'])
        if ask(self, txt, 'Отменить заказ', 'Не отменять'):
            r = call(self, 'cancel_order', number=o['number'], reason='отменён диспетчером')
            if r is not None:
                info(self, 'Заказ отменён.' + (' Возврат оплаты: %s.' % money(r['refunded']) if r['refunded'] else ''))
                self.refresh()

    # ------------------------------------------------------------ все заказы
    def build_all(self):
        self.filter = QComboBox()
        self.filter.addItems(['Все статусы', 'Оформлен', 'Оплачен', 'Сборка', 'Собран', 'Передан в доставку', 'В пути',
                              'Доставлен', 'Не доставлен', 'Отменён'])
        self.filter.currentIndexChanged.connect(lambda *_: self.fill_all())
        self.alltable = Table(['№', 'Дата', 'Клиент', 'Сумма', 'Статус', 'Оплата', 'Курьер'], stretch=2)
        self.alltable.picked.connect(self.show_all)
        self.allinfo = QTextBrowser()
        self.allinfo.setStyleSheet('QTextBrowser { border: none; }')
        self.allinfo.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.b_allcancel = btn('Отменить заказ', 'danger', lambda: self.alltable.current() and self.cancel_order(self.alltable.current()))
        right = card(label('Сведения о заказе', 'h2'), self.allinfo, self.b_allcancel)
        right.setFixedWidth(420)
        body = QWidget()
        h = QHBoxLayout(body)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(18)
        h.addWidget(vbox(hbox(self.filter, 'stretch'), self.alltable), 1)
        h.addWidget(right)
        self.show_all(None)
        return vbox(page_header('Все заказы'), body, spacing=12)

    def fill_all(self):
        f = self.filter.currentText()
        data = [o for o in reversed(self.all) if f == 'Все статусы' or o['status'] == f]
        self.alltable.set_rows([[o['number'], o['created'], o['client_fio'], money(o['cost']), o['status'], o['pay_status'],
                                 o['courier_fio'] or '—'] for o in data], data, key=lambda o: o['number'])
        self.show_all(self.alltable.current())

    def show_all(self, o):
        self.b_allcancel.setEnabled(bool(o and o['status'] in ('Оформлен', 'Оплачен', 'Сборка', 'Собран', 'Не доставлен')))
        if not o:
            self.allinfo.setHtml('<p style="color:#667085">Выберите заказ.</p>')
            return
        self.allinfo.setHtml('<h3>Заказ № %d</h3><p><b style="color:%s">%s</b> · %s</p><p>%s, %s<br>%s<br>Дата доставки: %s</p>'
                             '<table width="100%%" cellpadding="3">%s</table><p><b>Итого: %s</b></p><p style="color:#667085">%s</p>'
                             % (o['number'], STATUS_COLORS.get(o['status'], TEXT), o['status'], o['pay_status'], o['recipient'],
                                o['phone'], o['address'], o['delivery_date'], order_text(o), money(o['cost']),
                                '<br>'.join('%s — %s' % (x['time'], x['text']) for x in reversed(o['history']))))

    # ------------------------------------------------------------ обновление
    def refresh(self):
        self.couriers = api.request('couriers') or []
        self.products = api.request('products') or []
        asm = api.request('assembled') or []
        self.asm.set_rows([[o['number'], o['recipient'], o['address'], o['delivery_date'], money(o['cost'])] for o in asm], asm,
                          key=lambda o: o['number'])
        self.fill_couriers()
        dl = api.request('in_delivery') or []
        self.dtable.set_rows([[o['number'], o['status'], o['courier_fio'], o['address'], o['delivery_date']] for o in dl], dl,
                             key=lambda o: o['number'])
        if self.dtable.current():
            self.show_track(self.dtable.current())
        ap = api.request('appeals') or []
        self.atable.set_rows([[a['order'], a['time'], a['product'], a['need'], a['available'], a['comment']] for a in ap], ap,
                             key=lambda a: a['id'])
        rt = api.request('returned') or []
        self.rtable.set_rows([[o['number'], o['recipient'], o['address'], o['fail_reason'], o['pay_status']] for o in rt], rt,
                             key=lambda o: o['number'])
        self.all = api.request('all_orders') or []
        self.fill_all()
        counts = [len(asm), len(dl), len(ap), len(rt)]
        names = ['Распределение заказов', 'Слежение за доставкой', 'Обращения кладовщика', 'Возвращённые заказы']
        for b, n, c in zip(self.nav, names, counts):
            b.setText(n + ('  (%d)' % c if c else ''))
