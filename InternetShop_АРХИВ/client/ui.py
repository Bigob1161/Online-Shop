"""Общие элементы интерфейса: минималистичный стиль, кнопки, таблицы, диалоги, уведомления."""
import sys
from PyQt5.QtCore import Qt, QTimer, QDate, pyqtSignal, QPropertyAnimation, QPoint
from PyQt5.QtGui import QFont, QColor, QIcon, QPixmap, QPainter, QBrush
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView, QDialog, QLineEdit, QMessageBox, QFormLayout, QComboBox,
                             QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit, QSizePolicy,
                             QListWidget, QListWidgetItem, QTabWidget, QStackedWidget, QButtonGroup,
                             QRadioButton, QCheckBox, QScrollArea, QGraphicsOpacityEffect)

from net import api, ApiError

ACCENT = '#2563EB'
TEXT = '#101828'
MUTED = '#667085'
BORDER = '#E4E7EC'
SURFACE = '#F7F8FA'
DANGER = '#DC2626'
SUCCESS = '#16A34A'
WARNING = '#D97706'

STATUS_COLORS = {
    'Оформлен': '#475467', 'Оплачен': '#2563EB', 'Сборка': '#7C3AED', 'Собран': '#0E7490',
    'Передан в доставку': '#B45309', 'В пути': '#D97706', 'Доставлен': '#16A34A',
    'Не доставлен': '#DC2626', 'Отменён': '#98A2B3',
    'Не оплачен': '#DC2626', 'Возвращён': '#98A2B3',
    'Ожидает отбора': '#475467', 'Отобрана': '#16A34A', 'Нехватка: ждёт решения диспетчера': '#DC2626',
    'Исключена': '#98A2B3', 'Свободен': '#16A34A', 'Занят': '#D97706', 'Открыто': '#DC2626', 'Решено': '#16A34A',
}

QSS = """
* { color: %(TEXT)s; }
QMainWindow, QDialog, QWidget#page { background: #FFFFFF; }
QLabel#title { font-size: 20px; font-weight: 600; }
QLabel#h2 { font-size: 15px; font-weight: 600; }
QLabel#muted { color: %(MUTED)s; }
QLabel#hint { color: %(MUTED)s; font-size: 12px; }
QLabel#error { color: %(DANGER)s; }
QLabel#banner { background: #FEF3F2; color: #B42318; border: 1px solid #FECDCA; border-radius: 8px; padding: 10px 12px; }
QLabel#okbanner { background: #ECFDF3; color: #067647; border: 1px solid #ABEFC6; border-radius: 8px; padding: 10px 12px; }
QLabel#infobanner { background: #EFF4FF; color: #1D4ED8; border: 1px solid #C7D7FE; border-radius: 8px; padding: 10px 12px; }
QLabel#total { font-size: 18px; font-weight: 600; }
QFrame#header { background: #FFFFFF; border-bottom: 1px solid %(BORDER)s; }
QFrame#card { background: #FFFFFF; border: 1px solid %(BORDER)s; border-radius: 12px; }
QFrame#soft { background: %(SURFACE)s; border-radius: 10px; }
QPushButton { border-radius: 8px; padding: 8px 16px; font-weight: 500; min-height: 20px; }
QPushButton#primary { background: %(ACCENT)s; color: white; border: 1px solid %(ACCENT)s; }
QPushButton#primary:hover { background: #1D4ED8; }
QPushButton#primary:disabled { background: #B2CCFF; border-color: #B2CCFF; }
QPushButton#secondary { background: white; border: 1px solid #D0D5DD; }
QPushButton#secondary:hover { background: %(SURFACE)s; }
QPushButton#secondary:disabled { color: #98A2B3; border-color: %(BORDER)s; }
QPushButton#danger { background: white; color: %(DANGER)s; border: 1px solid #FDA29B; }
QPushButton#danger:hover { background: #FEF3F2; }
QPushButton#danger:disabled { color: #FDA29B; }
QPushButton#success { background: %(SUCCESS)s; color: white; border: 1px solid %(SUCCESS)s; }
QPushButton#success:hover { background: #15803D; }
QPushButton#success:disabled { background: #A6E3BA; border-color: #A6E3BA; }
QPushButton#ghost { background: transparent; border: none; color: %(MUTED)s; padding: 6px 10px; }
QPushButton#ghost:hover { color: %(TEXT)s; background: %(SURFACE)s; }
QPushButton#link { background: transparent; border: none; color: %(ACCENT)s; padding: 2px; }
QPushButton#link:hover { text-decoration: underline; }
QPushButton#nav { background: transparent; border: none; border-radius: 8px; padding: 9px 14px; text-align: left; color: %(MUTED)s; }
QPushButton#nav:hover { background: %(SURFACE)s; color: %(TEXT)s; }
QPushButton#nav:checked { background: #EFF4FF; color: %(ACCENT)s; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit, QPlainTextEdit {
    border: 1px solid #D0D5DD; border-radius: 8px; padding: 7px 10px; background: white; selection-background-color: %(ACCENT)s; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid %(ACCENT)s; }
QLineEdit[invalid="true"] { border: 1px solid %(DANGER)s; }
QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 22px; }
QTableWidget { border: 1px solid %(BORDER)s; border-radius: 10px; gridline-color: transparent; background: white;
    selection-background-color: #EFF4FF; selection-color: %(TEXT)s; alternate-background-color: #FCFCFD; }
QTableWidget::item { padding: 6px 8px; border-bottom: 1px solid #F2F4F7; }
QHeaderView::section { background: %(SURFACE)s; color: %(MUTED)s; border: none; border-bottom: 1px solid %(BORDER)s;
    padding: 8px; font-weight: 600; }
QListWidget { border: 1px solid %(BORDER)s; border-radius: 10px; background: white; }
QListWidget::item { padding: 10px; border-bottom: 1px solid #F2F4F7; }
QListWidget::item:selected { background: #EFF4FF; color: %(TEXT)s; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: transparent; padding: 10px 16px; color: %(MUTED)s; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: %(ACCENT)s; border-bottom: 2px solid %(ACCENT)s; font-weight: 600; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #D0D5DD; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QRadioButton, QCheckBox { spacing: 8px; padding: 3px 0; }
QToolTip { background: %(TEXT)s; color: white; border: none; padding: 6px; }
QFrame#toast { background: #101828; border-radius: 10px; }
QLabel#toasttext { color: white; }
""" % dict(TEXT=TEXT, MUTED=MUTED, BORDER=BORDER, SURFACE=SURFACE, ACCENT=ACCENT, DANGER=DANGER, SUCCESS=SUCCESS)


def setup_app(app):
    f = QFont()
    for fam in ('Segoe UI', 'SF Pro Text', 'Helvetica Neue', 'Inter', 'Noto Sans', 'DejaVu Sans', 'Arial'):
        f.setFamily(fam)
        if QFont(fam).exactMatch():
            break
    f.setPointSize(10)
    app.setFont(f)
    app.setStyleSheet(QSS)
    app.setWindowIcon(app_icon())


def app_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QBrush(QColor(ACCENT)))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 14, 14)
    p.setPen(QColor('white'))
    f = QFont()
    f.setPixelSize(30)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignCenter, 'М')
    p.end()
    return QIcon(pm)


def money(v):
    s = '{:,.2f}'.format(float(v or 0)).replace(',', ' ').replace('.', ',')
    if s.endswith(',00'):
        s = s[:-3]
    return s + ' ₽'


# ----------------------------------------------------------------------- виджеты
def btn(text, kind='secondary', slot=None, tip=None):
    b = QPushButton(text)
    b.setObjectName(kind)
    b.setCursor(Qt.PointingHandCursor)
    b.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
    if slot:
        b.clicked.connect(slot)
    if tip:
        b.setToolTip(tip)
    return b


def label(text='', kind=None, wrap=False):
    l = QLabel(text)
    if kind:
        l.setObjectName(kind)
    l.setWordWrap(wrap)
    return l


def hbox(*items, spacing=8, margins=(0, 0, 0, 0)):
    w = QWidget()
    l = QHBoxLayout(w)
    l.setContentsMargins(*margins)
    l.setSpacing(spacing)
    for it in items:
        if it == 'stretch':
            l.addStretch(1)
        elif isinstance(it, int):
            l.addSpacing(it)
        else:
            l.addWidget(it)
    return w


def vbox(*items, spacing=8, margins=(0, 0, 0, 0)):
    w = QWidget()
    l = QVBoxLayout(w)
    l.setContentsMargins(*margins)
    l.setSpacing(spacing)
    for it in items:
        if it == 'stretch':
            l.addStretch(1)
        elif isinstance(it, int):
            l.addSpacing(it)
        else:
            l.addWidget(it)
    return w


def card(*items, spacing=10, margins=(16, 16, 16, 16), name='card'):
    f = QFrame()
    f.setObjectName(name)
    l = QVBoxLayout(f)
    l.setContentsMargins(*margins)
    l.setSpacing(spacing)
    for it in items:
        if it == 'stretch':
            l.addStretch(1)
        else:
            l.addWidget(it)
    return f


class Table(QTableWidget):
    """Таблица только для чтения с выбором строки и сохранением выбора при обновлении."""
    picked = pyqtSignal(object)

    def __init__(self, headers, stretch=0, widths=None):
        super().__init__(0, len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(38)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWordWrap(False)
        h = self.horizontalHeader()
        h.setHighlightSections(False)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for i in range(len(headers)):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(stretch, QHeaderView.Stretch)
        self._data = []
        self.itemSelectionChanged.connect(lambda: self.picked.emit(self.current()))

    def set_rows(self, rows, data, key=None):
        """rows — список списков текста; data — объекты строк; key — функция ключа для сохранения выбора."""
        cur = self.current()
        cur_key = key(cur) if (key and cur is not None) else None
        self.blockSignals(True)
        self.setRowCount(len(rows))
        self._data = list(data)
        sel = -1
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                it = QTableWidgetItem('' if val is None else str(val))
                col = STATUS_COLORS.get(str(val))
                if col:
                    it.setForeground(QColor(col))
                    f = it.font()
                    f.setBold(True)
                    it.setFont(f)
                self.setItem(r, c, it)
            if key and cur_key is not None and key(self._data[r]) == cur_key:
                sel = r
        if sel >= 0:
            self.selectRow(sel)
        else:
            self.clearSelection()
        self.blockSignals(False)
        if (sel < 0) != (cur is None):
            self.picked.emit(self.current())

    def current(self):
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
        if not rows:
            return None
        r = rows[0].row()
        return self._data[r] if r < len(self._data) else None

    def current_index(self):
        rows = self.selectionModel().selectedRows()
        return rows[0].row() if rows else -1


# ----------------------------------------------------------------------- сообщения
def _box(parent, icon, title, text, buttons):
    m = QMessageBox(parent)
    m.setIcon(icon)
    m.setWindowTitle(title)
    m.setText(text)
    res = {}
    for i, (t, role) in enumerate(buttons):
        b = m.addButton(t, role)
        res[b] = i
        if i == 0:
            m.setDefaultButton(b)
    m.exec_()
    return res.get(m.clickedButton(), len(buttons) - 1)


def info(parent, text, title='Готово'):
    _box(parent, QMessageBox.Information, title, text, [('Понятно', QMessageBox.AcceptRole)])


def warn(parent, text, title='Внимание'):
    _box(parent, QMessageBox.Warning, title, text, [('Понятно', QMessageBox.AcceptRole)])


def error(parent, text, title='Ошибка'):
    _box(parent, QMessageBox.Critical, title, text, [('Понятно', QMessageBox.AcceptRole)])


def ask(parent, text, yes='Да', no='Отмена', title='Подтверждение'):
    return _box(parent, QMessageBox.Question, title, text, [(yes, QMessageBox.AcceptRole), (no, QMessageBox.RejectRole)]) == 0


def choose(parent, text, options, title='Выберите действие'):
    """Несколько вариантов: возвращает индекс выбранного варианта."""
    return _box(parent, QMessageBox.Question, title, text, [(o, QMessageBox.ActionRole) for o in options])


def call(parent, cmd, **kw):
    """Запрос к серверу; при ошибке показывает сообщение и возвращает None."""
    try:
        return api.request(cmd, **kw)
    except ApiError as e:
        error(parent, str(e))
        return None


# ----------------------------------------------------------------------- формы
class FormDialog(QDialog):
    """Простая форма: заголовок, поля, строка ошибки, кнопки «Сохранить»/«Отмена»."""

    def __init__(self, parent, title, subtitle='', ok_text='Сохранить', width=460):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(24, 22, 24, 20)
        self.lay.setSpacing(12)
        self.lay.addWidget(label(title, 'title'))
        if subtitle:
            self.lay.addWidget(label(subtitle, 'muted', wrap=True))
        self.form = QFormLayout()
        self.form.setLabelAlignment(Qt.AlignLeft)
        self.form.setFormAlignment(Qt.AlignTop)
        self.form.setHorizontalSpacing(14)
        self.form.setVerticalSpacing(10)
        self.lay.addLayout(self.form)
        self.err = label('', 'error', wrap=True)
        self.err.hide()
        self.lay.addWidget(self.err)
        self.ok = btn(ok_text, 'primary', self.on_ok)
        self.ok.setDefault(True)
        self.cancel = btn('Отмена', 'secondary', self.reject)
        self.lay.addSpacing(4)
        self.lay.addWidget(hbox('stretch', self.cancel, self.ok))

    def add(self, caption, w):
        self.form.addRow(label(caption, 'muted'), w)
        return w

    def show_error(self, text):
        self.err.setText(text)
        self.err.show()

    def on_ok(self):
        self.accept()


def line(text='', placeholder='', password=False):
    e = QLineEdit(text)
    e.setPlaceholderText(placeholder)
    if password:
        e.setEchoMode(QLineEdit.Password)
    return e


def date_edit(value=None, min_today=True):
    d = QDateEdit()
    d.setCalendarPopup(True)
    d.setDisplayFormat('dd.MM.yyyy')
    if min_today:
        d.setMinimumDate(QDate.currentDate())
    d.setDate(QDate.fromString(value, 'dd.MM.yyyy') if value else QDate.currentDate().addDays(1))
    return d


# ----------------------------------------------------------------------- уведомления
class Toast(QFrame):
    """Всплывающее уведомление в правом нижнем углу окна."""

    def __init__(self, parent, text, kind='info'):
        super().__init__(parent)
        self.setObjectName('toast')
        l = QHBoxLayout(self)
        l.setContentsMargins(14, 10, 14, 10)
        dot = QLabel('●')
        dot.setStyleSheet('color: %s;' % {'ok': '#32D583', 'warn': '#FDB022', 'chat': '#84ADFF'}.get(kind, '#84ADFF'))
        t = QLabel(text)
        t.setObjectName('toasttext')
        t.setWordWrap(True)
        t.setMaximumWidth(360)
        l.addWidget(dot)
        l.addWidget(t, 1)
        self.adjustSize()
        self.show()
        self.raise_()
        Toast.stack(parent)
        QTimer.singleShot(6000, self.close_toast)

    @staticmethod
    def stack(parent):
        y = parent.height() - 20
        for ch in reversed([c for c in parent.findChildren(Toast) if c.isVisible()]):
            ch.adjustSize()
            y -= ch.height()
            ch.move(parent.width() - ch.width() - 20, y)
            y -= 8

    def close_toast(self):
        p = self.parent()
        self.hide()
        self.deleteLater()
        if p:
            QTimer.singleShot(0, lambda: Toast.stack(p))


class NotificationsDialog(QDialog):
    def __init__(self, parent, items):
        super().__init__(parent)
        self.setWindowTitle('Уведомления и сообщения')
        self.resize(620, 480)
        l = QVBoxLayout(self)
        l.setContentsMargins(20, 18, 20, 18)
        l.addWidget(label('Уведомления и сообщения', 'title'))
        lst = QListWidget()
        lst.setWordWrap(True)
        for m in reversed(items):
            it = QListWidgetItem('%s   ·   %s\n%s' % (m['time'], m.get('from') or 'Система', m['text']))
            if m.get('kind') == 'warn':
                it.setForeground(QColor('#B42318'))
            lst.addItem(it)
        if not items:
            lst.addItem('Пока нет уведомлений')
        l.addWidget(lst, 1)
        l.addWidget(hbox('stretch', btn('Закрыть', 'secondary', self.accept)))


class BaseWindow(QMainWindow):
    """Окно подсистемы: шапка с именем пользователя, уведомления, выход; периодическое обновление."""
    logout = pyqtSignal()
    REFRESH_MS = 4000

    def __init__(self, title):
        super().__init__()
        self.setWindowTitle('Интернет-магазин — ' + title)
        self.resize(1240, 780)
        self.setMinimumSize(980, 640)
        root = QWidget()
        root.setObjectName('page')
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        head = QFrame()
        head.setObjectName('header')
        h = QHBoxLayout(head)
        h.setContentsMargins(22, 12, 18, 12)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(30, 30))
        h.addWidget(logo)
        h.addSpacing(8)
        h.addWidget(vbox(label('Интернет-магазин', 'h2'), label(title, 'hint'), spacing=0))
        h.addStretch(1)
        u = api.user or {}
        h.addWidget(vbox(label(u.get('fio', ''), None), label(u.get('role', ''), 'hint'), spacing=0))
        h.addSpacing(10)
        self.bell = btn('Уведомления', 'ghost', self.show_notifications)
        h.addWidget(self.bell)
        h.addWidget(btn('Выйти', 'ghost', self.do_logout))
        v.addWidget(head)
        self.body = QWidget()
        self.body.setObjectName('page')
        v.addWidget(self.body, 1)
        self.notes = []
        self.unread = 0
        self.last_id = 0
        self._first_poll = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(self.REFRESH_MS)
        QTimer.singleShot(50, self.tick)

    def tick(self):
        try:
            new = api.request('notifications', since=self.last_id) or []
        except ApiError:
            self.statusBar().showMessage('Нет связи с сервером. Повторная попытка через несколько секунд…')
            return
        self.statusBar().clearMessage()
        if new:
            self.last_id = max(m['id'] for m in new)
            self.notes += new
            if not self._first_poll:
                self.unread += len(new)
                for m in new[-3:]:
                    Toast(self, m['text'], m.get('kind', 'info'))
        self._first_poll = False
        self.bell.setText('Уведомления' + (' (%d)' % self.unread if self.unread else ''))
        self.bell.setStyleSheet('color: %s; font-weight: 600;' % ACCENT if self.unread else '')
        try:
            self.refresh()
        except ApiError:
            pass

    def refresh(self):
        pass

    def show_notifications(self):
        self.unread = 0
        self.bell.setText('Уведомления')
        self.bell.setStyleSheet('')
        NotificationsDialog(self, self.notes).exec_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        Toast.stack(self)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, lambda: Toast.stack(self))

    def do_logout(self):
        if ask(self, 'Завершить работу и выйти из системы?', 'Выйти'):
            self.timer.stop()
            try:
                api.request('logout')
            except ApiError:
                pass
            api.token = None
            api.user = None
            self.logout.emit()
            self.close()

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)


def nav_layout(window, pages):
    """Левая панель навигации + страницы. pages: список (название, виджет)."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(0)
    side = QFrame()
    side.setFixedWidth(260)
    side.setStyleSheet('QFrame { background: #FCFCFD; border-right: 1px solid %s; }' % BORDER)
    sv = QVBoxLayout(side)
    sv.setContentsMargins(12, 18, 12, 18)
    sv.setSpacing(4)
    stack = QStackedWidget()
    group = QButtonGroup(w)
    buttons = []
    for i, (name, page) in enumerate(pages):
        b = QPushButton(name)
        b.setObjectName('nav')
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        group.addButton(b, i)
        sv.addWidget(b)
        buttons.append(b)
        wrap = QWidget()
        wrap.setObjectName('page')
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(26, 22, 26, 22)
        wl.addWidget(page)
        stack.addWidget(wrap)
    sv.addStretch(1)
    group.idClicked.connect(stack.setCurrentIndex)
    buttons[0].setChecked(True)
    h.addWidget(side)
    h.addWidget(stack, 1)
    lay = QVBoxLayout(window.body)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(w)
    window.nav_buttons = buttons
    window.stack = stack
    return buttons


def page_header(title, subtitle=''):
    return vbox(label(title, 'title'), label(subtitle, 'muted', wrap=True) if subtitle else QWidget(), spacing=2)


def order_text(o):
    """Краткая карточка заказа в виде HTML."""
    rows = ''.join('<tr><td>%s%s</td><td align="right">%d шт.</td><td align="right">%s</td><td style="color:%s">&nbsp;&nbsp;%s</td></tr>'
                   % (i['name'], ('<br><span style="color:#667085">%s</span>' % i['note']) if i.get('note') else '',
                      i['qty'], money(i['price'] * i['qty']), STATUS_COLORS.get(i['status'], MUTED), i['status'])
                   for i in o['items'])
    return rows
