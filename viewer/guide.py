"""First-run guidance: recording recommendations and a step-by-step tour of the window."""
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QEvent, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QWidget, QFrame, QScrollArea

TIPS = '''
<h2>Recording climbs for accurate measurements</h2>
<p>Measurements are only as precise as the footage. A few minutes of set-up makes every athlete comparable.</p>
<h3>Camera position</h3>
<ul>
<li><b>Tripod or fixed mount</b>, never handheld. No zooming or panning while recording.</li>
<li><b>Face the wall straight on</b>, far enough back that the whole route, from the start hold to the top, fits in the frame with a margin. Slightly raised is ideal.</li>
<li><b>Same spot, same zoom for every athlete</b> on the route, so positions and timings compare directly.</li>
<li>Keep hands, holds and quickdraws visible. Strong side angles hide clips and hand contacts.</li>
</ul>
<h3>Resolution and frame rate</h3>
<ul>
<li><b>1080p minimum</b>; <b>4K</b> for tall routes or when filming from far away, where hands and quickdraws become small.</li>
<li><b>60 fps recommended</b>: every frame is ~17 ms, so marks are twice as precise as at 30 fps (~33 ms). 30 fps still works.</li>
<li>Slow-motion (120/240 fps) is not needed and creates very large files.</li>
<li>Lock focus and exposure (tap and hold on a phone) so the picture does not pump. Avoid filming against bright windows.</li>
<li>Turn <b>HDR video off</b> (iPhone: Settings › Camera › Record Video). HDR clips look flat and washed out here.
H.264 (“Most Compatible”) scrubs most easily; HEVC works too: prepare a smooth preview.</li>
<li>Start recording before the climber touches the wall and stop after they are lowered.</li>
</ul>
<h3>Keep the original file</h3>
<p>Copy videos with a USB cable, AirDrop, the Files app or the camera’s SD card.
<b>YouTube, Google Photos, WhatsApp, Messenger and e-mail re-encode videos</b>: they recompress them, often lower the resolution or
frame rate, and produce a different file. Google Photos “Storage saver” and iCloud “Optimise storage” keep reduced copies, so download the
original or “unmodified original”. Measurements are tied to the exact file, so keep the file you measured.</p>
'''


class TipsDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent);self.setWindowTitle('Recording tips');self.resize(640, 620);self.settings = settings
        layout = QVBoxLayout(self);text = QLabel(TIPS);text.setWordWrap(True);text.setTextFormat(Qt.TextFormat.RichText)
        scroll = QScrollArea();scroll.setWidgetResizable(True);holder = QWidget();inner = QVBoxLayout(holder);inner.addWidget(text);inner.addStretch();scroll.setWidget(holder);layout.addWidget(scroll, 1)
        line = QHBoxLayout();self.again = QCheckBox('Show these tips when Climb Studio starts');self.again.setChecked(settings.value('show_tips', True, type=bool));line.addWidget(self.again);line.addStretch()
        ok = QPushButton('Got it');ok.setProperty('role', 'primary');ok.clicked.connect(self.accept);line.addWidget(ok);layout.addLayout(line)
    def done(self, result):
        self.settings.setValue('show_tips', self.again.isChecked());super().done(result)


class Tour(QWidget):
    """Dims the window, cuts a spotlight around one control and explains it in a bubble."""
    def __init__(self, window, steps, finished=lambda:None):
        super().__init__(window);self.window = window;self.steps = steps;self.index = 0;self.finished = finished;self.spot = QRect()
        self.bubble = QFrame(self);self.bubble.setObjectName('card');self.bubble.setFixedWidth(360)
        box = QVBoxLayout(self.bubble);box.setContentsMargins(16, 14, 16, 12)
        self.title = QLabel();self.title.setObjectName('section');self.text = QLabel();self.text.setWordWrap(True);self.count = QLabel();self.count.setObjectName('muted')
        for widget in (self.title, self.text):box.addWidget(widget)
        line = QHBoxLayout();line.addWidget(self.count);line.addStretch()
        self.skip = QPushButton('Skip tour');self.skip.setProperty('role', 'quiet');self.back = QPushButton('Back');self.next = QPushButton('Next');self.next.setProperty('role', 'primary')
        self.skip.clicked.connect(self.close_tour);self.back.clicked.connect(lambda:self.show_step(self.index-1));self.next.clicked.connect(lambda:self.show_step(self.index+1))
        for b in (self.skip, self.back, self.next):line.addWidget(b)
        box.addLayout(line);window.installEventFilter(self)
    def start(self):self.setGeometry(self.window.rect());self.show();self.raise_();self.show_step(0)
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize and self.isVisible():self.setGeometry(self.window.rect());self.place()
        return False
    def show_step(self, index):
        if index >= len(self.steps):return self.close_tour()
        self.index = max(0, index);step = self.steps[self.index]
        if step.get('before'):step['before']()
        self.title.setText(step['title']);self.text.setText(step['text']);self.count.setText(f'{self.index+1} / {len(self.steps)}')
        self.back.setEnabled(self.index > 0);self.next.setText('Finish' if self.index == len(self.steps)-1 else 'Next');self.place()
        QTimer.singleShot(60, self.place)  # again once tab switches and scrolling have settled the layout
    def place(self):
        if not self.isVisible():return
        rect = self.steps[self.index]['target']()
        self.spot = rect.adjusted(-6, -6, 6, 6) if rect else QRect();self.bubble.adjustSize();b = self.bubble.size();area = self.rect()
        if self.spot.isNull():x, y = (area.width()-b.width())//2, (area.height()-b.height())//2
        else:
            below = self.spot.bottom()+12+b.height() <= area.height();x = self.spot.center().x()-b.width()//2
            y = self.spot.bottom()+12 if below else self.spot.top()-12-b.height()
            if y < 0:x, y = (self.spot.right()+12 if self.spot.right()+12+b.width() <= area.width() else self.spot.left()-12-b.width()), self.spot.center().y()-b.height()//2
        self.bubble.move(max(8, min(area.width()-b.width()-8, x)), max(8, min(area.height()-b.height()-8, y)));self.update()
    def paintEvent(self, event):
        p = QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);path = QPainterPath();path.addRect(QRectF(self.rect()))
        if not self.spot.isNull():
            hole = QPainterPath();hole.addRoundedRect(QRectF(self.spot), 10, 10);path = path.subtracted(hole)
            p.setPen(QColor('#ffb74d'));p.drawRoundedRect(QRectF(self.spot), 10, 10)
        p.fillPath(path, QColor(5, 12, 24, 165))
    def close_tour(self):
        self.window.removeEventFilter(self);self.hide();self.deleteLater();self.finished()


def rect_of(window, widget):
    """A widget's rectangle in window coordinates, or None when it is not on screen."""
    if widget is None or not widget.isVisible():return None
    return QRect(widget.mapTo(window, QPoint(0, 0)), widget.size())


def tab_rect(window, tabs, index):
    bar = tabs.tabBar();r = bar.tabRect(index);return QRect(bar.mapTo(window, r.topLeft()), r.size())


def steps(w):
    workspace = lambda:w.main_tabs.setCurrentIndex(0)
    def panel(widget):
        def before():workspace();w.measurement_scroll.ensureWidgetVisible(widget, 0, 40)
        return before
    return [
        dict(title='Welcome to Climb Studio', text='A one-minute tour of where everything is. You can replay it any time from Help › Show tour.', target=lambda:None),
        dict(title='Projects', text='Group videos, measurements and reports per event or route, e.g. “SYCC Genf”. Open the project browser here to create, switch, export or import projects.', target=lambda:rect_of(w, w.project_button), before=workspace),
        dict(title='Videos in this project', text='Switch between the project’s videos here, or step through them with ← →. Add videos imports more files.', target=lambda:rect_of(w, w.collection_bar)),
        dict(title='Import & library', text='See every video’s resolution, frame rate and storage needs, and prepare smooth previews in bulk while you do something else.', target=lambda:tab_rect(w, w.main_tabs, 1)),
        dict(title='The video', text='Play with Space, step frames with ← → (Shift for one frame). Pinch or scroll to zoom into the picture.', target=lambda:rect_of(w, w.image), before=workspace),
        dict(title='Timeline', text='Drag to scrub. Pinch or scroll to zoom the timeline down to single frames; marked rests, clips and chalking appear as coloured bars.', target=lambda:rect_of(w, w.precision_scrubber)),
        dict(title='Smooth preview', text='For 4K or HEVC videos, prepare a smooth preview once: scrubbing and stepping backwards become instant. Hover any control for an explanation.', target=lambda:rect_of(w, w.preview_button)),
        dict(title='Athlete, start and end', text='Name the athlete, then pause on the first grip and press Climb start (S), and on the fall or top press Climb end (E).', target=lambda:rect_of(w, w.boundary_box), before=panel(w.boundary_box)),
        dict(title='Named points', text='Mark when the athlete reaches a shared point (P). Use the same names for every athlete; the last name used is kept.', target=lambda:rect_of(w, w.point_box), before=panel(w.point_box)),
        dict(title='Left hand and right hand', text='Each hand has its own clip, rest and chalk timers. Press once to start, again to stop. Keys are shown on each button.', target=lambda:rect_of(w, w.hands_box), before=panel(w.hands_box)),
        dict(title='Everything recorded', text='The recorded timeline and table list every interval. Click to jump, double-click to edit, Delete removes.', target=lambda:rect_of(w, w.event_timeline), before=panel(w.event_timeline)),
        dict(title='Compare and report', text='Compare athletes, view charts and patterns, or watch several attempts Side by side aligned at the climb start.', target=lambda:tab_rect(w, w.main_tabs, 2).united(tab_rect(w, w.main_tabs, w.main_tabs.count()-1))),
        dict(title='Save and export', text='Save athlete stores the measurements; Export all athletes writes HTML + CSV. PDF, storage, updates and these tips live in the menus.', target=lambda:rect_of(w, w.export_button)),
    ]
