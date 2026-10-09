"""A stable keyboard focus ring for the shared desktop button roles."""
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QPushButton as NativeButton, QLabel, QStyleOptionButton, QStylePainter, QStyle, QTabWidget, QScrollArea, QFrame, QToolTip, QWidget, QHBoxLayout, QListWidget, QStackedWidget


KEYBOARD_REASONS = (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)


class Button(NativeButton):
    keyboard_focus = False
    def focusInEvent(self, event):
        self.keyboard_focus = event.reason() in KEYBOARD_REASONS
        super().focusInEvent(event)
    def paintEvent(self, event):
        if self.property('elide'):
            option = QStyleOptionButton()
            self.initStyleOption(option)
            option.text = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideMiddle, max(0, self.width()-24))
            painter = QStylePainter(self)
            painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
            painter.end()
        else:
            super().paintEvent(event)
        if self.hasFocus() and self.keyboard_focus:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            colour = self.palette().highlight().color()
            if self.property('role') in ('primary', 'stop'):
                colour = self.palette().highlightedText().color()
            painter.setPen(QPen(colour, 2))
            painter.drawRoundedRect(self.rect().adjusted(3, 3, -3, -3), 4, 4)


class Banner(QFrame):
    """A message strip that slides open instead of snapping the layout."""
    def __init__(self):
        super().__init__();self.setObjectName('banner');self.animation=None
    def setVisible(self, visible):
        if visible and not self.isVisible():
            super().setVisible(True);target=self.sizeHint().height();self.setMaximumHeight(0)
            self.animation=QPropertyAnimation(self,b'maximumHeight',self);self.animation.setDuration(180);self.animation.setStartValue(0);self.animation.setEndValue(target)
            self.animation.setEasingCurve(QEasingCurve.Type.OutCubic);self.animation.finished.connect(lambda:self.setMaximumHeight(16777215));self.animation.start()
        else:super().setVisible(visible)


class SideTabs(QWidget):
    """A vertical list of pages beside a stack: a second tab style, so nested tabs stop looking alike."""
    def __init__(self):
        super().__init__();row=QHBoxLayout(self);row.setContentsMargins(0,0,0,0);row.setSpacing(12)
        self.list=QListWidget();self.list.setObjectName('sideTabs');self.list.setFixedWidth(150);self.list.setFrameShape(QFrame.Shape.NoFrame);self.stack=QStackedWidget()
        row.addWidget(self.list);row.addWidget(self.stack,1);self.list.currentRowChanged.connect(self.stack.setCurrentIndex);self.currentChanged=self.list.currentRowChanged
    def addTab(self,widget,title):self.stack.addWidget(widget);self.list.addItem(title.replace('&&','&'));self.list.setCurrentRow(max(0,self.list.currentRow()))
    def setCurrentIndex(self,index):self.list.setCurrentRow(index)
    def currentIndex(self):return self.list.currentRow()
    def count(self):return self.list.count()
    def widget(self,index):return self.stack.widget(index)
    def currentWidget(self):return self.stack.currentWidget()
    def tabText(self,index):return self.list.item(index).text()


def info_button(text):
    """An info icon whose hover and click show one explanatory paragraph, instead of a paragraph on the page."""
    from .design import icon_button
    b=icon_button('info',None,'quiet',text);b.setFixedSize(26,26);b.setAccessibleName('About this view');b.setAccessibleDescription(text)
    b.clicked.connect(lambda:QToolTip.showText(b.mapToGlobal(QPoint(0,b.height())),text,b));return b


class ElidedLabel(QLabel):
    """Keep the full accessible text, while limiting a single-line context row."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, self.width()))


class ReviewTabs(QTabWidget):
    """Scroll each review page independently; its navigation stays visible."""
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.pages = {}
        self.currentChanged.connect(self.changed)

    def insertTab(self, index, widget, title):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        self.pages[widget] = scroll
        return super().insertTab(index, scroll, title)

    def addTab(self, widget, title):
        return self.insertTab(self.count(), widget, title)

    def setCurrentWidget(self, widget):
        super().setCurrentWidget(self.pages.get(widget, widget))

    def indexOf(self, widget):
        return super().indexOf(self.pages.get(widget, widget))

    def changed(self, index):
        if index >= 0:
            self.window.measurement_scroll = super().currentWidget()
            if self.window.measurement_scroll.widget() is getattr(self.window,'footwork_panel',None):
                self.window.footwork_panel.toggle.setChecked(True)
