#!/usr/bin/env python3
"""harmonogram_faz.py — czas trwania faz i łańcuch zależności od „teraz” (plan GANTT-CZAS-20261111, Phase 40).

Prototyp (`harmonogram.py` w katalogu planu) przeniesiony tu i dopasowany do gantt.py: wejściem są
dane planów z gantt.py (`przetworz_plan`), nie drugi odczyt plików. Nazwa modułu inna niż `harmonogram.py`
celowo: w `sys.path` programów, które go ładują, może leżeć cudzy `harmonogram.py` i przesłoniłby import.
Kalibracja, osoby, limity wykonawców i ścieżki pochodzą z pliku ustawień (`--ustawienia PLIK`, ustawienia_planu.py).

Wywołuje to gantt.py (`naloz_prognoze`), czyli przy każdym odczycie /plany/gantt.json (pamięć 60 s) —
prognoza liczy się od aktualnej chwili i aktualnych statusów faz, bez zapisywania czegokolwiek w planach.

Użycie (CLI, podgląd):
  harmonogram_faz.py [--dzis 'RRRR-MM-DD GG:MM'] [--zapisz PLIK.json]
  harmonogram_faz.py --zbuduj-szacunki     zapis szacunki-czasu.json (wstępne) — NIE nadpisuje szacunki-reczne.json

Zasady modelu:
  * czas fazy = praca_h + czeka_h (kalendarzowo; czeka_h = oczekiwanie na człowieka lub recenzję, nie zajmuje wykonawcy),
  * `szacunki-reczne.json` (klucz „PLAN_ID:nr”) wygrywa z `szacunki-czasu.json`; faza bez żadnego wpisu dostaje szacunek
    z klasy planu i wykonawcy (jak `--zbuduj-szacunki`, po samym tytule), oznaczony zrodlo „auto”,
  * faza complete nie wchodzi; in_progress: start rzeczywisty, koniec = max(start + czas, teraz + 15 min),
  * pending: start = max(teraz, koniec poprzedniej otwartej fazy planu, koniec zależności międzyplanowych z bloku potok-v2
    specyfikacji, wolny wykonawca (sloty z ustawienia `limit_wykonawcy`; ludzie bez limitu),
  * trzy warianty (optymistyczny / oczekiwany / pesymistyczny) = ta sama struktura, czasy mnożone (MNOZNIK).
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta

SK = os.path.dirname(os.path.abspath(__file__))
if SK not in sys.path:
    sys.path.insert(0, SK)
import ustawienia_planu  # noqa: E402

if __name__ == "__main__":
    ustawienia_planu.ustaw_z_argv(sys.argv)  # `--ustawienia PLIK` przed odczytem stałych poniżej
_UST = ustawienia_planu.wczytaj()

# JEDNO miejsce ścieżek szacunków (karta t_3bc6ac12 (a)): właściciele faz poprawiają szacunki w katalogu z ustawienia
# `szacunki_katalog`; bez niego prognoza liczy szacunki z kalibracji (źródło „auto”), a pliki szacunków nie są czytane ani pisane.
KAT_SZACUNKI = _UST["szacunki_katalog"]
PLIK_SZAC = os.path.join(KAT_SZACUNKI, "szacunki-czasu.json") if KAT_SZACUNKI else None
PLIK_REKA = os.path.join(KAT_SZACUNKI, "szacunki-reczne.json") if KAT_SZACUNKI else None
SPEC = _UST["spec_potoku"]
FMT = "%Y-%m-%d %H:%M"

# Kalibracja (np. z faz complete): średnia obcięta do p90, godziny kalendarzowe. Ustawienie `kalibracja`:
# "klasa planu|wykonawca" -> (praca_h = zajęcie wykonawcy, czas_h = czas kalendarzowy fazy, p50 kal., p80 kal.)
KAL = {tuple(k.split("|", 1)): tuple(v) for k, v in _UST["kalibracja"].items()}
DOMYSLNA = tuple(_UST["kalibracja_domyslna"])
CZEKA = dict(_UST["czeka_h"])    # godziny kalendarzowo oczekiwania na odpowiedź osoby
LIMIT = dict(_UST["limit_wykonawcy"])
MNOZNIK = {"optymistyczny": 0.35, "oczekiwany": 1.0, "pesymistyczny": 2.2}   # p50/średnia ≈ 0,35; p80/średnia ≈ 2,2–2,8
WARIANT_DOMYSLNY = "oczekiwany"
LUDZIE = set(_UST["ludzie"])


def klasa_planu(plan):
    for wyrazenie, klasa in _UST["klasy_planow"]:
        if re.match(wyrazenie, plan):
            return klasa
    return "inne"


def szac_wstepne(plan, wyk, tekst):
    """Szacunek wstępny fazy z klasy planu i wykonawcy (tekst = tytuł [+ „gotowe, gdy” i blokady, gdy są])."""
    kl, tekst = klasa_planu(plan), (tekst or "").lower()
    if wyk in LUDZIE:
        return {"praca_h": 0.0, "czas_h": 0.0, "czeka_h": CZEKA.get(wyk, 0.0), "czeka_na": wyk, "pewnosc": "niska",
                "zrodlo": _UST["opis_czeka_czlowiek"]}
    rec = _UST["recenzent"]
    if rec and (wyk == rec["wykonawca"] or rec["fraza"] in tekst):
        return {"praca_h": 0.0, "czas_h": CZEKA.get(rec["klucz"], 0.0), "czeka_h": 0.0, "czeka_na": rec["klucz"],
                "pewnosc": "średnia", "zrodlo": _UST["opis_czeka_recenzent"]}
    praca, czas, p50, p80 = KAL.get((kl, wyk), DOMYSLNA)
    czeka_na, czeka = "", 0.0
    for wyrazenie, osoba in _UST["czekanie_w_tekscie"]:
        if re.search(wyrazenie, tekst):
            czeka_na, czeka = osoba, CZEKA.get(osoba, 0.0)
            break
    return {"praca_h": praca, "czas_h": max(czas, praca), "czeka_h": czeka, "czeka_na": czeka_na, "pewnosc": "niska",
            "p50_h": p50, "p80_h": p80, "zrodlo": "kalibracja faz complete: %s/%s" % (kl, wyk or "?")}


# ---------------------------------------------------------------- potok SPEC-GT (zależności między planami)
def potok(spec=SPEC):
    """({rozdział: {kolejnosc, plan, zalezy}}, {rozdział: plan}) z tabeli potok-v2; brak pliku/znaczników = puste."""
    if not spec:
        return {}, {}
    try:
        t = open(spec, encoding="utf-8").read()
        a, b = t.index("<!-- potok-v2:poczatek -->"), t.index("<!-- potok-v2:koniec -->")
    except (OSError, ValueError):
        return {}, {}
    out, rz2plan = {}, {}
    for l in t[a:b].splitlines():
        k = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(k) >= 5 and k[0].isdigit():
            out[k[1]] = {"kolejnosc": int(k[0]), "plan": k[3], "zalezy": k[4]}
            rz2plan[k[1]] = k[3]
    return out, rz2plan


def wczytaj_json(plik):
    if not plik:
        return {}
    try:
        with open(plik, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


# ---------------------------------------------------------------- wejście z gantt.py
def plany_z_gantt(lista):
    """{plan: {projekt, fazy: [{id, nr, tytul, status, wyk, start_real}]}} z danych gantt.py (`przetworz_plan`)."""
    wyn = {}
    for d in lista:
        m = re.match(_UST["projekt_regex"], d.get("sciezka", "") + "/")
        fz = []
        for t in d["data"][1:]:
            sr = t.get("start_real")
            try:
                sr = datetime.fromisoformat(sr) if sr else None
            except ValueError:
                sr = None
            fz.append({"id": t["id"], "nr": t["nr"], "tytul": t.get("tytul", ""), "status": t["status"],
                       "wyk": t.get("wykonawca_klucz") or "", "start_real": sr})
        wyn[d["plan"]] = {"projekt": m.group(1) if m else _UST["projekt_domyslny_prognoza"], "fazy": fz}
    return wyn


def szacunek(plan, f, szac, reka):
    """(szacunek fazy, znacznik: reczne|wstepne|auto)."""
    k = "%s:%s" % (plan, f["nr"])
    s, zn = dict(szac.get(k) or {}), "wstepne" if k in szac else "auto"
    if not s:
        s = szac_wstepne(plan, f["wyk"], f["tytul"])
        s["zrodlo"] = "auto (brak wpisu w szacunki-czasu.json): " + s.get("zrodlo", "")
    if k in reka:
        s.update(reka[k])
        zn = "reczne"
    return s, zn


# ---------------------------------------------------------------- harmonogram
def licz(plany, szac, reka, teraz, mn, pot=None):
    """Harmonogram jednego wariantu. -> (wezly, start, koniec, cykle, szacunki)."""
    pot, rz2plan = pot if pot is not None else potok()
    nr_plan = {v["plan"]: v["kolejnosc"] for v in pot.values()}
    dep_plan, dep_faza = {}, {}
    for v in pot.values():
        pl = v["plan"]
        for ref in re.findall(r"§?\d{3}(?:\.\d{2})?", v["zalezy"]):
            r3 = ref.lstrip("§")[:3]
            if r3 not in rz2plan or rz2plan[r3] == pl or rz2plan[r3] == "—":
                continue
            if "." in ref:
                dep_faza.setdefault(pl, set()).add((rz2plan[r3], str(int(ref.split(".")[1]))))
            else:
                dep_plan.setdefault(pl, set()).add(rz2plan[r3])
    wezly, szacunki, pierwsza, ostatnia, po_nr = {}, {}, {}, {}, {}
    for plan, d in plany.items():
        pop = None
        for poz, f in enumerate(d["fazy"]):
            if f["status"] == "complete":
                continue
            k = f["id"]
            wezly[k] = {"plan": plan, "nr": f["nr"], "poz": poz, "wyk": f["wyk"], "status": f["status"],
                        "poprz": [pop] if pop else [], "start_real": f["start_real"]}
            szacunki[k] = szacunek(plan, f, szac, reka)
            pierwsza.setdefault(plan, k)
            po_nr.setdefault((plan, f["nr"]), k)
            ostatnia[plan] = k
            pop = k
    for plan, k in pierwsza.items():   # pierwsza otwarta faza planu czeka na plany i fazy, od których plan zależy
        for q in sorted(dep_plan.get(plan, ())):
            if q in ostatnia and ostatnia[q] not in wezly[k]["poprz"]:
                wezly[k]["poprz"].append(ostatnia[q])
        for (q, nr) in sorted(dep_faza.get(plan, ())):
            kk = po_nr.get((q, nr))
            if kk and kk not in wezly[k]["poprz"]:
                wezly[k]["poprz"].append(kk)

    def kol(k):
        w = wezly[k]
        return (0 if w["status"] == "in_progress" else 1, nr_plan.get(w["plan"], 500), w["plan"], w["poz"])

    wolny, koniec, start = {}, {}, {}
    pozostale, cykl = set(wezly), 0
    while pozostale:
        kand = [k for k in pozostale if all(p in koniec for p in wezly[k]["poprz"])]
        if not kand:   # cykl zależności — zerwij krawędzie najstarszej fazy
            cykl += 1
            k0 = min(pozostale, key=kol)
            wezly[k0]["poprz"] = [p for p in wezly[k0]["poprz"] if p in koniec]
            continue
        k = min(kand, key=kol)
        w, s = wezly[k], szacunki[k][0]
        pozostale.discard(k)
        czeka, praca = s.get("czeka_h", 0.0) * mn, s.get("praca_h", 0.0) * mn
        czk = max(s.get("czas_h", 0.0), s.get("praca_h", 0.0)) * mn
        h = czeka + czk
        pocz = max([teraz] + [koniec[p] for p in w["poprz"]])
        wyk = w["wyk"]
        zasob = bool(wyk) and wyk not in LUDZIE
        sl = wolny.setdefault(wyk, [teraz] * LIMIT.get(wyk, 1)) if zasob else []
        sl.sort()
        trwa, sr = w["status"] == "in_progress", w["start_real"]
        if trwa and isinstance(sr, datetime):
            pocz = pr0 = min(sr, teraz)
        else:
            pr0 = pocz + timedelta(hours=czeka)   # oczekiwanie na człowieka przed pracą — zasobu nie zajmuje
            if zasob:
                pr0 = max(pr0, sl[0])
                pocz = max(pocz, pr0 - timedelta(hours=czeka))
        kon = max(pocz + timedelta(hours=h), pr0 + timedelta(hours=czk))
        if trwa:
            kon = max(kon, teraz + timedelta(minutes=15))
        if zasob:
            sl[0] = max(sl[0], pr0 + timedelta(hours=praca))
        start[k], koniec[k] = pocz, kon
    return wezly, start, koniec, cykl, szacunki


def prognoza(lista_gantt, teraz, szac=None, reka=None):
    """Prognoza trzech wariantów dla wszystkich otwartych faz.

    -> {"teraz", "warianty": {nazwa: {mnoznik, cykle_zerwane, koniec_projektu, koniec_planu, fazy: {id: {start, koniec, h, wyk, po}}}},
        "szacunki": {id: {...szacunek, znacznik}}}
    `po` = poprzednicy fazy (id faz, także z innych planów). Nic nie jest zapisywane."""
    szac = wczytaj_json(PLIK_SZAC) if szac is None else szac
    reka = wczytaj_json(PLIK_REKA) if reka is None else reka
    plany = plany_z_gantt(lista_gantt)
    pot = potok()
    out = {"teraz": teraz.strftime(FMT), "warianty": {}, "szacunki": {}}
    for nazwa, mn in MNOZNIK.items():
        wezly, st, ko, cykl, szk = licz(plany, szac, reka, teraz, mn, pot)
        per_proj, per_plan = {}, {}
        for k, w in wezly.items():
            pr = plany[w["plan"]]["projekt"]
            per_proj[pr] = max(per_proj.get(pr, teraz), ko[k])
            per_plan[w["plan"]] = max(per_plan.get(w["plan"], teraz), ko[k])
        out["warianty"][nazwa] = {
            "mnoznik": mn, "cykle_zerwane": cykl,
            "koniec_projektu": {p: t.strftime(FMT) for p, t in per_proj.items()},
            "koniec_planu": {p: t.strftime(FMT) for p, t in per_plan.items()},
            "fazy": {k: {"start": st[k].strftime(FMT), "koniec": ko[k].strftime(FMT),
                         "h": round((ko[k] - st[k]).total_seconds() / 3600, 2), "wyk": wezly[k]["wyk"], "po": wezly[k]["poprz"]}
                     for k in wezly}}
        if nazwa == WARIANT_DOMYSLNY:
            out["szacunki"] = {k: dict(v[0], znacznik=v[1]) for k, v in szk.items()}
    return out


# ---------------------------------------------------------------- budowa szacunków wstępnych i CLI
def zbuduj_szacunki():
    """Szacunki wstępne wszystkich otwartych faz (z tytułu, „gotowe, gdy” i blokad) → PLIK_SZAC. Ręcznych nie rusza."""
    import fazy_planu
    import gantt
    kolory = gantt.wczytaj_kolory()
    out = {}
    if not PLIK_SZAC:
        raise SystemExit("brak ustawienia `szacunki_katalog` — nie ma gdzie zapisać szacunków")
    for d in sorted(p for wz in _UST["wzorce_planow"] for p in glob.glob(wz)):
        p = os.path.join(d, "task_plan.md")
        if not os.path.exists(p):
            continue
        try:
            fz = fazy_planu.parsuj_plan(fazy_planu.czytaj_linie(p))
        except Exception:
            continue
        plan = d.rstrip("/").split("/")[-1]
        for f in fz:
            if f.get("status_norm") == "complete":
                continue
            pola = f.get("pola") or {}
            tekst = " ".join([f.get("tytul", "")] + [str(pola.get(k, "")) for k in ("gotowe, gdy", "blokady")])
            wyk = gantt.klucz_wykonawcy(f.get("wykonawca") or "", kolory) or ""
            out["%s:%s" % (plan, f["nr"])] = {"tytul": f["tytul"][:90], "wykonawca": wyk, "status": f["status_norm"],
                                              **szac_wstepne(plan, wyk, tekst)}
    json.dump(out, open(PLIK_SZAC, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("szacunki wstępne:", len(out), "faz →", PLIK_SZAC)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zbuduj-szacunki", action="store_true")
    ap.add_argument("--dzis", help="RRRR-MM-DD GG:MM (domyślnie: teraz)")
    ap.add_argument("--zapisz", help="zapis pełnej prognozy do pliku JSON")
    a = ap.parse_args(argv)
    if a.zbuduj_szacunki:
        return zbuduj_szacunki()
    import gantt
    teraz = datetime.strptime(a.dzis, FMT) if a.dzis else gantt.teraz()
    lista = [gantt.przetworz_plan(k) for k in gantt.znajdz_plany()
             if os.path.isfile(os.path.join(k, "task_plan.md")) and not os.path.basename(k).startswith("PRZYKLAD-")]
    pr = prognoza(lista, teraz)
    if a.zapisz:
        json.dump(pr, open(a.zapisz, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    o = pr["warianty"][WARIANT_DOMYSLNY]
    print("teraz:", pr["teraz"], "| faz otwartych:", len(o["fazy"]), "| zerwane cykle:", o["cykle_zerwane"])
    for p in sorted(o["koniec_projektu"], key=lambda x: o["koniec_projektu"][x]):
        print("  %-16s koniec: opt %s | oczekiwany %s | pes %s" % (
            p, pr["warianty"]["optymistyczny"]["koniec_projektu"].get(p, "-")[:10], o["koniec_projektu"][p][:10],
            pr["warianty"]["pesymistyczny"]["koniec_projektu"].get(p, "-")[:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
