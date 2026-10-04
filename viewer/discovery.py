"""Find private manual labels by video content, including renamed videos."""
from pathlib import Path
from .labels import load

def matching_labels(sha256,folders):
    matches=[];seen=set()
    for folder in folders:
        for path in Path(folder).glob('*.labels.json'):
            path=path.resolve()
            if path in seen:continue
            seen.add(path)
            try:
                document=load(path)
                if document['source']['sha256']==sha256:matches.append((path,document))
            except (ValueError,OSError,KeyError):continue
            except Exception:continue  # Invalid files must not prevent opening a video.
    return sorted(matches,key=lambda pair:pair[0].stat().st_mtime_ns,reverse=True)
