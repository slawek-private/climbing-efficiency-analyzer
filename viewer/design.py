"""Portable Qt presentation for the manual climbing workspace.

Layout rules: show the current step and hide the rest; one primary action per screen, drawn
monochrome so colour stays reserved for the data (clip blue, rest green, chalk purple, points
amber, climb end red); every fact drawn once.
"""
from PySide6.QtCore import Qt,QRect
from PySide6.QtGui import QColor,QPainter,QAction,QKeySequence
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QFrame,QTabWidget,QSplitter,QScrollArea,QHeaderView,
    QAbstractItemView,QComboBox,QTableWidget,QSpinBox,QMessageBox,QMenu,QDialog,QFormLayout,QCheckBox,QDialogButtonBox,QStyledItemDelegate,QStyle,QSizePolicy)
from .version import APP_NAME,__version__
from .platform_runtime import GPU_LABEL,timecode_font

STYLE='''
QWidget { font-size: 13px; color: #25334a; }
QMainWindow, QWidget#workspace { background: #f2f5fa; }
QFrame#card, QWidget#page { background: #ffffff; border-radius: 14px; }
QFrame#step { background: #ffffff; border: 1px solid #e1e8f2; border-radius: 10px; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 20px; font-weight: 700; color: #15263f; }
QLabel#muted { color: #65748b; font-size: 12px; }
QLabel#section { font-size: 14px; font-weight: 600; }
QLabel#eyebrow { color: #65748b; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
QLabel#timer { font-size: 15px; font-weight: 600; color: #15263f; }
QLabel#timecode { font-size: 19px; font-weight: 600; color: #15263f; }
QPushButton { background: #ffffff; border: 1px solid #d8e1ed; border-radius: 8px; padding: 7px 12px; min-height: 18px; font-weight: 500; }
QPushButton:hover { background: #eaf1fb; border-color: #8ba9d0; }
QPushButton:focus { border: 2px solid #2265d8; }
QPushButton:pressed { background: #dce8f7; }
QPushButton[role="quiet"] { background: transparent; border: none; color: #6c7b91; padding: 4px 6px; }
QPushButton[role="quiet"]:hover { color: #15263f; }
QPushButton[kind] { min-height: 34px; }
QPushButton[keycap="true"] { padding-right: 36px; }
QPushButton:disabled { background: #f0f3f7; color: #a1adbd; border-color: #e5eaf0; }
QPushButton::menu-indicator { width: 0; }
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox { background: white; border: 1px solid #d7e0ec; border-radius: 7px; padding: 6px 7px; selection-background-color: #2265d8; }
QLineEdit:focus,QSpinBox:focus,QComboBox:focus { border: 1px solid #2265d8; }
QComboBox QAbstractItemView { background: white; selection-background-color: #e4edfd; selection-color: #25334a; }
QTabWidget::pane { border: none; background: white; border-radius: 12px; }
QTabBar::tab { background: transparent; color: #68778e; padding: 10px 18px; border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: #15263f; border-bottom: 2px solid #15263f; }
QTabBar::tab:hover { color: #15263f; }
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

SHORTCUTS='Space  Play / pause\n← / →  Step (step size in Settings)\nShift+← / →  One frame\nS / E  Climb start / end\nP  Mark point\nL / R  Left / right clip\nQ / W  Left / right rest\nC / V  Left / right chalk\nDelete  Remove selected\nCtrl+[ / Ctrl+]  Previous / next video\nCtrl+Z / Ctrl+Y  Undo / redo\nMeasurements save automatically.'

for shortcut in ('Ctrl+[','Ctrl+]','Ctrl+Z','Ctrl+Y'):
    SHORTCUTS=SHORTCUTS.replace(shortcut,QKeySequence(shortcut).toString(QKeySequence.SequenceFormat.NativeText))

LOADING_HELP=('Opening a video reads the whole file once: it computes the checksum that finds saved measurements for this exact file, '
    'and records the timestamp of every frame so marks are frame-accurate, including variable-frame-rate phone videos. '
    'Large 4K files take a while the first time; afterwards the frame list is cached and opening is fast.')
PREVIEW_HELP=('Prepare smooth preview decodes the whole video once and stores every frame as a compressed 1280-pixel image in a local cache. '
    'Afterwards any frame appears instantly, so scrubbing, zooming the timeline and stepping backwards are smooth, especially for 4K and HEVC. '
    'It takes roughly as long as the video plays and you can keep working meanwhile. Frame numbers and timestamps stay those of the original; '
    'measurements always refer to the original file. Once prepared, the preview is used automatically for this video everywhere. '
    'Disk space is shown in Library and can be limited or freed in File › Storage.')
CHECKLIST='Best results: tripod, wall straight on · 1080p or 4K at 60 fps · the original file, not a copy from WhatsApp, YouTube or Google Photos.'

# Colour owned by the data; actions are monochrome.
ACCENTS={'clip':'#245fc4','rest':'#117451','chalk':'#7844b5'}
TINTS={False:{'clip':('#e8f0fe','#1f5fd1','#c5d8fb'),'rest':('#e3f5ee','#137054','#bfe5d5'),'chalk':('#f2eafc','#7444b8','#dccaf5')},
       True:{'clip':('#1c3358','#a9c8ff','#34558a'),'rest':('#16403a','#8fe6c1','#2a6352'),'chalk':('#33264d','#d6bdff','#55407a')}}
def extra_style(dark):
    ink,on_ink,ink_hover,muted,banner,banner_border,drop,drop_line,warn=('#e8edf4','#101824','#ffffff','#8fa1bb','#1c3a5e','#2f5b8f','#0d1522','#43546d','#ffad74') if dark else ('#141a24','#ffffff','#2b3442','#7a879b','#e8f0fe','#c5d8fb','#122137','#4d6180','#c4521c')
    rules=[f'QPushButton[role="primary"] {{ background: {ink}; color: {on_ink}; border: 1px solid {ink}; font-weight: 600; }}',
           f'QPushButton[role="primary"]:hover {{ background: {ink_hover}; border-color: {ink_hover}; }}',
           f'QPushButton[role="primary"]:disabled {{ background: transparent; color: {muted}; border: 1px solid {muted}; }}',
           f'QFrame#banner {{ background: {banner}; border: 1px solid {banner_border}; border-radius: 10px; }}',
           f'QFrame#drop {{ background: {drop}; border: 2px dashed {drop_line}; border-radius: 12px; }}',
           'QFrame#drop QLabel { color: #c4d1e4; } QFrame#drop QLabel#dropTitle { color: #ffffff; font-size: 24px; font-weight: 700; }',
           'QFrame#drop QPushButton[role="quiet"] { color: #c4d1e4; text-decoration: underline; }',
           f'QLabel#saveState[state="error"] {{ color: {warn}; font-weight: 600; }}',
           f'QLabel#handTitle {{ font-size: 11px; font-weight: 700; letter-spacing: 1px; color: {muted}; }}']
    for kind,(bg,fg,line) in TINTS[dark].items():
        rules+=[f'QPushButton[role="start"][kind="{kind}"] {{ background: {bg}; color: {fg}; border: 1px solid {line}; font-weight: 600; }}',
                f'QPushButton[role="start"][kind="{kind}"]:hover {{ border: 1px solid {ACCENTS[kind]}; }}',
                f'QPushButton[role="stop"][kind="{kind}"] {{ background: {ACCENTS[kind]}; color: white; border: 1px solid {ACCENTS[kind]}; font-weight: 700; }}']
    disabled=('#202d40','#7b8ca3','#2b394e') if dark else ('#f0f3f7','#8996a8','#e5eaf0')
    rules.append(f'QPushButton[role][kind]:disabled {{ background: {disabled[0]}; color: {disabled[1]}; border: 1px solid {disabled[2]}; }}')
    return '\n'.join(rules)

def label(text,name=None,wrap=True):
    w=QLabel(text)
    if name:w.setObjectName(name)
    w.setWordWrap(wrap);return w

def button(text,callback,role=None):
    w=QPushButton(text);w.clicked.connect(callback)
    if role:w.setProperty('role',role)
    return w

class KeyButton(QPushButton):
    """A button that shows its keyboard shortcut as a small keycap on the right."""
    def __init__(self,text,key,callback=None,role=None):
        super().__init__(text);self.key=key;self.setProperty('keycap',True)
        if role:self.setProperty('role',role)
        if callback:self.clicked.connect(callback)
        self.setToolTip(f'{text} · key {key}')
    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);font=p.font();font.setPointSizeF(max(8.,font.pointSizeF()-2));font.setBold(False);p.setFont(font)
        width=max(18,p.fontMetrics().horizontalAdvance(self.key)+10);rect=QRect(self.width()-width-9,(self.height()-18)//2,width,18)
        colour=self.palette().buttonText().color() if self.isEnabled() else self.palette().color(self.palette().ColorGroup.Disabled,self.palette().ColorRole.ButtonText)
        if self.property('role') in ('stop','primary'):colour=QColor('white') if self.property('role')=='stop' else colour
        colour.setAlpha(255);p.setPen(colour);p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(rect,4,4);p.drawText(rect,Qt.AlignmentFlag.AlignCenter,self.key)

class BarDelegate(QStyledItemDelegate):
    """Draws a proportional bar before the value; the item's UserRole holds the number, UserRole+2 the maximum."""
    def paint(self,painter,option,index):
        value=index.data(Qt.ItemDataRole.UserRole);maximum=index.data(Qt.ItemDataRole.UserRole+2) or 0
        self.initStyleOption(option,index)
        if option.state & QStyle.StateFlag.State_Selected:painter.fillRect(option.rect,option.palette.highlight())
        if isinstance(value,(int,float)) and maximum>0:
            r=option.rect.adjusted(8,0,-8,0);bar=QRect(r.left(),r.center().y()-4,max(2,int(56*value/maximum)),8)
            painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor('#189a72'));painter.drawRoundedRect(bar,2,2);painter.restore()
            text_rect=r.adjusted(66,0,0,0)
        else:text_rect=option.rect.adjusted(8,0,-8,0)
        painter.save();painter.setPen(option.palette.text().color());painter.drawText(text_rect,Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,option.text);painter.restore()

def step_card(name):
    frame=QFrame();frame.setObjectName('step');box=QVBoxLayout(frame);box.setContentsMargins(10,8,10,9);box.setSpacing(6)
    if name:box.addWidget(label(name,'eyebrow',wrap=False))
    return frame,box

def menu_button(text,items,tip):
    b=QPushButton(text);b.setProperty('role','quiet');b.setToolTip(tip);menu=QMenu(b)
    for title,callback in items:
        if title is None:menu.addSeparator()
        else:menu.addAction(title,callback)
    b.setMenu(menu);return b

class SettingsDialog(QDialog):
    """Rarely changed technical settings, moved out of the workspace."""
    def __init__(self,w):
        super().__init__(w);self.setWindowTitle('Settings');form=QFormLayout(self)
        w.decoder_choice=QComboBox();w.decoder_choice.addItems(['CPU · low latency',GPU_LABEL,'Prepared preview · fast seek']);w.decoder_choice.currentIndexChanged.connect(w.change_decoder)
        w.decoder_choice.setToolTip('Automatic by default: the GPU decoder where the file allows it, the smooth preview whenever one exists.')
        form.addRow('Video decoder',w.decoder_choice)
        w.frame_step=QSpinBox();w.frame_step.setRange(1,120);w.frame_step.setValue(int(w.settings.value("frame_step",5)));w.frame_step.setSuffix(' frames');w.frame_step.valueChanged.connect(w.set_frame_step)
        w.frame_step.setToolTip('Frames moved by ← / → and the step buttons. Shift+← / → always moves one frame.');form.addRow('Step size',w.frame_step)
        updates=QCheckBox('Check for updates automatically');updates.setChecked(w.settings.value('auto_update',True,type=bool));updates.toggled.connect(lambda on:(w.settings.setValue('auto_update',on),w.auto_update_action.setChecked(on)))
        form.addRow('',updates);storage=button('Storage…',w.show_storage);form.addRow('Cache',storage)
        close=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);close.rejected.connect(self.reject);form.addRow(close)

def build(w):
    # Retain inherited editor fields and callbacks while moving visible controls.
    old=w.takeCentralWidget();old.setParent(w);old.hide();w.legacy_widget=old
    root=QWidget();root.setObjectName('workspace');outer=QVBoxLayout(root);outer.setContentsMargins(14,10,14,4);outer.setSpacing(8);w.setCentralWidget(root)
    w.settings_dialog=SettingsDialog(w)
    # Menu bar (native on macOS): everything that is not part of measuring a climb.
    bar=w.menuBar();menu=bar.addMenu('File')
    for text,cb in [('Projects…',w.show_projects),('New project…',lambda:w.show_projects('new')),('Import project…',lambda:w.show_projects('import')),('Export this project…',lambda:w.show_projects('export'))]:menu.addAction(text,cb)
    menu.addSeparator()
    for text,cb in [('Add videos…',w.open_video),('Load labels…',w.load_labels)]:menu.addAction(text,cb)
    menu.addSeparator();menu.addAction('Storage…',w.show_storage)
    settings=QAction('Settings…',w);settings.setMenuRole(QAction.MenuRole.PreferencesRole);settings.setShortcut('Ctrl+,');settings.triggered.connect(w.settings_dialog.exec);menu.addAction(settings)
    export_items=[('Selected attempts · HTML + CSV…',w.export_all),('PDF report…',w.export_pdf),(None,None),('This project as a file…',lambda:w.show_projects('export'))]
    menu=bar.addMenu('Export')
    for text,cb in export_items:
        if text:menu.addAction(text,cb)
        else:menu.addSeparator()
    menu=bar.addMenu('Measurements');menu.addAction('Clear this athlete…',w.clear_athlete);menu.addAction('Clear measurements…',w.clear_measurements)
    menu=bar.addMenu('View');w.theme_button=menu.addAction('Dark mode',w.toggle_theme);menu.addAction('Fit video',w.image.fit)
    menu=bar.addMenu('Help')
    for text,cb in [('Recording tips…',w.show_tips),('Show tour',w.show_tour),('Keyboard shortcuts',lambda:QMessageBox.information(w,'Keyboard shortcuts',SHORTCUTS))]:menu.addAction(text,cb)
    menu.addSeparator();menu.addAction('Check for updates…',lambda:w.check_updates(manual=True))
    w.auto_update_action=menu.addAction('Check for updates automatically');w.auto_update_action.setCheckable(True);w.auto_update_action.setChecked(w.settings.value('auto_update',True,type=bool));w.auto_update_action.toggled.connect(lambda on:w.settings.setValue('auto_update',on))
    menu.addAction('Diagnostics…',w.show_diagnostics)
    about=QAction(f'About {APP_NAME}',w);about.setMenuRole(QAction.MenuRole.AboutRole);about.triggered.connect(w.show_about);menu.addAction(about)
    # Header: project, video, save state, export.
    top=QHBoxLayout();top.setSpacing(8)
    w.project_button=button('Project',w.show_projects);w.project_button.setToolTip('Current project. Click to create, switch, export or import projects.');top.addWidget(w.project_button)
    w.collection_bar=QWidget();queue=QHBoxLayout(w.collection_bar);queue.setContentsMargins(0,0,0,0);queue.setSpacing(8)
    w.video_selector=QComboBox();w.video_selector.setMinimumWidth(100);w.video_selector.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);w.video_selector.setPlaceholderText('No videos yet: drop them into the window');w.video_selector.setToolTip('Videos in this project · Ctrl+[ / Ctrl+] for previous / next')
    w.video_selector.currentIndexChanged.connect(w.select_video);queue.addWidget(w.video_selector,1)
    w.video_count=label('','muted',wrap=False);queue.addWidget(w.video_count)
    w.add_button=button('+ Add videos',w.open_video);w.add_button.setToolTip('Add video files to this project, or drop them anywhere in the window. The last folder used is remembered.');queue.addWidget(w.add_button)
    top.addWidget(w.collection_bar,1);top.addSpacing(6)
    w.save_state=label('','saveState',wrap=False);w.save_state.setToolTip('Measurements save automatically to the project’s labels folder.');top.addWidget(w.save_state)
    w.export_button=QPushButton('Export ▾');w.export_button.setToolTip('Export the selected route and attempts from Compare; detailed measurements are included');export_menu=QMenu(w.export_button)
    for text,cb in export_items:
        if text:export_menu.addAction(text,cb)
        else:export_menu.addSeparator()
    w.export_button.setMenu(export_menu);top.addWidget(w.export_button);outer.addLayout(top)
    # Shown only when a newer release exists.
    w.update_banner=QFrame();w.update_banner.setObjectName('banner');banner=QHBoxLayout(w.update_banner);banner.setContentsMargins(12,6,8,6)
    w.update_text=QLabel();w.update_text.setWordWrap(True);banner.addWidget(w.update_text,1);w.update_buttons={}
    for key,text,role in [('install','Update now','primary'),('notes',"What's new",None),('skip','Skip this version','quiet'),('later','Later','quiet')]:
        b=button(text,lambda checked=False,k=key:w.update_action(k),role);banner.addWidget(b);w.update_buttons[key]=b
    w.update_banner.hide();outer.addWidget(w.update_banner)
    w.save_banner=QFrame();w.save_banner.setObjectName('banner');failure=QHBoxLayout(w.save_banner);w.save_detail=label('');failure.addWidget(w.save_detail,1)
    for text,cb in [('Retry',w.autosave),('Save copy…',w.save_copy),('Show folder',w.show_save_folder)]:failure.addWidget(button(text,cb))
    w.save_banner.hide();outer.addWidget(w.save_banner)
    w.progress.setFormat('Opening video · reading every frame timestamp · %p%');w.progress.setTextVisible(True);w.progress.setToolTip(LOADING_HELP);outer.addWidget(w.progress)
    # Three places: measure one climb, compare climbs, manage the videos.
    w.main_tabs=QTabWidget();w.main_tabs.setDocumentMode(True);outer.addWidget(w.main_tabs,1)
    split=QSplitter(Qt.Orientation.Horizontal);w.main_tabs.addTab(split,'Measure');w.measure_page=split
    video=QFrame();video.setObjectName('card');v=QVBoxLayout(video);v.setContentsMargins(10,10,10,8);v.setSpacing(6)
    w.empty_hint=QFrame();w.empty_hint.setObjectName('drop');drop=QVBoxLayout(w.empty_hint);drop.setContentsMargins(24,24,24,24);drop.addStretch()
    w.drop_title=label('Drop climbing videos here','dropTitle');w.drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter);drop.addWidget(w.drop_title)
    line=QHBoxLayout();line.addStretch();w.drop_choose=button('Choose files…',w.open_video,'primary');line.addWidget(w.drop_choose);line.addWidget(button('Open project…',w.show_projects));line.addStretch();drop.addLayout(line)
    w.drop_note=label('MP4, MOV or MKV · originals stay where they are, nothing is uploaded','muted');w.drop_note.setAlignment(Qt.AlignmentFlag.AlignCenter);drop.addWidget(w.drop_note)
    checklist=label(CHECKLIST,'muted');checklist.setAlignment(Qt.AlignmentFlag.AlignCenter);drop.addSpacing(10);drop.addWidget(checklist)
    line=QHBoxLayout();line.addStretch();line.addWidget(button('Recording tips',w.show_tips,'quiet'));line.addStretch();drop.addLayout(line);drop.addStretch()
    v.addWidget(w.empty_hint,1)
    w.image.setParent(video);w.image.setBackgroundBrush(QColor('#122137'));w.image.setAcceptDrops(False);w.image.viewport().setAcceptDrops(False);v.addWidget(w.image,1)
    from .scrubber import PrecisionScrubber
    w.precision_scrubber=PrecisionScrubber();w.precision_scrubber.seek.connect(w.scrub_seconds);w.precision_scrubber.released.connect(w.finish_scrub);v.addWidget(w.precision_scrubber)
    w.slider.hide()
    w.transport=QWidget();transport_rows=QVBoxLayout(w.transport);transport_rows.setContentsMargins(0,0,0,0);transport_rows.setSpacing(4);controls=QHBoxLayout();controls.setSpacing(4);transport_rows.addLayout(controls);secondary=QHBoxLayout();secondary.setSpacing(4);transport_rows.addLayout(secondary)
    w.play_button.setParent(w.transport);w.play_button.setProperty('role','primary');w.play_button.setMinimumWidth(80);controls.addWidget(w.play_button)
    w.step_back_button=button('◀',lambda:w.step(-1));w.step_forward_button=button('▶',lambda:w.step(1))
    for b in (w.step_back_button,w.step_forward_button):b.setFixedWidth(40);controls.addWidget(b)
    w.speed.setParent(w.transport);w.speed.setToolTip('Playback speed');controls.addWidget(w.speed);controls.addStretch()
    w.position.setParent(w.transport);w.position.setObjectName('timecode');w.position.setWordWrap(False);w.position.setTextFormat(Qt.TextFormat.RichText);w.position.setToolTip('Playhead: minutes:seconds.milliseconds and the frame number in the original video.\n\n'+LOADING_HELP)
    font=timecode_font();font.setPixelSize(19);w.position.setFont(font);controls.addWidget(w.position);controls.addStretch()
    w.timeline_zoom=QComboBox();w.timeline_zoom.setToolTip('Timeline zoom · pinch or scroll on the timeline; two-finger swipe or right-drag pans')
    for title,seconds in [('Full video',0),('60 s',60),('30 s',30),('15 s',15),('5 s',5),('1 s',1)]:w.timeline_zoom.addItem(title,seconds)
    w.timeline_zoom.currentIndexChanged.connect(lambda index:w.precision_scrubber.set_span(w.timeline_zoom.itemData(index)));secondary.addWidget(w.timeline_zoom)
    def update_zoom(seconds):
        w.timeline_zoom.blockSignals(True);index=w.timeline_zoom.findData(seconds)
        if index<0:
            if w.timeline_zoom.count()>6:w.timeline_zoom.removeItem(6)
            w.timeline_zoom.addItem(f'{seconds:.2f} s',seconds);index=w.timeline_zoom.count()-1
        w.timeline_zoom.setCurrentIndex(index);w.timeline_zoom.blockSignals(False)
    w.precision_scrubber.zoomChanged.connect(update_zoom)
    w.preview_status=label('','muted',wrap=False);w.preview_status.hide()
    w.preview_button=button('Prepare smooth preview',w.prepare_preview);w.preview_button.setToolTip(PREVIEW_HELP);secondary.addWidget(w.preview_button)
    secondary.addWidget(button('Fit',w.image.fit,'quiet'));secondary.addStretch();w.inspector_button=button('Hide controls',w.toggle_inspector,'quiet');secondary.addWidget(w.inspector_button);v.addWidget(w.transport)
    w.active_timers=label('','timer');w.active_timers.setWordWrap(True);v.addWidget(w.active_timers)
    split.addWidget(video)
    w.set_frame_step(w.frame_step.value())
    # The measuring panel follows the climb: athlete, start and end, timers during the climb, review.
    panel=QWidget();panel.setObjectName('page');measure=QVBoxLayout(panel);measure.setContentsMargins(10,10,10,10);measure.setSpacing(8);panel.setMinimumWidth(380)
    measurement_scroll=QScrollArea();measurement_scroll.setWidgetResizable(True);measurement_scroll.setMinimumWidth(400);measurement_scroll.setWidget(panel);split.addWidget(measurement_scroll);split.setSizes([950,380]);w.workspace_tabs=None;w.measurement_scroll=measurement_scroll
    w.empty_panel=label('Load a video to start measuring.\n\nThe panel then follows the climb: name the athlete, mark the start, time each hand’s clips, rests and chalking, mark the end.','muted');measure.addWidget(w.empty_panel)
    w.boundary_box,box=step_card('ATHLETE · START · END')
    line=QHBoxLayout();line.addWidget(w.climber,1);w.climber.setPlaceholderText('Athlete name');line.addWidget(label('Attempt','muted',wrap=False));w.attempt.setMaximumWidth(55);line.addWidget(w.attempt)
    line.addWidget(menu_button('⋯',[('New attempt',w.new_attempt),('Open another attempt…',w.choose_attempt),('Set route…',w.set_route),(None,None),('Clear this athlete…',w.clear_athlete),('Clear measurements…',w.clear_measurements)],'More actions for this athlete'));box.addLayout(line)
    line=QHBoxLayout();w.start_button=KeyButton('Mark start','S',w.set_start);w.start_button.setToolTip('Pause on the first grip, then mark the climb start (S). Press again to move it to the current frame.');line.addWidget(w.start_button,1)
    w.start_clear=button('×',lambda:w.clear_boundary('start'),'quiet');w.start_clear.setToolTip('Remove the climb start');w.start_clear.setAccessibleName('Remove climb start');line.addWidget(w.start_clear);box.addLayout(line);line=QHBoxLayout()
    w.end_button=KeyButton('Mark end','E',w.set_failure);w.end_button.setToolTip('Pause on the fall (rope weighted) or the top, then mark the end (E).');line.addWidget(w.end_button,1)
    w.end_edit=button('✎',w.edit_climb_outcome,'quiet');w.end_edit.setToolTip('Change the result: fell or topped');w.end_edit.setAccessibleName('Change climb result');line.addWidget(w.end_edit)
    w.end_clear=button('×',lambda:w.clear_boundary('end'),'quiet');w.end_clear.setToolTip('Remove the climb end');w.end_clear.setAccessibleName('Remove climb end');line.addWidget(w.end_clear);box.addLayout(line)
    w.duration_status.setObjectName('timer');box.addWidget(w.duration_status)
    for hidden in (w.start_status,w.end_status):hidden.setParent(w.boundary_box);hidden.hide()
    measure.addWidget(w.boundary_box)
    w.climb_box,box=step_card('DURING THE CLIMB')
    line=QHBoxLayout();line.addWidget(label('Clip method','muted',wrap=False));w.clip_method=QComboBox()
    for title,value in [('Not set',None),('Rope to mouth',"mouth"),('Direct · no mouth',"direct")]:w.clip_method.addItem(title,value)
    w.clip_method.setToolTip('Captured separately for each hand when its clip timer starts. Changing this selector affects the next clip only.\nRope to mouth: rope pulled up and held in the mouth before clipping.\nDirect: moved to a favourable position and clipped without the mouth.')
    line.addWidget(w.clip_method,1);line.addWidget(label('Quickdraw','muted',wrap=False));w.draw.setMaximumWidth(62);w.draw.setToolTip('Number of the next quickdraw; advances after each completed clip.');line.addWidget(w.draw);box.addLayout(line)
    # Timers: two columns (hands) × three activities, in the timeline's colours. A running tile fills and shows its time.
    w.hands_box=QWidget();grid=QGridLayout(w.hands_box);grid.setContentsMargins(0,0,0,0);grid.setHorizontalSpacing(8);grid.setVerticalSpacing(6);w.hand_timer_buttons={};w.hand_timer_cancel={};w.hand_timer_status={}
    keys={'clip':{'left':'L','right':'R'},'rest':{'left':'Q','right':'W'},'chalk':{'left':'C','right':'V'}}
    for col,hand in enumerate(('left','right')):
        grid.addWidget(label(hand.upper()+' HAND','handTitle',wrap=False),0,col)
        for row,kind in enumerate(('clip','rest','chalk'),1):
            cell=QWidget();line=QHBoxLayout(cell);line.setContentsMargins(0,0,0,0);line.setSpacing(2)
            control=KeyButton(kind.capitalize(),keys[kind][hand],lambda checked=False,k=kind,h=hand:w.toggle_hand_timer(k,h),'start');control.setProperty('kind',kind);control.setMinimumHeight(44);control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);control.setAccessibleName(hand.capitalize()+' hand '+kind)
            control.setToolTip(f'{hand.capitalize()} hand {kind}: press to start the timer at this frame, press again to stop it (key {keys[kind][hand]}).');line.addWidget(control,1)
            cancel=button('×',lambda checked=False,k=kind,h=hand:w.cancel_hand_timer(k,h),'quiet');cancel.setToolTip('Discard this running timer');cancel.setAccessibleName('Discard '+hand+' '+kind+' timer');cancel.setFixedWidth(22);line.addWidget(cancel)
            w.hand_timer_buttons[kind,hand]=control;w.hand_timer_cancel[kind,hand]=cancel;grid.addWidget(cell,row,col)
    box.addWidget(w.hands_box)
    w.point_box=QWidget();points=QVBoxLayout(w.point_box);points.setContentsMargins(0,4,0,0);points.setSpacing(6)
    line=QHBoxLayout();w.point_name.setToolTip('Point name. Starts as the point marked most recently; use the same names for every athlete.');line.addWidget(w.point_name,1)
    line.addWidget(KeyButton('Mark point','P',w.add_point))
    line.addWidget(menu_button('⋯',[('Rename selected point…',w.rename_point),('Delete selected point',w.delete_point),(None,None),('Comment at current frame…',w.comment_at_frame),('Edit selected comment…',w.edit_point_comment)],'Rename, delete or comment points'))
    points.addLayout(line);w.points_table.setMinimumHeight(0);w.points_table.setMaximumHeight(96);points.addWidget(w.points_table);box.addWidget(w.point_box)
    w.legacy_rest_panel=QWidget();legacy=QHBoxLayout(w.legacy_rest_panel);legacy.setContentsMargins(0,0,0,0);legacy.addWidget(label('Earlier rest timer','muted'));legacy.addWidget(button('Stop',w.stop_legacy_rest));legacy.addWidget(button('Cancel',lambda:w.cancel_hand_timer('rest','none'),'quiet'));box.addWidget(w.legacy_rest_panel)
    measure.addWidget(w.climb_box)
    w.events_card,box=step_card('')
    w.events_toggle=button('Events',w.toggle_events,'quiet');w.events_toggle.setStyleSheet('text-align: left; font-weight: 600;');box.addWidget(w.events_toggle)
    w.events_body=QWidget();body=QVBoxLayout(w.events_body);body.setContentsMargins(0,0,0,0);body.setSpacing(6)
    w.table.setMinimumHeight(140);body.addWidget(w.table,1)
    line=QHBoxLayout()
    for text,cb in [('Edit',w.edit_event),('Delete',w.delete_event)]:line.addWidget(button(text,cb))
    line.addStretch()
    for text,cb in [('Undo',w.undo),('Redo',w.redo)]:line.addWidget(button(text,cb,'quiet'))
    body.addLayout(line);review=QGridLayout()
    for i,(key,checkbox) in enumerate(w.review.items()):
        checkbox.setText(key.replace('_',' ').capitalize()+' reviewed');review.addWidget(checkbox,i//2,i%2)
    body.addLayout(review);box.addWidget(w.events_body,1);measure.addWidget(w.events_card,1)
    w.events_body.setVisible(w.settings.value('events_open',False,type=bool))
    for table in (w.table,w.points_table):
        table.setAlternatingRowColors(True);table.setShowGrid(False);table.verticalHeader().hide();table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    # Compare: a leaderboard first, every other view one click away.
    w.compare_page=QWidget();cp=QVBoxLayout(w.compare_page);cp.setContentsMargins(0,6,0,0);w.compare_tabs=QTabWidget();w.compare_tabs.setDocumentMode(True)
    from .compare_scope import CompareScope
    w.compare_scope=CompareScope();w.compare_scope.changed.connect(w.refresh_comparison);cp.addWidget(w.compare_scope);cp.addWidget(w.compare_tabs)
    comparison=QWidget();comparison.setObjectName('page');c=QVBoxLayout(comparison);c.setContentsMargins(16,14,16,14);c.setSpacing(8);w.comparison_page=comparison
    w.collection_summary=label('Measure at least one climb to compare.','muted');c.addWidget(w.collection_summary)
    w.comparison_table=QTableWidget();w.comparison_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);w.comparison_table.setAlternatingRowColors(True);w.comparison_table.setShowGrid(False);w.comparison_table.verticalHeader().hide()
    w.comparison_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);w.comparison_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);w.comparison_table.setSortingEnabled(True)
    w.comparison_table.cellDoubleClicked.connect(w.comparison_open);w.comparison_table.itemSelectionChanged.connect(w.comparison_selected);w.comparison_table.setToolTip('Click a column to sort. Select an athlete for details; double-click to open their video.')
    w.bar_delegate=BarDelegate(w.comparison_table);c.addWidget(w.comparison_table,3)
    w.comparison_detail_title=label('Select an athlete to see every rest, clip and chalk.','section');c.addWidget(w.comparison_detail_title)
    w.comparison_activity_table=QTableWidget(0,7);w.comparison_activity_table.setHorizontalHeaderLabels(['Activity','Hand','Quickdraw','Clip method','Start (s)','End (s)','Duration (s)'])
    w.comparison_activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);w.comparison_activity_table.setAlternatingRowColors(True);w.comparison_activity_table.setShowGrid(False);w.comparison_activity_table.verticalHeader().hide();w.comparison_activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    c.addWidget(w.comparison_activity_table,2);w.compare_tabs.addTab(comparison,'Table')
    from .charts import ComparisonCharts
    w.comparison_charts=ComparisonCharts();w.compare_tabs.addTab(w.comparison_charts,'Charts')
    from .dashboard import Dashboard
    w.pattern_dashboard=Dashboard();w.compare_tabs.addTab(w.pattern_dashboard,'More metrics')
    from .sync_view import SyncView
    w.sync_view=SyncView(w);w.compare_tabs.addTab(w.sync_view,'Side by side');w.compare_tabs.setTabToolTip(w.compare_tabs.count()-1,'Watch several attempts next to each other, aligned at the climb start or a named point.')
    w.main_tabs.addTab(w.compare_page,'Compare')
    from .library import LibraryTab
    w.library=LibraryTab(w);w.main_tabs.addTab(w.library,'Library')
    def view_changed(*_):
        if w.sync_active():w.pause();w.sync_view.activate()
        else:
            w.sync_view.pause();w.sync_view.timer.stop()
            if w.isFullScreen():w.showNormal();w.sync_view.full.setText('Full screen')
        if w.main_tabs.currentWidget() is w.library:w.library.activate()
    w.main_tabs.currentChanged.connect(view_changed);w.compare_tabs.currentChanged.connect(view_changed)
    # Kept for Help › Diagnostics; the status bar is for messages only.
    w.usage_label=label('Resource usage: sampling starts when the app opens.','muted');w.usage_label.hide()
    w.setAcceptDrops(True)
    apply_theme(w,w.settings.value('theme','light'));w.setWindowTitle(APP_NAME)


def apply_theme(w,theme):
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication
    dark=theme=='dark';style=STYLE
    mapping={'#125a62':'#79dccb','#f2f5fa':'#101824','#ffffff':'#182333','#25334a':'#d6e2f4','#15263f':'#edf4ff','#65748b':'#9dadc5','#68778e':'#9dadc5','#e3eaf6':'#28394f','#365578':'#b3c9e8','#d8e1ed':'#34445c','#eaf1fb':'#243a55','#8ba9d0':'#52769e','#dce8f7':'#2b4464','#e5f5ef':'#173f36','#137054':'#8ce3bb','#c3e5d8':'#285746','#fff0e8':'#4a3027','#9b4721':'#ffc4a1','#f4d8c9':'#78513c','#6c7b91':'#a9b7cc','#f0f3f7':'#202d40','#a1adbd':'#66788f','#e5eaf0':'#2b394e','#d7e0ec':'#34445c','#e4edfd':'#29486e','#f3f6fa':'#152131','#c6d2e3':'#40536c','#f7f9fc':'#1c2a3e','#e4eaf2':'#34445c','#edf1f7':'#24344a','#e1ecff':'#2c4c73','#174fa7':'#c5ddff','#f3f6fb':'#1e2c40','#60708a':'#a5b8d2','#d9e2ee':'#34445c','#e3ebf6':'#26384f','#e1e8f2':'#2c3c54'}
    if dark:
        import re
        style=re.sub(r'#[0-9a-fA-F]{6}',lambda m:mapping.get(m.group(),m.group()),style)
        style=style.replace('background: white','background: #182333')
    palette=QPalette()
    for role,color in [(QPalette.ColorRole.Window,'#101824' if dark else '#f2f5fa'),(QPalette.ColorRole.Base,'#182333' if dark else '#ffffff'),(QPalette.ColorRole.AlternateBase,'#1c2a3e' if dark else '#f7f9fc'),(QPalette.ColorRole.Button,'#24344a' if dark else '#ffffff'),(QPalette.ColorRole.WindowText,'#d6e2f4' if dark else '#25334a'),(QPalette.ColorRole.Text,'#d6e2f4' if dark else '#25334a'),(QPalette.ColorRole.ButtonText,'#d6e2f4' if dark else '#25334a'),(QPalette.ColorRole.Highlight,'#2265d8'),(QPalette.ColorRole.HighlightedText,'#ffffff')]:palette.setColor(role,QColor(color))
    QApplication.instance().setPalette(palette);w.setStyleSheet(style+'\n'+extra_style(dark));w.theme=theme;w.theme_button.setText('Light mode' if dark else 'Dark mode')
    w.precision_scrubber.dark=dark;w.precision_scrubber.update();w.comparison_charts.dark=dark;w.comparison_charts.redraw();w.settings.setValue('theme',theme)
