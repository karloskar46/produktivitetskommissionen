"""harvest_riksdagen.py - hamtar fran Riksdagens oppna data."""
from __future__ import annotations
import json, re, sys, time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
import httpx

UTDATA = Path("data/sources/riksdagen.jsonl")
BASE = "https://data.riksdagen.se"
PAUS_SEK = 0.4

DOKTYPER = {
    "prop": {"display": "Proposition", "status_klass": "beslut"},
    "bet": {"display": "Utskottsbetankande", "status_klass": "beslut"},
    "sfs": {"display": "Forfattning (SFS)", "status_klass": "beslut"},
    "dir": {"display": "Kommittedirektiv", "status_klass": "beslut"},
    "ds": {"display": "Departementsserien", "status_klass": "omnamnande"},
    "mot": {"display": "Motion", "status_klass": "omnamnande"},
    "ip": {"display": "Interpellation", "status_klass": "omnamnande"},
    "fr": {"display": "Skriftlig fraga", "status_klass": "omnamnande"},
    "anf": {"display": "Anforande", "status_klass": "omnamnande"},
}

NYCKELORD = [
    "produktivitetskommission", "SOU 2024:29", "SOU 2025:96",
    "regelforenkling", "konsekvensutredning", "tillstandsprocess",
    "hyressattning", "bostadsbyggande", "detaljplan", "skolval",
    "friskola", "lararlegitimation", "marginalskatt", "skiktgrans",
    "FoU-avdrag", "3:12-regler", "famansforetag", "expertskatt",
    "arbetskraftsinvandring", "startupvisum", "riskkapital",
    "listranta", "koncentrationsprovning", "karnkraft", "vindkraft",
    "havsbaserad vindkraft", "flexibel lonebildning",
    "omstallningsstudiestod", "arbetsmarknadsutbildning",
    "foraldraforsakring", "digitalisering offentlig sektor",
    "AI offentlig sektor", "offentlighet sekretess", "GDPR",
    "regulatoriska sandlador", "offentlig upphandling",
    "overprovning", "LOV", "valfrihetssystem", "primarvard",
    "ROT-avdrag", "bensinskatt", "dieselskatt", "koldioxidskatt",
    "kommunala statsbidrag", "riktade statsbidrag", "Trafikverket",
    "kalkylranta", "infrastrukturplan", "strandskydd", "planmonopol",
    "personlig assistans", "arbetslivskriminalitet",
]


def httpx_get(client, url, **kwargs):
    for forsok in range(3):
        try:
            r = client.get(url, timeout=30, **kwargs)
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
    utan_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    utan_tags = re.sub(r"<[^>]+>", " ", utan_script)
    utan_ent = re.sub(r"&[a-z]+;", " ", utan_tags)
    return re.sub(r"\s+", " ", utan_ent).strip()


def sok(client, query, doktyp, from_datum, sida=1, size=50):
    params = {"sok": query, "doktyp": doktyp, "from": from_datum,
              "sort": "datum", "sortorder": "desc", "utformat": "json",
              "sz": size, "p": sida}
    url = f"{BASE}/dokumentlista/?{urlencode(params)}"
    r = httpx_get(client, url)
    data = r.json().get("dokumentlista", {})
    dokument = data.get("dokument", [])
    if isinstance(dokument, dict):
        dokument = [dokument]
    return dokument


def hamta_fulltext(client, dok_id):
    url = f"{BASE}/dokument/{dok_id}.html"
    try:
        r = httpx_get(client, url)
        return rensa_html(r.text)
    except Exception as e:
        print(f"  ! Kunde inte hamta {dok_id}: {e}", file=sys.stderr)
        return ""


def normalisera(rad, doktyp):
    dok_id = rad.get("dok_id") or rad.get("id")
    if not dok_id:
        return None
    partier = [p.strip() for p in rad.get("parti", "").split(",") if p.strip()]
    info = DOKTYPER[doktyp]
    return {
        "id": dok_id, "typ": doktyp,
        "typ_display": info["display"],
        "status_klass": info["status_klass"],
        "titel": (rad.get("titel") or rad.get("notisrubrik") or "").strip(),
        "publicerad": rad.get("publicerad", "")[:10],
        "url": rad.get("dokument_url_html") or f"https://www.riksdagen.se/sv/dokument-och-lagar/dokument/{doktyp}/{dok_id}",
        "partier": partier,
        "organ": rad.get("organ", ""),
        "rm": rad.get("rm", ""),
        "text_utdrag": "",
    }


def las_befintliga():
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


def main():
    UTDATA.parent.mkdir(parents=True, exist_ok=True)
    kanda_ids = las_befintliga()
    print(f"[i] Redan skordade: {len(kanda_ids)}")
    if kanda_ids:
        from_datum = (date.today() - timedelta(days=28)).isoformat()
    else:
        from_datum = (date.today() - timedelta(days=365)).isoformat()
    print(f"[i] Hamtar fran {from_datum}")

    nya_dokument = []
    with httpx.Client(headers={"User-Agent": "Produktivitetskommissionen.se-skordare"}) as client:
        for doktyp in DOKTYPER:
            print(f"[*] {doktyp}...")
            for query in NYCKELORD:
                sida = 1
                while True:
                    try:
                        traff = sok(client, query, doktyp, from_datum, sida=sida)
                    except Exception:
                        break
                    if not traff:
                        break
                    for rad in traff:
                        obj = normalisera(rad, doktyp)
                        if obj and obj["id"] not in kanda_ids:
                            kanda_ids.add(obj["id"])
                            nya_dokument.append(obj)
                    if len(traff) < 50:
                        break
                    sida += 1
                    if sida > 4:
                        break

        print(f"[*] Hamtar utdrag for {len(nya_dokument)} nya...")
        for i, obj in enumerate(nya_dokument, 1):
            if i % 20 == 0:
                print(f"  ... {i}/{len(nya_dokument)}")
            fulltext = hamta_fulltext(client, obj["id"])
            obj["text_utdrag"] = (fulltext or "")[:800]

    with UTDATA.open("a", encoding="utf-8") as f:
        for obj in nya_dokument:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(f"[OK] Lade till {len(nya_dokument)} nya dokument.")


if __name__ == "__main__":
    main()
