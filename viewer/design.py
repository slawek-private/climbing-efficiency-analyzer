"""Portable Qt presentation for the manual climbing workspace."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont,QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QFrame,QTabWidget,QSplitter,QScrollArea,QHeaderView,QAbstractItemView,QComboBox,QTableWidget,QSpinBox,QMessageBox)
from .version import APP_NAME,__version__
from .platform_runtime import GPU_LABEL

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

SHORTCUTS='Space  Play / pause\n← / →  Step (frame step)\nShift+← / →  One frame\nS / E  Climb start / end\nP  Mark point\nL / R  Left / right clip\nQ / W  Left / right rest\nC / V  Left / right chalk\nDelete  Remove selected\nCtrl+S  Save · Ctrl+Z / Ctrl+Y  Undo / redo'

LOADING_HELP=('Opening a video reads the whole file once: it computes the checksum that finds saved measurements for this exact file, '
    'and records the timestamp of every frame so marks are frame-accurate, including variable-frame-rate phone videos. '
    'Large 4K files take a while the first time; afterwards the frame list is cached and opening is fast.')
PREVIEW_HELP=('Prepare smooth preview decodes the whole video once and stores every frame as a compressed 1280-pixel image in a local cache. '
    'Afterwards any frame appears instantly, so scrubbing, zooming the timeline and stepping backwards are smooth, especially for 4K and HEVC. '
    'It takes roughly as long as the video plays and you can keep working meanwhile. Frame numbers and timestamps stay those of the original; '
    'measurements always refer to the original file. Once prepared, the preview is used automatically for this video everywhere. '
    'Disk space is shown in Import & library and can be limited or freed in File › Storage.')

# Per-theme colours for the hand cards and banner, written out instead of derived by the dark-mode mapping.
ACCENTS={'clip':'#2f74ea','rest':'#189a72','chalk':'#9461d9'}
TINTS={False:{'clip':('#e8f0fe','#1f5fd1','#c5d8fb'),'rest':('#e3f5ee','#137054','#bfe5d5'),'chalk':('#f2eafc','#7444b8','#dccaf5')},
       True:{'clip':('#1c3358','#a9c8ff','#34558a'),'rest':('#16403a','#8fe6c1','#2a6352'),'chalk':('#33264d','#d6bdff','#55407a')}}
def extra_style(dark):
    card,border,title,muted,running,banner,banner_border=('#1b283b','#2c3c54','#edf4ff','#8fa1bb','#ffad74','#1c3a5e','#2f5b8f') if dark else ('#f7f9fd','#e1e8f2','#15263f','#7a879b','#d4581f','#e8f0fe','#c5d8fb')
    rules=[f'QFrame#hand {{ background: {card}; border: 1px solid {border}; border-radius: 12px; }}',
           f'QLabel#handTitle {{ font-size: 14px; font-weight: 800; letter-spacing: 1px; color: {title}; }}',
           f'QLabel#timerStatus {{ color: {muted}; font-size: 12px; }}',f'QLabel#timerStatus[state="running"] {{ color: {running}; font-weight: 700; }}',
           f'QLabel#timerStatus[state="recorded"] {{ color: {title}; }}',
           f'QFrame#banner {{ background: {banner}; border: 1px solid {banner_border}; border-radius: 10px; }}']
    for kind,(bg,fg,line) in TINTS[dark].items():
        rules+=[f'QLabel#kind[kind="{kind}"] {{ color: {fg}; font-weight: 700; }}',
                f'QPushButton[role="start"][kind="{kind}"] {{ background: {bg}; color: {fg}; border: 1px solid {line}; }}',
                f'QPushButton[role="start"][kind="{kind}"]:hover {{ border: 1px solid {ACCENTS[kind]}; }}',
                f'QPushButton[role="stop"][kind="{kind}"] {{ background: {ACCENTS[kind]}; color: white; border: 1px solid {ACCENTS[kind]}; font-weight: 800; }}']
    disabled=('#202d40','#5d6f87','#2b394e') if dark else ('#f0f3f7','#a1adbd','#e5eaf0')
    rules.append(f'QPushButton[role][kind]:disabled {{ background: {disabled[0]}; color: {disabled[1]}; border: 1px solid {disabled[2]}; }}')
    return '\n'.join(rules)

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
    root=QWidget();root.setObjectName('workspace');outer=QVBoxLayout(root);outer.setContentsMargins(14,10,14,4);outer.setSpacing(8);w.setCentralWidget(root)
    # Rarely used actions live in the menu bar (native on macOS), keeping the window for the video.
    bar=w.menuBar();menu=bar.addMenu('File')
    for text,cb in [('Projects…',w.show_projects),('New project…',lambda:w.show_projects('new')),('Import project…',lambda:w.show_projects('import')),('Export this project…',lambda:w.show_projects('export'))]:menu.addAction(text,cb)
    menu.addSeparator()
    for text,cb in [('Add videos…',w.open_video),('Load labels…',w.load_labels),('Save athlete',w.save_labels)]:menu.addAction(text,cb)
    menu.addSeparator();menu.addAction('Storage…',w.show_storage)
    menu=bar.addMenu('Export')
    for text,cb in [('All athletes · HTML + CSV…',w.export_all),('PDF report…',w.export_pdf)]:menu.addAction(text,cb)
    menu=bar.addMenu('Measurements');menu.addAction('Clear this athlete…',w.clear_athlete);menu.addAction('Clear measurements…',w.clear_measurements)
    menu=bar.addMenu('View');w.theme_button=menu.addAction('Dark mode',w.toggle_theme);menu.addAction('Fit video',w.image.fit)
    menu=bar.addMenu('Help')
    for text,cb in [('Recording tips…',w.show_tips),('Show tour',w.show_tour),('Keyboard shortcuts',lambda:QMessageBox.information(w,'Keyboard shortcuts',SHORTCUTS))]:menu.addAction(text,cb)
    menu.addSeparator();menu.addAction('Check for updates…',lambda:w.check_updates(manual=True))
    w.auto_update_action=menu.addAction('Check for updates automatically');w.auto_update_action.setCheckable(True);w.auto_update_action.setChecked(w.settings.value('auto_update',True,type=bool));w.auto_update_action.toggled.connect(lambda on:w.settings.setValue('auto_update',on))
    top=QHBoxLayout();top.setSpacing(6);top.addWidget(label(APP_NAME,'brand'));badge=label('v'+__version__,'badge');badge.setWordWrap(False);top.addWidget(badge);top.addSpacing(10)
    w.project_button=button('Project',w.show_projects);w.project_button.setToolTip('Current project. Click to open the project browser: create, switch, export or import projects.');top.addWidget(w.project_button)
    w.collection_bar=QWidget();queue=QHBoxLayout(w.collection_bar);queue.setContentsMargins(0,0,0,0);queue.setSpacing(6)
    queue.addWidget(button('←',lambda:w.next_video(-1)));w.video_selector=QComboBox();w.video_selector.setMinimumWidth(220);w.video_selector.setToolTip('Videos in this project');w.video_selector.currentIndexChanged.connect(w.select_video);queue.addWidget(w.video_selector,1);queue.addWidget(button('→',lambda:w.next_video(1)))
    w.add_button=button('Add videos',w.open_video);w.add_button.setToolTip('Add video files to this project. The folder you used last time is remembered.');queue.addWidget(w.add_button);top.addWidget(w.collection_bar,1)
    top.addSpacing(10);top.addWidget(button('Save athlete',w.save_labels));w.export_button=button('Export all athletes',w.export_all,'primary');top.addWidget(w.export_button)
    outer.addLayout(top)
    # Shown only when a newer release exists.
    w.update_banner=QFrame();w.update_banner.setObjectName('banner');banner=QHBoxLayout(w.update_banner);banner.setContentsMargins(12,6,8,6)
    w.update_text=QLabel();w.update_text.setWordWrap(True);banner.addWidget(w.update_text,1);w.update_buttons={}
    for key,text,role in [('install','Update now','primary'),('notes',"What's new",None),('skip','Skip this version','quiet'),('later','Later','quiet')]:
        b=button(text,lambda checked=False,k=key:w.update_action(k),role);banner.addWidget(b);w.update_buttons[key]=b
    w.update_banner.hide();outer.addWidget(w.update_banner)
    w.progress.setFormat('Opening video · reading every frame timestamp · %p%');w.progress.setTextVisible(True);w.progress.setToolTip(LOADING_HELP);outer.addWidget(w.progress)
    w.main_tabs=QTabWidget();outer.addWidget(w.main_tabs,1)
    split=QSplitter(Qt.Orientation.Horizontal);w.main_tabs.addTab(split,'Video workspace')
    from .library import LibraryTab
    w.library=LibraryTab(w);w.main_tabs.addTab(w.library,'Import && library')
    video=QFrame();video.setObjectName('card');v=QVBoxLayout(video);v.setContentsMargins(10,10,10,8);v.setSpacing(6);w.image.setParent(video);w.image.setBackgroundBrush(QColor('#122137'));v.addWidget(w.image,1)
    w.empty_hint=label('Open a video to begin.\nPlay to the moment you want to measure, pause, then mark it.','muted');w.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter);v.addWidget(w.empty_hint)
    controls=QHBoxLayout();controls.setSpacing(6);w.play_button.setParent(video);w.play_button.setProperty('role','primary');w.play_button.setMinimumWidth(110);controls.addWidget(w.play_button)
    w.step_back_button=button('← 5 frames',lambda:w.step(-1));w.step_forward_button=button('5 frames →',lambda:w.step(1));controls.addWidget(w.step_back_button);controls.addWidget(w.step_forward_button)
    w.frame_step=QSpinBox();w.frame_step.setRange(1,120);w.frame_step.setValue(int(w.settings.value("frame_step",5)));w.frame_step.setPrefix("Step ");w.frame_step.setMaximumWidth(90);w.frame_step.setToolTip('Frames per step button / arrow key. Shift+arrow steps one frame.');w.frame_step.valueChanged.connect(w.set_frame_step);controls.addWidget(w.frame_step);w.set_frame_step(w.frame_step.value())
    w.speed.setParent(video);w.speed.setToolTip('Playback speed');controls.addWidget(w.speed);controls.addStretch()
    w.position.setParent(video);w.position.setObjectName('muted');w.position.setWordWrap(False);w.position.setToolTip('Current frame number and its exact time in the original video.\n\n'+LOADING_HELP);controls.addWidget(w.position);controls.addWidget(button('Fit',w.image.fit,'quiet'));v.addLayout(controls)
    w.slider.hide()
    from .scrubber import PrecisionScrubber
    w.precision_scrubber=PrecisionScrubber();w.precision_scrubber.seek.connect(w.scrub_seconds);w.precision_scrubber.released.connect(w.finish_scrub);v.addWidget(w.precision_scrubber)
    ruler=QHBoxLayout();ruler.setSpacing(6);ruler.addWidget(label('Zoom','muted'));w.timeline_zoom=QComboBox();w.timeline_zoom.setToolTip('Pinch / wheel: zoom · two-finger scroll / right drag: pan')
    for title,seconds in [('Full video',0),('60 seconds',60),('30 seconds',30),('15 seconds',15),('5 seconds',5),('1 second',1)]:w.timeline_zoom.addItem(title,seconds)
    w.timeline_zoom.currentIndexChanged.connect(lambda index:w.precision_scrubber.set_span(w.timeline_zoom.itemData(index)));ruler.addWidget(w.timeline_zoom)
    ruler.addWidget(button('Centre',lambda:w.precision_scrubber.set_span(w.precision_scrubber.span),'quiet'));ruler.addStretch()
    def update_zoom(seconds):
        w.timeline_zoom.blockSignals(True);index=w.timeline_zoom.findData(seconds)
        if index<0:
            if w.timeline_zoom.count()>6:w.timeline_zoom.removeItem(6)
            w.timeline_zoom.addItem(f'{seconds:.2f} seconds',seconds);index=w.timeline_zoom.count()-1
        w.timeline_zoom.setCurrentIndex(index);w.timeline_zoom.blockSignals(False)
    w.precision_scrubber.zoomChanged.connect(update_zoom)
    w.preview_status=label('Original video · prepare once for fast seeking','muted');w.preview_status.setWordWrap(False);w.preview_status.setToolTip(PREVIEW_HELP);ruler.addWidget(w.preview_status);w.preview_button=button('Prepare smooth preview',w.prepare_preview);w.preview_button.setToolTip(PREVIEW_HELP);ruler.addWidget(w.preview_button)
    w.decoder_choice=QComboBox();w.decoder_choice.addItems(['CPU · low latency',GPU_LABEL,'Prepared preview · fast seek']);w.decoder_choice.setToolTip('How frames are decoded. CPU: works everywhere. GPU: hardware decoding, lighter on the processor for H.264/HEVC. Prepared preview: instant random access once a smooth preview exists, and used automatically whenever it does.');w.decoder_choice.currentIndexChanged.connect(w.change_decoder);ruler.addWidget(w.decoder_choice);v.addLayout(ruler);split.addWidget(video)
    panel=QWidget();panel.setObjectName('page');measure=QVBoxLayout(panel);measure.setContentsMargins(12,10,12,10);measure.setSpacing(7);panel.setMinimumWidth(450);measurement_scroll=QScrollArea();measurement_scroll.setWidgetResizable(True);measurement_scroll.setMinimumWidth(475);measurement_scroll.setWidget(panel);split.addWidget(measurement_scroll);split.setSizes([870,500]);w.workspace_tabs=None;w.measurement_scroll=measurement_scroll
    w.boundary_box=QWidget();box=QVBoxLayout(w.boundary_box);box.setContentsMargins(0,0,0,0);box.setSpacing(6)
    line=QHBoxLayout();line.addWidget(w.climber,1);w.climber.setPlaceholderText('Athlete');line.addWidget(label('Attempt','muted'));w.attempt.setMaximumWidth(55);line.addWidget(w.attempt);line.addWidget(button('Clear this athlete',w.clear_athlete,'quiet'));box.addLayout(line)
    line=QHBoxLayout();line.addWidget(button('Climb start · S',w.set_start,'start'));line.addWidget(button('×',lambda:w.clear_boundary('start'),'quiet'));line.addWidget(button('Climb end · E',w.set_failure,'stop'));line.addWidget(button('×',lambda:w.clear_boundary('end'),'quiet'));box.addLayout(line)
    line=QHBoxLayout();line.addWidget(w.start_status);line.addWidget(w.end_status);line.addWidget(button('Edit result',w.edit_climb_outcome,'quiet'));box.addLayout(line);w.duration_status.setObjectName('timer');box.addWidget(w.duration_status);measure.addWidget(w.boundary_box)
    w.point_box=QWidget();box=QVBoxLayout(w.point_box);box.setContentsMargins(0,0,0,0);box.setSpacing(6)
    line=QHBoxLayout();w.point_name.setToolTip('Point name. Defaults to the last point you marked; use the same names for every athlete.');line.addWidget(w.point_name,1);line.addWidget(button('Mark point · P',w.add_point,'primary'));line.addWidget(button('Rename',w.rename_point,'quiet'));line.addWidget(button('Delete',w.delete_point,'quiet'));box.addLayout(line)
    line=QHBoxLayout();line.addWidget(button('Comment at current frame',w.comment_at_frame,'quiet'));line.addWidget(button('Edit selected comment',w.edit_point_comment,'quiet'));box.addLayout(line)
    w.points_table.setMinimumHeight(0);w.points_table.setMaximumHeight(75);box.addWidget(w.points_table);measure.addWidget(w.point_box)
    line=QHBoxLayout();line.addWidget(label('Clip method','muted'));w.clip_method=QComboBox()
    for title,value in [('Not set',None),('Rope to mouth',"mouth"),('Direct · no mouth',"direct")]:w.clip_method.addItem(title,value)
    w.clip_method.setToolTip('Recorded on the clip when its timer stops, then resets.\nRope to mouth: rope pulled up and held in the mouth before clipping.\nDirect: moved to a favourable position and clipped without the mouth.');line.addWidget(w.clip_method,1);line.addWidget(label('Quickdraw #','muted'));w.draw.setMaximumWidth(65);w.draw.setToolTip('Number of the next quickdraw; advances after each completed clip.');line.addWidget(w.draw);measure.addLayout(line)
    # One card per hand; activities share the timeline's colours.
    w.hands_box=QWidget();hands=QHBoxLayout(w.hands_box);hands.setContentsMargins(0,0,0,0);hands.setSpacing(8);w.hand_timer_buttons={};w.hand_timer_status={}
    keys={'clip':{'left':'L','right':'R'},'rest':{'left':'Q','right':'W'},'chalk':{'left':'C','right':'V'}}
    for hand in ('left','right'):
        card=QFrame();card.setObjectName('hand');col=QVBoxLayout(card);col.setContentsMargins(10,8,10,8);col.setSpacing(3)
        title=QHBoxLayout();title.addWidget(label(hand.upper()+' HAND','handTitle'));title.addStretch();title.addWidget(label(' · '.join(keys[k][hand] for k in keys),'muted'));col.addLayout(title)
        for kind in ('clip','rest','chalk'):
            line=QHBoxLayout();line.setSpacing(4);name=label('● '+kind.capitalize(),'kind');name.setProperty('kind',kind);name.setWordWrap(False);name.setFixedWidth(62);line.addWidget(name)
            control=button(f'Start {kind} · {keys[kind][hand]}',lambda checked=False,k=kind,h=hand:w.toggle_hand_timer(k,h),'start');control.setProperty('kind',kind);control.setMinimumHeight(26);line.addWidget(control,1)
            cancel=button('×',lambda checked=False,k=kind,h=hand:w.cancel_hand_timer(k,h),'quiet');cancel.setToolTip('Discard this unfinished timer');line.addWidget(cancel);col.addLayout(line)
            status=label('Ready','timerStatus');status.setWordWrap(False);status.setContentsMargins(66,0,0,4);w.hand_timer_status[kind,hand]=status;col.addWidget(status);w.hand_timer_buttons[kind,hand]=control
        hands.addWidget(card)
    measure.addWidget(w.hands_box);w.legacy_rest_panel=QWidget();legacy=QHBoxLayout(w.legacy_rest_panel);legacy.setContentsMargins(0,0,0,0);legacy.addWidget(label('Earlier rest timer','muted'));legacy.addWidget(button('Stop',w.stop_legacy_rest,'stop'));legacy.addWidget(button('Cancel',lambda:w.cancel_hand_timer('rest','none'),'quiet'));measure.addWidget(w.legacy_rest_panel)
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
    w.pattern_dashboard=Dashboard();w.main_tabs.addTab(w.pattern_dashboard,"Patterns && efficiency")
    from .sync_view import SyncView
    w.sync_view=SyncView(w);w.main_tabs.addTab(w.sync_view,'Side by side');w.main_tabs.setTabToolTip(w.main_tabs.count()-1,'Watch several attempts next to each other, aligned at the climb start or a named point.')
    def tab_changed(index):
        if w.main_tabs.widget(index) is w.sync_view:w.pause();w.sync_view.activate()
        else:
            w.sync_view.pause();w.sync_view.timer.stop()
            if w.isFullScreen():w.showNormal();w.sync_view.full.setText('Full screen')
        if w.main_tabs.widget(index) is w.library:w.library.activate()
    w.main_tabs.currentChanged.connect(tab_changed)
    w.usage_label=label('Resource usage: sampling starts when the app opens.','muted');w.usage_label.setWordWrap(False);w.usage_label.setToolTip('CPU is this process as a fraction of total logical CPU capacity. Core equivalents are CPU time, not a count of busy physical cores. GPU percentage and device VRAM include other programs. App VRAM may be unavailable under Windows WDDM or for video-decoding contexts.');w.statusBar().addPermanentWidget(w.usage_label)
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
    QApplication.instance().setPalette(palette);w.setStyleSheet(style+'\n'+extra_style(dark));w.theme=theme;w.theme_button.setText('Light mode' if dark else 'Dark mode');w.precision_scrubber.dark=dark;w.precision_scrubber.update();w.event_timeline.dark=dark;w.event_timeline.update();w.settings.setValue('theme',theme)
