#!/usr/bin/env python3
"""daty_faz.py — stemplowanie dat faz `task_plan.md` (acting-with-files; opcjonalny skrypt obok kontroli dowodów).

Wydzielone z `fazy_planu.py` (plan WYDANIE-PRZEROBKA, Phase 22): kontrola dowodów (`sprawdz_dowody.py`) działa bez tego
pliku; gdy leży obok, przy zmianie statusu fazy dopisuje pod `**Status:**` pole `**Start:** RRRR-MM-DD GG:MM`
(zmiana na in_progress) albo `**Koniec:** RRRR-MM-DD GG:MM` (zmiana na complete), czas z zegara systemowego
(Europe/Warsaw). Poprzedni stan statusów leży w `.stan.json` w katalogu planu; pierwsze uruchomienie na planie bez
`.stan.json` niczego nie dopisuje wstecz, tylko zapisuje stan. Ponowne uruchomienie nic nie zmienia.

Użycie samodzielne: daty_faz.py [--tylko-odczyt] <katalog planu albo task_plan.md>
Biblioteka standardowa; parser faz z `fazy_planu.py`.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # także pod `python -I`
from fazy_planu import klucze_faz, parsuj_plan, teraz  # noqa: E402

FORMAT_STEMPLA = "%Y-%m-%d %H:%M"
PLIK_STANU = ".stan.json"


def wczytaj_stan(katalog):
    """(słownik {klucz: status} | None gdy brak/uszkodzony, ostrzeżenie | None)."""
    p = os.path.join(katalog, PLIK_STANU)
    if not os.path.exists(p):
        return None, None
    try:
        with open(p, encoding="utf-8") as f:
            dane = json.load(f)
        fazy = dane["fazy"]
        if not isinstance(fazy, dict):
            raise ValueError("fazy nie jest słownikiem")
        return {str(k): str(v) for k, v in fazy.items()}, None
    except (OSError, ValueError, KeyError) as e:
        return None, "uszkodzony %s (%s) — stan zapisany od nowa, nic nie dopisano wstecz" % (PLIK_STANU, e)


def zapisz_atomowo(sciezka, tresc_bajty):
    tmp = sciezka + ".tmp"
    with open(tmp, "wb") as f:
        f.write(tresc_bajty)
    if os.path.exists(sciezka):
        shutil.copymode(sciezka, tmp)
    os.replace(tmp, sciezka)


def zapisz_stan(katalog, klucze, fazy, kiedy):
    dane = {"wersja": 1, "zapisano": kiedy.strftime(FORMAT_STEMPLA),
            "fazy": {k: f["status_norm"] for k, f in zip(klucze, fazy)}}
    zapisz_atomowo(os.path.join(katalog, PLIK_STANU),
                   (json.dumps(dane, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def stempluj_plan(sciezka_planu, kiedy=None, zapisuj=True):
    """Dopisuje `**Start:**` / `**Koniec:**` fazom, których status właśnie się zmienił.

    Zwraca listę komunikatów (str). Zmiany względem poprzedniego stanu z `.stan.json`:
      → in_progress  : `**Start:** <teraz>` (jeśli faza nie ma jeszcze pola Start),
      → complete     : `**Koniec:** <teraz>` (jeśli faza nie ma jeszcze pola Koniec; Startu NIE zgadujemy —
                       faza, która nie była widziana jako in_progress, dostaje tylko Koniec).
    Nigdy nie nadpisuje istniejącego pola, nie kasuje stempli (cofnięcie statusu zostawia je w planie;
    widok bierze Koniec tylko przy statusie complete). Ponowne uruchomienie nic nie zmienia.
    Brak `.stan.json` = pierwsze uruchomienie: zapisuje stan, niczego nie dopisuje wstecz.
    zapisuj=False: tylko raport, bez zapisu planu i stanu.
    """
    kiedy = kiedy or teraz()
    sciezka_planu = str(sciezka_planu)
    katalog = os.path.dirname(os.path.abspath(sciezka_planu))
    with open(sciezka_planu, "rb") as f:
        surowe = f.read()
    tekst = surowe.decode("utf-8", errors="replace")
    bom = tekst.startswith("\ufeff")
    tekst = tekst.lstrip("\ufeff")
    eol = "\r\n" if "\r\n" in tekst else "\n"
    linie = [l.rstrip("\r") for l in tekst.split("\n")]
    fazy = parsuj_plan(linie)
    klucze = klucze_faz(fazy)
    stan, ostrz = wczytaj_stan(katalog)
    komunikaty = ["UWAGA: " + ostrz] if ostrz else []

    if stan is None:
        if zapisuj:
            try:
                zapisz_stan(katalog, klucze, fazy, kiedy)
                komunikaty.append("stan statusów zapisany (%s, %d faz) — pierwsze uruchomienie, nic nie dopisano wstecz"
                                  % (PLIK_STANU, len(fazy)))
            except OSError as e:
                komunikaty.append("UWAGA: nie zapisano %s: %s" % (PLIK_STANU, e))
        return komunikaty

    stempel = kiedy.strftime(FORMAT_STEMPLA)
    wstawki = []  # (indeks_linii_po_ktorej_wstawic, tekst_linii) — wstawiamy od końca
    for k, f in zip(klucze, fazy):
        przed = stan.get(k, "pending")  # faza dodana po ostatnim stanie liczy się jako pending
        teraz_st = f["status_norm"]
        if teraz_st == przed or f["linia_status"] is None:
            continue
        po = f["linia_status"]  # 1-based → wstawiamy po tej linii (indeks listy = po)
        if teraz_st == "complete" and f["linie_pol"].get("start"):
            po = max(po, f["linie_pol"]["start"])  # Koniec pod Startem, gdy Start już jest
        pref = f["prefiks_status"]
        nowe = []
        if teraz_st == "in_progress":
            if f["start_bez_godziny"]:
                komunikaty.append("Phase %s: `**Start:**` bez godziny to data planowana — stempla nie dopisano "
                                  "(planowany start zapisuj jako `**Start plan:**`)" % f["nr"])
            elif not f["ma_start"]:
                nowe.append("%s**Start:** %s" % (pref, stempel))
        elif teraz_st == "complete":
            if not f["ma_koniec"]:
                nowe.append("%s**Koniec:** %s" % (pref, stempel))
        if nowe:
            wstawki.append((po, nowe))
            for n in nowe:
                komunikaty.append("Phase %s (%s → %s): dopisano %s" % (f["nr"], przed or "?", teraz_st, n.strip()))

    if wstawki and zapisuj:
        for po, nowe in sorted(wstawki, key=lambda w: -w[0]):
            # Start ma stać przed Koniec, więc wstawiamy po linii Status w kolejności listy.
            linie[po:po] = nowe
        try:
            zapisz_atomowo(sciezka_planu, ("\ufeff" if bom else "").encode("utf-8") + eol.join(linie).encode("utf-8"))
        except OSError as e:
            komunikaty.append("UWAGA: nie zapisano planu: %s — stempli nie ma, stan niezmieniony" % e)
            return komunikaty
    if zapisuj:
        fazy_po = parsuj_plan(linie) if wstawki else fazy
        stan_nowy = {k: f["status_norm"] for k, f in zip(klucze_faz(fazy_po), fazy_po)}
        if stan_nowy != stan:
            try:
                zapisz_stan(katalog, klucze_faz(fazy_po), fazy_po, kiedy)
            except OSError as e:
                komunikaty.append("UWAGA: nie zapisano %s: %s" % (PLIK_STANU, e))
    return komunikaty


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    arg = [a for a in sys.argv[1:] if a != "--tylko-odczyt"]
    if len(arg) != 1:
        print(__doc__)
        sys.exit(2)
    p = arg[0]
    if os.path.isdir(p):
        p = os.path.join(p, "task_plan.md")
    if not os.path.isfile(p):
        print("BRAK PLIKU: %s" % p)
        sys.exit(2)
    for m in stempluj_plan(p, zapisuj=len(arg) == len(sys.argv) - 1):
        print(m)
