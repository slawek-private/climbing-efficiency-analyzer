"""Portable Qt presentation for the manual climbing workspace."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QFrame,QTabWidget,QSplitter,QScrollArea,QHeaderView,QAbstractItemView,QComboBox,QTableWidget,QSpinBox)
from .version import APP_NAME,__version__

STYLE='''
QWidget { font-family: "Segoe UI", "Arial"; font-size: 13px; color: #25334a; }
QMainWindow, QWidget#workspace { background: #f2f5fa; }
QFrame#card, QWidget#page { background: #ffffff; border-radius: 14px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 24px; font-weight: 700; color: #15263f; }
QLabel#muted { color: #65748b; font-size: 12px; }
QLabel#section { font-size: 15px; font-weight: 700; }
QLabel#timer { font-size: 17px; font-weight: 600; color: #125a62; }
QLabel#badge { background: #e3eaf6; color: #365578; border-radius: 10px; padding: 5px 10px; font-size: 12px; }
QPushButton { background: #ffffff; border: 1px solid #d8e1ed; border-radius: 8px; padding: 8px 12px; min-height: 18px; font-weight: 600; }
QPushButton:hover { background: #eaf1fb; border-color: #8ba9d0; }
QPushButton:pressed { background: #dce8f7; }
QPushButton[role="primary"] { background: #2265d8; color: white; border-color: #2265d8; }
QPushButton[role="primary"]:hover { background: #174fb1; }
QPushButton[role="start"] { background: #e5f5ef; color: #137054; border-color: #c3e5d8; }
QPushButton[role="stop"] { background: #fff0e8; color: #9b4721; border-color: #f4d8c9; }
QPushButton[role="quiet"] { background: transparent; border: none; color: #6c7b91; padding: 4px; }
QPushButton:disabled { background: #f0f3f7; color: #a1adbd; border-color: #e5eaf0; }
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox { background: white; border: 1px solid #d7e0ec; border-radius: 7px; padding: 7px; selection-background-color: #2265d8; }
QLineEdit:focus,QSpinBox:focus,QComboBox:focus { border: 1px solid #2265d8; }
QComboBox QAbstractItemView { background: white; selection-background-color: #e4edfd; selection-color: #25334a; }
QTabWidget::pane { border: none; background: white; border-radius: 12px; }
QTabBar::tab { background: transparent; color: #68778e; padding: 12px 18px; border-bottom: 3px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #2265d8; border-bottom: 3px solid #2265d8; }
QTabBar::tab:hover { background: #eaf1fb; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #f3f6fa; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #c6d2e3; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height: 0; }
QTableWidget { background: white; alternate-background-color: #f7f9fc; border: 1px solid #e4eaf2; border-radius: 8px; gridline-color: #edf1f7; selection-background-color: #e1ecff; selection-color: #174fa7; }
QHeaderView { background: #f3f6fb; }
QHeaderView::section { background: #f3f6fb; border: none; padding: 6px 8px; color: #60708a; font-size: 11px; font-weight: 600; }
QSlider::groove:horizontal { background: #d9e2ee; height: 6px; border-radius: 3px; }
QSlider::sub-page:horizontal { background: #2265d8; border-radius: 3px; }
QSlider::handle:horizontal { background: #2265d8; border: 3px solid white; width: 14px; height: 14px; margin: -7px 0; border-radius: 10px; }
QSplitter::handle { background: transparent; width: 12px; }
QStatusBar { background: #f2f5fa; color: #68778e; }
QProgressBar { border: none; background: #e3ebf6; border-radius: 6px; text-align: center; }
QProgressBar::chunk { background: #2265d8; border-radius: 6px; }
'''

def label(text,name=None):
    w=QLabel(text)
    if name:w.setObjectName(name)
    w.setWordWrap(True);return w

def button(text,callback,role=None):
    w=QPushButton(text);w.clicked.connect(callback)
    if role:w.setProperty('role',role)
    return w

def card(title):
    frame=QFrame();frame.setObjectName('card');layout=QVBoxLayout(frame);layout.setContentsMargins(16,14,16,14);layout.setSpacing(9);layout.addWidget(label(title,'section'));return frame,layout

def page(tabs,title):
    content=QWidget();content.setObjectName('page');layout=QVBoxLayout(content);layout.setContentsMargins(14,14,14,14);layout.setSpacing(12)
    scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(content);tabs.addTab(scroll,title);return layout

def build(w):
    # Retain inherited editor fields and callbacks while moving visible controls.
    old=w.takeCentralWidget();old.setParent(w);old.hide();w.legacy_widget=old
    root=QWidget();root.setObjectName('workspace');outer=QVBoxLayout(root);outer.setContentsMargins(22,18,22,10);outer.setSpacing(16);w.setCentralWidget(root)
    top=QHBoxLayout();brand=QVBoxLayout();brand.setSpacing(2);brand.addWidget(label(APP_NAME,'brand'));brand.addWidget(label('Blue route  /  Manual measurement workspace','muted'));top.addLayout(brand)
    badge=label('v'+__version__,'badge');badge.setFixedHeight(30);top.addWidget(badge);top.addStretch();w.theme_button=button('Dark mode',w.toggle_theme);top.addWidget(w.theme_button)
    for text,cb,role in [('Add videos',w.open_video,None),('Load labels',w.load_labels,None),('Save athlete',w.save_labels,None),('Clear measurements',w.clear_measurements,'stop'),('Export all athletes',w.export_all,'primary'),('PDF',w.export_pdf,None)]:top.addWidget(button(text,cb,role))
    outer.addLayout(top);outer.addWidget(w.progress)
    queue=QHBoxLayout();queue.addWidget(label('VIDEO COLLECTION','muted'));queue.addWidget(button('← Previous',lambda:w.next_video(-1)));w.video_selector=QComboBox();w.video_selector.setMinimumWidth(300);w.video_selector.currentIndexChanged.connect(w.select_video);queue.addWidget(w.video_selector,1);queue.addWidget(button('Next →',lambda:w.next_video(1)));outer.addLayout(queue)
    w.main_tabs=QTabWidget();outer.addWidget(w.main_tabs,1)
    split=QSplitter(Qt.Orientation.Horizontal);w.main_tabs.addTab(split,'Video workspace')
    video,v=card('VIDEO');w.image.setParent(video);w.image.setBackgroundBrush(QColor('#122137'));v.addWidget(w.image,1)
    w.empty_hint=label('Open a video to begin.\nPlay to the moment you want to measure, pause, then mark it.','muted');w.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter);v.addWidget(w.empty_hint)
    controls=QHBoxLayout();w.play_button.setParent(video);w.play_button.setProperty('role','primary');controls.addWidget(w.play_button)
    w.step_back_button=button('← 5 frames',lambda:w.step(-1));w.step_forward_button=button('5 frames →',lambda:w.step(1));controls.addWidget(w.step_back_button);controls.addWidget(w.step_forward_button);controls.addStretch();controls.addWidget(label('Speed','muted'));w.speed.setParent(video);controls.addWidget(w.speed);controls.addWidget(button('Fit view',w.image.fit));v.addLayout(controls)
    w.slider.hide()
    from .scrubber import PrecisionScrubber
    w.precision_scrubber=PrecisionScrubber();w.precision_scrubber.seek.connect(w.scrub_seconds);w.precision_scrubber.released.connect(w.finish_scrub);v.addWidget(w.precision_scrubber)
    ruler=QHBoxLayout();ruler.addWidget(label('Timeline zoom','muted'));w.timeline_zoom=QComboBox()
    for title,seconds in [('Full video',0),('60 seconds',60),('30 seconds',30),('15 seconds',15),('5 seconds',5),('1 second',1)]:w.timeline_zoom.addItem(title,seconds)
    w.timeline_zoom.currentIndexChanged.connect(lambda index:w.precision_scrubber.set_span(w.timeline_zoom.itemData(index)));ruler.addWidget(w.timeline_zoom)
    ruler.addWidget(button('Centre on playhead',lambda:w.precision_scrubber.set_span(w.precision_scrubber.span),'quiet'));ruler.addStretch();ruler.addWidget(label('Wheel: zoom · Shift+wheel / right drag: pan','muted'));v.addLayout(ruler)
    def update_zoom(seconds):
        w.timeline_zoom.blockSignals(True);index=w.timeline_zoom.findData(seconds)
        if index<0:
            if w.timeline_zoom.count()>6:w.timeline_zoom.removeItem(6)
            w.timeline_zoom.addItem(f'{seconds:.2f} seconds',seconds);index=w.timeline_zoom.count()-1
        w.timeline_zoom.setCurrentIndex(index);w.timeline_zoom.blockSignals(False)
    w.precision_scrubber.zoomChanged.connect(update_zoom)
    w.position.setParent(video);w.position.setObjectName('muted');v.addWidget(w.position)
    decode=QHBoxLayout();decode.addWidget(label('Video decoder','muted'));w.decoder_choice=QComboBox();w.decoder_choice.addItems(['CPU · low latency','NVIDIA GPU · CUDA','Prepared preview · fast seek']);w.decoder_choice.currentIndexChanged.connect(w.change_decoder);decode.addWidget(w.decoder_choice);decode.addStretch();decode.addWidget(label("Frame step","muted"));w.frame_step=QSpinBox();w.frame_step.setRange(1,120);w.frame_step.setValue(int(w.settings.value("frame_step",5)));w.frame_step.setMaximumWidth(75);w.frame_step.valueChanged.connect(w.set_frame_step);decode.addWidget(w.frame_step);w.set_frame_step(w.frame_step.value());v.addLayout(decode);split.addWidget(video)
    preview_line=QHBoxLayout();w.preview_button=button('Prepare smooth preview',w.prepare_preview,'primary');preview_line.addWidget(w.preview_button);w.preview_status=label('Original video · prepare once for fast seeking','muted');preview_line.addWidget(w.preview_status,1);v.addLayout(preview_line)
    panel=QWidget();panel.setObjectName('page');measure=QVBoxLayout(panel);measure.setContentsMargins(12,10,12,10);measure.setSpacing(7);panel.setMinimumWidth(450);measurement_scroll=QScrollArea();measurement_scroll.setWidgetResizable(True);measurement_scroll.setMinimumWidth(475);measurement_scroll.setWidget(panel);split.addWidget(measurement_scroll);split.setSizes([870,500]);w.workspace_tabs=None
    line=QHBoxLayout();line.addWidget(w.climber,1);w.climber.setPlaceholderText('Athlete');line.addWidget(label('Attempt','muted'));w.attempt.setMaximumWidth(55);line.addWidget(w.attempt);line.addWidget(button('Clear this athlete',w.clear_athlete,'quiet'));measure.addLayout(line)
    line=QHBoxLayout();line.addWidget(button('Climb start · S',w.set_start,'start'));line.addWidget(button('×',lambda:w.clear_boundary('start'),'quiet'));line.addWidget(button('Climb end · E',w.set_failure,'stop'));line.addWidget(button('×',lambda:w.clear_boundary('end'),'quiet'));measure.addLayout(line)
    line=QHBoxLayout();line.addWidget(w.start_status);line.addWidget(w.end_status);line.addWidget(button('Edit result',w.edit_climb_outcome,'quiet'));measure.addLayout(line);w.duration_status.setObjectName('timer');measure.addWidget(w.duration_status)
    line=QHBoxLayout();line.addWidget(w.point_name,1);line.addWidget(button('Mark point · P',w.add_point,'primary'));line.addWidget(button('Rename',w.rename_point,'quiet'));line.addWidget(button('Delete',w.delete_point,'quiet'));measure.addLayout(line)
    line=QHBoxLayout();line.addWidget(button('Comment at current frame',w.comment_at_frame,'quiet'));line.addWidget(button('Edit selected comment',w.edit_point_comment,'quiet'));measure.addLayout(line)
    w.points_table.setMinimumHeight(0);w.points_table.setMaximumHeight(75);measure.addWidget(w.points_table)
    line=QHBoxLayout();line.addWidget(label('REST · CLIP · CHALK','muted'));line.addStretch();line.addWidget(label('Draw #','muted'));w.draw.setMaximumWidth(65);line.addWidget(w.draw);measure.addLayout(line)
    grid=QGridLayout();grid.setSpacing(5);w.hand_timer_buttons={};w.hand_timer_status={}
    for row,kind in enumerate(('clip','rest','chalk')):
        for col,hand in enumerate(('left','right')):
            key={'clip':{'left':'L','right':'R'},'rest':{'left':'Q','right':'W'},'chalk':{'left':'C','right':'V'}}[kind][hand]
            cell=QWidget();tile=QVBoxLayout(cell);tile.setContentsMargins(0,0,0,0);tile.setSpacing(5);cell.setMinimumHeight(65);line=QHBoxLayout();line.setSpacing(3)
            control=button(hand.capitalize()+' '+kind+' · '+key,lambda checked=False,k=kind,h=hand:w.toggle_hand_timer(k,h),'start');control.setMinimumHeight(22);line.addWidget(control,1);line.addWidget(button('×',lambda checked=False,k=kind,h=hand:w.cancel_hand_timer(k,h),'quiet'));tile.addLayout(line);status=label('Ready','muted');status.setWordWrap(False);status.setFixedHeight(20);w.hand_timer_status[kind,hand]=status;tile.addWidget(status);w.hand_timer_buttons[kind,hand]=control;grid.addWidget(cell,row,col)
    measure.addLayout(grid);w.legacy_rest_panel=QWidget();legacy=QHBoxLayout(w.legacy_rest_panel);legacy.setContentsMargins(0,0,0,0);legacy.addWidget(label('Earlier rest timer','muted'));legacy.addWidget(button('Stop',w.stop_legacy_rest,'stop'));legacy.addWidget(button('Cancel',lambda:w.cancel_hand_timer('rest','none'),'quiet'));measure.addWidget(w.legacy_rest_panel)
    measure.addWidget(label('Recorded timeline · climb-relative seconds','section'))
    from .timeline import EventTimeline
    w.event_timeline=EventTimeline();w.event_timeline.seek.connect(w.seek_seconds);w.event_timeline.selected.connect(w.select_timeline_event);measure.addWidget(w.event_timeline)
    w.table.setMinimumHeight(140);measure.addWidget(w.table,1)
    line=QHBoxLayout()
    for text,cb in [('Edit',w.edit_event),('Delete selected',w.delete_event),('Undo',w.undo),('Redo',w.redo)]:line.addWidget(button(text,cb))
    measure.addLayout(line)
    for table in (w.table,w.points_table):
        table.setAlternatingRowColors(True);table.setShowGrid(False);table.verticalHeader().hide();table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    comparison=QWidget();comparison.setObjectName('page');c=QVBoxLayout(comparison);c.setContentsMargins(20,20,20,20);c.addWidget(label('Compare every climb','brand'));w.collection_summary=label('Add multiple videos to start comparing.','muted');c.addWidget(w.collection_summary);c.addWidget(label('Times are seconds from climb start. Double-click an athlete to return to their video. Changes appear here immediately. Unmarked data stays unknown.','muted'));w.comparison_table=QTableWidget();w.comparison_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);w.comparison_table.setAlternatingRowColors(True);w.comparison_table.setShowGrid(False);w.comparison_table.verticalHeader().hide();w.comparison_table.cellDoubleClicked.connect(w.comparison_open);c.addWidget(w.comparison_table,2);c.addWidget(label('Rest, clip & chalk timing · seconds from climb start','section'));w.comparison_activity_table=QTableWidget(0,6);w.comparison_activity_table.setHorizontalHeaderLabels(['Athlete','Activity','Hand','Start in climb (s)','End in climb (s)','Duration (s)']);w.comparison_activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);w.comparison_activity_table.setAlternatingRowColors(True);w.comparison_activity_table.setShowGrid(False);w.comparison_activity_table.verticalHeader().hide();w.comparison_activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);c.addWidget(w.comparison_activity_table,1);c.addWidget(button('Export this comparison · HTML + CSV',w.export_all,'primary'));w.main_tabs.addTab(comparison,'Compare athletes')
    from .charts import ComparisonCharts
    w.comparison_charts=ComparisonCharts();w.main_tabs.addTab(w.comparison_charts,'Charts')
    from .dashboard import Dashboard
    w.pattern_dashboard=Dashboard();w.main_tabs.addTab(w.pattern_dashboard,"Patterns & efficiency")
    foot=QHBoxLayout();foot.addWidget(label('Space  Play/pause   S/E  Climb start/end   P  Point   L/R  Clip   Q/W  Rest   C/V  Chalk   Delete  Remove selected   Shift+arrows  1 frame   Ctrl+S  Save','muted'));foot.addStretch();foot.addWidget(label('Local processing  •  HTML + CSV comparison','muted'));outer.addLayout(foot)
    w.usage_label=label('Resource usage: sampling starts when the app opens.','muted');w.usage_label.setToolTip('CPU is this process as a fraction of total logical CPU capacity. Core equivalents are CPU time, not a count of busy physical cores. GPU percentage and device VRAM include other programs. App VRAM may be unavailable under Windows WDDM or for video-decoding contexts.');outer.addWidget(w.usage_label)
    apply_theme(w,w.settings.value('theme','light'));w.setWindowTitle(APP_NAME+' · v'+__version__)


def apply_theme(w,theme):
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication
    dark=theme=='dark';style=STYLE
    mapping={'#125a62':'#79dccb','#f2f5fa':'#101824','#ffffff':'#182333','#25334a':'#d6e2f4','#15263f':'#edf4ff','#65748b':'#9dadc5','#68778e':'#9dadc5','#e3eaf6':'#28394f','#365578':'#b3c9e8','#d8e1ed':'#34445c','#eaf1fb':'#243a55','#8ba9d0':'#52769e','#dce8f7':'#2b4464','#e5f5ef':'#173f36','#137054':'#8ce3bb','#c3e5d8':'#285746','#fff0e8':'#4a3027','#9b4721':'#ffc4a1','#f4d8c9':'#78513c','#6c7b91':'#a9b7cc','#f0f3f7':'#202d40','#a1adbd':'#66788f','#e5eaf0':'#2b394e','#d7e0ec':'#34445c','#e4edfd':'#29486e','#f3f6fa':'#152131','#c6d2e3':'#40536c','#f7f9fc':'#1c2a3e','#e4eaf2':'#34445c','#edf1f7':'#24344a','#e1ecff':'#2c4c73','#174fa7':'#c5ddff','#f3f6fb':'#1e2c40','#60708a':'#a5b8d2','#d9e2ee':'#34445c','#e3ebf6':'#26384f'}
    if dark:
        import re
        style=re.sub(r'#[0-9a-fA-F]{6}',lambda m:mapping.get(m.group(),m.group()),style)
        style=style.replace('background: white','background: #182333')
    palette=QPalette()
    for role,color in [(QPalette.ColorRole.Window,'#101824' if dark else '#f2f5fa'),(QPalette.ColorRole.Base,'#182333' if dark else '#ffffff'),(QPalette.ColorRole.AlternateBase,'#1c2a3e' if dark else '#f7f9fc'),(QPalette.ColorRole.Button,'#24344a' if dark else '#ffffff'),(QPalette.ColorRole.WindowText,'#d6e2f4' if dark else '#25334a'),(QPalette.ColorRole.Text,'#d6e2f4' if dark else '#25334a'),(QPalette.ColorRole.ButtonText,'#d6e2f4' if dark else '#25334a'),(QPalette.ColorRole.Highlight,'#2265d8'),(QPalette.ColorRole.HighlightedText,'#ffffff')]:palette.setColor(role,QColor(color))
    QApplication.instance().setPalette(palette);w.setStyleSheet(style);w.theme=theme;w.theme_button.setText('Light mode' if dark else 'Dark mode');w.precision_scrubber.dark=dark;w.precision_scrubber.update();w.event_timeline.dark=dark;w.event_timeline.update();w.settings.setValue('theme',theme)
