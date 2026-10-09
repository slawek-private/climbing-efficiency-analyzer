"""Home: the first screen. Continue a project, or start a training session, a competition event or a single video."""
import hashlib,time
from pathlib import Path
from PySide6.QtCore import Qt,QThread,Signal,QDate,QSize
from PySide6.QtGui import QImage,QPixmap,QPainter,QColor,QIcon
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QFrame,QMenu,QScrollArea,QSizePolicy,QDialog,QFormLayout,QLineEdit,QDateEdit,
    QComboBox,QRadioButton,QCheckBox,QDialogButtonBox,QStackedWidget,QFileDialog,QButtonGroup)
from .controls import Button
from .version import APP_NAME,__version__
from . import identity,projects

INTENTS=[('training','Training session','One route, many attempts. Track progress per athlete.'),
         ('competition','Competition event','One round, many athletes. Compare the field.'),
         ('video','Open a video','Measure one climb now, organise later.'),
         ('project','Open project','Browse, create or import a .climbproject.')]


def label(text,name=None,wrap=True):
    w=QLabel(text);w.setWordWrap(wrap)
    if name:w.setObjectName(name)
    return w


def poster_image(path,width=480):
    """First decodable frame as a QImage, or None. Reads one frame only."""
    try:
        import av
        with av.open(str(path)) as container:
            stream=container.streams.video[0];stream.thread_type='AUTO'
            for frame in container.decode(stream):
                rgb=frame.to_ndarray(format='rgb24');image=QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format.Format_RGB888).copy()
                return image.scaledToWidth(width,Qt.TransformationMode.SmoothTransformation)
    except Exception:return None
    return None


def poster_path(root,video):
    """Cached poster in the ignored artifacts folder, keyed by path and modification time."""
    try:key=hashlib.sha1(f'{video}:{Path(video).stat().st_mtime_ns}'.encode()).hexdigest()
    except OSError:return None
    return Path(root)/'artifacts'/'posters'/(key+'.jpg')


class PosterWorker(QThread):
    ready=Signal(str,QImage)
    def __init__(self,root,jobs):
        super().__init__();self.root=root;self.jobs=jobs
    def run(self):
        for slug,video in self.jobs:
            if self.isInterruptionRequested():return
            target=poster_path(self.root,video)
            if target is None:continue
            image=QImage(str(target)) if target.exists() else None
            if image is None or image.isNull():
                image=poster_image(video)
                if image is None:continue
                target.parent.mkdir(parents=True,exist_ok=True);image.save(str(target),'JPG',82)
            self.ready.emit(slug,image)


def pending(project):
    """One reason to open the project, from data it already stores."""
    data=project.workspace();states=data.get('states',{});assignments=data.get('assignments',{})
    docs=[s['document'] for s in states.values()]+[e['state']['document'] for e in data.get('attempts',[])]
    clips=sum(len(identity.unanswered(d)) for d in docs)
    if clips:return f'{clips} clip answer{"s" if clips>1 else ""} needed','warn'
    unassigned=sum(1 for v in data.get('videos',[]) if v not in states and v not in assignments)
    if unassigned:return f'{unassigned} video{"s need" if unassigned>1 else " needs"} an athlete','warn'
    drafts=sum(1 for d in docs if not (d.get('start') and d.get('end')))
    if drafts:return f'{drafts} attempt{"s" if drafts>1 else ""} without start and end','warn'
    return 'Up to date','good'


def summary(project):
    data=project.workspace();org=data.get('organisation') or {};sessions=org.get('sessions',[]);routes=org.get('routes',[])
    kinds={s['kind'] for s in sessions};kind='Competition' if kinds=={'competition'} else 'Training' if kinds=={'training'} else 'Training and competition' if kinds else ''
    parts=[kind] if kind else []
    if len(routes)==1:parts.append(routes[0]['name'])
    athletes=len(org.get('athletes',[]));videos=len(data.get('videos',[]))
    if athletes:parts.append(f'{athletes} athlete{"s" if athletes!=1 else ""}')
    parts.append(f'{videos} video{"s" if videos!=1 else ""}')
    return ' · '.join(parts)


class Tile(QFrame):
    """One project: poster, name, what it holds, what is pending."""
    def __init__(self,home,project):
        super().__init__();self.home=home;self.project=project;self.setObjectName('tile');self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Open project '+project.name);box=QVBoxLayout(self);box.setContentsMargins(10,10,10,10);box.setSpacing(4)
        self.poster=QLabel();self.poster.setObjectName('poster');self.poster.setFixedHeight(96);self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter);self.poster.setText(project.name[:1].upper());box.addWidget(self.poster)
        self.title=label(project.name,'tileTitle',wrap=False);box.addWidget(self.title)
        self.meta=label(summary(project),'muted');box.addWidget(self.meta)
        text,state=pending(project);self.badge=label(text,'badge');self.badge.setProperty('state',state);box.addWidget(self.badge)
        self.setToolTip(str(project.folder));self.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Fixed)
    def set_poster(self,image):
        pixmap=QPixmap.fromImage(image).scaled(self.poster.width() or 240,96,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation)
        self.poster.setText('');self.poster.setPixmap(pixmap)
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):self.home.open(self.project)
        super().mouseReleaseEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Space):self.home.open(self.project)
        else:super().keyPressEvent(event)
    def contextMenuEvent(self,event):
        menu=QMenu(self)
        for text,action in [('Open',lambda:self.home.open(self.project)),('Rename…','rename'),('Export as a file…','export'),('Show folder','reveal'),(None,None),('Delete…','delete')]:
            if text is None:menu.addSeparator()
            elif callable(action):menu.addAction(text,action)
            else:menu.addAction(text,lambda a=action:self.home.project_action(self.project,a))
        menu.exec(event.globalPos())


class IntentCard(QFrame):
    def __init__(self,home,kind,title,text):
        super().__init__();self.home=home;self.kind=kind;self.setObjectName('intent');self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus);self.setAccessibleName(title)
        box=QVBoxLayout(self);box.setContentsMargins(14,14,14,14);box.setSpacing(4);box.addWidget(label(title,'tileTitle'));box.addWidget(label(text,'muted'));box.addStretch()
    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):self.home.start(self.kind)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter,Qt.Key.Key_Space):self.home.start(self.kind)
        else:super().keyPressEvent(event)


class HomePage(QWidget):
    def __init__(self,w):
        super().__init__();self.w=w;self.setObjectName('home');self.worker=None;self.tiles={}
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);scroll=QScrollArea();scroll.setWidgetResizable(True);outer.addWidget(scroll)
        body=QWidget();body.setObjectName('homeBody');scroll.setWidget(body);col=QVBoxLayout(body);col.setContentsMargins(40,28,40,40);col.setSpacing(18)
        head=QHBoxLayout();brand=QHBoxLayout();brand.setSpacing(10)
        self.mark=QLabel();self.mark.setFixedSize(28,28);self.mark.setPixmap(QIcon(str(Path(__file__).resolve().parent/'assets'/'icon.png')).pixmap(28,28));brand.addWidget(self.mark);brand.addWidget(label(APP_NAME,'brand',wrap=False));head.addLayout(brand);head.addStretch()
        self.new_button=Button('New ▾');self.new_button.setProperty('role','primary');menu=QMenu(self.new_button)
        for kind,title,_ in INTENTS[:3]:menu.addAction(title+'…',lambda k=kind:self.start(k))
        menu.addSeparator();menu.addAction('New project…',lambda:self.browse('new'));menu.addAction('Import .climbproject…',lambda:self.browse('import'));self.new_button.setMenu(menu);head.addWidget(self.new_button)
        for text,callback in [('Recording tips',self.w.show_tips),('Take the tour',self.tour)]:
            b=Button(text);b.setProperty('role','quiet');b.clicked.connect(callback);head.addWidget(b)
        self.version=label(__version__,'muted',wrap=False);head.addWidget(self.version);col.addLayout(head)
        # First run: ask the intent. Afterwards: the work.
        self.intro=QWidget();intro=QVBoxLayout(self.intro);intro.setContentsMargins(0,12,0,0);intro.setSpacing(12);intro.addWidget(label('What are you working on?','homeTitle'))
        grid=QGridLayout();grid.setSpacing(12);self.cards=[]
        for n,(kind,title,text) in enumerate(INTENTS):
            card=IntentCard(self,kind,title,text);card.setMinimumHeight(104);grid.addWidget(card,n//2,n%2);self.cards.append(card)
        intro.addLayout(grid);intro.addWidget(label('Drop videos anywhere on this window to start with them.','muted'))
        steps=QHBoxLayout();steps.setSpacing(24)
        for n,(title,text) in enumerate([('Record','Tripod, whole climber in frame, original file.'),('Mark','Climb start and end, clips, rests, chalk, feet.'),('Compare','Athletes and attempts, side by side, then export.')],1):
            step=QFrame();step.setObjectName('step');s=QVBoxLayout(step);s.setContentsMargins(0,10,0,0);s.addWidget(label(f'{n}  {title}','tileTitle'));s.addWidget(label(text,'muted'));steps.addWidget(step,1)
        intro.addLayout(steps);col.addWidget(self.intro)
        self.continue_title=label('Continue','homeTitle');col.addWidget(self.continue_title)
        self.grid_holder=QWidget();self.grid=QGridLayout(self.grid_holder);self.grid.setContentsMargins(0,0,0,0);self.grid.setSpacing(12);self.grid.setAlignment(Qt.AlignmentFlag.AlignTop);col.addWidget(self.grid_holder)
        self.sessions=label('','muted');col.addWidget(self.sessions);col.addStretch()
    def tour(self):
        self.w.show_workspace()
        if self.w.reader:self.w.show_tour()
        else:self.w.statusBar().showMessage('Open a video first; the tour points at real controls.',6000)
    def refresh(self):
        all_projects=projects.all_projects(self.w.data_root());worked=[p for p in all_projects if p.stats()['videos'] or p.meta().get('created')]
        first=not any(p.stats()['videos'] for p in all_projects)
        self.intro.setVisible(first);self.continue_title.setText('Continue' if worked else 'Projects')
        while self.grid.count():
            item=self.grid.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.tiles={};order=sorted(all_projects,key=lambda p:-(p.stats()['last_opened'] or 0));columns=4;jobs=[]
        for n,project in enumerate(order):
            tile=Tile(self,project);self.grid.addWidget(tile,n//columns,n%columns);self.tiles[project.folder]=tile
            videos=[v for v in project.workspace().get('videos',[]) if Path(v).is_file()]
            if videos:jobs.append((str(project.folder),videos[-1]))
        new=QFrame();new.setObjectName('newTile');new.setCursor(Qt.CursorShape.PointingHandCursor);new.setFixedHeight(176);box=QVBoxLayout(new);box.addStretch();t=label('+  New project','tileTitle');t.setAlignment(Qt.AlignmentFlag.AlignCenter);box.addWidget(t);box.addStretch()
        new.mouseReleaseEvent=lambda e:self.browse('new');self.grid.addWidget(new,len(order)//columns,len(order)%columns)
        for c in range(columns):self.grid.setColumnStretch(c,1)
        recent=[]
        for project in order:
            for s in (project.workspace().get('organisation') or {}).get('sessions',[]):recent.append((s.get('date',''),identity.session_label(s),project.name))
        recent.sort(reverse=True);self.sessions.setText('Recent sessions: '+'  ·  '.join(f'{l} ({p})' for _,l,p in recent[:4]) if recent else '')
        if self.worker and self.worker.isRunning():self.worker.requestInterruption();self.worker.wait()
        if jobs:self.worker=PosterWorker(self.w.data_root(),jobs);self.worker.ready.connect(self.poster_ready);self.worker.start()
    def poster_ready(self,slug,image):
        tile=self.tiles.get(Path(slug))
        if tile:tile.set_poster(image)
    def shutdown(self):
        if self.worker and self.worker.isRunning():self.worker.requestInterruption();self.worker.wait()
    def open(self,project):
        if self.w.open_project(project):self.w.show_workspace()
    def project_action(self,project,action):
        browser=projects.ProjectBrowser(self.w);browser.table.selectRow(browser.projects.index(project));getattr(browser,action)();self.refresh()
    def browse(self,action=None):
        before=self.w.project;self.w.show_projects(action)
        if self.w.project!=before:self.w.show_workspace()
        else:self.refresh()
    def start(self,kind):
        if kind=='project':return self.browse()
        if kind=='video':
            self.w.show_workspace();self.w.open_video();return
        wizard=NewSessionWizard(self.w,kind)
        if wizard.exec()==QDialog.DialogCode.Accepted:self.w.show_workspace();self.w.open_video()


class NewSessionWizard(QDialog):
    """Kind and name, then route and athletes. Nothing is created until Finish."""
    def __init__(self,w,kind,allow_project=True):
        super().__init__(w);self.w=w;self.kind=kind;self.setWindowTitle('New training session' if kind=='training' else 'New competition event');self.setMinimumWidth(520)
        box=QVBoxLayout(self);self.stack=QStackedWidget();box.addWidget(self.stack)
        # Step 1
        page=QWidget();form=QFormLayout(page);self.name=QLineEdit();self.name.setPlaceholderText('Team practice' if kind=='training' else 'Nationals · Lead final')
        self.day=QDateEdit(QDate.currentDate());self.day.setCalendarPopup(True);self.day.setDisplayFormat('dd MMM yyyy')
        self.event=QLineEdit();self.round=QLineEdit();self.round.setPlaceholderText('Qualification, semi-final, final');self.team=QLineEdit();self.goal=QLineEdit()
        form.addRow('Session name' if kind=='training' else 'Event name',self.name if kind=='training' else self.event)
        if kind=='competition':form.addRow('Round',self.round)
        form.addRow('Date',self.day)
        if kind=='training':form.addRow('Goal (optional)',self.goal)
        form.addRow('Team (optional)',self.team)
        self.where=QButtonGroup(self);self.current_project=QRadioButton('In the current project · '+w.project.name);self.new_project=QRadioButton('In a new project');self.project_name=QLineEdit()
        self.project_name.setPlaceholderText('Project name')
        for b in (self.current_project,self.new_project):self.where.addButton(b)
        (self.new_project if kind=='competition' else self.current_project).setChecked(True)
        if allow_project:form.addRow('',self.current_project);form.addRow('',self.new_project);form.addRow('',self.project_name)
        self.new_project.toggled.connect(lambda on:self.project_name.setEnabled(on));self.project_name.setEnabled(self.new_project.isChecked())
        self.error1=label('','muted');form.addRow(self.error1);self.stack.addWidget(page)
        # Step 2
        page=QWidget();form=QFormLayout(page);data=w.workspace.organisation
        self.route=QComboBox();self.route.addItem('New route version…','')
        for r in data['routes']:self.route.addItem(identity.route_label(r),r['id'])
        self.route_name=QLineEdit();self.route_name.setPlaceholderText('Route name / grade');self.route_version=QLineEdit();self.route_version.setPlaceholderText('Version, e.g. set 5 Oct')
        form.addRow('Route',self.route);form.addRow('',self.route_name);form.addRow('',self.route_version)
        self.route.currentIndexChanged.connect(lambda i:[f.setVisible(i==0) for f in (self.route_name,self.route_version)])
        self.roster=QWidget();roster=QVBoxLayout(self.roster);roster.setContentsMargins(0,0,0,0);self.checks=[]
        for a in data['athletes']:
            c=QCheckBox(identity.athlete_label(a));c.setProperty('athlete',a['id']);roster.addWidget(c);self.checks.append(c)
        self.new_athletes=QLineEdit();self.new_athletes.setPlaceholderText('Add athletes, comma separated');roster.addWidget(self.new_athletes)
        form.addRow('Athletes',self.roster);self.error2=label('','muted');form.addRow(self.error2);self.stack.addWidget(page)
        line=QHBoxLayout();self.step=label('Step 1 of 2','muted');line.addWidget(self.step);line.addStretch()
        self.back=Button('Back');self.back.clicked.connect(lambda:self.go(0));self.next=Button('Next');self.next.setProperty('role','primary');self.next.clicked.connect(self.advance)
        cancel=Button('Cancel');cancel.setProperty('role','quiet');cancel.clicked.connect(self.reject)
        for b in (cancel,self.back,self.next):line.addWidget(b)
        box.addLayout(line);self.go(0)
    def go(self,index):
        self.stack.setCurrentIndex(index);self.step.setText(f'Step {index+1} of 2');self.back.setVisible(index>0);self.next.setText('Next' if index==0 else 'Finish and add videos')
    def advance(self):
        if self.stack.currentIndex()==0:
            if self.kind=='training' and not self.name.text().strip():return self.error1.setText('Enter a session name.')
            if self.kind=='competition' and not (self.event.text().strip() and self.round.text().strip()):return self.error1.setText('Enter the event and the round.')
            if self.new_project.isChecked() and not self.project_name.text().strip():return self.error1.setText('Name the new project.')
            return self.go(1)
        self.finish()
    def finish(self):
        route_new=not self.route.currentData()
        if route_new and not (self.route_name.text().strip() and self.route_version.text().strip()):return self.error2.setText('Enter the route name and its version.')
        names=[n.strip() for n in self.new_athletes.text().split(',') if n.strip()]
        if not names and not any(c.isChecked() for c in self.checks):return self.error2.setText('Choose or add at least one athlete.')
        w=self.w
        if self.new_project.isChecked():
            project=projects.create(w.data_root(),self.project_name.text())
            if not w.open_project(project):return
        data=w.workspace.organisation
        try:
            name=self.name.text() if self.kind=='training' else self.event.text()+' · '+self.round.text()
            session=identity.session(data,name,self.kind,self.day.date().toString('yyyy-MM-dd'),self.team.text(),self.event.text() if self.kind=='competition' else '',self.round.text() if self.kind=='competition' else '',self.goal.text() if self.kind=='training' else '')
            if route_new:identity.route(data,self.route_name.text(),self.route_version.text())
            for n in names:
                if not any(a['name'].casefold()==n.casefold() for a in data['athletes']):identity.athlete(data,n,teams=[self.team.text().strip()] if self.team.text().strip() else ())
            w.workspace.session_id=session['id'];w.workspace.save()
        except (ValueError,OSError) as error:return self.error2.setText(str(error))
        w.refresh_collection();w.library.render()
        w.compare_scope.intent.setCurrentIndex(2 if self.kind=='competition' else 0)
        self.accept()
