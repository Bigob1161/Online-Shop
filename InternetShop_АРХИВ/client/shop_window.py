"""
«boundary» Окно клиента (Клиентская система «Оформление заказов»).
Таблица «Каталог товаров», Таблица «Корзина», Поле «Адрес доставки»,
Кнопки «Добавить в корзину», «Удалить из корзины», «Оформить заказ», «Оплатить заказ».
Реализует диаграмму деятельности «Составление и оплата заказа клиентом».
"""
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QComboBox, QSpinBox, QTextBrowser, QListWidget,
                             QListWidgetItem, QPlainTextEdit, QDialog, QSplitter)

from net import api, ApiError
from ui import *


class AnalogDialog(QDialog):
    """Выбор аналогичного товара вместо закончившегося."""

    def __init__(self, parent, product, analogs):
        super().__init__(parent)
        self.setWindowTitle('Замена товара')
        self.resize(560, 380)
        l = QVBoxLayout(self)
        l.setContentsMargins(22, 20, 22, 18)
        l.addWidget(label('Замена аналогичным товаром', 'title'))
        l.addWidget(label('Товара «%s» нет в нужном количестве. Выберите похожий товар из категории «%s».'
                          % (product['name'], product['category']), 'muted', True))
        self.table = Table(['Наименование', 'Цена', 'В наличии'])
        self.table.set_rows([[a['name'], money(a['price']), '%d шт.' % a['qty']] for a in analogs], analogs)
        if analogs:
            self.table.selectRow(0)
        self.table.doubleClicked.connect(self.accept)
        l.addWidget(self.table, 1)
        l.addWidget(hbox('stretch', btn('Отмена', 'secondary', self.reject), btn('Выбрать', 'primary', self.accept)))

    def selected(self):
        return self.table.current()


class CheckoutDialog(FormDialog):
    """Подтверждение заказа и ввод адреса доставки."""

    def __init__(self, parent, total):
        super().__init__(parent, 'Оформление заказа', 'Проверьте данные получателя и укажите адрес доставки.',
                         ok_text='Подтвердить заказ', width=520)
        u = api.user
        self.recipient = self.add('Получатель', line(u.get('fio', ''), 'ФИО получателя'))
        phone = u.get('contacts', '').split(',')[0].strip()
        self.phone = self.add('Телефон', line(phone, '+7 900 000-00-00'))
        self.address = self.add('Адрес доставки', line('', 'Город, улица, дом, квартира'))
        self.date = self.add('Дата доставки', date_edit())
        self.comment = self.add('Комментарий', line('', 'Например: позвонить за час, домофон 25'))
        s = label('Итого к оплате: ' + money(total), 'total')
        self.lay.insertWidget(self.lay.count() - 3, s)
        self.address.setFocus()

    def values(self):
        return dict(recipient=self.recipient.text(), phone=self.phone.text(), address=self.address.text(),
                    date=self.date.date().toString('dd.MM.yyyy'), comment=self.comment.text())


class PaymentDialog(FormDialog):
    """Оплата заказа (учебная платёжная форма)."""

    def __init__(self, parent, order):
        super().__init__(parent, 'Оплата заказа № %d' % order['number'],
                         'К оплате: %s. Данные карты не сохраняются в системе.' % money(order['cost']),
                         ok_text='Оплатить %s' % money(order['cost']), width=580)
        self.order = order
        self.card = self.add('Номер карты', line('', '0000 0000 0000 0000'))
        self.card.setInputMask('9999 9999 9999 9999;_')
        self.exp = self.add('Срок действия', line('', 'ММ/ГГ'))
        self.exp.setInputMask('99/99;_')
        self.cvv = self.add('CVC / CVV', line('', '3 цифры', True))
        self.cvv.setMaxLength(3)
        self.cvv.setValidator(QRegExpValidator(QRegExp(r'\d{0,3}')))
        self.holder = self.add('Владелец карты', line('', 'IVAN IVANOV'))
        note = label('Учебный режим: реальные деньги не списываются. Для проверки успешной оплаты подойдёт карта '
                     '4111 1111 1111 1111, для проверки отказа банка — 4000 0000 0000 0002.', 'hint', True)
        self.lay.insertWidget(self.lay.count() - 3, note)
        self.cancel.setText('Оплатить позже')
        self.refuse = btn('Отказаться от оплаты', 'danger', self.do_refuse)
        self.refuse.hide()
        self.lay.itemAt(self.lay.count() - 1).widget().layout().insertWidget(0, self.refuse)
        self.paid = None
        self.refused = False
        self.card.setFocus()

    def on_ok(self):
        try:
            self.paid = api.request('pay', number=self.order['number'], card=self.card.text(), exp=self.exp.text(),
                                    cvv=self.cvv.text(), holder=self.holder.text())
        except ApiError as e:
            # альтернативный поток «Оплата не прошла»: повторить оплату или отказаться
            self.show_error(str(e))
            self.ok.setText('Повторить оплату')
            self.refuse.show()
            return
        self.accept()

    def do_refuse(self):
        if ask(self, 'Отказаться от оплаты? Заказ № %d будет отменён, товары вернутся на склад.' % self.order['number'],
               'Отказаться и отменить заказ', 'Вернуться к оплате'):
            try:
                api.request('client_cancel', number=self.order['number'], reason='оплата не поступила')
            except ApiError as e:
                return self.show_error(str(e))
            self.refused = True
            self.reject()


def pay_order(parent, order):
    d = PaymentDialog(parent, order)
    d.exec_()
    if d.paid:
        info(parent, 'Оплата прошла успешно.\nЗаказ № %d оплачен и передан на склад для сборки.' % order['number'], 'Оплата')
    elif d.refused:
        info(parent, 'Заказ № %d отменён.' % order['number'])
    else:
        info(parent, 'Заказ № %d сохранён и ожидает оплаты.\nОплатить его можно в разделе «Мои заказы».' % order['number'])
    return d.paid


class ShopWindow(BaseWindow):
    def __init__(self):
        super().__init__('Клиентская система «Оформление заказов»')
        self.products = []
        self.cart = []   # [{product_id, name, price, qty}]
        self.orders = []
        nav_layout(self, [('Каталог и корзина', self.build_catalog()), ('Мои заказы', self.build_orders()),
                          ('Сообщения', self.build_messages())])
        self.load_products()

    # ------------------------------------------------------------------ каталог
    def build_catalog(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(18)
        self.search = line('', 'Поиск товара по названию')
        self.search.textChanged.connect(self.fill_catalog)
        self.cat = QComboBox()
        self.cat.currentIndexChanged.connect(self.fill_catalog)
        self.only_stock = QCheckBox('Только в наличии')
        self.only_stock.toggled.connect(self.fill_catalog)
        self.catalog = Table(['Наименование', 'Категория', 'Цена', 'В наличии'])
        self.catalog.doubleClicked.connect(self.add_to_cart)
        self.qty = QSpinBox()
        self.qty.setRange(1, 99)
        self.qty.setPrefix('Количество: ')
        self.qty.setMinimumWidth(150)
        left = vbox(page_header('Каталог товаров', 'Выберите товар и нажмите «Добавить в корзину». Двойной щелчок — быстрое добавление.'),
                    hbox(self.search, self.cat, self.only_stock), self.catalog,
                    hbox('stretch', self.qty, btn('Добавить в корзину', 'primary', self.add_to_cart)), spacing=12)
        self.cart_table = Table(['Товар', 'Кол-во', 'Сумма'])
        self.total = label('Итого: 0 ₽', 'total')
        self.cart_qty = QSpinBox()
        self.cart_qty.setRange(1, 99)
        self.cart_table.picked.connect(lambda it: it and self.cart_qty.setValue(it['qty']))
        right = card(label('Корзина', 'h2'), self.cart_table,
                     hbox(self.cart_qty, btn('Изменить количество', 'secondary', self.change_qty), 'stretch'),
                     btn('Удалить из корзины', 'danger', self.remove_from_cart),
                     self.total, btn('Оформить заказ', 'primary', self.checkout))
        right.setFixedWidth(400)
        h.addWidget(left, 1)
        h.addWidget(right)
        return w

    def load_products(self):
        try:
            self.products = api.request('products') or []
        except ApiError as e:
            return error(self, str(e))
        cur = self.cat.currentText()
        cats = sorted({p['category'] for p in self.products})
        self.cat.blockSignals(True)
        self.cat.clear()
        self.cat.addItem('Все категории')
        self.cat.addItems(cats)
        i = self.cat.findText(cur)
        self.cat.setCurrentIndex(max(i, 0))
        self.cat.blockSignals(False)
        self.fill_catalog()

    def fill_catalog(self):
        q = self.search.text().strip().lower()
        c = self.cat.currentText()
        rows, data = [], []
        for p in self.products:
            if q and q not in p['name'].lower():
                continue
            if c and c != 'Все категории' and p['category'] != c:
                continue
            if self.only_stock.isChecked() and p['qty'] <= 0:
                continue
            rows.append([p['name'], p['category'], money(p['price']), ('%d шт.' % p['qty']) if p['qty'] > 0 else 'Нет в наличии'])
            data.append(p)
        self.catalog.set_rows(rows, data, key=lambda p: p['id'])

    def in_cart(self, pid):
        return next((c for c in self.cart if c['product_id'] == pid), None)

    def add_to_cart(self, *_):
        p = self.catalog.current()
        if not p:
            return warn(self, 'Выберите товар в каталоге.')
        self.put(p, self.qty.value())

    def put(self, p, qty):
        have = self.in_cart(p['id'])
        total_qty = qty + (have['qty'] if have else 0)
        r = call(self, 'check_stock', product_id=p['id'], qty=total_qty)   # Проверить наличие товара()
        if r is None:
            return
        if r['ok']:
            if have:
                have['qty'] = total_qty
            else:
                self.cart.append({'product_id': p['id'], 'name': p['name'], 'price': p['price'], 'qty': qty})
            self.fill_cart()
            Toast(self, 'Товар «%s» добавлен в корзину' % p['name'], 'ok')
            return
        # альтернативный поток «Товар закончился»
        self.handle_shortage(r, total_qty, have)

    def handle_shortage(self, r, wanted, have):
        p, avail, analogs = r['product'], r['available'], r['analogs']
        text = ('Товар «%s» закончился на складе.' % p['name']) if avail <= 0 else \
               ('На складе осталось только %d шт. товара «%s» (нужно %d).' % (avail, p['name'], wanted))
        opts = []
        if analogs:
            opts.append('Заменить аналогичным')
        if avail > 0:
            opts.append('Взять %d шт.' % avail)
        opts.append('Удалить из корзины' if have else 'Не добавлять')
        k = choose(self, text + '\nЧто сделать с этим товаром?', opts, 'Товар закончился на складе')
        choice = opts[k]
        if choice == 'Заменить аналогичным':
            d = AnalogDialog(self, p, analogs)
            if d.exec_() and d.selected():
                if have:
                    self.cart.remove(have)
                self.put(d.selected(), wanted)
                return
        elif choice.startswith('Взять'):
            if have:
                have['qty'] = avail
            else:
                self.cart.append({'product_id': p['id'], 'name': p['name'], 'price': p['price'], 'qty': avail})
        elif have:
            self.cart.remove(have)
        self.fill_cart()

    def fill_cart(self):
        self.cart_table.set_rows([[c['name'], c['qty'], money(c['price'] * c['qty'])] for c in self.cart], self.cart,
                                 key=lambda c: c['product_id'])
        # Рассчитать стоимость()
        self.total.setText('Итого: ' + money(sum(c['price'] * c['qty'] for c in self.cart)))

    def remove_from_cart(self):
        c = self.cart_table.current()
        if not c:
            return warn(self, 'Выберите товар в корзине.')
        self.cart.remove(c)
        self.fill_cart()

    def change_qty(self):
        c = self.cart_table.current()
        if not c:
            return warn(self, 'Выберите товар в корзине.')
        q = self.cart_qty.value()
        r = call(self, 'check_stock', product_id=c['product_id'], qty=q)
        if r is None:
            return
        if not r['ok']:
            return self.handle_shortage(r, q, c)
        c['qty'] = q
        self.fill_cart()

    def verify_cart(self):
        """Повторная проверка наличия всех товаров корзины перед оформлением."""
        for c in list(self.cart):
            r = call(self, 'check_stock', product_id=c['product_id'], qty=c['qty'])
            if r is None:
                return False
            if not r['ok']:
                self.handle_shortage(r, c['qty'], c)
        return bool(self.cart)

    def checkout(self):
        if not self.cart:
            return warn(self, 'Корзина пуста. Добавьте товары из каталога.')
        if not self.verify_cart():
            return
        total = sum(c['price'] * c['qty'] for c in self.cart)
        d = CheckoutDialog(self, total)
        while d.exec_():
            try:
                order = api.request('create_order', cart=[{'product_id': c['product_id'], 'qty': c['qty']} for c in self.cart],
                                    **d.values())
            except ApiError as e:
                # альтернативный поток «Ошибка оформления заказа»: повторный ввод данных
                error(self, str(e), 'Ошибка оформления заказа')
                if 'закончился' in str(e):
                    self.load_products()
                    self.verify_cart()
                    return
                continue
            self.cart = []
            self.fill_cart()
            self.load_products()
            pay_order(self, order)
            self.refresh()
            return

    # ------------------------------------------------------------------ заказы
    def build_orders(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(18)
        self.otable = Table(['№', 'Дата', 'Сумма', 'Статус', 'Оплата', 'Дата доставки'], stretch=5)
        self.otable.picked.connect(self.show_order)
        self.odetail = QTextBrowser()
        self.odetail.setStyleSheet('QTextBrowser { border: none; }')
        self.odetail.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.b_pay = btn('Оплатить заказ', 'primary', self.pay_selected)
        self.b_cancel = btn('Отменить заказ', 'danger', self.cancel_selected)
        self.b_write = btn('Написать диспетчеру', 'secondary', self.write_dispatcher)
        right = card(label('Сведения о заказе', 'h2'), self.odetail, hbox(self.b_pay, self.b_cancel), self.b_write)
        right.setFixedWidth(430)
        h.addWidget(vbox(page_header('Мои заказы', 'Здесь видно, на каком этапе находится каждый заказ.'), self.otable, spacing=12), 1)
        h.addWidget(right)
        self.show_order(None)
        return w

    def refresh(self):
        self.orders = api.request('my_orders') or []
        rows = [[o['number'], o['created'], money(o['cost']), o['status'], o['pay_status'], o['delivery_date']]
                for o in reversed(self.orders)]
        self.otable.set_rows(rows, list(reversed(self.orders)), key=lambda o: o['number'])
        self.show_order(self.otable.current())
        self.fill_messages()

    def show_order(self, o):
        self.b_pay.setEnabled(bool(o and o['status'] == 'Оформлен' and o['pay_status'] == 'Не оплачен'))
        self.b_cancel.setEnabled(bool(o and o['status'] in ('Оформлен', 'Оплачен', 'Сборка')))
        self.b_write.setEnabled(bool(o))
        if not o:
            self.odetail.setHtml('<p style="color:#667085">Выберите заказ в списке слева.</p>')
            return
        hist = ''.join('<div style="color:#475467">%s — %s</div>' % (x['time'], x['text']) for x in reversed(o['history']))
        pay = o['pay_status'] + ((' (возвращено %s)' % money(o['refund_sum'])) if o['refund_sum'] else '')
        self.odetail.setHtml(
            '<h3>Заказ № %d</h3><p><b style="color:%s">%s</b> · оплата: %s</p>'
            '<p>Получатель: %s, %s<br>Адрес: %s<br>Дата доставки: %s%s</p>'
            '<table width="100%%" cellspacing="0" cellpadding="3">%s</table><p><b>Итого: %s</b></p>'
            '<p style="color:#667085"><b>История</b></p>%s'
            % (o['number'], STATUS_COLORS.get(o['status'], TEXT), o['status'], pay, o['recipient'], o['phone'], o['address'],
               o['delivery_date'], ('<br>Курьер: ' + o['courier_fio']) if o['courier_fio'] else '', order_text(o),
               money(o['cost']), hist))

    def pay_selected(self):
        o = self.otable.current()
        if o:
            pay_order(self, o)
            self.refresh()

    def cancel_selected(self):
        o = self.otable.current()
        if not o:
            return
        txt = 'Отменить заказ № %d?' % o['number']
        if o['pay_status'] == 'Оплачен':
            txt += '\nОплаченная сумма %s будет возвращена на карту.' % money(o['paid_sum'] - o['refund_sum'])
        if ask(self, txt, 'Отменить заказ', 'Не отменять'):
            r = call(self, 'client_cancel', number=o['number'], reason='клиент отказался от заказа')
            if r is not None:
                info(self, 'Заказ отменён.' + (' Деньги возвращены: %s.' % money(r['refunded']) if r['refunded'] else ''))
                self.refresh()
                self.load_products()

    def write_dispatcher(self):
        o = self.otable.current()
        d = FormDialog(self, 'Сообщение диспетчеру', 'По заказу № %d' % o['number'] if o else '', ok_text='Отправить')
        t = QPlainTextEdit()
        t.setPlaceholderText('Например: прошу доставить после 18:00')
        t.setFixedHeight(110)
        d.add('Текст', t)
        if d.exec_():
            if call(self, 'msg_dispatcher', text=t.toPlainText(), number=o['number'] if o else None) is not None:
                info(self, 'Сообщение отправлено диспетчеру.')

    # ------------------------------------------------------------------ сообщения
    def build_messages(self):
        self.mlist = QListWidget()
        self.mlist.setWordWrap(True)
        return vbox(page_header('Сообщения', 'Уведомления о ходе заказа и сообщения диспетчера.'), self.mlist,
                    hbox('stretch', btn('Написать диспетчеру', 'secondary', self.write_dispatcher)), spacing=12)

    def fill_messages(self):
        if self.mlist.count() == len(self.notes):
            return
        self.mlist.clear()
        for m in reversed(self.notes):
            it = QListWidgetItem('%s   ·   %s\n%s' % (m['time'], m.get('from') or 'Система', m['text']))
            self.mlist.addItem(it)
