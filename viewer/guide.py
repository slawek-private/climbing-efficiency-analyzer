"""First-run guidance: recording recommendations and a step-by-step tour of the window."""
from PySide6.QtCore import Qt, QRect, QRectF, QPoint, QEvent, QTimer, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QWidget, QFrame, QScrollArea, QListWidget, QTextBrowser

TIPS = '''
<h2>Recording climbs for accurate measurements</h2>
<p>Measurements are only as precise as the footage. Choose a camera position that keeps the contacts you want to review visible.</p>
<h3 id="camera">Camera position</h3>
<ul>
<li><b>Tripod or fixed mount</b>, never handheld. No zooming or panning while recording.</li>
<li><b>Keep the whole climber and relevant holds in frame</b>, with a margin. A front view usually helps compare hand and foot contacts; an oblique side view can help review body position on overhangs. Check for hidden feet before recording.</li>
<li><b>Same spot, same zoom for every athlete</b> on the route, so positions and timings compare directly.</li>
<li>Keep both feet, hands, holds and quickdraws visible. Mark obscured sections as unknown; a foot touching the wall, a smear or a hook still counts as contact.</li>
</ul>
<h3 id="quality">Resolution and frame rate</h3>
<ul>
<li><b>1080p minimum</b>; <b>4K</b> for tall routes or when filming from far away, where hands and quickdraws become small.</li>
<li><b>60 fps recommended</b>: nominal frame spacing is ~17 ms, compared with ~33 ms at 30 fps. Visibility, blur and judgment still limit annotation precision. 30 fps works; do not convert it to 60 fps to invent detail.</li>
<li>Use higher frame rates only when fast contacts are the question and lighting is sufficient; they increase file size.</li>
<li>Lock focus and exposure (tap and hold on a phone) so the picture does not pump. Avoid filming against bright windows.</li>
<li>Turn <b>HDR video off</b> (iPhone: Settings › Camera › Record Video). HDR clips look flat and washed out here.
H.264 (“Most Compatible”) scrubs most easily; HEVC works too: prepare a smooth preview.</li>
<li>Start recording before the climber touches the wall and stop after they are lowered.</li>
</ul>
<h3 id="original">Keep the original file</h3>
<p>Copy videos with a USB cable, AirDrop, the Files app or the camera’s SD card.
<b>YouTube produces playback transcodes; Google Photos “Storage saver” and messaging apps may recompress footage.</b> Google Photos “Original quality” and an original file attached to e-mail can preserve the uploaded file. Download an original or “unmodified original”, rather than a playback copy. Measurements are tied to the exact file, so keep the file you measured.</p>
'''


class TipsDialog(QDialog):
    """Recording guidance as a page: contents on the left, text in the app's type scale on the right."""
    SECTIONS = [('Camera position', 'camera'), ('Resolution and frame rate', 'quality'), ('Keep the original file', 'original')]
    def __init__(self, parent, settings):
        super().__init__(parent);self.setWindowTitle('Recording tips');self.resize(760, 600);self.settings = settings
        layout = QVBoxLayout(self);row = QHBoxLayout();row.setSpacing(16);layout.addLayout(row, 1)
        self.contents = QListWidget();self.contents.setObjectName('sideTabs');self.contents.setFixedWidth(190);self.contents.setFrameShape(QFrame.Shape.NoFrame)
        for title, _ in self.SECTIONS:self.contents.addItem(title)
        self.contents.currentRowChanged.connect(lambda i:self.text.scrollToAnchor(self.SECTIONS[i][1]) if i >= 0 else None);row.addWidget(self.contents)
        self.text = QTextBrowser();self.text.setFrameShape(QFrame.Shape.NoFrame);self.text.setOpenExternalLinks(True)
        ink = parent.palette().windowText().color().name() if parent else '#20252b'
        self.text.document().setDefaultStyleSheet(f'body {{ font-size: 13px; color: {ink}; }} h2 {{ font-size: 20px; font-weight: 600; margin-bottom: 4px; }} h3 {{ font-size: 15px; font-weight: 600; margin-top: 18px; }} p, li {{ line-height: 1.45; }}')
        self.text.setHtml(TIPS);self.text.setStyleSheet('QTextBrowser { background: transparent; }');row.addWidget(self.text, 1)
        line = QHBoxLayout();line.addStretch();ok = QPushButton('Got it');ok.setProperty('role', 'primary');ok.clicked.connect(self.accept);line.addWidget(ok);layout.addLayout(line)
        self.again = QCheckBox();self.again.setChecked(settings.value('show_tips', False, type=bool));self.again.hide()


class Tour(QWidget):
    """Dims the window, cuts a spotlight around one control and explains it in a bubble."""
    def __init__(self, window, steps, finished=lambda:None):
        super().__init__(window);self.window = window;self.steps = steps;self.index = 0;self.finished = finished;self.spot = QRect();self.glide = None;self.pointer = None
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
        target = rect.adjusted(-6, -6, 6, 6) if rect else QRect()
        if not self.spot.isNull() and not target.isNull() and target != self.spot:
            self.glide = QVariantAnimation(self);self.glide.setDuration(150);self.glide.setStartValue(self.spot);self.glide.setEndValue(target);self.glide.setEasingCurve(QEasingCurve.Type.OutCubic)
            self.glide.valueChanged.connect(lambda value:(setattr(self, 'spot', value), self.update()));self.glide.start()
        self.spot = target;self.bubble.adjustSize();b = self.bubble.size();area = self.rect();self.pointer = None
        if self.spot.isNull():x, y = (area.width()-b.width())//2, (area.height()-b.height())//2
        else:
            below = self.spot.bottom()+12+b.height() <= area.height();x = self.spot.center().x()-b.width()//2
            y = self.spot.bottom()+12 if below else self.spot.top()-12-b.height();self.pointer = 'up' if below else 'down'
            if y < 0:x, y = (self.spot.right()+12 if self.spot.right()+12+b.width() <= area.width() else self.spot.left()-12-b.width()), self.spot.center().y()-b.height()//2;self.pointer = 'left' if x > self.spot.center().x() else 'right'
        self.bubble.move(max(8, min(area.width()-b.width()-8, x)), max(8, min(area.height()-b.height()-8, y)));self.update()
    def paintEvent(self, event):
        p = QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);path = QPainterPath();path.addRect(QRectF(self.rect()))
        if not self.spot.isNull():
            hole = QPainterPath();hole.addRoundedRect(QRectF(self.spot), 10, 10);path = path.subtracted(hole)
            p.setPen(QColor('#ffb74d'));p.drawRoundedRect(QRectF(self.spot), 10, 10)
        p.fillPath(path, QColor(5, 12, 24, 165))
        if self.pointer and not self.spot.isNull():
            g = self.bubble.geometry();c = self.spot.center();fill = self.bubble.palette().window().color();p.setPen(Qt.PenStyle.NoPen);p.setBrush(fill);s = 9
            if self.pointer == 'up':x = max(g.left()+16, min(g.right()-16, c.x()));p.drawPolygon(QPolygonF([QPointF(x-s, g.top()+1), QPointF(x+s, g.top()+1), QPointF(x, g.top()-s)]))
            elif self.pointer == 'down':x = max(g.left()+16, min(g.right()-16, c.x()));p.drawPolygon(QPolygonF([QPointF(x-s, g.bottom()), QPointF(x+s, g.bottom()), QPointF(x, g.bottom()+s)]))
            elif self.pointer == 'left':y = max(g.top()+16, min(g.bottom()-16, c.y()));p.drawPolygon(QPolygonF([QPointF(g.left()+1, y-s), QPointF(g.left()+1, y+s), QPointF(g.left()-s, y)]))
            else:y = max(g.top()+16, min(g.bottom()-16, c.y()));p.drawPolygon(QPolygonF([QPointF(g.right(), y-s), QPointF(g.right(), y+s), QPointF(g.right()+s, y)]))
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
        dict(title='1 · Find the moment', text='Space plays and pauses; ← → step frames, Shift for one frame. Scroll or pinch the timeline to zoom down to single frames.', target=video_rect, before=measure),
        dict(title='2 · Start and end', text='Pause on the first grip and press S; on the fall or the top press E. Climb time appears here.', target=lambda:rect_of(w, w.boundary_box), before=panel(w.boundary_box)),
        dict(title='3 · Time each hand', text='Clip, rest and chalk timers per hand: press once to start at this frame, again to stop. A running tile fills and pulses.', target=lambda:rect_of(w, w.hands_box), before=panel(w.hands_box)),
        dict(title='4 · Named points', text='Press P when the athlete reaches a shared point such as the roof. Same names for every athlete, so splits compare.', target=lambda:rect_of(w, w.point_box), before=panel(w.point_box)),
        dict(title='5 · Review footwork', text='Feet: slips, deliberate releases and both-feet-off intervals. Mark hidden feet as obscured so coverage stays honest.', target=lambda:rect_of(w,w.footwork_panel), before=panel(w.footwork_panel)),
        dict(title='6 · Compare and export', text='Compare athletes and attempts, then export a coaching review or comparison. Timings describe; they do not rank ability. Replay this tour from Help.', target=lambda:tab_rect(w, w.main_tabs, 1)),
    ]
