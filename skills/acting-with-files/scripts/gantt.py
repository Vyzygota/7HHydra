#!/usr/bin/env python3
"""gantt.py — fazy planow acting-with-files + daty z Kanbana -> gantt.json i gantt.svg.

Uzycie:
  gantt.py <katalog planu>            zapis gantt.json i gantt.svg w katalogu planu
  gantt.py --wszystkie                katalogi planów z ustawienia `wzorce_planow`
  gantt.py ... --wyjscie KATALOG      zapis poza planami (--wszystkie: KATALOG/<projekt>/<plan>/)
  gantt.py ... --db PLIK              baza Kanbana (domyslnie ustawienie `kanban_db`, tylko odczyt)
  gantt.py ... --ustawienia PLIK      plik ustawien zespolu (ustawienia_planu.py); bez niego: ustawienia obok skryptu
  gantt.py ... --dzis RRRR-MM-DD      stala "dzis" (testy)
  gantt.py ... --prognoza             dodaj prognoze czasu otwartych faz i lancuch zaleznosci (harmonogram_faz.py)

Zasady (karta t_8f20e3b4, plan GANTT-20261029):
  * faza = od `### Phase N: tytul` do NASTEPNEGO `### Phase` (nie do nagłówka `##`);
    liczba faz = liczba linii `^### Phase` (jak `grep -c`), pola fazy czytane tylko sprzed
    pierwszego nagłówka `##` w bloku fazy (sekcje typu `## Korekta` nie podmieniaja pol),
  * parser faz jest WSPOLNY (fazy_planu.py, uzywa go tez centrum/plany.py i sprawdz_dowody.py),
  * daty rzeczywiste: najpierw stemple w planie (`**Start:**` z godzina, `**Koniec:**`, wpisywane
    przez sprawdz_dowody.py przy zmianie statusu), potem karty Kanban fazy (start = min(started_at |
    created_at), koniec = max(completed_at)), a bez kart z linii progress.md `- RRRR-MM-DD ... Phase N`;
    brak daty = null (nigdy zgadywanie),
  * daty planowane: opcjonalne `**Start plan:**` (albo `**Start:**` bez godziny) i `**Termin:**` (RRRR-MM-DD),
  * gantt.json ma te same dane drugi raz w ksztalcie DHTMLX Gantt (klucze `data` i `links`):
    plan = zadanie type "project", fazy = dzieci (`parent`), `progress` 0..1, `start_date`/`end_date`
    ("RRRR-MM-DD GG:MM") ALBO ich brak z `bez_daty: true` + `unscheduled: true` (nigdy null udajacy date),
    `links` typu "0" (finish -> start) z kolejnosci faz,
  * faza nie-complete z terminem w przeszlosci: po_terminie_dni,
  * kolory osob: czytane z opis-wizualny-osobowosci.md (generowany z bazy osób Centrum; pierwsza tabela), nie zaszyte.
Baza Kanbana jest otwierana wylacznie `mode=ro`.
"""
import argparse
import glob
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fazy_planu  # jeden parser faz (wspólny z podglądem planów w konsoli i sprawdz_dowody.py)
import ustawienia_planu  # ścieżki, wzorce planów, projekt ze ścieżki — z pliku ustawień, nie z kodu

if __name__ == "__main__":
    ustawienia_planu.ustaw_z_argv(sys.argv)  # `--ustawienia PLIK` musi być znane przed odczytem stałych poniżej
_UST = ustawienia_planu.wczytaj()

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Warsaw")
except Exception:  # brak tzdata
    TZ = None

DB_DOMYSLNA = _UST["kanban_db"]
KOLORY_PLIK = _UST["kolory_plik"]  # tabela kolorów osób (w naszej instalacji generowana z bazy osób, IP45.6)
WZORCE_PLANOW = list(_UST["wzorce_planow"])
STATUSY = fazy_planu.STATUSY
# nazwy profili/skroty -> klucz osoby z tabeli kolorow (tabela zna osoby, nie profile)
ALIASY = {"antygrawiusz": "geminiusz", "ag": "geminiusz", "imhotepprime": "imhotep"}
KOLOR_REZERWOWY = "#9E9E9E"  # „nikt / zrobione”: stała (nie osoba w bazie osób; IP45.6), nadpisana wierszem „nikt”, jeśli plik go ma

RE_DATA = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
RE_PROGRESS = re.compile(r"^-\s+(\d{4}-\d{2}-\d{2})\b(.*)$")
RE_WZMIANKA = re.compile(r"Phases?\s+(\d+)([a-z]?)(?:\s*[\u2013\u2014-]\s*(\d+))?")


# ---------------------------------------------------------------- pliki
czytaj_linie = fazy_planu.czytaj_linie


def teraz(dzis=None):
    if dzis is not None:
        return datetime(dzis.year, dzis.month, dzis.day, 23, 59)
    return datetime.now(TZ).replace(tzinfo=None) if TZ else datetime.now()


def epoch_lokalnie(ts):
    if ts is None:
        return None
    d = datetime.fromtimestamp(ts, TZ) if TZ else datetime.fromtimestamp(ts)
    return d.replace(tzinfo=None)


def data_lub_none(s):
    m = RE_DATA.search(s or "")
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


# ---------------------------------------------------------------- kolory
def wczytaj_kolory(plik=KOLORY_PLIK):
    """{slowo_nazwy_malymi: '#HEX'} z pierwszej tabeli pliku (kolumna HEX)."""
    kolory = {}
    if not plik:
        return kolory
    try:
        linie = czytaj_linie(plik)
    except OSError:
        return kolory
    idx = None
    w_tabeli = False
    for l in linie:
        if not l.startswith("|"):
            if w_tabeli:
                break  # koniec pierwszej tabeli
            continue
        komorki = [c.strip() for c in l.strip().strip("|").split("|")]
        if idx is None:
            for i, c in enumerate(komorki):
                if "HEX" in c.upper() or c.strip().lower() == "kolor":  # „HEX …” (stary układ) albo „Kolor” (baza osób)
                    idx = i
                    break
            w_tabeli = idx is not None
            continue
        if set("".join(komorki)) <= set("-: "):
            continue  # wiersz |---|---|
        if idx >= len(komorki):
            continue
        m = re.search(r"#[0-9A-Fa-f]{6}", komorki[idx])
        if not m:
            continue
        for slowo in re.findall(r"\w+", komorki[0].lower()):
            kolory.setdefault(slowo, m.group(0).upper())
    return kolory


def klucz_wykonawcy(tekst, kolory):
    """Najwczesniej wymieniona osoba/agent z tabeli kolorow (z ALIASAMI) albo None."""
    if not tekst:
        return None
    t = tekst.lower()
    najlepszy = None
    kandydaci = [k for k in kolory if k not in ("nikt", "zrobione")] + list(ALIASY)
    for k in kandydaci:
        m = re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", t)
        if m and (najlepszy is None or m.start() < najlepszy[0]):
            najlepszy = (m.start(), ALIASY.get(k, k))
    return najlepszy[1] if najlepszy else None


# ---------------------------------------------------------------- task_plan.md
wyciagnij_karty = fazy_planu.wyciagnij_karty
parsuj_plan = fazy_planu.parsuj_plan


# ---------------------------------------------------------------- progress.md
def wpisy_progress(linie):
    """[(data, tekst)] z linii `- RRRR-MM-DD ...`."""
    wynik = []
    for l in linie:
        m = RE_PROGRESS.match(l)
        if m:
            try:
                wynik.append((date.fromisoformat(m.group(1)), m.group(2)))
            except ValueError:
                pass
    return wynik


def daty_z_progress(wpisy, nr):
    """Daty wpisow progress.md wspominajacych `Phase <nr>` (takze zakres `Phase 2-6`)."""
    wynik = []
    for d, tekst in wpisy:
        for m in RE_WZMIANKA.finditer(tekst):
            a, lit, b = m.group(1), m.group(2), m.group(3)
            if b is not None and not lit:
                traf = nr.isdigit() and int(a) <= int(nr) <= int(b)
            else:
                traf = (a + lit) == nr
            if traf:
                wynik.append(d)
                break
    return wynik


# ---------------------------------------------------------------- Kanban (tylko odczyt)
def wczytaj_karty(db, ids):
    """{id: (created, started, completed, status)} dla znalezionych kart; ostrzezenia osobno."""
    if not ids:
        return {}, []
    if not db:
        return {}, []  # instalacja bez Kanbana: fazy bez dat z kart
    if not os.path.exists(db):
        return {}, ["brak bazy Kanbana: " + db]
    try:
        con = sqlite3.connect("file:" + db + "?mode=ro", uri=True, timeout=10)
        try:
            marker = ",".join("?" * len(ids))
            wiersze = con.execute(
                "SELECT id, created_at, started_at, completed_at, status FROM tasks WHERE id IN (%s)" % marker,
                list(ids)).fetchall()
        finally:
            con.close()
    except sqlite3.Error as e:
        return {}, ["blad odczytu Kanbana: %s" % e]
    return {r[0]: r[1:] for r in wiersze}, []


def iso(dt):
    return dt.isoformat(timespec="minutes") if dt is not None else None


def wczytaj_info_kart(db, ids):
    """{id: {status, assignee, powod}} — stan kart do widoku (31.10.2026, plan STANY-KART: jeden stan fazy, rodzaj blokady,
    wykonawca z karty, gdy faza nie ma swojego). powod = ostatni powód blokady (tylko dla blocked), do 200 znaków."""
    if not ids or not db or not os.path.exists(db):
        return {}
    try:
        con = sqlite3.connect("file:" + db + "?mode=ro", uri=True, timeout=10)
        try:
            m = ",".join("?" * len(ids))
            info = {r[0]: {"status": r[1], "assignee": r[2], "powod": None}
                    for r in con.execute("SELECT id, status, assignee FROM tasks WHERE id IN (%s)" % m, list(ids))}
            zabl = [k for k, v in info.items() if v["status"] == "blocked"]
            for k in zabl:
                r = con.execute("SELECT payload FROM task_events WHERE task_id=? AND kind='blocked' ORDER BY id DESC LIMIT 1",
                                (k,)).fetchone()
                try:
                    info[k]["powod"] = (json.loads(r[0] or "{}").get("reason") or "")[:200] if r else None
                except ValueError:
                    pass
        finally:
            con.close()
    except sqlite3.Error:
        return {}
    return info


_POTOK = {}


def potok_projektu(projekt):
    """{rozdział 'NNN' albo plan_id: kolejność} z „Dodatek A. Kolejność budowy” SPEC projektu (blok <!-- potok-v2:… -->,
    31.10.2026, t_50c38b54). Sortowanie „wg potoku” w konsoli = ta mapa, nie numer rozdziału."""
    pliki = sorted(glob.glob(_UST["spec_glob"].format(projekt=projekt), recursive=True))
    znacznik = tuple((x, os.path.getmtime(x)) for x in pliki)  # pamięć ważna, dopóki SPEC się nie zmieni (proces CSW żyje długo)
    if _POTOK.get(projekt, (None,))[0] == znacznik:
        return _POTOK[projekt][1]
    wynik = {}
    for plik in pliki:
        try:
            tekst = open(plik, encoding="utf-8").read()
        except OSError:
            continue
        m = re.search(r"<!-- potok-v2:poczatek -->(.*?)<!-- potok-v2:koniec -->", tekst, re.S)
        if not m:
            continue
        for w in m.group(1).splitlines():
            k = [x.strip() for x in w.strip().strip("|").split("|")]
            if len(k) >= 4 and k[0].isdigit():
                wynik[k[1]] = int(k[0])
                if k[3] not in ("", "—", "-"):
                    wynik[k[3]] = int(k[0])
        break
    _POTOK[projekt] = (znacznik, wynik)
    return wynik


def daty_z_lancucha(faza, karty_db, wpisy):
    """(start, koniec, zrodlo, w_toku, karty_brak) z Kanbana albo progress.md — daty jako datetime albo None."""
    znane = [karty_db[k] for k in faza["karty"] if k in karty_db]
    brak = [k for k in faza["karty"] if k not in karty_db]
    if znane:
        starty = [epoch_lokalnie(c[1] if c[1] is not None else c[0]) for c in znane]
        starty = [s for s in starty if s is not None]
        konce = [epoch_lokalnie(c[2]) for c in znane if c[2] is not None]
        wszystkie = len(konce) == len(znane)
        start = min(starty) if starty else None
        if wszystkie or (faza["status"] == "complete" and konce):
            koniec = max(konce)
        else:
            koniec = None
        return start, koniec, "kanban", (koniec is None and start is not None), brak
    if faza["status"] == "pending":
        return None, None, "brak", False, brak
    dni = daty_z_progress(wpisy, faza["nr"])
    if dni:
        start = datetime.combine(min(dni), datetime.min.time())
        if faza["status"] == "complete":
            koniec = datetime.combine(max(dni), datetime.min.time())
            return start, koniec, "progress.md", False, brak
        return start, None, "progress.md", True, brak
    return None, None, "brak", False, brak


def daty_rzeczywiste(faza, karty_db, wpisy):
    """(start, koniec, zrodlo, w_toku, karty_brak, zrodlo_start, zrodlo_koniec).

    Stempel w planie (`**Start:**` z godzina, `**Koniec:**`) wygrywa z Kanbanem i progress.md; kazdy koniec
    liczony osobno. `**Koniec:**` liczy sie tylko przy statusie complete (cofnieta faza nie ma konca).
    """
    start, koniec, zrodlo, _w_toku, brak = daty_z_lancucha(faza, karty_db, wpisy)
    zr_start = zrodlo if start is not None else None
    zr_koniec = zrodlo if koniec is not None else None
    if faza["start_stempel"] is not None:
        start, zr_start = faza["start_stempel"], "stempel"
    if faza["status"] == "complete":
        if faza["koniec_stempel"] is not None:
            koniec, zr_koniec = faza["koniec_stempel"], "stempel"
        elif faza["koniec_data"] is not None:
            koniec, zr_koniec = datetime.combine(faza["koniec_data"], datetime.min.time()), "stempel"
    if zr_start == "stempel" or (zr_start is None and zr_koniec == "stempel"):
        zrodlo = "stempel"  # sam Koniec ze stempla = faza zamknieta bez widzianego startu
    w_toku = koniec is None and start is not None
    return start, koniec, zrodlo, w_toku, brak, zr_start, zr_koniec


def tytul_planu(linie, katalog):
    for l in linie:
        if l.startswith("# "):
            t = l[2:].strip()
            return t[5:].strip() if t.lower().startswith("plan:") else t
    return os.path.basename(os.path.normpath(katalog))


def przetworz_plan(katalog, db=DB_DOMYSLNA, dzis=None, kolory=None):
    """Dane planu jako slownik (to, co trafia do gantt.json)."""
    kolory = wczytaj_kolory() if kolory is None else kolory
    dzis_d = dzis or teraz().date()
    tp = os.path.join(katalog, "task_plan.md")
    linie_planu = czytaj_linie(tp)
    fazy = parsuj_plan(linie_planu)
    pp = os.path.join(katalog, "progress.md")
    wpisy = wpisy_progress(czytaj_linie(pp)) if os.path.exists(pp) else []
    ids = sorted({k for f in fazy for k in f["karty"]})
    karty_db, ostrzezenia = wczytaj_karty(db, ids)
    info_kart = wczytaj_info_kart(db, ids)
    ostrzezenia = list(ostrzezenia) + fazy_planu.ostrzezenia_formatu(linie_planu, fazy)
    wyjscie = []
    for f in fazy:
        start, koniec, zrodlo, w_toku, brak, zr_start, zr_koniec = daty_rzeczywiste(f, karty_db, wpisy)
        po = None
        if f["status"] != "complete" and f["termin_plan"] and f["termin_plan"] < dzis_d:
            po = (dzis_d - f["termin_plan"]).days
        klucz = klucz_wykonawcy(f["wykonawca"], kolory)
        wyjscie.append({
            "nr": f["nr"],
            "tytul": f["tytul"],
            "linia": f["linia"],
            "status": f["status"],
            "wykonawca": f["wykonawca"],
            "wykonawca_klucz": klucz,
            "kolor": kolory.get(klucz) if klucz else None,
            "karty": f["karty"],
            "karty_brak_w_bazie": brak,
            "karty_info": [dict(id=k, **info_kart[k]) for k in f["karty"] if k in info_kart],
            "start_plan": f["start_plan"].isoformat() if f["start_plan"] else None,
            "termin_plan": f["termin_plan"].isoformat() if f["termin_plan"] else None,
            "start_real": iso(start),
            "koniec_real": iso(koniec),
            "w_toku": w_toku,
            "zrodlo_dat": zrodlo,
            "zrodlo_start": zr_start,
            "zrodlo_koniec": zr_koniec,
            "po_terminie_dni": po,
        })
        if koniec is not None and start is not None and koniec < start:
            ostrzezenia.append("Phase %s: koniec (%s) wczesniej niz start (%s)" % (f["nr"], iso(koniec), iso(start)))
    wygenerowano = iso(teraz(dzis)) if dzis else iso(teraz())
    dane = {
        "plan": os.path.basename(os.path.normpath(katalog)),
        "tytul": tytul_planu(linie_planu, katalog),
        "sciezka": os.path.normpath(katalog),
        "wygenerowano": wygenerowano,
        "dzis": dzis_d.isoformat(),
        "fazy": wyjscie,
        "ostrzezenia": ostrzezenia,
        "potok": (lambda mapa, nazwa: mapa.get(nazwa) or mapa.get((re.match(r"SPEC-(\d{3})", nazwa, re.I) or [None, None])[1]))(
            potok_projektu(projekt_planu(os.path.normpath(katalog))), os.path.basename(os.path.normpath(katalog))),
        # 31.10.2026 (sortowanie „po czasie” — także ostatnia aktywność): najpóźniejsza zmiana planu albo jego kart
        "aktywnosc": iso(max([datetime.fromtimestamp(os.path.getmtime(x)) for x in (tp, pp) if os.path.exists(x)]
                             + [datetime.fromtimestamp(v) for k in karty_db.values() for v in k[:3] if v],
                             default=None)),
    }
    dane.update(buduj_dhtmlx(dane, [f["nr"] for f in fazy]))
    return dane


# ---------------------------------------------------------------- ksztalt DHTMLX Gantt
def data_dhtmlx(s, koniec=False):
    """ISO (data albo data+godzina) -> 'RRRR-MM-DD GG:MM'; data-koniec = poczatek nastepnego dnia."""
    dt = dt_z_iso(s, koniec)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else None


def buduj_dhtmlx(dane, numery):
    """{'data': [...], 'links': [...]} dla gantt.parse(): plan = project, fazy = dzieci, links typu \"0\".

    Os czasu fazy: daty rzeczywiste (start_real [+ koniec_real; bez konca = do `wygenerowano`]; nie dla
    statusu pending), a gdy ich nie ma, daty planowane (oba: start_plan i termin_plan); faza zamknieta ze sam koncem = kamien milowy
    (type milestone); bez zadnej z tych dat = `bez_daty: true`, `unscheduled: true` i BRAK pol
    start_date/end_date (nigdy null udajacy date).
    """
    plan_id = dane["plan"]
    teraz_dh = data_dhtmlx(dane["wygenerowano"])
    klucze = fazy_planu.klucze_faz([{"nr": n} for n in numery])
    dzieci, linki = [], []
    for f, klucz in zip(dane["fazy"], klucze):
        zadanie = {
            "id": "%s:%s" % (plan_id, klucz),
            "text": "Phase %s: %s" % (f["nr"], f["tytul"]),
            "parent": plan_id,
            "type": "task",
            "progress": {"complete": 1.0, "in_progress": 0.5}.get(f["status"], 0.0),
            "progress_zrodlo": "status",  # konwencja widoku (0 / 0,5 / 1), nie pomiar
        }
        # faza pending nie ma osi rzeczywistej (karta Kanban zalozona != praca zaczeta); dostaje plan albo bez_daty
        sr, kr = (f["start_real"], f["koniec_real"]) if f["status"] != "pending" else (None, None)
        if sr:
            zadanie["start_date"] = data_dhtmlx(sr)
            koniec_dh = data_dhtmlx(kr, koniec=len(kr) == 10) if kr else teraz_dh
            zadanie["end_date"] = max(koniec_dh, zadanie["start_date"])
            zadanie["zrodlo_osi"] = "real"
        elif kr:
            zadanie["type"] = "milestone"
            zadanie["start_date"] = data_dhtmlx(kr, koniec=len(kr) == 10)
            zadanie["zrodlo_osi"] = "koniec"
        elif f["start_plan"] and f["termin_plan"]:
            zadanie["start_date"] = data_dhtmlx(f["start_plan"])
            zadanie["end_date"] = max(data_dhtmlx(f["termin_plan"], koniec=True), zadanie["start_date"])
            zadanie["zrodlo_osi"] = "plan"
        if "start_date" in zadanie:
            zadanie["bez_daty"] = False
        else:
            zadanie["bez_daty"] = True
            zadanie["unscheduled"] = True
            zadanie["zrodlo_osi"] = None
        zadanie.update(f)  # zachowane pola kontraktu (start_plan, termin_plan, start_real, koniec_real, ...)
        dzieci.append(zadanie)
    for i in range(len(dzieci) - 1):
        z, do = dzieci[i], dzieci[i + 1]
        linki.append({"id": "%s:l%d" % (plan_id, i + 1), "source": z["id"], "target": do["id"], "type": "0",
                      "aktywny": not z["bez_daty"] and not do["bez_daty"]})  # widok rysuje tylko aktywne
    daty = [d for d in dzieci if not d["bez_daty"]]
    projekt = {
        "id": plan_id,
        "text": dane.get("tytul") or plan_id,
        "type": "project",
        "parent": 0,
        "open": True,
        "progress": round(sum(1 for f in dane["fazy"] if f["status"] == "complete") / len(dane["fazy"]), 4)
        if dane["fazy"] else 0.0,
    }
    if daty:
        projekt["start_date"] = min(d["start_date"] for d in daty)
        projekt["end_date"] = max(d.get("end_date", d["start_date"]) for d in daty)
        projekt["bez_daty"] = False
    else:
        projekt["bez_daty"] = True
        projekt["unscheduled"] = True
    return {"data": [projekt] + dzieci, "links": linki}


# ---------------------------------------------------------------- prognoza czasu (GANTT-CZAS-20261111, Phase 40)
def _w_dh(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def naloz_prognoze(plany, chwila=None, wariant=None, szac=None, reka=None):
    """Prognoza czasu otwartych faz (harmonogram_faz.py) naniesiona na dane planów (lista wyników `przetworz_plan`).

    Faza pending: start_date/end_date z prognozy, `zrodlo_osi: "prognoza"`, `bez_daty: false`, bez `unscheduled`.
    Faza in_progress: start bez zmian (rzeczywisty), end_date z prognozy, `zrodlo_osi: "prognoza"`.
    Faza complete i kamienie milowe: bez zmian. Pola istniejącego kontraktu (start_real, koniec_real, status…) nietknięte.
    Nowe pola (tylko dodane): faza `prognoza` {wariant, warianty{nazwa: {start, koniec, h}}, praca_h, czeka_h, czeka_na,
    pewnosc, zrodlo, znacznik}; plan `prognoza` {teraz, wariant, koniec{wariant: czas}, cykle_zerwane} i `links_x` (zależności
    MIĘDZY planami, osobno od `links`, bo wskazują fazy innych planów). Daty wariantu wybranego = `wariant`
    (domyślnie oczekiwany); pozostałe warianty tylko w `prognoza.warianty` (widok przełącza je bez nowego zapytania).
    Zmienia przekazane słowniki i zwraca tę samą listę."""
    import harmonogram_faz as hf
    chwila = chwila or teraz()
    wariant = wariant or hf.WARIANT_DOMYSLNY
    pr = hf.prognoza(plany, chwila, szac, reka)
    war, szk = pr["warianty"], pr["szacunki"]
    id2plan = {t["id"]: d["plan"] for d in plany for t in d["data"][1:]}
    for d in plany:
        zad = {t["id"]: t for t in d["data"][1:]}
        for tid, t in zad.items():
            if tid not in war[wariant]["fazy"]:
                continue   # complete / spoza prognozy
            w = war[wariant]["fazy"][tid]
            s = szk.get(tid, {})
            t["prognoza"] = {
                "wariant": wariant,
                "warianty": {n: {"start": war[n]["fazy"][tid]["start"], "koniec": war[n]["fazy"][tid]["koniec"], "h": war[n]["fazy"][tid]["h"]}
                             for n in war},
                "praca_h": s.get("praca_h", 0.0), "czeka_h": s.get("czeka_h", 0.0), "czeka_na": s.get("czeka_na", ""),
                "pewnosc": s.get("pewnosc", ""), "zrodlo": s.get("zrodlo", ""), "znacznik": s.get("znacznik", ""),
            }
            if t["status"] != "in_progress" or not t.get("start_real"):
                t["start_date"] = w["start"]
            t["end_date"] = max(w["koniec"], t["start_date"])
            t["zrodlo_osi"] = "prognoza"
            t["bez_daty"] = False
            t.pop("unscheduled", None)
        # wiersz planu: zakres z faz z datą (jak buduj_dhtmlx)
        proj = d["data"][0]
        daty = [t for t in d["data"][1:] if not t.get("bez_daty")]
        if daty:
            proj["start_date"] = min(t["start_date"] for t in daty)
            proj["end_date"] = max(t.get("end_date", t["start_date"]) for t in daty)
            proj["bez_daty"] = False
            proj.pop("unscheduled", None)
        for l in d["links"]:   # strzałka następstwa fazy w planie jest aktywna, gdy obie fazy mają daty
            l["aktywny"] = not zad[l["source"]]["bez_daty"] and not zad[l["target"]]["bez_daty"]
        lx = []
        for tid in zad:
            f = war[wariant]["fazy"].get(tid)
            for i, src in enumerate((f or {}).get("po", [])):
                if id2plan.get(src) not in (None, d["plan"]):
                    lx.append({"id": "%s:x%d" % (tid, i), "source": src, "target": tid, "type": "0", "aktywny": True, "miedzyplanowy": True})
        d["links_x"] = lx
        d["prognoza"] = {"teraz": pr["teraz"], "wariant": wariant, "cykle_zerwane": war[wariant]["cykle_zerwane"],
                         "koniec": {n: war[n]["koniec_planu"].get(d["plan"]) for n in war}}
    return plany


def przytnij_odnosniki(plany):
    """Usuwa `links_x` wskazujące plany spoza listy (np. ukryte prywatne): nic o nich nie wycieka do widoku."""
    znane = {t["id"] for d in plany for t in d["data"][1:]}
    for d in plany:
        d["links_x"] = [l for l in d.get("links_x", []) if l["source"] in znane]
    return plany


# ---------------------------------------------------------------- SVG
def dt_z_iso(s, koniec=False):
    """ISO (data albo data+godzina) -> datetime; data-koniec liczy sie do konca dnia."""
    if s is None:
        return None
    if len(s) == 10:
        d = datetime.fromisoformat(s)
        return d + timedelta(days=1) if koniec else d
    return datetime.fromisoformat(s)


def skroc(s, n):
    s = s or ""
    return s if len(s) <= n else s[: n - 1].rstrip() + "\u2026"


def rysuj_svg(dane, kolory=None):
    kolory = wczytaj_kolory() if kolory is None else kolory
    szary = kolory.get("nikt", KOLOR_REZERWOWY)
    fazy = dane["fazy"]
    dzis = datetime.fromisoformat(dane["wygenerowano"]) if dane.get("wygenerowano") else teraz()

    punkty = [dzis]
    for f in fazy:
        for k, koniec in (("start_plan", False), ("termin_plan", True), ("start_real", False), ("koniec_real", True)):
            v = dt_z_iso(f[k], koniec) if f[k] else None
            if v:
                punkty.append(v)
    t0 = min(punkty).replace(hour=0, minute=0) - timedelta(days=1)
    t1 = max(punkty).replace(hour=0, minute=0) + timedelta(days=2)
    if (t1 - t0).days < 7:
        t1 = t0 + timedelta(days=7)
    rozpietosc = (t1 - t0).total_seconds()

    W, lewa, prawa = 1040, 340, 24
    wykres_w = W - lewa - prawa
    gora, wiersz, dol = 64, 38, 74
    H = gora + wiersz * max(len(fazy), 1) + dol

    def X(dt):
        return lewa + (dt - t0).total_seconds() / rozpietosc * wykres_w

    o = []
    a = o.append
    a('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" '
      'aria-label="Gantt: %s">' % (W, H, W, H, escape(dane["plan"], {'"': "&quot;"})))
    a("<style>"
      "@media (prefers-color-scheme: dark){svg{--gantt-tlo:#e6e6e6}}"
      "svg{color:var(--foreground,var(--gantt-tlo,#222))}"
      "svg{font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;font-size:12px}"
      ".t{fill:var(--foreground,var(--gantt-tlo,#222))}"
      ".s{stroke:var(--foreground,var(--gantt-tlo,#222))}"
      ".m{opacity:.55}.siatka{opacity:.14}.tytul{font-size:15px;font-weight:600}"
      "</style>")
    a('<text class="t tytul" x="%d" y="22">%s</text>' % (10, escape(dane["plan"])))
    a('<text class="t m" x="10" y="40">%s \u00b7 stan na %s \u00b7 dane: task_plan.md, progress.md, Kanban</text>'
      % (escape(str(len(fazy)) + " faz"), escape(dane["wygenerowano"][:16].replace("T", " "))))

    # oś: kreski
    dni = (t1 - t0).days
    krok = next((k for k in (1, 2, 7, 14, 30, 60, 90) if dni / k <= 14), 90)
    d = t0
    while d <= t1:
        x = X(d)
        a('<line class="s siatka" x1="%.1f" y1="%d" x2="%.1f" y2="%d"/>' % (x, gora - 6, x, gora + wiersz * len(fazy)))
        a('<text class="t m" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (x, gora - 12, d.strftime("%m-%d")))
        d += timedelta(days=krok)

    for i, f in enumerate(fazy):
        y = gora + i * wiersz
        kol = f.get("kolor")
        if f["status"] == "complete":
            kolor_paska, krycie = szary, "1"
        elif f["status"] == "in_progress":
            kolor_paska, krycie = kol or "currentColor", "1"
        else:
            kolor_paska, krycie = kol or "currentColor", "0.3"
        # etykieta
        a('<rect x="10" y="%d" width="8" height="%d" fill="%s" rx="2"/>' % (y + 6, wiersz - 14, kol or szary))
        a('<text class="t" x="26" y="%d">Phase %s: %s</text>'
          % (y + 17, escape(f["nr"]), escape(skroc(f["tytul"], 44))))
        meta = "%s \u00b7 %s" % (f["wykonawca_klucz"] or skroc(f["wykonawca"] or "?", 16), f["status"])
        if f["po_terminie_dni"] is not None:
            meta += " \u00b7 po terminie +%dd" % f["po_terminie_dni"]
        a('<text class="t m" x="26" y="%d">%s</text>' % (y + 31, escape(meta)))

        # pasek planowany (obrys)
        sp, tp = dt_z_iso(f["start_plan"]), dt_z_iso(f["termin_plan"], True)
        if sp and tp and tp > sp:
            a('<rect class="pasek-plan" x="%.1f" y="%d" width="%.1f" height="9" rx="2" fill="none" stroke="%s" '
              'stroke-width="1.5"><title>plan %s \u2192 %s</title></rect>'
              % (X(sp), y + 6, max(X(tp) - X(sp), 2), kolor_paska, f["start_plan"], f["termin_plan"]))
        elif sp or tp:
            xp = X(sp or tp)
            a('<line class="pasek-plan" x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="%s" stroke-width="1.5">'
              '<title>plan: %s</title></line>' % (xp, y + 4, xp, y + 17, kolor_paska, f["start_plan"] or f["termin_plan"]))

        # pasek rzeczywisty (wypełnienie)
        sr = dt_z_iso(f["start_real"])
        kr = dt_z_iso(f["koniec_real"], koniec=len(f["koniec_real"] or "") == 10)
        if sr:
            otwarty = kr is None
            do = kr or dzis
            szer = max(X(do) - X(sr), 4)
            a('<rect class="pasek-real" x="%.1f" y="%d" width="%.1f" height="11" rx="2" fill="%s" '
              'fill-opacity="%s"%s><title>%s \u2192 %s (%s)</title></rect>'
              % (X(sr), y + 19, szer, kolor_paska, krycie,
                 ' stroke="%s" stroke-dasharray="3 2"' % kolor_paska if otwarty else "",
                 f["start_real"], f["koniec_real"] or "w toku", f["zrodlo_dat"]))
        elif f["status"] != "pending":
            a('<line class="brak-dat s" x1="%d" y1="%d" x2="%d" y2="%d" stroke-width="1.5" '
              'stroke-dasharray="5 4" opacity=".45"><title>brak dat rzeczywistych</title></line>'
              % (lewa, y + 25, lewa + wykres_w, y + 25))
            a('<text class="t m" x="%d" y="%d">brak dat</text>' % (lewa + 6, y + 22))
        a('<line class="s siatka" x1="10" y1="%d" x2="%d" y2="%d"/>' % (y + wiersz, W - prawa, y + wiersz))

    # dziś
    xd = X(dzis)
    a('<line class="s dzis" x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke-dasharray="2 3" stroke-width="1.5"/>'
      % (xd, gora - 6, xd, gora + wiersz * len(fazy)))
    a('<text class="t" x="%.1f" y="%d" text-anchor="middle">dzi\u015b</text>' % (xd, gora + wiersz * len(fazy) + 14))

    # legenda
    ly = gora + wiersz * len(fazy) + 30
    a('<rect x="10" y="%d" width="22" height="10" fill="%s"/>' % (ly, szary))
    a('<text class="t" x="38" y="%d">zrobione (szary = \u201enikt / zrobione\u201d)</text>' % (ly + 9))
    a('<rect x="250" y="%d" width="22" height="10" fill="currentColor"/>' % ly)
    a('<text class="t" x="278" y="%d">w toku (kolor wykonawcy)</text>' % (ly + 9))
    a('<rect x="448" y="%d" width="22" height="10" fill="currentColor" fill-opacity=".3"/>' % ly)
    a('<text class="t" x="476" y="%d">nie zacz\u0119te</text>' % (ly + 9))
    a('<rect x="570" y="%d" width="22" height="10" fill="none" class="s" stroke-width="1.5"/>' % ly)
    a('<text class="t" x="598" y="%d">plan (obrys)</text>' % (ly + 9))
    a('<line class="s" x1="700" y1="%d" x2="730" y2="%d" stroke-dasharray="5 4" stroke-width="1.5"/>' % (ly + 5, ly + 5))
    a('<text class="t" x="738" y="%d">brak dat (\u201enie wiem\u201d)</text>' % (ly + 9))
    wyk = []
    for f in fazy:
        if f["wykonawca_klucz"] and f["kolor"] and f["wykonawca_klucz"] not in [w[0] for w in wyk]:
            wyk.append((f["wykonawca_klucz"], f["kolor"]))
    x = 10
    for nazwa, kol in wyk:
        a('<rect x="%d" y="%d" width="8" height="10" rx="2" fill="%s"/>' % (x, ly + 22, kol))
        a('<text class="t" x="%d" y="%d">%s</text>' % (x + 13, ly + 31, escape(nazwa)))
        x += 24 + 7 * len(nazwa)
    a("</svg>")
    return "\n".join(o) + "\n"


# ---------------------------------------------------------------- zapis i CLI
def zapisz(dane, katalog_wyjscia, kolory):
    os.makedirs(katalog_wyjscia, exist_ok=True)
    for nazwa, tresc in (("gantt.json", json.dumps(dane, ensure_ascii=False, indent=2) + "\n"),
                         ("gantt.svg", rysuj_svg(dane, kolory))):
        cel = os.path.join(katalog_wyjscia, nazwa)
        tmp = cel + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(tresc)
        os.replace(tmp, cel)


def znajdz_plany():
    wynik = []
    for wz in WZORCE_PLANOW:
        for k in sorted(glob.glob(wz)):
            wynik.append(k.rstrip("/"))
    return wynik


def projekt_planu(sciezka):
    return ustawienia_planu.projekt_z_planu(sciezka, _UST)


def grep_c(plik):
    p = subprocess.run(["grep", "-c", "^### Phase", plik], capture_output=True, text=True)
    return int(p.stdout.strip() or 0)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", nargs="?", help="katalog planu (z task_plan.md)")
    ap.add_argument("--wszystkie", action="store_true")
    ap.add_argument("--wyjscie")
    ap.add_argument("--db", default=DB_DOMYSLNA)
    ap.add_argument("--dzis")
    ap.add_argument("--kolory", default=KOLORY_PLIK)
    ap.add_argument("--prognoza", action="store_true",
                    help="dodaj prognozę czasu otwartych faz (harmonogram_faz.py); z --dzis liczona od końca tego dnia")
    a = ap.parse_args(argv)
    if bool(a.plan) == bool(a.wszystkie):
        ap.error("podaj katalog planu ALBO --wszystkie")
    dzis = date.fromisoformat(a.dzis) if a.dzis else None
    kolory = wczytaj_kolory(a.kolory)
    if not kolory and a.kolory:
        print("UWAGA: brak kolorow z %s (kolory rezerwowe)" % a.kolory, file=sys.stderr)

    zprognoza = {}
    if a.prognoza:   # prognoza liczy się po WSZYSTKICH planach (zależności międzyplanowe, wolni wykonawcy), potem trafia do wybranych
        wszystkie = [przetworz_plan(k, a.db, dzis, kolory) for k in znajdz_plany()
                     if os.path.isfile(os.path.join(k, "task_plan.md")) and not os.path.basename(k).startswith("PRZYKLAD-")]
        naloz_prognoze(wszystkie, teraz(dzis))
        zprognoza = {d["sciezka"]: d for d in wszystkie}

    if a.plan:
        dane = zprognoza.get(os.path.normpath(a.plan)) or przetworz_plan(a.plan, a.db, dzis, kolory)
        zapisz(dane, a.wyjscie or a.plan, kolory)
        print("%s: %d faz -> %s" % (dane["plan"], len(dane["fazy"]), a.wyjscie or a.plan))
        return 0

    t0 = time.time()
    plany = znajdz_plany()
    przetworzone, bez_planu, rozbieznosci, suma_faz, suma_grep = 0, [], [], 0, 0
    for k in plany:
        tp = os.path.join(k, "task_plan.md")
        if not os.path.isfile(tp):
            bez_planu.append(k)
            continue
        dane = zprognoza.get(os.path.normpath(k)) or przetworz_plan(k, a.db, dzis, kolory)
        n_gantt, n_grep = len(dane["fazy"]), grep_c(tp)
        suma_faz += n_gantt
        suma_grep += n_grep
        if n_gantt != n_grep:
            rozbieznosci.append("%s:1 gantt=%d grep=%d" % (tp, n_gantt, n_grep))
        wy = os.path.join(a.wyjscie, projekt_planu(k), dane["plan"]) if a.wyjscie else k
        zapisz(dane, wy, kolory)
        przetworzone += 1
        print("%4d %4d  %s" % (n_gantt, n_grep, k))
    print("---")
    print("katalogow planow (glob): %d; z task_plan.md: %d; bez task_plan.md: %d"
          % (len(plany), przetworzone, len(bez_planu)))
    print("faz gantt.py: %d; faz grep -c '^### Phase': %d" % (suma_faz, suma_grep))
    print("rozbieznosci mianownika: %d" % len(rozbieznosci))
    for r in rozbieznosci:
        print("  " + r)
    for b in bez_planu:
        print("  pominiety (brak task_plan.md): " + b)
    print("czas przebiegu: %.2f s" % (time.time() - t0))
    return 1 if rozbieznosci else 0


if __name__ == "__main__":
    sys.exit(main())
