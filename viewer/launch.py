"""Process entry: a splash appears before the heavy imports, then fades into the window."""
import sys
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QPropertyAnimation,QEasingCurve,QRect
from PySide6.QtGui import QColor,QPainter,QIcon,QFont,QGuiApplication
from PySide6.QtWidgets import QApplication,QWidget


class Splash(QWidget):
    def __init__(self):
        super().__init__(None,Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.resize(420,260);self.progress=0.;self.dark=QGuiApplication.styleHints().colorScheme()==Qt.ColorScheme.Dark
        from .version import APP_NAME,__version__
        self.name=APP_NAME;self.version=__version__;self.icon=QIcon(str(Path(__file__).resolve().parent/'assets'/'icon.png')).pixmap(72,72)
        screen=QGuiApplication.primaryScreen().availableGeometry();self.move(screen.center().x()-210,screen.center().y()-130)
        self.pulse=QTimer(self);self.pulse.setInterval(40);self.pulse.timeout.connect(self.tick);self.pulse.start()
    def tick(self):
        self.progress=min(.9,self.progress+(.9-self.progress)*.06);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing);bg=QColor('#17191c' if self.dark else '#ffffff');ink=QColor('#f3f4f5' if self.dark else '#20252b');muted=QColor('#8b939d')
        p.setPen(QColor(0,0,0,60));p.setBrush(bg);p.drawRoundedRect(self.rect().adjusted(0,0,-1,-1),12,12)
        p.drawPixmap(40,56,self.icon);font=QFont(self.font());font.setPointSizeF(22);font.setWeight(QFont.Weight.DemiBold);p.setFont(font);p.setPen(ink);p.drawText(130,98,self.name)
        font.setPointSizeF(11);font.setWeight(QFont.Weight.Normal);p.setFont(font);p.setPen(muted);p.drawText(132,122,'Frame-accurate, fully local')
        p.drawText(QRect(0,220,380,20),Qt.AlignmentFlag.AlignRight,self.version)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#2c3137' if self.dark else '#e5e7eb'));p.drawRoundedRect(40,200,340,3,1.5,1.5);p.setBrush(QColor('#245fc4'));p.drawRoundedRect(40,200,int(340*self.progress),3,1.5,1.5)


def fade(widget,start,end,duration,done=None):
    animation=QPropertyAnimation(widget,b'windowOpacity',widget);animation.setDuration(duration);animation.setStartValue(start);animation.setEndValue(end);animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    if done:animation.finished.connect(done)
    animation.start();widget._fade=animation


def main(video=None):
    app=QApplication.instance() or QApplication(sys.argv);app.setStyle('Fusion')
    splash=Splash();splash.setWindowOpacity(0);splash.show();fade(splash,0,1,180);app.processEvents()
    from .simple import Window,ROOT
    from PySide6.QtGui import QIcon as Icon
    app.setWindowIcon(Icon(str(Path(__file__).resolve().parent/'assets'/'icon.png')));window=Window(video)
    available=app.primaryScreen().availableGeometry();window.resize(min(1450,available.width()-40),min(1000,available.height()-40));window.guidance=True
    window.setWindowOpacity(0);window.show();window.setFocus();splash.progress=1;splash.update();app.processEvents()
    QTimer.singleShot(0,lambda:window.resize(min(1450,available.width()-40),min(1000,available.height()-40)))
    fade(window,0,1,260);fade(splash,1,0,260,splash.close)
    window.start_resource_monitor();QTimer.singleShot(400,window.first_run);return app.exec()
