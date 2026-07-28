"""harvest_regeringen.py - hamtar fran regeringen.se RSS-floden."""
from __future__ import annotations
import hashlib, json, re, sys, time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET
import httpx

UTDATA = Path("data/sources/regeringen.jsonl")
PAUS_SEK = 0.5

FEEDS = [
    {"url": "https://www.regeringen.se/rattsliga-dokument/proposition/?feed=rss",
     "typ": "proposition", "display": "Proposition", "status_klass": "beslut"},
    {"url": "https://www.regeringen.se/rattsliga-dokument/kommittedirektiv/?feed=rss",
     "typ": "direktiv", "display": "Kommittedirektiv", "status_klass": "beslut"},
    {"url": "https://www.regeringen.se/rattsliga-dokument/statens-offentliga-utredningar/?feed=rss",
     "typ": "sou", "display": "SOU", "status_klass": "omnamnande"},
    {"url": "https://www.regeringen.se/rattsliga-dokument/departementsserien-och-promemorior/?feed=rss",
     "typ": "ds", "display": "Departementsserien", "status_klass": "omnamnande"},
    {"url": "https://www.regeringen.se/rattsliga-dokument/lagradsremiss/?feed=rss",
     "typ": "lagradsremiss", "display": "Lagradsremiss", "status_klass": "beslut"},
    {"url": "https://www.regeringen.se/pressmeddelanden/?feed=rss",
     "typ": "pressmeddelande", "display": "Pressmeddelande", "status_klass": "omnamnande"},
    {"url": "https://www.regeringen.se/artiklar/?feed=rss",
     "typ": "artikel", "display": "Artikel", "status_klass": "omnamnande"},
]

INTRESSE_ORD = [
    "produktivitet", "regelforenkl", "konsekvensutred", "tillstand",
    "hyres", "bostad", "byggregler", "detaljplan", "karnkraft",
    "vindkraft", "elmarknad", "skiktgrans", "marginalskatt", "faman",
    "expertskatt", "FoU", "forskning", "innovation", "kompetens",
    "arbetskraftsinvandring", "digitali", "AI ", "artificiell",
    "offentlighet", "sekretess", "GDPR", "sandlad", "upphandling",
    "valfrihetssystem", " LOV", "primarvard", "regleringsbrev",
    "myndighetsinstruktion", "kommunsektorn", "statsbidrag",
    "Trafikverk", "infrastruktur", "kalkylranta", "skolval", "friskola",
    "lararlegitim", "foraldraforsakr", "koncentrationsprovning",
    "arbetslivskrim", "personlig assistans", "korruption",
    "produktivitetskommission", "SOU 2024:29", "SOU 2025:96",
    "ROT-avdrag", "listranta", "bensinskatt", "koldioxidskatt",
]


def httpx_get(client, url):
    for forsok in range(3):
        try:
            r = client.get(url, timeout=30, follow_redirects=True)
            if r.status_code == 200:
                time.sleep(PAUS_SEK)
                return r
            if r.status_code in (429, 503):
                time.sleep(5 * (forsok + 1))
                continue
            r.raise_for_status()
        except httpx.RequestError:
            if forsok == 2:
                raise
            time.sleep(3)
    raise RuntimeError(f"Kunde inte hamta {url}")


def rensa_html(html):
    utan_script = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    utan_tags = re.sub(r"<[^>]+>", " ", utan_script)
    utan_ent = re.sub(r"&nbsp;|&#160;", " ", utan_tags)
    utan_ent = re.sub(r"&[a-z]+;", " ", utan_ent)
    return re.sub(r"\s+", " ", utan_ent).strip()


def parsa_datum(s):
    if not s:
        return ""
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return s[:10]


def dok_id(url):
    return "reg-" + hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def parsa_rss(xml_text):
    """Parsa RSS/Atom. Om XML-parsern misslyckas: fall tillbaka till regex."""
    try:
        root = ET.fromstring(xml_text)
        poster = []
        for item in root.iter():
            tag = item.tag.split("}")[-1].lower()
            if tag not in ("item", "entry"):
                continue
            titel = lank = publicerad = beskrivning = ""
            for child in item:
                ctag = child.tag.split("}")[-1].lower()
                text = (child.text or "").strip()
                if ctag == "title":
                    titel = text
                elif ctag == "link":
                    lank = child.get("href") or text
                elif ctag in ("pubdate", "published", "updated"):
                    publicerad = parsa_datum(text)
                elif ctag in ("description", "summary"):
                    beskrivning = rensa_html(text)
            if titel and lank:
                poster.append({"titel": titel, "url": lank,
                              "publicerad": publicerad, "beskrivning": beskrivning})
        return poster
    except ET.ParseError as e:
        print(f"  ! XML-fel, byter till regex-lage: {e}", file=sys.stderr)
        return parsa_rss_regex(xml_text)


def parsa_rss_regex(xml_text):
    """Fallback-parser med regex som klarar trasig XML."""
    poster = []
    items = re.findall(r"<item[^>]*>(.*?)</item>", xml_text, flags=re.S | re.I)
    if not items:
        items = re.findall(r"<entry[^>]*>(.*?)</entry>", xml_text, flags=re.S | re.I)
    for it in items:
        m_titel = re.search(r"<title[^>]*>(.*?)</title>", it, re.S | re.I)
        m_lank = re.search(r"<link[^>]*>(.*?)</link>", it, re.S | re.I)
        m_datum = re.search(r"<(?:pubDate|published|updated)[^>]*>(.*?)</(?:pubDate|published|updated)>", it, re.S | re.I)
        m_desc = re.search(r"<description[^>]*>(.*?)</description>", it, re.S | re.I)
        titel = m_titel.group(1) if m_titel else ""
        lank = m_lank.group(1) if m_lank else ""
        # Rensa CDATA-omslag
        titel = re.sub(r"<!\[CDATA\[|\]\]>", "", titel).strip()
        lank = re.sub(r"<!\[CDATA\[|\]\]>", "", lank).strip()
        # Klipp bort ev inbaddade taggar i titel/lank
        titel = re.sub(r"<[^>]+>", " ", titel)
        titel = re.sub(r"\s+", " ", titel).strip()
        lank = re.sub(r"<[^>]+>", " ", lank)
        lank = re.sub(r"\s+", "", lank).strip()
        publicerad = parsa_datum(m_datum.group(1).strip()) if m_datum else ""
        beskrivning = rensa_html(m_desc.group(1)) if m_desc else ""
        if titel and lank:
            poster.append({"titel": titel, "url": lank,
                          "publicerad": publicerad, "beskrivning": beskrivning})
    return poster


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


def hamta_utdrag(client, url, max_tecken=800):
    try:
        r = httpx_get(client, url)
        text = rensa_html(r.text)
        meningar = re.split(r"(?<=[.!?])\s+", text)
        renset = " ".join(m for m in meningar if len(m) > 40)
        return (renset or text)[:max_tecken]
    except Exception:
        return ""


def main():
    UTDATA.parent.mkdir(parents=True, exist_ok=True)
    kanda_ids = las_befintliga_ids()
    print(f"[i] Redan skordade: {len(kanda_ids)}")
    nya = []
    with httpx.Client(headers={"User-Agent": "Produktivitetskommissionen.se-skordare"}) as client:
        for feed in FEEDS:
            print(f"[*] {feed['display']}")
            try:
                r = httpx_get(client, feed["url"])
                poster = parsa_rss(r.text)
            except Exception as e:
                print(f"  ! Fel: {e}", file=sys.stderr)
                continue
            print(f"  Hittade {len(poster)} poster i flodet")
            for post in poster:
                dok_ident = dok_id(post["url"])
                if dok_ident in kanda_ids:
                    continue
                if feed["typ"] in ("pressmeddelande", "artikel"):
                    if not ar_intressant(post["titel"] + " " + post["beskrivning"]):
                        continue
                utdrag = hamta_utdrag(client, post["url"])
                if not ar_intressant(f"{post['titel']} {post['beskrivning']} {utdrag}"):
                    continue
                nya.append({
                    "id": dok_ident, "typ": feed["typ"],
                    "typ_display": feed["display"],
                    "status_klass": feed["status_klass"],
                    "titel": post["titel"], "publicerad": post["publicerad"],
                    "url": post["url"], "beskrivning": post["beskrivning"][:400],
                    "text_utdrag": utdrag, "kalla": "regeringen.se",
                })
                kanda_ids.add(dok_ident)
    with UTDATA.open("a", encoding="utf-8") as f:
        for obj in nya:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(f"[OK] Lade till {len(nya)} nya dokument.")


if __name__ == "__main__":
    main()
