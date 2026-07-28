"""harvest_statsliggaren.py - hamtar regleringsbrev fran Statsliggaren."""
from __future__ import annotations
import hashlib, json, re, sys, time
from datetime import date
from pathlib import Path
import httpx

UTDATA = Path("data/sources/statsliggaren.jsonl")
BASE = "https://www.statskontoret.se/statsliggaren"
PAUS_SEK = 0.8
INNEVARANDE_AR = date.today().year
AR_ATT_HAMTA = [INNEVARANDE_AR, INNEVARANDE_AR - 1]

PRIORITERADE_MYNDIGHETER = [
    "Ekonomistyrningsverket", "Boverket", "Trafikverket",
    "Skolverket", "Skolinspektionen", "Universitetskanslersambetet",
    "Statskontoret", "Digg", "Myndigheten for digital forvaltning",
    "Kungliga biblioteket", "SCB", "Statistiska centralbyran",
    "Konkurrensverket", "Upphandlingsmyndigheten", "Riksgaldskontoret",
    "Finansinspektionen", "Kammarkollegiet", "Socialstyrelsen",
    "Folkhalsomyndigheten", "Arbetsformedlingen",
    "Myndigheten for yrkeshogskolan", "Medlingsinstitutet",
    "Naturvardsverket", "Svenska kraftnat",
    "Patent- och registreringsverket", "VTI", "Trafikanalys",
    "Verksamt", "Verksamt.se",
]

INTRESSE_ORD = [
    "produktivitetskommission", "SOU 2024:29", "SOU 2025:96",
    "regelforenkl", "konsekvensutred", "tillstand", "handlaggning",
    "digitali", "AI", "artificiell", "automatiser", "upphandling",
    "valfrihetssystem", "LOV", "bostad", "byggreg", "detaljplan",
    "hyres", "infrastruktur", "kalkylranta", "underhall", "skolval",
    "friskola", "lararleg", "yrkeshogskola", "arbetskraft",
    "kompetens", "arbetsmarknadsutbildning", "karnkraft", "vindkraft",
    "elmarknad", "flaskhals", "riskkapital", "bors", "primarvard",
    "regleringsbrev", "aterrapporter",
]


def httpx_get(client, url):
    for forsok in range(3):
        try:
            r = client.get(url, timeout=45, follow_redirects=True)
            if r.status_code == 200:
                time.sleep(PAUS_SEK)
                return r
            if r.status_code == 404:
                return None
            if r.status_code in (429, 503):
                time.sleep(6 * (forsok + 1))
                continue
        except httpx.RequestError:
            if forsok == 2:
                return None
            time.sleep(4)
    return None


def rensa_html(html):
    utan_script = re.sub(r"<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    utan_tags = re.sub(r"<[^>]+>", " ", utan_script)
    utan_ent = re.sub(r"&nbsp;|&#160;", " ", utan_tags)
    utan_ent = re.sub(r"&[a-z]+;", " ", utan_ent)
    return re.sub(r"\s+", " ", utan_ent).strip()


def dok_id(url):
    return "stat-" + hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def ar_intressant(text):
    tl = text.lower()
    return any(o.lower() in tl for o in INTRESSE_ORD)


def las_befintliga_ids():
    if not UTDATA.exists():
        return set()
    ids = set()
    with UTDATA.open(encoding="utf-8") as f:
        for rad in f:
            try:
                ids.add(json.loads(rad)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def hitta_arliga_lankar(client, ar):
    url = f"{BASE}/regleringsbrev?asring={ar}"
    r = httpx_get(client, url)
    if r is None:
        return []
    lankar = re.findall(r'href="([^"]*regleringsbrev/[^"]*RBID=[^"]+)"', r.text)
    absoluta = []
    for l in lankar:
        if l.startswith("http"):
            absoluta.append(l)
        elif l.startswith("/"):
            absoluta.append("https://www.statskontoret.se" + l)
        else:
            absoluta.append(f"{BASE}/" + l.lstrip("./"))
    return list(dict.fromkeys(absoluta))


def extrahera_regleringsbrev(client, url):
    r = httpx_get(client, url)
    if r is None:
        return None
    html = r.text
    text = rensa_html(html)
    m_titel = re.search(r"<title>([^<]+)</title>", html, re.I)
    titel = (m_titel.group(1).strip() if m_titel else "Regleringsbrev")
    titel = re.sub(r"\s+", " ", titel)
    m_datum = re.search(r"(\d{4}-\d{2}-\d{2})", text[:2000])
    datum = m_datum.group(1) if m_datum else ""
    myndighet = ""
    for m in PRIORITERADE_MYNDIGHETER:
        if m.lower() in text[:1500].lower():
            myndighet = m
            break
    return {
        "id": dok_id(url), "typ": "regleringsbrev",
        "typ_display": "Regleringsbrev", "status_klass": "beslut",
        "titel": titel[:200], "myndighet": myndighet,
        "publicerad": datum, "url": url,
        "text_utdrag": text[:1200], "kalla": "Statsliggaren",
    }


def main():
    UTDATA.parent.mkdir(parents=True, exist_ok=True)
    kanda_ids = las_befintliga_ids()
    print(f"[i] Redan skordade: {len(kanda_ids)}")
    nya = []
    with httpx.Client(headers={"User-Agent": "Produktivitetskommissionen.se-skordare"}) as client:
        alla_lankar = []
        for ar in AR_ATT_HAMTA:
            print(f"[*] Budgetar {ar}")
            alla_lankar.extend(hitta_arliga_lankar(client, ar))
        alla_lankar = list(dict.fromkeys(alla_lankar))
        att_hamta = [l for l in alla_lankar if dok_id(l) not in kanda_ids]
        print(f"[*] Nya att bearbeta: {len(att_hamta)}")
        for i, url in enumerate(att_hamta, 1):
            if i % 25 == 0:
                print(f"  ... {i}/{len(att_hamta)}")
            obj = extrahera_regleringsbrev(client, url)
            if obj is None:
                continue
            if not obj["myndighet"] and not ar_intressant(obj["text_utdrag"]):
                continue
            nya.append(obj)
            kanda_ids.add(obj["id"])
    with UTDATA.open("a", encoding="utf-8") as f:
        for obj in nya:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(f"[OK] Lade till {len(nya)} nya regleringsbrev.")


if __name__ == "__main__":
    main()
