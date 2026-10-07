"""Private multi-video workspace, persisted separately from exported labels."""
import copy,json,shutil
from pathlib import Path
from .labels import validate,SCHEMA
from jsonschema import ValidationError,Draft202012Validator
from . import identity

class Workspace:
    def __init__(self,path):
        self.path=Path(path);self.videos=[];self.states={};self.point_names=[];self.attempts=[];self.load_error=None;self.version=3
        self.organisation=identity.empty();self.assignments={};self.session_id=''
        if self.path.exists():
            try:
                data=json.loads(self.path.read_text(encoding='utf-8'));self.version=data.get('version',1);self.point_names=data.get('point_names',[])
                if self.version>3:raise ValueError('This workspace needs a newer Climb Studio version; original file preserved')
                self.organisation=data.get('organisation',identity.empty());self.assignments=data.get('assignments',{});self.session_id=data.get('session_id','')
                for group,definition in [('athletes','athlete'),('sessions','session'),('routes','routeVersion')]:
                    seen=set()
                    for item in self.organisation[group]:
                        Draft202012Validator({'$ref':'#/$defs/'+definition,'$defs':SCHEMA['$defs']}).validate(item)
                        if group=='sessions':
                            from datetime import date
                            date.fromisoformat(item['date'])
                            if item['kind']=='competition' and (not item['event'].strip() or not item['round'].strip()):raise ValueError('Competition session needs event and round')
                        if item['id'] in seen:raise ValueError('Duplicate '+group+' ID')
                        seen.add(item['id'])
                for p in data.get('videos',[]):
                    self.add(p)
                for p,state in data.get('states',{}).items():
                    if p in self.videos:
                        validate(state['document']);identity.register(self.organisation,state['document']);self.states[p]=state
                for entry in data.get('attempts',[]):
                    validate(entry['state']['document']);identity.register(self.organisation,entry['state']['document']);self.attempts.append(entry)
                for assignment in self.assignments.values():
                    if set(assignment)!= {'athlete','session','route'}:raise ValueError('Invalid queued video assignment')
                    for field,group in [('athlete','athletes'),('session','sessions'),('route','routes')]:
                        if not identity.entry(self.organisation,group,assignment[field]):raise ValueError('Queued video has an unknown '+field+' identity')
            except (ValueError,KeyError,OSError,TypeError,ValidationError) as error:
                self.load_error=str(error);self.assignments={}
    def add(self,path):
        key=str(Path(path).resolve())
        if key not in self.videos:self.videos.append(key)
        return key
    def remember(self,path,document,label_path=None,frame=0):
        key=self.add(path);validate(document)
        identity.register(self.organisation,document)
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
        if old in self.assignments:self.assignments[new]=self.assignments.pop(old)
        for entry in self.attempts:
            if entry['path']==old:entry['path']=new
        self.save()
    def documents(self):return [e['state']['document'] for e in self.attempts]+[self.states[p]['document'] for p in self.videos if p in self.states]
    def save(self):
        if self.load_error:raise OSError('Workspace could not be read; original file preserved: '+self.load_error)
        backup=self.path.with_suffix(f'.v{self.version}-backup.json')
        if self.version<3 and self.path.exists() and not backup.exists():shutil.copy2(self.path,backup)
        self.point_names=self.shared_points()
        self.path.parent.mkdir(parents=True,exist_ok=True)
        target=self.path.with_suffix('.tmp');target.write_text(json.dumps({'version':3,'organisation':self.organisation,'assignments':self.assignments,'session_id':self.session_id,'attempts':self.attempts,'point_names':self.shared_points(),'videos':self.videos,'states':self.states},indent=2),encoding='utf-8');target.replace(self.path);self.version=3
