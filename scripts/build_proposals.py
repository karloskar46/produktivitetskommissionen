"""build_proposals.py - konverterar Excel-listan till proposals.json."""
from __future__ import annotations
import json, re
from pathlib import Path
import pandas as pd

INDATA = Path("data/kalla/forslag.xlsx")
UTDATA = Path("data/proposals.json")

SOU_URLS = {
    "SOU 2024:29": "https://www.regeringen.se/contentassets/f95ea38d4f914bf6acc8af3ec8b5e7c5/goda-mojligheter-till-okat-valstand-sou-202429/",
    "SOU 2025:96": "https://www.regeringen.se/contentassets/473a81415a454a85b36b0af5c044a96c/fler-mojligheter-till-okat-valstand-sou-202596.pdf",
}

AREA_KEYWORDS = {
    "Finanspolitiskt ramverk": ["riksdagsutskott", "reservationsforbud", "statens budget"],
    "Regelforenkling": ["regelforenkling", "konsekvensutredning", "ESV", "regelverk"],
    "Tillstandsprocesser": ["tillstand", "miljobalk", "provning"],
    "Bostader och byggande": ["bostad", "detaljplan", "bygglov", "hyres", "plan- och bygg"],
    "Transportinfrastruktur": ["trafikverk", "jarnvag", "kalkylranta", "infrastruktur"],
    "Utbildning": ["skola", "gymnas", "laros", "larar", "betyg", "elev"],
    "Skatter": ["skatt", "marginalskatt", "beskatt", "moms"],
    "Kommunsektorn": ["kommun", "statsbidrag", "region"],
    "Policyutveckling och forsoksverksamhet": ["forsoksverksamhet", "sandlada", "kommitte"],
}

AREA_FROM_CHAPTER = {
    "Regelforenkling": "Regelforenkling",
    "Tillstandsprocesser": "Tillstandsprocesser",
    "Bostader och byggande": "Bostader och byggande",
    "Bostadsmarknaden": "Bostader och byggande",
    "Transportinfrastruktur": "Transportinfrastruktur",
    "Utbildning": "Utbildning",
    "Policyutveckling och forsoksverksamhet": "Policyutveckling",
    "Kommunsektorn": "Kommunsektorn",
    "Kommunsektorn mm": "Kommunsektorn",
    "Teknisk utveckling och innovation": "Forskning och innovation",
    "Digitalisering och AI": "Digitalisering och AI",
    "Arbetsmarknad och kompetensforsorjning": "Arbetsmarknad",
    "Kapitalforsorjning": "Kapitalforsorjning",
    "Konkurrens och handel": "Konkurrens och handel",
    "Klimat- och industripolitik": "Klimat och industri",
    "Energiforsorjning": "Energi",
    "Kriminalitet och tillit": "Kriminalitet och tillit",
    "Administration i offentlig sektor": "Offentlig administration",
    "Offentlig upphandling": "Offentlig upphandling",
    "Konkurrens inom valfardssektorn": "Valfardssektorn",
    "Halso- och sjukvard": "Halso- och sjukvard",
}


def clean(v):
    if pd.isna(v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def derive_area(kapitel_namn, text):
    if kapitel_namn and kapitel_namn in AREA_FROM_CHAPTER:
        return AREA_FROM_CHAPTER[kapitel_namn]
    text_low = text.lower()
    for area, kws in AREA_KEYWORDS.items():
        if any(kw.lower() in text_low for kw in kws):
            return area
    return "Ovrigt"


def sou_from_source(kalla):
    return "SOU 2024:29" if "elbet" in kalla.lower() else "SOU 2025:96"


def build():
    df = pd.read_excel(INDATA, sheet_name=0)
    df.columns = [c.strip() for c in df.columns]
    proposals = []
    cols = list(df.columns)
    for _, row in df.iterrows():
        kod = clean(row[cols[1]])
        if not kod:
            continue
        # Anpassa till exakta kolumnnamn i Excel-filen
        typ = clean(row[cols[2]]) if len(cols) > 2 else ""
        kalla = clean(row[cols[3]]) if len(cols) > 3 else ""
        text = clean(row[cols[4]]) if len(cols) > 4 else ""
        kort = clean(row[cols[5]]) if len(cols) > 5 else ""
        kap_nr = clean(row[cols[6]]) if len(cols) > 6 else ""
        kap_namn = clean(row[cols[7]]) if len(cols) > 7 else ""
        avsn = clean(row[cols[8]]) if len(cols) > 8 else ""
        sou = sou_from_source(kalla)
        proposals.append({
            "id": kod, "kalla": kalla, "sou": sou,
            "sou_url": SOU_URLS.get(sou, ""),
            "typ": typ, "text": text, "kort": kort,
            "kapitel_nr": kap_nr, "kapitel_namn": kap_namn,
            "avsnitt": avsn, "omrade": derive_area(kap_namn, text),
            "status": "ej_klassificerat", "status_motivering": "",
            "senast_uppdaterad": None, "kopplade_kallor": [],
        })
    return proposals


def main():
    UTDATA.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if UTDATA.exists():
        for p in json.loads(UTDATA.read_text(encoding="utf-8")):
            existing[p["id"]] = p
    proposals = build()
    for p in proposals:
        if p["id"] in existing:
            prev = existing[p["id"]]
            p["status"] = prev.get("status", p["status"])
            p["status_motivering"] = prev.get("status_motivering", "")
            p["senast_uppdaterad"] = prev.get("senast_uppdaterad")
            p["kopplade_kallor"] = prev.get("kopplade_kallor", [])
    UTDATA.write_text(json.dumps(proposals, ensure_ascii=False, indent=2), encoding="utf-8")
    d = sum(1 for p in proposals if p["id"].startswith("D"))
    s = sum(1 for p in proposals if p["id"].startswith("S"))
    print(f"Skrev {UTDATA} med {len(proposals)} poster (D: {d}, S: {s})")


if __name__ == "__main__":
    main()
