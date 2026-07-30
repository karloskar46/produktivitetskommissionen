"""classify.py - matchar skordat material mot forslagen med Gemini AI."""
from __future__ import annotations
import json, os, re, sys, time
from datetime import date
from pathlib import Path
import httpx

PROPOSALS_FIL = Path("data/proposals.json")
KALLOR = [Path("data/sources/riksdagen.jsonl"),
          Path("data/sources/regeringen.jsonl"),
          Path("data/sources/statsliggaren.jsonl")]
KLASS_CACHE = Path("data/classified.json")
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

STOPPORD = {"och", "eller", "att", "för", "till", "med", "av", "på", "i",
            "en", "ett", "det", "den", "som", "är", "har", "kan", "ska",
            "bör", "vid", "från", "om", "de", "inte", "över", "mellan",
            "detta", "denna", "sin", "sitt", "sina"}

DELVIS_TYPER = {"dir", "direktiv"}

PROMPT_MALL = """Du bedomer om ett svenskt politiskt dokument beror specifika forslag fran Produktivitetskommissionen (SOU 2024:29 och SOU 2025:96).

DOKUMENT
Typ: {typ}
Titel: {titel}
Datum: {datum}
Utdrag: {utdrag}

KANDIDATFORSLAG (numrerade)
{kandidater}

INSTRUKTIONER
For varje kandidatforslag, bedom relationen till dokumentet:
- "genomfor"   - Dokumentet ar ett beslut som faktiskt genomfor forslaget (endast tillatet for dokumenttyper: proposition, utskottsbetankande, SFS, regeringsbeslut, regleringsbrev, myndighetsinstruktion, lagradsremiss)
- "delvis"     - Delvis eller pa vag (kommittedirektiv, utredning tillsatt, delvis reform)
- "namner"     - Dokumentet handlar om samma sak men ar inte ett beslut (motion, debatt, anforande, interpellation)
- "avvisar"    - Dokumentet avvisar eller motverkar forslaget aktivt
- "ingen"      - Ingen tydlig koppling

VIKTIGT: "genomfor" och "delvis" far ENDAST anvandas for dokumenttyper som ar beslut. En motion eller ett anforande kan aldrig genomfora ett forslag.

Svara ENBART med giltig JSON pa formen:
{{
  "matchningar": [
    {{"forslag_id": "D4", "relation": "namner", "motivering": "Kort mening."}}
  ]
}}
Utelamna kandidater med relation "ingen"."""


def las_proposals():
    return json.loads(PROPOSALS_FIL.read_text(encoding="utf-8"))


def spara_proposals(props):
    PROPOSALS_FIL.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")


def las_kallor():
    alla = []
    for fil in KALLOR:
        if not fil.exists():
            continue
        with fil.open(encoding="utf-8") as f:
            for rad in f:
                try:
                    alla.append(json.loads(rad))
                except json.JSONDecodeError:
                    continue
    return alla


def las_klassificerat():
    if not KLASS_CACHE.exists():
        return set()
    try:
        return set(json.loads(KLASS_CACHE.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return set()


def spara_klassificerat(ids):
    KLASS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    KLASS_CACHE.write_text(json.dumps(sorted(ids), ensure_ascii=False), encoding="utf-8")


def tokenisera(text):
    tokens = re.findall(r"\b[a-zåäö]{4,}\b", (text or "").lower())
    return {t for t in tokens if t not in STOPPORD}


def hitta_kandidater(kalla, proposals, n=8):
    kalla_tokens = tokenisera(f"{kalla.get('titel','')} {kalla.get('text_utdrag','')} {kalla.get('beskrivning','')}")
    if not kalla_tokens:
        return []
    scored = []
    for p in proposals:
        p_tokens = tokenisera(f"{p['text']} {p.get('kort','')}")
        if not p_tokens:
            continue
        overlap = len(kalla_tokens & p_tokens)
        if overlap >= 2:
            scored.append((overlap, p))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [p for _, p in scored[:n]]


def anropa_gemini(prompt, api_nyckel):
    time.sleep(8)
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1,
                                "responseMimeType": "application/json"}}
    for forsok in range(3):
        try:
            r = httpx.post(f"{GEMINI_URL}?key={api_nyckel}", json=body, timeout=60)
            if r.status_code == 200:
                text = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    m = re.search(r"\{.*\}", text, re.S)
                    if m:
                        return json.loads(m.group(0))
                    return None
            if r.status_code == 429:
                print(f"    ! 429 svar. Body: {r.text[:500]}", flush=True)
                time.sleep(20 * (forsok + 1))
                continue
            if r.status_code >= 500:
                print(f"    ! Server-fel {r.status_code}, sover 5s", flush=True)
                time.sleep(5)
                continue
            print(f"    ! Ovantad status {r.status_code}: {r.text[:200]}", flush=True)
            return None
        except httpx.RequestError as e:
            print(f"    ! Natfel: {e}", flush=True)
            if forsok == 2:
                return None
            time.sleep(3)
    return None


def berakna_status(kopplingar):
    if not kopplingar:
        return "ej_klassificerat", ""
    genomfor, delvis, namner, avvisar = [], [], [], []
    for k in kopplingar:
        relation = k.get("relation", "")
        kalla_typ = k.get("kalla_typ", "").lower()
        status_klass = k.get("status_klass", "omnamnande")
        if relation == "genomfor":
            if status_klass == "beslut" and kalla_typ not in DELVIS_TYPER:
                genomfor.append(k)
            elif kalla_typ in DELVIS_TYPER:
                delvis.append(k)
            else:
                namner.append(k)
        elif relation == "delvis":
            if status_klass == "beslut":
                delvis.append(k)
            else:
                namner.append(k)
        elif relation == "namner":
            namner.append(k)
        elif relation == "avvisar":
            avvisar.append(k)
    if genomfor:
        e = genomfor[0]
        return "genomfort", f"{e.get('kalla_typ_display', 'Beslut')} {e.get('titel', '')[:80]}"
    if delvis:
        e = delvis[0]
        return "delvis_genomfort", f"{e.get('kalla_typ_display', 'Delvis')} {e.get('titel', '')[:80]}"
    if avvisar and not namner:
        return "ej_genomfort", "Aktivt avvisat i beslutshandlingar."
    if namner:
        return "ej_klassificerat", f"Diskuteras politiskt ({len(namner)} omnamnanden) men inget genomforandebeslut hittat."
    return "ej_klassificerat", ""


def main():
    api_nyckel = os.environ.get("GEMINI_API_KEY")
    if not api_nyckel:
        print("! GEMINI_API_KEY saknas.", file=sys.stderr)
        sys.exit(1)
    proposals = las_proposals()
    kallor = las_kallor()
    redan_klassade = las_klassificerat()
    p_by_id = {p["id"]: p for p in proposals}
    nya_kallor = [k for k in kallor if k["id"] not in redan_klassade]
    print(f"[i] Nya kallor totalt: {len(nya_kallor)}", flush=True)

    MAX = 200
    if len(nya_kallor) > MAX:
        nya_kallor = nya_kallor[:MAX]
        print(f"[i] Bearbetar de forsta {MAX} denna korning", flush=True)

    antal = 0
    tomma_kandidater = 0
    tomma_svar_fran_gemini = 0

    for i, kalla in enumerate(nya_kallor, 1):
        kandidater = hitta_kandidater(kalla, proposals, n=8)

        if not kandidater:
            tomma_kandidater += 1
            redan_klassade.add(kalla["id"])
            if i <= 5:
                print(f"  [{i}] Inga kandidater for '{kalla.get('titel','')[:80]}'", flush=True)
            if i % 5 == 0:
                print(f"  ... {i}/{len(nya_kallor)} ({antal} matchningar, {tomma_kandidater} utan kandidater, {tomma_svar_fran_gemini} tomma Gemini-svar)", flush=True)
            continue

        if i <= 5:
            print(f"  [{i}] '{kalla.get('titel','')[:60]}' -> {len(kandidater)} kandidater", flush=True)

        kand_text = "\n".join(f"{n+1}. [{p['id']}] {p['text'][:220]}" for n, p in enumerate(kandidater))
        prompt = PROMPT_MALL.format(
            typ=kalla.get("typ_display", kalla.get("typ", "")),
            titel=kalla.get("titel", "")[:200],
            datum=kalla.get("publicerad", ""),
            utdrag=(kalla.get("text_utdrag", "") or kalla.get("beskrivning", ""))[:2000],
            kandidater=kand_text)
        svar = anropa_gemini(prompt, api_nyckel)

        if not svar:
            if i <= 5:
                print(f"  [{i}] Inget svar fran Gemini", flush=True)
            continue

        matchningar_i_svar = svar.get("matchningar", [])
        if not matchningar_i_svar:
            tomma_svar_fran_gemini += 1
            if i <= 5:
                print(f"  [{i}] Gemini svarade tomt (inga matchningar)", flush=True)

        for m in matchningar_i_svar:
            fid = m.get("forslag_id", "").strip()
            rel = m.get("relation", "").lower()
            if rel == "ingen" or fid not in p_by_id:
                continue
            koppling = {
                "kalla_id": kalla["id"],
                "kalla_typ": kalla.get("typ", ""),
                "kalla_typ_display": kalla.get("typ_display", ""),
                "status_klass": kalla.get("status_klass", "omnamnande"),
                "titel": kalla.get("titel", ""), "url": kalla.get("url", ""),
                "publicerad": kalla.get("publicerad", ""),
                "partier": kalla.get("partier", []),
                "relation": rel, "motivering": m.get("motivering", "")[:300],
                "tillagd": date.today().isoformat(),
            }
            bef = p_by_id[fid].get("kopplade_kallor", [])
            if not any(b["kalla_id"] == kalla["id"] for b in bef):
                bef.append(koppling)
                p_by_id[fid]["kopplade_kallor"] = bef
                antal += 1

        redan_klassade.add(kalla["id"])

        if i % 5 == 0:
            print(f"  ... {i}/{len(nya_kallor)} ({antal} matchningar, {tomma_kandidater} utan kandidater, {tomma_svar_fran_gemini} tomma Gemini-svar)", flush=True)

    print("[*] Raknar om status...", flush=True)
    for p in proposals:
        status, mot = berakna_status(p.get("kopplade_kallor", []))
        p["status"] = status
        p["status_motivering"] = mot
        p["senast_uppdaterad"] = date.today().isoformat()
    spara_proposals(proposals)
    spara_klassificerat(redan_klassade)
    from collections import Counter
    c = Counter(p["status"] for p in proposals)
    print(f"[OK] {antal} nya matchningar. Sammanfattning:", flush=True)
    print(f"    Utan kandidater: {tomma_kandidater}", flush=True)
    print(f"    Tomma Gemini-svar: {tomma_svar_fran_gemini}", flush=True)
    for s in ("genomfort", "delvis_genomfort", "ej_genomfort", "ej_klassificerat"):
        n = c.get(s, 0)
        print(f"    {s}: {n}", flush=True)


if __name__ == "__main__":
    main()
