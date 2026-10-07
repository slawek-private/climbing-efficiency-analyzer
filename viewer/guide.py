"""First-run guidance: recording recommendations and a step-by-step tour of the window."""
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QEvent, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QWidget, QFrame, QScrollArea

TIPS = '''
<h2>Recording climbs for accurate measurements</h2>
<p>Measurements are only as precise as the footage. Choose a camera position that keeps the contacts you want to review visible.</p>
<h3>Camera position</h3>
<ul>
<li><b>Tripod or fixed mount</b>, never handheld. No zooming or panning while recording.</li>
<li><b>Keep the whole climber and relevant holds in frame</b>, with a margin. A front view usually helps compare hand and foot contacts; an oblique side view can help review body position on overhangs. Check for hidden feet before recording.</li>
<li><b>Same spot, same zoom for every athlete</b> on the route, so positions and timings compare directly.</li>
<li>Keep both feet, hands, holds and quickdraws visible. Mark obscured sections as unknown; a foot touching the wall, a smear or a hook still counts as contact.</li>
</ul>
<h3>Resolution and frame rate</h3>
<ul>
<li><b>1080p minimum</b>; <b>4K</b> for tall routes or when filming from far away, where hands and quickdraws become small.</li>
<li><b>60 fps recommended</b>: nominal frame spacing is ~17 ms, compared with ~33 ms at 30 fps. Visibility, blur and judgment still limit annotation precision. 30 fps works; do not convert it to 60 fps to invent detail.</li>
<li>Use higher frame rates only when fast contacts are the question and lighting is sufficient; they increase file size.</li>
<li>Lock focus and exposure (tap and hold on a phone) so the picture does not pump. Avoid filming against bright windows.</li>
<li>Turn <b>HDR video off</b> (iPhone: Settings › Camera › Record Video). HDR clips look flat and washed out here.
H.264 (“Most Compatible”) scrubs most easily; HEVC works too: prepare a smooth preview.</li>
<li>Start recording before the climber touches the wall and stop after they are lowered.</li>
</ul>
<h3>Keep the original file</h3>
<p>Copy videos with a USB cable, AirDrop, the Files app or the camera’s SD card.
<b>YouTube produces playback transcodes; Google Photos “Storage saver” and messaging apps may recompress footage.</b> Google Photos “Original quality” and an original file attached to e-mail can preserve the uploaded file. Download an original or “unmodified original”, rather than a playback copy. Measurements are tied to the exact file, so keep the file you measured.</p>
'''


class TipsDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent);self.setWindowTitle('Recording tips');self.resize(640, 620);self.settings = settings
        layout = QVBoxLayout(self);text = QLabel(TIPS);text.setWordWrap(True);text.setTextFormat(Qt.TextFormat.RichText)
        scroll = QScrollArea();scroll.setWidgetResizable(True);holder = QWidget();inner = QVBoxLayout(holder);inner.addWidget(text);inner.addStretch();scroll.setWidget(holder);layout.addWidget(scroll, 1)
        line = QHBoxLayout();self.again = QCheckBox('Show these tips when Climb Studio starts');self.again.setChecked(settings.value('show_tips', False, type=bool));line.addWidget(self.again);line.addStretch()
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
    """Five steps, shown once a video is loaded so every highlight points at real data."""
    measure=lambda:w.show_view(w.measure_page)
    def panel(widget):
        def before():
            measure()
            page=widget if w.review_tabs.indexOf(widget)>=0 else None
            if page:w.review_tabs.setCurrentWidget(page)
            if widget is w.footwork_panel:w.footwork_panel.toggle.setChecked(True)
            if page:w.measurement_scroll.ensureWidgetVisible(widget,0,40)
        return before
    def video_rect():
        a, b = rect_of(w, w.image), rect_of(w, w.transport)
        return a.united(b) if a and b else a or b
    return [
        dict(title='1 · Find the moment', text='Space plays and pauses; ← → step through frames (Shift for one frame). Drag, pinch or scroll the timeline under the video to zoom down to single frames. The timecode shows exactly where you are.', target=video_rect, before=measure),
        dict(title='2 · Start and end', text='Name the athlete. Pause on the first grip and press S, then on the fall or the top press E. The climb time appears below.', target=lambda:rect_of(w, w.boundary_box), before=panel(w.boundary_box)),
        dict(title='3 · Time each hand', text='Clip, rest and chalk timers for the left and right hand. Press once to start at the current frame, again to stop. A running timer fills its tile and shows its time.', target=lambda:rect_of(w, w.hands_box), before=panel(w.hands_box)),
        dict(title='4 · Named points', text='Mark when the athlete reaches a shared point, such as a rest or the roof (P). Use the same names for every athlete to compare their splits.', target=lambda:rect_of(w, w.point_box), before=panel(w.point_box)),
        dict(title='5 · Review footwork', text='Open Feet review for left/right slips, deliberate releases and both-feet-off intervals. Review coverage explicitly and mark hidden feet as obscured. Confirm intent; intentional dynamic moves stay separate from unplanned releases.', target=lambda:rect_of(w,w.footwork_panel), before=panel(w.footwork_panel)),
        dict(title='6 · Coach and export', text='Record a session goal, athlete reflection and next-session action in Coaching goal. Export a coaching review with an evidence index, printable PDF and optional local video sections. Compare describes timings; it does not rank ability. Replay this tour from Help.', target=lambda:tab_rect(w, w.main_tabs, 1)),
    ]
