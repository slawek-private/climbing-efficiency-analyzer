"""Portable Qt presentation for the manual climbing workspace.

Layout rules: show the current step and hide the rest; one primary action per screen, drawn
with activity colour reinforcing text labels (clip blue, rest green, chalk purple, points
amber, climb end red); every fact drawn once.
"""
from PySide6.QtCore import Qt,QRect
from PySide6.QtGui import QColor,QPainter,QAction,QKeySequence
from PySide6.QtWidgets import (QApplication,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QFrame,QTabWidget,QSplitter,QScrollArea,QHeaderView,
    QAbstractItemView,QLineEdit,QComboBox,QTableWidget,QSpinBox,QMessageBox,QMenu,QDialog,QFormLayout,QCheckBox,QDialogButtonBox,QStyledItemDelegate,QStyle,QSizePolicy)
from .version import APP_NAME,__version__
from .platform_runtime import GPU_LABEL,timecode_font

TOKENS={False:dict(ink='#20252b',muted='#59616b',background='#f4f5f6',panel='#ffffff',line='#8b939d',soft='#e5e7eb',hover='#edf0f3',selected='#e8f0fe',accent='#245fc4',onaccent='#ffffff'),
        True:dict(ink='#f3f4f5',muted='#b2b8bf',background='#151719',panel='#202326',line='#727c87',soft='#383e45',hover='#2c3137',selected='#293d58',accent='#245fc4',onaccent='#ffffff')}
STYLE='''
QWidget { font-size: 13px; color: $ink; }
QMainWindow, QWidget#workspace { background: $background; }
QFrame#card, QWidget#page { background: $panel; border-radius: 8px; }
QFrame#step { background: transparent; border: none; border-top: 1px solid $soft; border-radius: 0; }
QLabel { background: transparent; border: none; }
QLabel#brand { font-size: 20px; font-weight: 600; }
QLabel#muted,QLabel#eyebrow { color: $muted; font-size: 12px; }
QLabel#section { font-size: 15px; font-weight: 600; }
QLabel#timer { font-size: 15px; font-weight: 600; }
QLabel#timecode { font-size: 19px; font-weight: 600; }
QPushButton { background: $panel; border: 1px solid $line; border-radius: 6px; padding: 6px 10px; min-height: 20px; font-weight: 400; }
QPushButton:checked { background: $selected; border: 2px solid $accent; font-weight: 600; }
QPushButton:hover { background: $hover; }
QPushButton:focus { border: 2px solid $accent; }
QPushButton:pressed { background: $selected; }
QPushButton[role="primary"] { background: $accent; color: $onaccent; border-color: $accent; font-weight: 600; }
QPushButton[role="quiet"] { background: transparent; border: 1px solid transparent; color: $muted; padding: 4px 6px; min-height: 22px; }
QPushButton[role="quiet"]:focus { border: 2px solid $accent; }
QPushButton[role="quiet"]:hover { color: $ink; background: $hover; }
QPushButton[kind] { min-height: 34px; }
QPushButton[keycap="true"] { padding-right: 30px; }
QPushButton:disabled { background: $background; color: $muted; border-color: $soft; }
QPushButton::menu-indicator { width: 0; }
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QPlainTextEdit { background: $panel; border: 1px solid $line; border-radius: 5px; padding: 6px; selection-background-color: $accent; selection-color: white; }
QLineEdit:focus,QSpinBox:focus,QComboBox:focus,QPlainTextEdit:focus { border: 2px solid $accent; }
QComboBox QAbstractItemView { background: $panel; selection-background-color: $selected; selection-color: $ink; }
QTabWidget::pane { border: none; background: $panel; border-radius: 8px; }
QTabBar::tab { background: transparent; color: $muted; padding: 10px 16px; border-bottom: 2px solid transparent; font-weight: 500; }
QTabBar::tab:selected { color: $ink; border-bottom: 2px solid $accent; }
QTabBar::tab:hover { background: $hover; }
QTabBar::tab:focus { border: 2px solid $accent; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: $background; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $line; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height: 0; }
QLineEdit#eventSearch { min-width: 0; }
QWidget#dashboardCard { background: $panel; border: 1px solid $soft; border-radius: 6px; }
QTableWidget { background: $panel; alternate-background-color: $background; border: none; gridline-color: $soft; selection-background-color: $selected; selection-color: $ink; }
QHeaderView { background: $background; }
QHeaderView::section { background: $background; border: none; padding: 6px 8px; color: $muted; font-size: 12px; font-weight: 500; }
QSlider::groove:horizontal { background: $soft; height: 6px; border-radius: 3px; }
QSlider::sub-page:horizontal { background: $accent; }
QSlider::handle:horizontal { background: $accent; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }
QSplitter::handle { background: $background; width: 8px; }
QStatusBar { background: $background; color: $muted; }
QProgressBar { border: none; background: $soft; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background: $accent; }
QToolTip { color: $ink; background: $panel; border: 1px solid $line; padding: 8px; }
QMenu { color: $ink; background: $panel; border: 1px solid $line; }
QMenu::item:selected { background: $selected; }
QFrame#banner { background: $selected; border: 1px solid $line; border-radius: 6px; }
QFrame#drop { background: #101214; border: 2px dashed $line; border-radius: 8px; }
QFrame#drop QLabel,QFrame#drop QPushButton[role="quiet"] { color: #e5e7eb; }
QFrame#drop QLabel#dropTitle { color: white; font-size: 24px; font-weight: 600; }
QLabel#handTitle { font-size: 13px; color: $muted; }
QLabel#saveState[state="error"] { color: $ink; font-weight: 700; }
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

# Match each activity to its timeline colour; solid fills mean a running timer.
ACCENTS={'clip':'#245fc4','rest':'#117451','chalk':'#7844b5'}
def extra_style(dark):
    backgrounds={'clip':'#203451','rest':'#183b30','chalk':'#342342'} if dark else {'clip':'#eaf1ff','rest':'#e7f5ed','chalk':'#f3eafa'}
    inks={'clip':'#93bcff','rest':'#8cd9b8','chalk':'#d8b4f8'} if dark else ACCENTS
    return '\n'.join(f'QPushButton[role="start"][kind="{kind}"] {{ background: {backgrounds[kind]}; color: {inks[kind]}; border: 2px solid {inks[kind]}; font-weight: 600; }}\nQPushButton[role="stop"][kind="{kind}"] {{ background: {color}; color: white; border: 2px solid {color}; font-weight: 700; }}' for kind,color in ACCENTS.items())

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
    if name:box.addWidget(label({'ATHLETE · START · END':'Athlete and climb','DURING THE CLIMB':'Hands and points'}.get(name,name),'section',wrap=False))
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
    from .platform_runtime import interface_font
    w.setFont(interface_font())
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
    export_items=[('Coaching report…',w.export_coaching),('Selected attempts · HTML + CSV…',w.export_all),('PDF report…',w.export_pdf),(None,None),('This project as a file…',lambda:w.show_projects('export'))]
    menu=bar.addMenu('Export')
    for text,cb in export_items:
        if text:menu.addAction(text,cb)
        else:menu.addSeparator()
    menu=bar.addMenu('Measurements');menu.addAction('Check completeness…',w.check_completeness);menu.addAction('Clear this athlete…',w.clear_athlete);menu.addAction('Clear measurements…',w.clear_measurements)
    menu=bar.addMenu('View');w.theme_button=menu.addAction('Dark mode',w.toggle_theme)
    from PySide6.QtGui import QActionGroup
    appearance=menu.addMenu('Appearance');w.appearance_actions={};group=QActionGroup(w);group.setExclusive(True)
    for title,value in [('System','system'),('Light','light'),('Dark','dark')]:
        action=appearance.addAction(title);action.setCheckable(True);group.addAction(action);action.triggered.connect(lambda checked=False,v=value:apply_theme(w,v));w.appearance_actions[value]=action
    contrast=menu.addAction('Increase contrast');contrast.setCheckable(True);contrast.setChecked(w.settings.value('high_contrast',False,type=bool));contrast.toggled.connect(lambda on:(w.settings.setValue('high_contrast',on),apply_theme(w,w.appearance)))
    menu.addAction('Fit video',w.image.fit)
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
    w.video_selector.currentIndexChanged.connect(w.select_video);w.video_selector.hide()
    w.current_video_label=label('Choose a project video','currentVideo',wrap=False);w.current_video_label.setMinimumWidth(100);w.current_video_label.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);queue.addWidget(w.current_video_label,1)
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
    split=QSplitter(Qt.Orientation.Horizontal);w.main_tabs.addTab(split,'Video analysis');w.measure_page=split
    video=QFrame();video.setObjectName('card');v=QVBoxLayout(video);v.setContentsMargins(10,10,10,8);v.setSpacing(6)
    from .video_navigation import VideoNavigation
    w.video_navigation=VideoNavigation(w);v.addWidget(w.video_navigation)
    w.empty_hint=QFrame();w.empty_hint.setObjectName('drop');drop=QVBoxLayout(w.empty_hint);drop.setContentsMargins(24,24,24,24);drop.addStretch()
    w.drop_title=label('Drop climbing videos here','dropTitle');w.drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter);drop.addWidget(w.drop_title)
    line=QHBoxLayout();line.addStretch();w.drop_choose=button('Choose files…',w.open_video,'primary');line.addWidget(w.drop_choose);line.addWidget(button('Open project…',w.show_projects));line.addStretch();drop.addLayout(line)
    w.drop_note=label('MP4, MOV or MKV · originals stay where they are, nothing is uploaded','muted');w.drop_note.setAlignment(Qt.AlignmentFlag.AlignCenter);drop.addWidget(w.drop_note)
    checklist=label(CHECKLIST,'muted');checklist.setAlignment(Qt.AlignmentFlag.AlignCenter);drop.addSpacing(10);drop.addWidget(checklist)
    line=QHBoxLayout();line.addStretch();line.addWidget(button('Recording tips',w.show_tips,'quiet'));line.addStretch();drop.addLayout(line);drop.addStretch()
    v.addWidget(w.empty_hint,1)
    w.image.setParent(video);w.image.setBackgroundBrush(QColor('#101214'));w.image.setAcceptDrops(False);w.image.viewport().setAcceptDrops(False);v.addWidget(w.image,1)
    from .scrubber import PrecisionScrubber
    w.precision_scrubber=PrecisionScrubber();w.precision_scrubber.seek.connect(w.scrub_seconds);w.precision_scrubber.released.connect(w.finish_scrub);w.precision_scrubber.observationSelected.connect(w.select_timeline_event);v.addWidget(w.precision_scrubber)
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
    panel=QWidget();panel.setObjectName('page');measure=QVBoxLayout(panel);measure.setContentsMargins(10,10,10,10);measure.setSpacing(8);panel.setMinimumWidth(320)
    measurement_scroll=QScrollArea();measurement_scroll.setWidgetResizable(True);measurement_scroll.setMinimumWidth(340);measurement_scroll.setWidget(panel);split.addWidget(measurement_scroll);split.setSizes([1000,340]);w.workspace_tabs=None;w.measurement_scroll=measurement_scroll
    w.empty_panel=label('Load a video to start measuring.\n\nThe panel then follows the climb: name the athlete, mark the start, time each hand’s clips, rests and chalking, mark the end.','muted');measure.addWidget(w.empty_panel)
    w.boundary_box,box=step_card('ATHLETE · START · END')
    line=QHBoxLayout();line.addWidget(w.climber,1);w.climber.setPlaceholderText('Athlete name');line.addWidget(label('Attempt','muted',wrap=False));w.attempt.setMaximumWidth(55);line.addWidget(w.attempt)
    line.addWidget(menu_button('⋯',[('New attempt',w.new_attempt),('Open another attempt…',w.choose_attempt),('Set route…',w.set_route),('Coaching goal and context…',w.edit_coaching),(None,None),('Clear this athlete…',w.clear_athlete),('Clear measurements…',w.clear_measurements)],'More actions for this athlete'));box.addLayout(line)
    line=QHBoxLayout();w.start_button=KeyButton('Mark start','S',w.set_start);w.start_button.setToolTip('Pause on the first grip, then mark the climb start (S). Press again to move it to the current frame.');line.addWidget(w.start_button,1)
    w.start_clear=button('×',lambda:w.clear_boundary('start'),'quiet');w.start_clear.setToolTip('Remove the climb start');w.start_clear.setAccessibleName('Remove climb start');line.addWidget(w.start_clear);box.addLayout(line);line=QHBoxLayout()
    w.end_button=KeyButton('Mark end','E',w.set_failure);w.end_button.setToolTip('Pause on the fall (rope weighted) or the top, then mark the end (E).');line.addWidget(w.end_button,1)
    w.end_edit=button('✎',w.edit_climb_outcome,'quiet');w.end_edit.setToolTip('Change the result: fell or topped');w.end_edit.setAccessibleName('Change climb result');line.addWidget(w.end_edit)
    w.end_clear=button('×',lambda:w.clear_boundary('end'),'quiet');w.end_clear.setToolTip('Remove the climb end');w.end_clear.setAccessibleName('Remove climb end');line.addWidget(w.end_clear);box.addLayout(line)
    w.duration_status.setObjectName('timer');box.addWidget(w.duration_status)
    for hidden in (w.start_status,w.end_status):hidden.setParent(w.boundary_box);hidden.hide()
    measure.addWidget(w.boundary_box)
    w.climb_box,box=step_card('DURING THE CLIMB')
    line=QHBoxLayout();line.addWidget(label('Method','muted',wrap=False));w.clip_method=QComboBox()
    for title,value in [('Not set',None),('Rope to mouth',"mouth"),('Direct · no mouth',"direct")]:w.clip_method.addItem(title,value)
    w.clip_method.setToolTip('Captured separately for each hand when its clip timer starts. Changing this selector affects the next clip only.\nRope to mouth: rope pulled up and held in the mouth before clipping.\nDirect: moved to a favourable position and clipped without the mouth.')
    line.addWidget(w.clip_method,1);line.addWidget(label('Draw','muted',wrap=False));w.draw.setMaximumWidth(62);w.draw.setToolTip('Number of the next quickdraw; advances after each completed clip.');line.addWidget(w.draw);box.addLayout(line)
    # Timers: two columns (hands) × three activities, in the timeline's colours. A running tile fills and shows its time.
    w.hands_box=QWidget();grid=QGridLayout(w.hands_box);grid.setContentsMargins(0,0,0,0);grid.setHorizontalSpacing(8);grid.setVerticalSpacing(6);w.hand_timer_buttons={};w.hand_timer_cancel={};w.hand_timer_status={}
    keys={'clip':{'left':'L','right':'R'},'rest':{'left':'Q','right':'W'},'chalk':{'left':'C','right':'V'}}
    for col,hand in enumerate(('left','right')):
        grid.addWidget(label(hand.capitalize()+' hand','handTitle',wrap=False),0,col)
        for row,kind in enumerate(('clip','rest','chalk'),1):
            cell=QWidget();line=QHBoxLayout(cell);line.setContentsMargins(0,0,0,0);line.setSpacing(2)
            control=KeyButton(kind.capitalize(),keys[kind][hand],lambda checked=False,k=kind,h=hand:w.toggle_hand_timer(k,h),'start');control.setProperty('kind',kind);control.setMinimumHeight(44);control.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed);control.setAccessibleName(hand.capitalize()+' hand '+kind)
            control.setToolTip(f'{hand.capitalize()} hand {kind}: press to start the timer at this frame, press again to stop it (key {keys[kind][hand]}).');line.addWidget(control,1)
            cancel=button('×',lambda checked=False,k=kind,h=hand:w.cancel_hand_timer(k,h),'quiet');cancel.setToolTip('Discard this running timer');cancel.setAccessibleName('Discard '+hand+' '+kind+' timer');cancel.setFixedWidth(32);line.addWidget(cancel)
            w.hand_timer_buttons[kind,hand]=control;w.hand_timer_cancel[kind,hand]=cancel;grid.addWidget(cell,row,col)
    box.addWidget(w.hands_box)
    w.point_box=QWidget();points=QVBoxLayout(w.point_box);points.setContentsMargins(0,4,0,0);points.setSpacing(6)
    line=QHBoxLayout();w.point_name.setToolTip('Point name. Starts as the point marked most recently; use the same names for every athlete.');line.addWidget(w.point_name,1)
    line.addWidget(KeyButton('Mark point','P',w.add_point))
    line.addWidget(menu_button('⋯',[('Rename selected point…',w.rename_point),('Delete selected point',w.delete_point),(None,None),('Comment at current frame…',w.comment_at_frame),('Edit selected comment…',w.edit_point_comment)],'Rename, delete or comment points'))
    points.addLayout(line);w.points_table.setMinimumHeight(0);w.points_table.setMaximumHeight(96);points.addWidget(w.points_table);box.addWidget(w.point_box)
    w.legacy_rest_panel=QWidget();legacy=QHBoxLayout(w.legacy_rest_panel);legacy.setContentsMargins(0,0,0,0);legacy.addWidget(label('Earlier rest timer','muted'));legacy.addWidget(button('Stop',w.stop_legacy_rest));legacy.addWidget(button('Cancel',lambda:w.cancel_hand_timer('rest','none'),'quiet'));box.addWidget(w.legacy_rest_panel)
    measure.addWidget(w.climb_box)
    from .coaching_ui import FootworkPanel
    w.footwork_panel=FootworkPanel(w);measure.addWidget(w.footwork_panel)
    coach=button('Coaching goal and context…',w.edit_coaching,'quiet');measure.addWidget(coach)
    w.events_card,box=step_card('')
    w.events_toggle=button('Events',w.toggle_events,'quiet');w.events_toggle.setStyleSheet('text-align: left; font-weight: 600;');box.addWidget(w.events_toggle)
    w.events_body=QWidget();body=QVBoxLayout(w.events_body);body.setContentsMargins(0,0,0,0);body.setSpacing(6)
    filters=QHBoxLayout();w.event_kind=QComboBox();w.event_hand=QComboBox()
    for title,value in [('All activities',None),('Clips','clip'),('Rest','rest'),('Chalk','chalk'),('Hold contacts','contact'),('Hand away','offwall')]:w.event_kind.addItem(title,value)
    for title,value in [('Both hands',None),('Left hand','left'),('Right hand','right'),('Unassigned','none')]:w.event_hand.addItem(title,value)
    for field,title in [(w.event_kind,'Filter events by activity'),(w.event_hand,'Filter events by hand')]:field.setAccessibleName(title);field.setToolTip(title+'; saved measurements and reports stay complete');field.currentIndexChanged.connect(w.refresh);filters.addWidget(field,1)
    body.addLayout(filters);w.event_search=QLineEdit();w.event_search.setObjectName('eventSearch');w.event_search.setPlaceholderText('Search quickdraw, hold or note');w.event_search.setClearButtonEnabled(True);w.event_search.setAccessibleName('Search hand events');w.event_search.textChanged.connect(w.refresh);body.addWidget(w.event_search)
    w.table.setMinimumHeight(140);body.addWidget(w.table,1)
    line=QHBoxLayout()
    for text,cb in [('Edit',w.edit_event),('Delete',w.delete_event)]:line.addWidget(button(text,cb))
    line.addStretch()
    for text,cb in [('Undo',w.undo),('Redo',w.redo)]:line.addWidget(button(text,cb,'quiet'))
    body.addLayout(line)
    for checkbox in w.review.values():checkbox.hide()
    body.addWidget(button('Check completeness…',w.check_completeness,'quiet'));box.addWidget(w.events_body,1);measure.addWidget(w.events_card,1)
    w.events_body.setVisible(w.settings.value('events_open',False,type=bool))
    for table in (w.table,w.points_table):
        table.setAlternatingRowColors(True);table.setShowGrid(False);table.verticalHeader().hide();table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    # Compare: a leaderboard first, every other view one click away.
    w.compare_page=QWidget();cp=QVBoxLayout(w.compare_page);cp.setContentsMargins(0,6,0,0);w.compare_tabs=QTabWidget();w.compare_tabs.setDocumentMode(True)
    from .compare_scope import CompareScope
    w.compare_scope=CompareScope();w.compare_scope.changed.connect(w.refresh_comparison);cp.addWidget(w.compare_scope);cp.addWidget(w.compare_tabs)
    comparison=QWidget();comparison.setObjectName('page');outer=QVBoxLayout(comparison);outer.setContentsMargins(0,0,0,0);overview_scroll=QScrollArea();overview_scroll.setWidgetResizable(True);overview_body=QWidget();c=QVBoxLayout(overview_body);c.setContentsMargins(16,14,16,14);c.setSpacing(12);overview_scroll.setWidget(overview_body);outer.addWidget(overview_scroll);w.comparison_page=comparison
    w.collection_summary=label('Mark a climb start and end in Video analysis to compare.','muted');c.addWidget(w.collection_summary)
    w.comparison_table=QTableWidget();w.comparison_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);w.comparison_table.setAlternatingRowColors(True);w.comparison_table.setShowGrid(False);w.comparison_table.verticalHeader().hide()
    w.comparison_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);w.comparison_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);w.comparison_table.setSortingEnabled(True)
    w.comparison_table.cellDoubleClicked.connect(w.comparison_open);w.comparison_table.itemSelectionChanged.connect(w.comparison_selected);w.comparison_table.setToolTip('Click a column to sort. Select an athlete for details; double-click to open their video.')
    w.bar_delegate=BarDelegate(w.comparison_table);c.addWidget(w.comparison_table)
    from .charts import ComparisonCharts
    w.comparison_charts=ComparisonCharts(embedded=True);c.addWidget(w.comparison_charts)
    w.comparison_detail_toggle=button('Selected attempt · activity log ▸',lambda:w.toggle_comparison_detail(),'quiet');c.addWidget(w.comparison_detail_toggle)
    w.comparison_detail_title=label('Select an athlete to see every rest, clip and chalk.','section');w.comparison_detail_title.hide();c.addWidget(w.comparison_detail_title)
    w.comparison_activity_table=QTableWidget(0,7);w.comparison_activity_table.setHorizontalHeaderLabels(['Activity','Hand','Quickdraw','Clip method','Start (s)','End (s)','Duration (s)'])
    w.comparison_activity_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);w.comparison_activity_table.setAlternatingRowColors(True);w.comparison_activity_table.setShowGrid(False);w.comparison_activity_table.verticalHeader().hide();w.comparison_activity_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    w.comparison_activity_table.hide();w.comparison_activity_table.setMinimumHeight(180);c.addWidget(w.comparison_activity_table);c.addStretch();w.compare_tabs.addTab(comparison,'Overview')
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
    QApplication.instance().styleHints().colorSchemeChanged.connect(lambda *_:apply_theme(w,'system') if w.appearance=='system' else None)
    apply_theme(w,w.settings.value('theme','system'));w.setWindowTitle(APP_NAME)


def apply_theme(w,theme):
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance();dark=theme=='dark' or (theme=='system' and app.styleHints().colorScheme()==Qt.ColorScheme.Dark)
    tokens=dict(TOKENS[dark])
    if w.settings.value('high_contrast',False,type=bool):tokens.update(muted=tokens['ink'],line=tokens['ink'])
    style=STYLE
    for key,color in tokens.items():style=style.replace('$'+key,color)
    palette=QPalette()
    for role,color in [(QPalette.ColorRole.Window,tokens['background']),(QPalette.ColorRole.Base,tokens['panel']),(QPalette.ColorRole.AlternateBase,tokens['background']),(QPalette.ColorRole.Button,tokens['panel']),(QPalette.ColorRole.WindowText,tokens['ink']),(QPalette.ColorRole.Text,tokens['ink']),(QPalette.ColorRole.ButtonText,tokens['ink']),(QPalette.ColorRole.Highlight,tokens['accent']),(QPalette.ColorRole.HighlightedText,'white')]:palette.setColor(role,QColor(color))
    app.setPalette(palette);w.setStyleSheet(style+'\n'+extra_style(dark));w.theme='dark' if dark else 'light';w.appearance=theme;w.theme_button.setText('Light mode' if dark else 'Dark mode')
    for value,action in w.appearance_actions.items():action.setChecked(value==theme)
    for tile in w.sync_view.tiles:tile.timeline.dark=dark;tile.timeline.update()
    w.precision_scrubber.dark=dark;w.precision_scrubber.update();w.comparison_charts.dark=dark;w.comparison_charts.redraw();w.pattern_dashboard.render();w.settings.setValue('theme',theme)
