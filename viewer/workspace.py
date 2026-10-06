"""Private multi-video workspace, persisted separately from exported labels."""
import copy,json,shutil
from pathlib import Path
from .labels import validate
from jsonschema import ValidationError

class Workspace:
    def __init__(self,path):
        self.path=Path(path);self.videos=[];self.states={};self.point_names=[];self.attempts=[];self.load_error=None;self.version=2
        if self.path.exists():
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'));self.version=data.get('version',1);self.point_names=data.get('point_names',[])
                for p in data.get('videos',[]):
                    self.add(p)
                for p,state in data.get('states',{}).items():
                    if p in self.videos:
                        validate(state['document']);self.states[p]=state
                for entry in data.get('attempts',[]):
                    validate(entry['state']['document']);self.attempts.append(entry)
            except (ValueError,KeyError,OSError,ValidationError) as error:self.load_error=str(error)
    def add(self,path):
        key=str(Path(path).resolve())
        if key not in self.videos:self.videos.append(key)
        return key
    def remember(self,path,document,label_path=None,frame=0):
        key=self.add(path);validate(document)
        self.states[key]={'document':copy.deepcopy(document),'label_path':str(label_path) if label_path else None,'frame':frame}
    def shared_points(self):
        names={name.strip() for name in self.point_names if name.strip()}
        names.update(p['name'].strip() for d in self.documents() for p in d.get('checkpoints',[]))
        return sorted(names,key=str.casefold)
    def add_point_name(self,name):
        name=name.strip()
        canonical=next((p for p in self.shared_points() if p.casefold()==name.casefold()),name)
        if canonical and canonical not in self.point_names:self.point_names.append(canonical)
        return canonical
    def archive(self,path):
        key=str(Path(path).resolve())
        if key in self.states:self.attempts.append({'path':key,'state':copy.deepcopy(self.states[key])})
    def relink(self,old,new,digest):
        old=str(Path(old).resolve());new=str(Path(new).resolve())
        expected=self.states.get(old,{}).get('document',{}).get('source',{}).get('sha256')
        if expected and digest!=expected:raise ValueError('This is a different video. Choose the original file with the matching checksum.')
        if new in self.videos and new!=old:raise ValueError('That video is already in this project.')
        self.videos[self.videos.index(old)]=new
        if old in self.states:self.states[new]=self.states.pop(old)
        for entry in self.attempts:
            if entry['path']==old:entry['path']=new
        self.save()
    def documents(self):return [e['state']['document'] for e in self.attempts]+[self.states[p]['document'] for p in self.videos if p in self.states]
    def save(self):
        if self.load_error:raise OSError('Workspace could not be read; original file preserved: '+self.load_error)
        backup=self.path.with_suffix('.v1-backup.json')
        if self.version<2 and self.path.exists() and not backup.exists():shutil.copy2(self.path,backup)
        self.point_names=self.shared_points()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        target=self.path.with_suffix('.tmp');target.write_text(json.dumps({'version':2,'attempts':self.attempts,'point_names':self.shared_points(),'videos':self.videos,'states':self.states},indent=2),encoding='utf-8');target.replace(self.path);self.version=2
