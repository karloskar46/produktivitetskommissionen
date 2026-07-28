"""build_site.py - genererar HTML-sajten fran proposals.json."""
from __future__ import annotations
import html, json
from collections import Counter
from datetime import date
from pathlib import Path

PROPOSALS_FIL = Path("data/proposals.json")
UTDATA = Path("docs/index.html")

STATUS_LABEL = {
    "genomfort": ("Genomfort", "ok"),
    "delvis_genomfort": ("Delvis genomfort", "partial"),
    "ej_genomfort": ("Ej genomfort", "no"),
    "ej_klassificerat": ("Ej klassificerat", "none"),
}

CSS = """
:root { --bg:#eaf2f8; --bg-elev:#fff; --ink:#10263a; --ink-soft:#3a4a5c;
  --ink-mute:#6a7a8a; --line:#c4d6e4; --line-soft:#dde8f0;
  --accent:#1f4b73; --accent-2:#2d6ba3;
  --ok:#2f7a5c; --ok-bg:#d5ebe0; --partial:#a06018; --partial-bg:#f2e1c6;
  --no:#a53e3e; --no-bg:#f0d4d4; --none:#6a7a8a; --none-bg:#dde5ec; }
*{box-sizing:border-box} html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);
  font-family:Georgia,serif;font-size:17px;line-height:1.55}
a{color:var(--accent-2);text-decoration:none;border-bottom:1px solid rgba(45,107,163,.3)}
a:hover{border-bottom-color:var(--accent-2)}
.container{max-width:1180px;margin:0 auto;padding:0 32px}
header.masthead{border-bottom:2px solid var(--accent);padding:48px 0 32px;background:var(--bg-elev)}
.kicker{font-family:-apple-system,sans-serif;text-transform:uppercase;letter-spacing:.14em;font-size:12px;color:var(--accent-2);margin-bottom:8px}
h1{margin:0 0 12px;font-size:44px;line-height:1.1;color:var(--accent)}
.lede{margin:0 0 20px;max-width:720px;font-size:19px;color:var(--ink-soft)}
.source-links{font-family:-apple-system,sans-serif;font-size:14px;padding-top:12px;border-top:1px solid var(--line-soft);display:flex;flex-wrap:wrap;align-items:center;gap:8px 20px}
.spotify-link{display:inline-flex;align-items:center;gap:8px;padding:6px 14px;background:#1db954;color:#fff!important;border:none!important;border-radius:24px;font-size:13px;font-weight:600}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin:32px 0}
.stat{background:var(--bg-elev);padding:20px 24px}
.stat .label{font-family:-apple-system,sans-serif;text-transform:uppercase;letter-spacing:.1em;font-size:11px;color:var(--ink-mute);margin-bottom:6px}
.stat .number{font-size:34px;font-weight:700;color:var(--accent)}
.stat .sub{font-size:13px;color:var(--ink-mute);margin-top:4px;font-family:-apple-system,sans-serif}
.stat.ok .number{color:var(--ok)} .stat.partial .number{color:var(--partial)} .stat.no .number{color:var(--no)}
.method{margin:32px 0 8px;padding:24px 28px;background:var(--bg-elev);border:1px solid var(--line);font-family:-apple-system,sans-serif;font-size:13px;color:var(--ink-soft)}
.method h3{margin:0 0 12px;font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:var(--ink-mute)}
.method-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px 32px}
.method-col h4{margin:0 0 8px;font-size:13px;color:var(--ink);display:flex;align-items:center;gap:8px}
.method-col h4::before{content:"";width:10px;height:10px;border-radius:50%;display:inline-block}
.method-col.implementing h4::before{background:var(--ok)}
.method-col.debating h4::before{background:var(--ink-mute)}
.method-col ul{list-style:none;padding:0;margin:0}
.method-col li{padding:3px 0} .method-col li::before{content:"- ";color:var(--ink-mute)}
.filters{background:var(--bg-elev);border:1px solid var(--line);padding:20px 24px;margin-bottom:28px;font-family:-apple-system,sans-serif}
.filters h3{margin:0 0 12px;font-size:12px;text-transform:uppercase;letter-spacing:.14em;color:var(--ink-mute)}
.filter-row{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;align-items:center}
.filter-row .label{font-size:12px;color:var(--ink-mute);min-width:72px}
.chip{display:inline-block;padding:5px 12px;border:1px solid var(--line);background:var(--bg);color:var(--ink-soft);font-size:13px;border-radius:20px;cursor:pointer;font-family:inherit}
.chip:hover{background:#fff;border-color:var(--accent-2);color:var(--accent)}
.chip.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.section-title{margin:40px 0 20px;padding-bottom:12px;border-bottom:1px solid var(--line);display:flex;align-items:baseline;justify-content:space-between}
.section-title h2{margin:0;font-size:24px;color:var(--accent)}
.section-title .count{font-family:-apple-system,sans-serif;font-size:13px;color:var(--ink-mute)}
.proposals{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px}
.card{background:var(--bg-elev);border:1px solid var(--line);padding:22px 24px;display:flex;flex-direction:column}
.card:hover{box-shadow:0 4px 16px rgba(31,75,115,.1)}
.card-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:14px}
.card-id{font-family:Menlo,monospace;font-size:12px;color:var(--ink-mute)}
.card-id strong{color:var(--accent)}
.badge{display:inline-block;padding:3px 9px;font-size:11px;font-family:-apple-system,sans-serif;text-transform:uppercase;letter-spacing:.08em;font-weight:600;border-radius:3px}
.badge.typ-forslag{background:#1f4b73;color:#d5e5f0}
.badge.typ-bedomning{background:#d5dfea;color:#3a4a5c}
.card-area{font-family:-apple-system,sans-serif;font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--accent-2);margin-bottom:6px;font-weight:600}
.card-text{font-size:16px;color:var(--ink);margin:0 0 18px;flex:1}
.status-block{border-top:1px solid var(--line-soft);padding-top:14px;margin-top:auto;font-family:-apple-system,sans-serif;font-size:13px}
.status-label{font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:var(--ink-mute);margin-bottom:6px}
.status-pill{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:20px;font-size:13px;font-weight:600}
.status-pill::before{content:"";width:8px;height:8px;border-radius:50%;display:inline-block}
.status-pill.ok{background:var(--ok-bg);color:var(--ok)} .status-pill.ok::before{background:var(--ok)}
.status-pill.partial{background:var(--partial-bg);color:var(--partial)} .status-pill.partial::before{background:var(--partial)}
.status-pill.no{background:var(--no-bg);color:var(--no)} .status-pill.no::before{background:var(--no)}
.status-pill.none{background:var(--none-bg);color:var(--none)} .status-pill.none::before{background:var(--none)}
.status-motivation{margin-top:10px;color:var(--ink-soft);font-size:13px}
details.sources{margin-top:12px;font-size:13px}
details.sources summary{cursor:pointer;color:var(--accent-2);padding:6px 0;list-style:none}
details.sources ul{list-style:none;padding:8px 0 0;margin:0}
details.sources li{padding:4px 0;color:var(--ink-soft)}
details.sources li.kalla-header{padding:8px 0 4px;font-weight:600;color:var(--ink);text-transform:uppercase;font-size:10px;letter-spacing:.1em}
.source-typ{display:inline-block;font-size:10px;text-transform:uppercase;letter-spacing:.08em;padding:1px 6px;background:#d8e2ec;color:var(--ink-mute);border-radius:3px;margin-right:6px}
.source-typ.beslut{background:var(--ok-bg);color:var(--ok)}
.card-foot{display:flex;justify-content:space-between;margin-top:14px;padding-top:12px;border-top:1px solid var(--line-soft);font-family:-apple-system,sans-serif;font-size:12px;color:var(--ink-mute)}
footer.pagefoot{margin-top:80px;padding:40px 0;border-top:2px solid var(--accent);background:var(--bg-elev);font-family:-apple-system,sans-serif;font-size:13px;color:var(--ink-mute)}
footer h4{color:var(--accent);font-size:14px;text-transform:uppercase;letter-spacing:.1em;margin:0 0 12px}
.foot-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:32px}
@media(max-width:820px){h1{font-size:32px}.stats{grid-template-columns:repeat(2,1fr)}.proposals{grid-template-columns:1fr}.method-grid{grid-template-columns:1fr}.foot-grid{grid-template-columns:1fr}.container{padding:0 20px}}
"""


def esc(s):
    return html.escape(str(s or ""))


def rendera_kort(p):
    status, css = STATUS_LABEL.get(p["status"], ("Ej klassificerat", "none"))
    typ_klass = "typ-forslag" if p["typ"] == "Forslag" else "typ-bedomning"
    kallor = p.get("kopplade_kallor", [])
    beslut = [k for k in kallor if k.get("status_klass") == "beslut"]
    omn = [k for k in kallor if k.get("status_klass") != "beslut"]
    parts = []
    if beslut:
        parts.append("<li class='kalla-header'>Beslutshandlingar</li>")
        for k in beslut:
            parts.append(f"<li><span class='source-typ beslut'>{esc(k.get('kalla_typ_display', ''))}</span><a href='{esc(k.get('url',''))}' target='_blank' rel='noopener'>{esc(k.get('titel',''))}</a> <span style='color:var(--ink-mute);font-size:12px'>{esc(k.get('publicerad',''))}</span></li>")
    if omn:
        parts.append("<li class='kalla-header'>Omnamnanden och debatt</li>")
        for k in omn:
            parts.append(f"<li><span class='source-typ'>{esc(k.get('kalla_typ_display', ''))}</span><a href='{esc(k.get('url',''))}' target='_blank' rel='noopener'>{esc(k.get('titel',''))}</a> <span style='color:var(--ink-mute);font-size:12px'>{esc(k.get('publicerad',''))}</span></li>")
    kallor_block = ""
    if parts:
        antal = f"{len(beslut)} beslut, {len(omn)} omnamnanden" if beslut and omn else (f"{len(beslut)} beslutshandlingar" if beslut else f"{len(omn)} omnamnanden")
        kallor_block = f"<details class='sources'><summary>{antal}</summary><ul>{''.join(parts)}</ul></details>"
    kap = " - ".join(x for x in [f"Kap. {p['kapitel_nr']}" if p['kapitel_nr'] else "", f"Avsn. {p['avsnitt']}" if p['avsnitt'] else ""] if x) or p["kalla"]
    sou_lank = f"<a href='{esc(p['sou_url'])}' target='_blank' rel='noopener'>{esc(p['sou'])}</a>" if p.get("sou_url") else esc(p["sou"])
    return f"""<article class="card" data-status="{esc(p['status'])}" data-typ="{esc(p['typ'])}" data-kalla="{esc(p['kalla'])}" data-omrade="{esc(p['omrade'])}">
<div class="card-head"><div><div class="card-area">{esc(p['omrade'])}</div><div class="card-id"><strong>{esc(p['id'])}</strong> - {esc(p['kalla'])}</div></div><span class="badge {typ_klass}">{esc(p['typ'])}</span></div>
<p class="card-text">{esc(p['text'])}</p>
<div class="status-block"><div class="status-label">Status</div><span class="status-pill {css}">{esc(status)}</span>
<div class="status-motivation">{esc(p.get('status_motivering','') or 'Annu inga politiska kallor kopplade.')}</div>
{kallor_block}</div>
<div class="card-foot"><span>{esc(kap)} - {sou_lank}</span></div>
</article>"""


def main():
    UTDATA.parent.mkdir(parents=True, exist_ok=True)
    proposals = json.loads(PROPOSALS_FIL.read_text(encoding="utf-8"))
    proposals.sort(key=lambda p: (p["typ"] != "Forslag", p["kalla"] != "Slutbetankandet", p["id"]))
    c = Counter(p["status"] for p in proposals)
    ok = c.get("genomfort", 0); delvis = c.get("delvis_genomfort", 0)
    ej = c.get("ej_genomfort", 0); okl = c.get("ej_klassificerat", 0)
    omraden = Counter(p["omrade"] for p in proposals)
    omrade_chips = '<button class="chip active" data-filter-area="all">Alla</button>' + "".join(
        f'<button class="chip" data-filter-area="{esc(o)}">{esc(o)} ({n})</button>' for o, n in omraden.most_common())
    kort_html = "".join(rendera_kort(p) for p in proposals)
    idag = date.today().strftime("%Y-%m-%d")

    html_out = f"""<!DOCTYPE html>
<html lang="sv"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Produktivitetskommissionen.se</title>
<style>{CSS}</style></head><body>
<header class="masthead"><div class="container">
<div class="kicker">Produktivitetskommissionen - SOU 2024:29 &amp; SOU 2025:96</div>
<h1>Produktivitetskommissionen.se</h1>
<p class="lede">En lopande jamforelse mellan Produktivitetskommissionens {len(proposals)} forslag och bedomningar, och vad som faktiskt sker i svensk politik.</p>
<div class="source-links"><span><strong>Betankanden:</strong>
<a href="https://www.regeringen.se/contentassets/f95ea38d4f914bf6acc8af3ec8b5e7c5/goda-mojligheter-till-okat-valstand-sou-202429/" target="_blank">Delbetankandet (SOU 2024:29)</a> -
<a href="https://www.regeringen.se/contentassets/473a81415a454a85b36b0af5c044a96c/fler-mojligheter-till-okat-valstand-sou-202596.pdf" target="_blank">Slutbetankandet (SOU 2025:96)</a></span>
<a class="spotify-link" href="https://open.spotify.com/show/5oxVTcO7qYI93l7AUtjIy1" target="_blank" rel="noopener">Lyssna: Slutbetankandet som ljudbok</a>
</div></div></header>
<div class="container">
<section class="stats">
<div class="stat"><div class="label">Totalt</div><div class="number">{len(proposals)}</div><div class="sub">Forslag och bedomningar</div></div>
<div class="stat ok"><div class="label">Genomforda</div><div class="number">{ok}</div><div class="sub">Beslut, lagar, regleringsbrev</div></div>
<div class="stat partial"><div class="label">Delvis</div><div class="number">{delvis}</div><div class="sub">Utredning eller reform</div></div>
<div class="stat no"><div class="label">Ej genomforda</div><div class="number">{ej}</div><div class="sub">Aktivt avvisade</div></div>
</section>
<section class="method"><h3>Sa bedoms status</h3>
<p style="margin:0 0 16px;color:var(--ink)">Ett forslag raknas som <strong>genomfort</strong> eller <strong>delvis genomfort</strong> endast om det finns spar i faktiskt beslutsmaterial. Motioner, debattartiklar och uttalanden raknas som <em>omnamnanden</em> och paverkar inte statusen.</p>
<div class="method-grid">
<div class="method-col implementing"><h4>Raknas som genomforande</h4><ul>
<li>Antagen proposition/lag</li><li>Riksdagsbeslut</li><li>Utskottsbetankande (bifall)</li>
<li>Regeringsbeslut</li><li>Regleringsbrev (Statsliggaren)</li><li>Andrad myndighetsinstruktion</li>
<li>Kommittedirektiv (raknas som "delvis")</li></ul></div>
<div class="method-col debating"><h4>Raknas som omnamnande</h4><ul>
<li>Motioner (samtliga partier)</li><li>Anforanden i kammaren</li>
<li>Interpellationer och skriftliga fragor</li><li>Ledare och debattartiklar</li>
<li>Podcasts, seminarier</li><li>Valmanifest och partiprogram</li></ul></div>
</div></section>
<section class="filters"><h3>Filtrera</h3>
<div class="filter-row"><span class="label">Kalla</span>
<button class="chip active" data-filter-kalla="all">Alla</button>
<button class="chip" data-filter-kalla="Delbetankandet">Delbetankandet</button>
<button class="chip" data-filter-kalla="Slutbetankandet">Slutbetankandet</button></div>
<div class="filter-row"><span class="label">Typ</span>
<button class="chip active" data-filter-typ="all">Alla</button>
<button class="chip" data-filter-typ="Forslag">Forslag</button>
<button class="chip" data-filter-typ="Bedomning">Bedomning</button></div>
<div class="filter-row"><span class="label">Status</span>
<button class="chip active" data-filter-status="all">Alla</button>
<button class="chip" data-filter-status="genomfort">Genomfort</button>
<button class="chip" data-filter-status="delvis_genomfort">Delvis</button>
<button class="chip" data-filter-status="ej_genomfort">Ej genomfort</button>
<button class="chip" data-filter-status="ej_klassificerat">Ej klassificerat</button></div>
<div class="filter-row"><span class="label">Omrade</span>{omrade_chips}</div>
</section>
<div class="section-title"><h2>Forslag och bedomningar</h2><div class="count"><span id="visar-antal">{len(proposals)}</span> av {len(proposals)}</div></div>
<div class="proposals">{kort_html}</div>
</div>
<footer class="pagefoot"><div class="container"><div class="foot-grid">
<div><h4>Om projektet</h4>Oberoende medborgarinitiativ som foljer Produktivitetskommissionens {len(proposals)} forslag. Uppdateras automatiskt onsdag och lordag.<br><br><em>Senast: {idag}</em></div>
<div><h4>Kallor</h4>Riksdagens oppna data, regeringen.se, Statsliggaren, oppna nyhets-RSS, samt manuellt uppladdade valmanifest.</div>
<div><h4>Metod</h4>Varje politiskt dokument jamfors mot forslagen med sprakmodell. Endast beslutsdokument kan satta status till Genomfort/Delvis. Motioner och debatt visas som omnamnanden.</div>
</div></div></footer>
<script>
(function(){{const state={{kalla:'all',typ:'all',status:'all',omrade:'all'}};
const kort=Array.from(document.querySelectorAll('.card'));const antalEl=document.getElementById('visar-antal');
function upd(){{let s=0;kort.forEach(k=>{{const ok=(state.kalla=='all'||k.dataset.kalla==state.kalla)&&(state.typ=='all'||k.dataset.typ==state.typ)&&(state.status=='all'||k.dataset.status==state.status)&&(state.omrade=='all'||k.dataset.omrade==state.omrade);k.style.display=ok?'':'none';if(ok)s++;}});antalEl.textContent=s;}}
['kalla','typ','status','area'].forEach(f=>{{const attr='data-filter-'+f;document.querySelectorAll('['+attr+']').forEach(el=>{{el.addEventListener('click',()=>{{state[f=='area'?'omrade':f]=el.getAttribute(attr);el.parentElement.querySelectorAll('.chip').forEach(c=>c.classList.remove('active'));el.classList.add('active');upd();}});}});}});
}})();
</script>
</body></html>"""
    UTDATA.write_text(html_out, encoding="utf-8")
    print(f"[OK] Byggde {UTDATA} med {len(proposals)} kort")


if __name__ == "__main__":
    main()
