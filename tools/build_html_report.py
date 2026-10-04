"""Build a self-contained local report from the current footage inventory.

Until validated event results exist, measurement fields remain unavailable.
No footage, external assets, requests or telemetry are embedded.
"""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def esc(value):
    return html.escape(str(value), quote=True)


def clock(seconds):
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}:{remainder:05.2f}"


def diagnostics(video):
    folder = ROOT / "artifacts" / "m0" / Path(video["file"]).stem
    data = {}
    for stage in ("detector", "base", "large"):
        path = folder / f"blue_{stage}.json"
        if not path.exists():
            return None
        result = json.loads(path.read_text(encoding="utf-8"))
        identity = result.get("source_identity", {})
        if identity.get("sha256") != video["sha256"] or identity.get("file") != video["file"]:
            return None
        data[stage] = result
    return data


def diagnostic_html(data):
    records = data["detector"]["records"]
    counts = Counter(r["blue_route"]["status"] for r in records)
    candidates = counts["blue_route_candidate"]
    statuses = {"blue_route_candidate": "Route/person candidate (unverified)",
                "no_route_person": "No qualifying person on route",
                "insufficient_blue_holds": "Too few blue hold candidates",
                "ambiguous_blue_routes": "More than one plausible blue route",
                "ambiguous_route_people": "More than one plausible route person"}
    segments = "".join(f'<span class="sample {"found" if r["person_box"] else "missing"}" title="{r["seconds"]:.3f}s: {esc(statuses[r["blue_route"]["status"]])}" aria-label="{r["seconds"]:.3f}s: {esc(statuses[r["blue_route"]["status"]])}"></span>' for r in records)
    failures = "".join(f"<li>{esc(statuses[status])}: <strong>{count}</strong></li>" for status,count in sorted(counts.items()))
    timing_rows = []
    for stage,label in (("detector","Blue-route detector"),("base","ViTPose Base"),("large","ViTPose+ Large")):
        result = data[stage]
        if stage == "detector":
            fps = len(records)/sum(r["seconds_processing"] for r in records)
        else:
            fps = result["fps"]
        fps_text = f"{fps:.2f}" if fps is not None else "No person crops"
        timing_rows.append(f"<tr><th>{label}</th><td>{fps_text}</td><td>{result['peak_allocated_mib']:.0f} / {result['peak_reserved_mib']:.0f} MiB</td></tr>")
    return f'''<section class="diagnostics"><h3>Analysis actually run</h3><p><strong>{len(records)} PTS-based samples</strong> spread across this recording. <strong>{candidates}/{len(records)}</strong> produced a blue-route person candidate; identity remains unverified. This is a feasibility scan, not continuous event analysis.</p>
      <h4>Route/person candidate availability</h4><div class="samples" role="group" aria-label="Sample availability">{segments}</div><p class="hint">Blue: unverified candidate. Grey: no usable candidate. Hover a sample for its presentation timestamp and reason. Gaps are not rest intervals.</p>
      <div class="two-col"><section><h4>Reasons and coverage</h4><ul>{failures}</ul></section><section><h4>Measured processing performance</h4><table><thead><tr><th>Stage</th><th>Sample FPS</th><th>GPU allocated / reserved</th></tr></thead><tbody>{''.join(timing_rows)}</tbody></table><p class="hint">Batch 1, float32. Excludes decoding, model loading and overlays. GPU values are PyTorch allocator peaks. FPS is throughput, not climbing speed or accuracy.</p></section></div>
      <p><strong>Result decision: measurements withheld.</strong> These samples cannot establish continuous contacts, hold numbering, rest intervals, first grip or rope-weighting. No measured event accuracy exists.</p></section>'''


def build(inventory, destination):
    current = {p.name for p in (ROOT / "videos").iterdir() if p.suffix.lower() in {".mov", ".mp4"}}
    if current != {v["file"] for v in inventory}:
        raise ValueError("Video collection changed; refresh the inventory before reporting.")
    rows, details = [], []
    analysed = 0
    for index, video in enumerate(inventory):
        source = ROOT / "videos" / video["file"]
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != video["sha256"]:
            raise ValueError(f"Inventory is stale for {video['file']}; refresh it before reporting.")
        name = esc(Path(video["file"]).stem.split("_final_")[0].capitalize())
        data = diagnostics(video)
        if data:
            analysed += 1
        status = "Withheld" if data else "Unassessed"
        detail_status = "Scan complete · measurements withheld" if data else "Awaiting analysis"
        evidence = diagnostic_html(data) if data else ""
        identifier = f"attempt-{index}"
        rows.append(f'''<tr data-name="{name.lower()}"><th scope="row"><a href="#{identifier}">{name}</a><small>Attempt 1 · name from filename</small></th>
          <td><span class="badge pending">{status}</span></td>
          <td class="unavailable">Unavailable</td><td class="unavailable">Unavailable</td>
          <td class="unavailable">Unavailable</td><td class="unavailable">Unavailable</td>
          <td class="unavailable">Unavailable</td><td class="unavailable">Unavailable</td></tr>''')
        width, height = video["width_encoded"], video["height_encoded"]
        if abs(video["rotation"]) == 90:
            width, height = height, width
        measures = "".join(f'<div><dt>{label}</dt><dd class="unavailable">Unavailable</dd></div>' for label in
            ("Climb time", "First grip on hold 1", "First rope-weighting", "Furthest blue hold",
             "Unique blue holds", "Rest count", "Total rest time", "Rest share"))
        details.append(f'''<details class="attempt" id="{identifier}">
          <summary><span>{name}<small>{esc(video['file'])}</small></span><span class="badge pending">{detail_status}</span></summary>
          <div class="attempt-body"><dl class="measurements">{measures}</dl>
          <div class="notice"><strong>Why results are unavailable</strong><p>The current feasibility pipeline has not established reliable blue-route identity, hand contacts or rope-weighting. No verified events or confidence values exist for this attempt.</p></div>
          {evidence}
          <div class="two-col"><section><h3>Rests and movement</h3><p>No verified rest intervals, hand switches, reaches or hold contacts are available. An empty event list would not mean zero rests.</p></section>
          <section><h3>Recording information</h3><dl class="metadata"><dt>Recording length</dt><dd>{clock(video['duration_metadata_seconds'])} <small>container metadata; not climb time</small></dd>
          <dt>Display resolution</dt><dd>{width} × {height}</dd><dt>Codec</dt><dd>{esc(video['codec']).upper()}</dd>
          <dt>File size</dt><dd>{video['bytes']/2**20:,.1f} MiB</dd></dl></section></div>
          <details class="provenance"><summary>Source verification</summary><p>Report inventory matched the local file's SHA-256 when generated.</p><code>{esc(video['sha256'])}</code></details>
          </div></details>''')
    document = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'">
<title>Blue route — climber comparison</title>
<style>
:root{color-scheme:light;--ink:#18263c;--muted:#53647a;--line:#dce4ee;--blue:#1859c9;--paper:#fff;--bg:#f3f6fa}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:25px}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,Segoe UI,sans-serif}
main{max-width:1320px;margin:auto;padding:42px 28px 60px}header{background:#152944;color:white;padding:38px;border-radius:18px}
.eyebrow{letter-spacing:.12em;text-transform:uppercase;font-size:12px;font-weight:700;color:#9fc3ff}h1{font-size:clamp(28px,4vw,44px);line-height:1.15;margin:12px 0}header p{max-width:780px;color:#d6e3f6;margin-bottom:0}
nav{display:flex;gap:22px;padding:20px 4px;flex-wrap:wrap}a{color:var(--blue);text-underline-offset:4px}header a{color:white}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:8px 0 24px}.stat,.panel,.attempt{background:var(--paper);border:1px solid var(--line);border-radius:14px}.stat{padding:20px 24px}.stat strong{font-size:30px;display:block}.stat span{color:var(--muted)}
.notice{padding:18px 22px;background:#fff8e8;border-left:4px solid #b67b10;border-radius:8px}.notice p{margin:5px 0 0}.panel{padding:26px;margin-top:26px}h2{font-size:24px;margin:0 0 10px}h3{font-size:18px;margin:0 0 10px}.subtitle,p{color:var(--muted)}
.toolbar{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin:20px 0}input,button{font:inherit;border:1px solid #aebed2;border-radius:8px;padding:10px 14px;background:white;color:var(--ink)}input{min-width:260px}button{cursor:pointer}button:hover{background:#eaf1fc}label{font-weight:600}
.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:17px 12px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}thead th{background:#edf3fc;font-weight:600}tbody th small,summary small{display:block;font-weight:400;font-size:12px;color:var(--muted);margin-top:4px}
.unavailable{color:#64748b;font-weight:400}.badge{display:inline-block;font-size:12px;font-weight:600;padding:5px 10px;border-radius:30px}.pending{background:#eef2f6;color:#526176}.legend{font-size:14px;margin-top:14px}
.attempt{margin-top:14px;scroll-margin-top:20px}summary{cursor:pointer;display:flex;justify-content:space-between;align-items:center;gap:15px;padding:20px 24px;font-weight:650}summary::before{content:'+';color:var(--blue);margin-right:6px}details[open]>summary::before{content:'−'}summary>span:first-of-type{flex:1}.attempt-body{padding:0 24px 24px}
.measurements{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:0 0 20px}.measurements div{background:#f5f7fb;padding:16px;border-radius:8px}dt{color:var(--muted);font-size:13px}dd{margin:5px 0 0;font-size:18px}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-top:24px}.metadata{display:grid;grid-template-columns:150px 1fr;gap:8px}.metadata dd{font-size:14px;margin:0}.metadata small{display:block;color:var(--muted)}.provenance{margin-top:12px;background:#f5f7fb;border-radius:8px}.provenance p,.provenance code{margin:10px 20px;display:block;font-size:12px;overflow-wrap:anywhere}
.definitions{display:grid;grid-template-columns:1fr 1fr;gap:22px}.definitions section{padding:18px;background:#f5f7fb;border-radius:10px}.definitions p{margin-bottom:0}.empty{display:none;padding:20px}.footer{font-size:13px;color:var(--muted);margin-top:30px}.section-label{margin-top:34px}.hint{font-size:13px}
.diagnostics{margin-top:24px;padding:20px;border:1px solid var(--line);border-radius:10px}.samples{display:flex;gap:4px;height:25px}.sample{flex:1;border-radius:3px}.found{background:#1859c9}.missing{background:#dce4ee}.diagnostics h4{margin:18px 0 8px}.diagnostics td,.diagnostics th{white-space:normal;font-size:12px;padding:8px}.diagnostics ul{padding-left:18px}
@media(max-width:760px){main{padding:20px 12px}header{padding:25px}.stats{grid-template-columns:1fr}.measurements,.definitions,.two-col{grid-template-columns:1fr 1fr}.panel{padding:18px}.metadata{grid-template-columns:1fr}.metadata dt{margin-top:8px}}
@media(max-width:440px){.measurements,.definitions,.two-col{grid-template-columns:1fr}input{min-width:0;width:100%}}
@media print{body{background:white}main{padding:0;max-width:none}header{background:white;color:var(--ink);border-bottom:2px solid var(--blue)}header p,.eyebrow{color:var(--muted)}nav,.toolbar{display:none}.panel,.attempt{break-inside:avoid}.table-wrap{overflow:visible}th,td{font-size:10px;padding:8px 5px}.stats{grid-template-columns:repeat(3,1fr)}a{color:inherit;text-decoration:none}}
</style></head><body><main>
<header><div class="eyebrow">Local report · blue climbing route · 4 October 2026</div><h1>Climber comparison</h1><p>Compare time to rope-weighting, holds reached and recovery rests. Each result must come from observable events on the same blue route.</p></header>
<nav aria-label="Report sections"><a href="#comparison">Comparison</a><a href="#attempts">Climber details</a><a href="#definitions">Definitions</a><a href="#quality">Quality &amp; evidence</a></nav>
<section class="stats" aria-label="Report status"><div class="stat"><strong>__ANALYSED__ / __COUNT__</strong><span>Recordings with a current feasibility scan</span></div><div class="stat"><strong>0</strong><span>Attempts with validated event results</span></div><div class="stat"><strong>Blue route</strong><span>Target for every attempt</span></div></section>
<div class="notice" role="note"><strong>__ANALYSED__ sampled analyses completed; comparison measurements are withheld.</strong><p>The current M0 spike does not reliably establish route identity, contacts, rests or rope-weighting. Expand each climber to see the measured route coverage, rejection reasons and model performance. This report does not rank climbers or substitute recording lengths for climb times.</p></div>
<section class="panel" id="comparison"><h2>Comparison at a glance</h2><p class="subtitle">One provisional attempt per recording. Names are taken from filenames; identities and attempt boundaries are not verified.</p>
<div class="toolbar"><label for="search">Find a climber</label><input id="search" type="search" placeholder="Type a name" autocomplete="off"><button id="expand" type="button">Expand all details</button><button id="print" type="button">Print / save PDF</button></div>
<div class="table-wrap"><table><caption class="hint" style="text-align:left;padding-bottom:10px">Timing and rest fields require validated analysis. Select a name to open its details.</caption><thead><tr><th scope="col">Climber</th><th scope="col">Analysis status</th><th scope="col">Climb time</th><th scope="col">Furthest hold</th><th scope="col">Unique holds</th><th scope="col">Rest count</th><th scope="col">Rest time</th><th scope="col">Rest share</th></tr></thead><tbody>__ROWS__</tbody></table></div><p id="empty" class="empty" role="status">No matching climber.</p>
<p class="legend"><strong>Unavailable</strong> means no supported measurement exists. It does not mean zero, no rests or a failed climb.</p></section>
<section id="attempts"><h2 class="section-label">Climber details</h2><p>Expand an attempt for measurements, recording information and the reason results are withheld.</p>__DETAILS__</section>
<section class="panel" id="definitions"><h2>What the measurements mean</h2><div class="definitions">
<section><h3>Climb time — your speed comparison</h3><p>Elapsed time from the first grip by either hand on blue hold 1 until the climber first weights the rope. Includes rests. A fall's onset and the moment the rope takes weight can differ.</p></section>
<section><h3>Holds reached</h3><p>Unique blue-route holds with verified hand contacts, plus the furthest progression rank reached. Regrabbing a hold does not increase the unique count. A shared route map is required across videos.</p></section>
<section><h3>Rests</h3><p>Recovery intervals with little hip progression, supported by hand-contact and movement evidence. Report count, each duration, total duration, each hand's off-wall time and switches. A reach alone is not a rest. Thresholds still require validation.</p></section>
<section><h3>Rest share</h3><p>Total rest time divided by the measured climb time, expressed as a percentage. Overlapping rest intervals count once. All rest statistics use the same start-to-rope-weighting interval.</p></section>
<section><h3>Comparable outcomes</h3><p>Less time is not necessarily better if a climber reaches fewer holds. Compare equivalent progress as well as whole attempts. Completion, abandonment and failure must remain distinct.</p></section>
<section><h3>Missing boundaries</h3><p>If the recording starts after the first grip or ends before rope-weighting, the complete duration is unavailable. Hidden rope support must not be guessed. Intentional lowering after completion is not a failure.</p></section></div></section>
<section class="panel" id="quality"><h2>Quality and supporting evidence</h2><div class="two-col"><section><h3>Current feasibility verdict</h3><p>Native Windows execution, CUDA and local video decoding work. The preliminary route filter has low coverage and unverified climber identity. Reliable hand contacts, rest events and failure boundaries have not been demonstrated.</p><p>There are no measured event precision/recall values or calibrated confidence values for these eight attempts.</p></section>
<section><h3>What must precede a ranking</h3><p>Identify the same numbered blue-route holds across videos; track the correct climber; establish first contact and rope-weighting; label a reference sample; evaluate contacts, rests and boundary errors. Per-event uncertainty and reasons for rejected videos will accompany the results.</p><p>The current example recording differs from the original benchmark file. Earlier three-video benchmark counts are historical and cannot be applied to this collection.</p></section></div></section>
<footer class="footer">Generated locally from a SHA-256-verified footage inventory. No videos or images of people are embedded. This file uses no external scripts, fonts, APIs or telemetry and can be opened offline. Current stage: M0 feasibility and review.</footer>
</main><script>
const search=document.getElementById('search');search.addEventListener('input',()=>{let count=0;const term=search.value.trim().toLowerCase();document.querySelectorAll('tbody tr').forEach(row=>{const show=row.dataset.name.includes(term);row.hidden=!show;if(show)count++;});document.getElementById('empty').style.display=count?'none':'block';});
document.querySelectorAll('a[href^="#attempt-"]').forEach(link=>link.addEventListener('click',()=>{document.querySelector(link.getAttribute('href')).open=true;}));
document.getElementById('expand').addEventListener('click',event=>{const elements=[...document.querySelectorAll('details.attempt')];const open=elements.some(x=>!x.open);elements.forEach(x=>x.open=open);event.target.textContent=open?'Collapse all details':'Expand all details';});
document.getElementById('print').addEventListener('click',()=>{document.querySelectorAll('details.attempt').forEach(x=>x.open=true);window.print();});
</script></body></html>'''
    document = document.replace("__ANALYSED__", str(analysed)).replace("__COUNT__", str(len(inventory))).replace("__ROWS__", "\n".join(rows)).replace("__DETAILS__", "\n".join(details))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "reports" / "blue-route-report.html")
    args = parser.parse_args()
    inventory = json.loads((ROOT / "artifacts" / "video_inventory.json").read_text(encoding="utf-8"))
    print(build(inventory, args.output))
