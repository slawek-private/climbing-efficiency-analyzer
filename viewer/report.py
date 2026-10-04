"""Offline HTML and CSV reports of human annotations."""
import csv
import html
from pathlib import Path

from .labels import load,metrics,reaches


def esc(value):
    return html.escape(str(value),quote=True)


def fmt(value,percent=False):
    if value is None:
        return "Not reviewed"
    return f"{value*100:.1f}%" if percent else f"{value:.3f}" if isinstance(value,float) else str(value)


def export_csv(document,path):
    path=Path(path)
    with path.open("w",newline="",encoding="utf-8-sig") as target:
        writer=csv.writer(target)
        writer.writerow(["kind","hand","hold_or_quickdraw","start_seconds","end_seconds","duration_seconds","start_frame","end_frame","confidence","notes"])
        for e in sorted(document["events"],key=lambda e:e["start"]["seconds"]):
            writer.writerow([e["kind"],e["hand"],e["target"],e["start"]["seconds"],e["end"]["seconds"],
                             e["end"]["seconds"]-e["start"]["seconds"],e["start"]["frame"],e["end"]["frame"],e["confidence"],e["notes"]])
    summary_path=path.with_name(path.stem+"-summary.csv")
    with summary_path.open("w",newline="",encoding="utf-8-sig") as target:
        result=metrics(document);writer=csv.DictWriter(target,fieldnames=["climber","attempt","outcome",*result.keys()]);writer.writeheader()
        writer.writerow({"climber":document["climber"],"attempt":document["attempt"],"outcome":document["outcome"],**result})


def timeline(document):
    end=max([e["end"]["seconds"] for e in document["events"]]+[document["end"]["seconds"] if document["end"] else 1,1])
    lanes=[("Left contacts","contact","left"),("Right contacts","contact","right"),("Rests","rest","none"),("Clips L","clip","left"),("Clips R","clip","right"),("Off-wall L","offwall","left"),("Off-wall R","offwall","right")]
    output=[f'<svg viewBox="0 0 1000 245" role="img" aria-label="Human-labelled event timeline"><rect width="1000" height="245" fill="#f1f5fb"/>']
    colors={"contact":"#286bd1","rest":"#26986e","clip":"#d48713","offwall":"#8d5aba"}
    for i,(name,kind,hand) in enumerate(lanes):
        y=15+i*30
        output.append(f'<text x="8" y="{y+14}" font-size="12">{name}</text><line x1="120" x2="980" y1="{y+10}" y2="{y+10}" stroke="#d9e1ec"/>')
        for e in document["events"]:
            if e["kind"]==kind and e["hand"]==hand:
                x=120+860*e["start"]["seconds"]/end;w=max(2,860*(e["end"]["seconds"]-e["start"]["seconds"])/end)
                output.append(f'<rect x="{x:.2f}" y="{y}" width="{w:.2f}" height="20" fill="{colors[kind]}" opacity="{0.5 if e["confidence"]<.8 else 1}"><title>{esc(kind)} {esc(hand)} {e["start"]["seconds"]:.3f}–{e["end"]["seconds"]:.3f}s; target {esc(e["target"])}; confidence {e["confidence"]:.2f}</title></rect>')
    output.append(f'<text x="120" y="239" font-size="12">0s</text><text x="900" y="239" font-size="12">{end:.3f}s</text></svg>')
    return "".join(output)


def export_html(documents,path):
    rows,sections=[],[]
    for i,doc in enumerate(documents):
        result=metrics(doc)
        name=esc(doc["climber"])
        values=[doc["outcome"],fmt(result["climb_seconds"]),fmt(result["furthest_hold"]),fmt(result["unique_holds"]),fmt(result["rest_count"]),fmt(result["rest_seconds"]),fmt(result["rest_share"],True)]
        rows.append(f'<tr><th><a href="#attempt-{i}">{name} · {esc(doc["attempt"])}</a></th>'+"".join(f"<td>{esc(v)}</td>" for v in values)+"</tr>")
        events=[]
        for e in sorted(doc["events"],key=lambda e:e["start"]["seconds"]):
            values=[e["kind"],e["hand"],e["target"] if e["target"] is not None else "—",fmt(e["start"]["seconds"]),fmt(e["end"]["seconds"]),fmt(e["end"]["seconds"]-e["start"]["seconds"]),fmt(e["confidence"]),e["notes"]]
            events.append("<tr>"+"".join(f"<td>{esc(v)}</td>" for v in values)+"</tr>")
        reach_rows=[]
        for r in reaches(doc):
            reach_rows.append(f'<tr><td>{r["hand"]}</td><td>{r["from_hold"]} → {r["to_hold"]}</td><td>{r["start"]["seconds"]:.3f}</td><td>{r["end"]["seconds"]:.3f}</td><td>{r["seconds"]:.3f}</td></tr>')
        review=", ".join(k.replace("_"," ") for k,v in doc["reviewed"].items() if v) or "None"
        pending=f'<p class="warning">{len(doc["open_events"])} open event(s): close them before final review.</p>' if doc["open_events"] else ""
        sections.append(f'''<section id="attempt-{i}"><h2>{name} · attempt {esc(doc['attempt'])}</h2><p>{esc(doc['source']['file'])} · Outcome: {esc(doc['outcome'])} · Reviewed: {esc(review)}</p>{pending}
<p>Left hand contact: <strong>{fmt(result['left_contact_seconds'])}</strong>s · Right hand contact: <strong>{fmt(result['right_contact_seconds'])}</strong>s.<br>Off-wall during rests — left: <strong>{fmt(result['left_offwall_during_rests'])}</strong>s; right: <strong>{fmt(result['right_offwall_during_rests'])}</strong>s. Clips: <strong>{fmt(result['clip_count'])}</strong>; total clip duration: <strong>{fmt(result['clip_seconds'])}</strong>s.</p>
<p>Hand switches during rests: <strong>{fmt(result['rest_hand_switches'])}</strong>. Count changes between exclusively off-wall hands; a both-hands-off period resets the sequence.</p>{timeline(doc)}<h3>Every marked interval</h3><div class="scroll"><table><thead><tr><th>Event</th><th>Hand</th><th>Hold / draw</th><th>Start (s)</th><th>End (s)</th><th>Duration (s)</th><th>Confidence</th><th>Notes</th></tr></thead><tbody>{''.join(events) or '<tr><td colspan="8">No closed events marked. This does not establish zero events.</td></tr>'}</tbody></table></div>
<details><summary>Derived reaches (only between marked contacts)</summary><table><thead><tr><th>Hand</th><th>Holds</th><th>Release (s)</th><th>Grab (s)</th><th>Duration (s)</th></tr></thead><tbody>{''.join(reach_rows)}</tbody></table><p>Missing contacts can inflate these gaps. Treat them as complete only after the corresponding contact track is reviewed.</p></details>
<p>{esc(doc['notes'])}</p><details><summary>Source SHA-256</summary><code>{doc['source']['sha256']}</code></details></section>''')
    content='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; base-uri 'none'"><title>Blue route — human-labelled comparison</title><style>
*{box-sizing:border-box}body{margin:0;background:#f1f5fa;color:#18304d;font:16px/1.6 system-ui,Segoe UI,sans-serif}main{max-width:1280px;margin:auto;padding:30px}header{background:#16345b;color:white;padding:30px;border-radius:16px}section{background:white;padding:26px;margin-top:24px;border-radius:12px;border:1px solid #dce5ef}h1{margin:0}h2{margin-top:0}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:12px;border-bottom:1px solid #dce5ef}thead{background:#eaf1fb}a{color:#1c5bb2}.scroll{overflow:auto}svg{width:100%;min-width:500px}.warning{background:#fff0d2;padding:14px}code{overflow-wrap:anywhere}summary{cursor:pointer;font-weight:600}button,input{padding:10px;font:inherit;border:1px solid #9eb0c8;border-radius:8px;background:white}nav{margin:20px 0;display:flex;gap:20px}.hint{color:#566b82;font-size:14px}@media print{body{background:white}main{padding:0}button,input{display:none}section{break-inside:avoid}header{background:white;color:#18304d}}@media(max-width:650px){main{padding:10px}section{padding:15px}}
</style></head><body><main><header><h1>Blue route · climber comparison</h1><p>Human-marked contacts, clips, rests and climb boundaries. No automatic event predictions.</p></header><nav><a href="#comparison">Compare climbers</a><a href="#definitions">Definitions</a><button onclick="window.print()">Print / save PDF</button></nav>
<section id="comparison"><h2>Comparison</h2><p class="hint">Climb time starts at the first hand grip on hold 1 and ends at rope-weighting for a failed attempt. Faster time must be compared alongside holds reached and outcome.</p><input id="filter" placeholder="Filter climbers" aria-label="Filter climbers"><div class="scroll"><table><thead><tr><th>Climber / attempt</th><th>Outcome</th><th>Climb (s)</th><th>Furthest hold</th><th>Unique holds</th><th>Rests</th><th>Rest (s)</th><th>Rest share</th></tr></thead><tbody id="comparison-rows">__ROWS__</tbody></table></div><p class="hint">Not reviewed = incomplete track or boundaries. Zero is shown only for a reviewed track. Confidence is the annotator's subjective certainty, not measured model accuracy.</p></section>__SECTIONS__
<section id="definitions"><h2>Definitions and limits</h2><p>All times use decoded presentation timestamps, including variable-rate video. Intervals include their start and exclude their end. A contact runs from grab to release; a clip runs from taking rope to completing the clip; a rest is a manually identified recovery interval. Merged overlapping/adjacent rests count once. Each hand's off-wall periods are explicitly labelled; missing contact labels are not automatically interpreted as off-wall time.</p><p>Summary values are clipped to the marked attempt interval. Track review is a human assertion of completeness. Uncertain labels remain visible; review does not turn uncertainty into model validation. A completed climb uses a manually marked completion endpoint, not intentional lowering. These labels are suitable for subsequent evaluation, but the report makes no automatic accuracy claim.</p><p>This file is completely local, has no external assets or requests and embeds no footage.</p></section></main><script>document.getElementById('filter').addEventListener('input',e=>document.querySelectorAll('#comparison-rows tr').forEach(r=>r.hidden=!r.innerText.toLowerCase().includes(e.target.value.toLowerCase())));</script></body></html>'''
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(content.replace("__ROWS__","".join(rows)).replace("__SECTIONS__","".join(sections)),encoding="utf-8")
    return path


def export_folder(folder,path):
    documents=[load(p) for p in sorted(Path(folder).glob("*.labels.json"))]
    if not documents:
        raise ValueError("No saved labels in this folder")
    return export_html(documents,path)
