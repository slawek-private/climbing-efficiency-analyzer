"""Private multi-video workspace, persisted separately from exported labels."""
import copy,json
from pathlib import Path
from .labels import validate
from jsonschema import ValidationError

class Workspace:
    def __init__(self,path):
        self.path=Path(path);self.videos=[];self.states={};self.point_names=[]
        if self.path.exists():
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'));self.point_names=data.get('point_names',[])
                for p in data.get('videos',[]):
                    if Path(p).is_file():self.add(p)
                for p,state in data.get('states',{}).items():
                    if p in self.videos:
                        validate(state['document']);self.states[p]=state
            except (ValueError,KeyError,OSError,ValidationError):pass
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
    def documents(self):return [self.states[p]['document'] for p in self.videos if p in self.states]
    def save(self):
        self.point_names=self.shared_points()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        target=self.path.with_suffix('.tmp');target.write_text(json.dumps({'version':1,'point_names':self.shared_points(),'videos':self.videos,'states':self.states},indent=2),encoding='utf-8');target.replace(self.path)
