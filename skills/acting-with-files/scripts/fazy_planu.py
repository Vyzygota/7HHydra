#!/usr/bin/env python3
"""fazy_planu.py — JEDEN parser faz task_plan.md (acting-with-files).

Kto z tego korzysta (plan GANTT-20261029, Phase 3, karta t_ccc0679b; od Phase 22 planu WYDANIE-PRZEROBKA stemplowanie
dat jest osobno w `daty_faz.py`):
  * gantt.py            — gantt.json / gantt.svg,
  * podgląd planów w konsoli zespołu (importuje ten moduł),
  * sprawdz_dowody.py   — liczenie faz i ostrzeżenia o brakujących datach.

Reguła liczenia (jedna dla wszystkich): faza = linia zaczynająca się od `### Phase`
(dokładnie to, co liczy `grep -c '^### Phase'`). Nagłówki `## Phase`, `### Faza` itp. NIE są
fazami — `nieznormalizowane_naglowki()` je wypisuje, żeby plan z takim formatem dostał ostrzeżenie
zamiast cichego zera.

Pola fazy czytane są tylko sprzed pierwszego nagłówka `## ` w bloku fazy (sekcje typu
`## Korekta` nie podmieniają pól). Pierwsze wystąpienie pola wygrywa.

Daty (format w planie `RRRR-MM-DD GG:MM`, czas lokalny Europe/Warsaw):
  `**Start:**`   z godziną  = stempel rzeczywistego startu (pisze `stempluj_plan`),
                 bez godziny = data PLANOWANEGO startu (zgodność z prototypem gantt.py),
  `**Start plan:**`          = data planowanego startu (ma pierwszeństwo przed `**Start:**` bez godziny),
  `**Koniec:**`  = rzeczywisty koniec (stempel; sama data też przyjmowana),
  `**Termin:**`  = planowany termin (RRRR-MM-DD).

Stemplowanie dat (zapis `**Start:**`/`**Koniec:**` przy zmianie statusu) jest w `daty_faz.py` — ten moduł tylko czyta.
Biblioteka standardowa.
"""
import os
import re
from datetime import date, datetime

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Warsaw")
except Exception:  # brak tzdata
    TZ = None

STATUSY = ("pending", "in_progress", "complete")

RE_FAZA = re.compile(r"^### Phase\s*([^\s:]*)\s*(?:[:\u2013\u2014-]\s*)?(.*)$")
RE_POLE = re.compile(r"^(\s*(?:[-*]\s+)?)\*\*([^*:]+?):?\*\*:?\s*(.*)$")
RE_STATUS_TOKEN = re.compile(r"^([A-Za-z_ ]+)")
RE_DATA_GODZ = re.compile(r"\b(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?\b")
RE_KARTA = re.compile(r"\bt_[0-9a-f]{8}\b")
RE_ZLY_NAGLOWEK = re.compile(r"^#{1,6}\s*(?:Phase|Faza)\b", re.I)


# ---------------------------------------------------------------- pliki i czas
def czytaj_linie(sciezka):
    """Linie pliku jak widzi je grep: podział wyłącznie po \\n, \\r na końcu odcięty."""
    with open(sciezka, encoding="utf-8", errors="replace", newline="") as f:
        tekst = f.read()
    return [l.rstrip("\r") for l in tekst.lstrip("\ufeff").split("\n")]


def teraz():
    """Zegar systemowy w czasie lokalnym (Europe/Warsaw), bez strefy, do minuty."""
    d = datetime.now(TZ) if TZ else datetime.now()
    return d.replace(tzinfo=None, second=0, microsecond=0)


def parsuj_date_godz(tekst):
    """(date|None, datetime|None): data; datetime tylko gdy podano godzinę. Błędna data = (None, None)."""
    m = RE_DATA_GODZ.search(tekst or "")
    if not m:
        return None, None
    try:
        d = date.fromisoformat(m.group(1))
        if m.group(2):
            return d, datetime.fromisoformat(m.group(1) + " " + m.group(2))
    except ValueError:
        return None, None
    return d, None


# ---------------------------------------------------------------- parser faz
def status_znormalizowany(surowy):
    """Wartość pola Status do postaci `in_progress` (małe litery, spacje → `_`); brak = ''."""
    m = RE_STATUS_TOKEN.match((surowy or "").strip())
    return m.group(1).strip().lower().replace(" ", "_") if m else ""


def wyciagnij_karty(tekst):
    """Karty fazy z pola Kanban: id poza nawiasami i poza zależnościami 'po t_...'."""
    t = tekst
    for _ in range(5):
        t2 = re.sub(r"\([^()]*\)", " ", t)
        if t2 == t:
            break
        t = t2
    t = re.sub(r"\bpo\s+t_[0-9a-f]{8}(?:\s*,\s*t_[0-9a-f]{8})*", " ", t)
    wynik = []
    for k in RE_KARTA.findall(t):
        if k not in wynik:
            wynik.append(k)
    return wynik


def klucze_faz(fazy):
    """Stabilny klucz fazy do .stan.json: numer, a przy powtórzonym numerze 'nr#2', 'nr#3'."""
    licznik, klucze = {}, []
    for f in fazy:
        licznik[f["nr"]] = licznik.get(f["nr"], 0) + 1
        n = licznik[f["nr"]]
        klucze.append(f["nr"] if n == 1 else "%s#%d" % (f["nr"], n))
    return klucze


def parsuj_plan(linie):
    """Lista faz w kolejności pliku. Liczba = liczba linii zaczynających się od '### Phase'."""
    poczatki, w_bloku = [], False  # nagłówki w ogrodzonych blokach kodu to przykłady (PR #381 autora)
    for i, l in enumerate(linie):
        if l.lstrip().startswith(("```", "~~~")):
            w_bloku = not w_bloku
        elif not w_bloku and l.startswith("### Phase"):
            poczatki.append(i)
    fazy = []
    for n, p in enumerate(poczatki):
        koniec = poczatki[n + 1] if n + 1 < len(poczatki) else len(linie)
        m = RE_FAZA.match(linie[p])
        nr, tytul = (m.group(1), m.group(2).strip()) if m else ("", linie[p][4:].strip())
        pola, linie_pol, prefiksy = {}, {}, {}
        for j in range(p + 1, koniec):
            l = linie[j]
            if l.startswith("## ") or l.rstrip() == "##":
                break  # dalej sekcje planu, nie pola fazy
            mp = RE_POLE.match(l)
            if mp:
                k = mp.group(2).strip().lower()
                if k not in pola:
                    pola[k] = mp.group(3).strip()
                    linie_pol[k] = j + 1
                    prefiksy[k] = mp.group(1)
        status_surowy = pola.get("status")
        norm = status_znormalizowany(status_surowy)
        wyk = pola.get("wykonawca")
        if wyk is not None:
            wyk = re.split(r"\s\*\*", wyk)[0].strip()
        d_start, dt_start = parsuj_date_godz(pola.get("start"))
        d_start_plan, _ = parsuj_date_godz(pola.get("start plan"))
        d_koniec, dt_koniec = parsuj_date_godz(pola.get("koniec"))
        d_termin, _ = parsuj_date_godz(pola.get("termin"))
        fazy.append({
            "nr": nr,
            "tytul": tytul,
            "linia": p + 1,
            "status": norm if norm in STATUSY else "nieznany",
            "status_norm": norm,
            "status_surowy": status_surowy,
            "linia_status": linie_pol.get("status"),
            "prefiks_status": prefiksy.get("status", ""),
            "linie_pol": linie_pol,
            "wykonawca": wyk,
            "karty": wyciagnij_karty(pola.get("kanban", "")),
            # planowane
            "start_plan": d_start_plan or (d_start if dt_start is None else None),
            "termin_plan": d_termin,
            # stemple (rzeczywiste)
            "start_stempel": dt_start,
            "koniec_stempel": dt_koniec if dt_koniec else None,
            "koniec_data": d_koniec if dt_koniec is None else None,
            "ma_start": "start" in pola,
            "ma_koniec": "koniec" in pola,
            "start_bez_godziny": "start" in pola and dt_start is None,
            "pola": pola,
        })
    return fazy


def wczytaj_plan(sciezka):
    return parsuj_plan(czytaj_linie(sciezka))


def nieznormalizowane_naglowki(linie):
    """[(nr_linii, tekst)] nagłówków wyglądających na fazy (`## Phase`, `### Faza`…), które NIE są `### Phase`."""
    return [(i + 1, l.strip()[:100]) for i, l in enumerate(linie)
            if RE_ZLY_NAGLOWEK.match(l) and not l.startswith("### Phase")]


def ostrzezenia_formatu(linie, fazy):
    """Ostrzeżenie o nagłówkach faz w formie, której parser (i grep -c) nie liczy."""
    zle = nieznormalizowane_naglowki(linie)
    if not zle:
        return []
    return ["%d nagłówków fazy w formie innej niż `### Phase N:` — nie liczą się jako fazy (%d policzonych); "
            "np. linia %d: %s" % (len(zle), len(fazy), zle[0][0], zle[0][1])]
