#!/usr/bin/env python3
"""Kontrola dowodów planu (reguła 7 acting-with-files). Tylko odczyt, biblioteka standardowa.

Użycie: python3 -I sprawdz_dowody.py [--zamkniecie] <katalog-planu | task_plan.md>
Tryb --zamkniecie (własne pilnowanie zamknięcia faz, bez cudzego dodatku): oprócz kontroli dowodów
odmawia (kod 1), gdy któraś faza nie jest complete — wołasz go tuż przed ogłoszeniem pracy za skończoną.
Kod wyjścia: 0 = przechodzi, 1 = naruszenia, 2 = błąd użycia.

Sprawdza: dokładnie jedno pole **Status:** na fazę; faza complete ma konkretny „Dowód”;
faza complete/in_progress ma „Gotowe, gdy”; blokada (Phase N) przy fazie complete to naruszenie;
nagłówek fazy musi mieć postać `### Phase N: nazwa`.
"""
import re
import sys
from pathlib import Path

PUSTE = {"", "—", "-", "–", "brak", "ok", "zrobione", "działa", "dziala", "done", "tak", "n/a"}
MIN_DLUGOSC = 8


def wartosc(linia, etykieta):
    m = re.search(r"\*\*" + re.escape(etykieta) + r"\*\*\s*(.*)$", linia)
    return m.group(1).strip() if m else None


def pusta(w):
    if w is None:
        return True
    w = w.strip().strip(".").lower()
    return w in PUSTE or (w.startswith("[") and w.endswith("]")) or len(w) < MIN_DLUGOSC


def fazy_planu(tekst):
    fazy, bież = [], None
    for linia in tekst.splitlines():
        s = linia.strip()
        m = re.match(r"### Phase\s+(\d+)\s*[:\-—]?\s*(.*)", s)
        if m:
            bież = {"nr": int(m.group(1)), "nazwa": m.group(2).strip(), "status": None,
                    "statusow": 0, "gotowe": None, "dowod": None}
            fazy.append(bież)
            continue
        if re.match(r"#{1,3}\s", s):  # inny nagłówek kończy fazę; #### to podsekcja
            bież = None
            continue
        if bież is None:
            continue
        m = re.match(r"(?:[-*+]\s+)?\*\*Status:\*\*\s*(.*)$", s)
        if m:
            bież["statusow"] += 1
            if bież["status"] is None:  # liczy się pierwsze pole fazy
                bież["status"] = m.group(1).strip()
        for etykieta, klucz in (("Gotowe, gdy:", "gotowe"), ("Dowód:", "dowod")):
            w = wartosc(s, etykieta)
            if w is not None:
                bież[klucz] = w
    return fazy


def sekcja(tekst, tytul):
    wynik, w = [], False
    for linia in tekst.splitlines():
        if linia.startswith("## "):
            w = linia[3:].strip().lower().startswith(tytul.lower())
            continue
        if w:
            wynik.append(linia)
    return wynik


def main(argv):
    args = [a for a in argv[1:] if a != "--zamkniecie"]
    zamkniecie = len(args) != len(argv) - 1
    if len(args) != 1:
        print(__doc__)
        return 2
    p = Path(args[0])
    plan = p / "task_plan.md" if p.is_dir() else p
    if not plan.is_file():
        print(f"BRAK PLIKU: {plan}")
        return 2
    tekst = plan.read_text(encoding="utf-8")
    fazy = fazy_planu(tekst)
    bledy = []
    for l in tekst.splitlines():
        s = l.strip()
        if re.match(r"^#{1,6}\s*Phase\b", s) and not s.startswith("### Phase"):
            bledy.append(f"nagłówek fazy na złym poziomie (ma być `### Phase N:`): {s}")
    if not fazy:  # plan bez faz nie może dawać „OK”
        bledy.append("0 faz `### Phase N:` — plan bez faz nie przechodzi kontroli")
    for f in fazy:
        st = (f["status"] or "").lower()
        e = f"Phase {f['nr']}: {f['nazwa']}"
        if f["statusow"] != 1:
            bledy.append(f"{e} ma {f['statusow']} pól **Status:** (ma być dokładnie jedno)")
        if "complete" in st and pusta(f["dowod"]):
            bledy.append(f"{e} jest complete bez konkretnego dowodu (Dowód: {f['dowod'] or 'brak pola'})")
        if ("complete" in st or "in_progress" in st) and pusta(f["gotowe"]):
            bledy.append(f"{e} nie ma warunku „Gotowe, gdy:”")
    zamkniete = {f["nr"] for f in fazy if "complete" in (f["status"] or "").lower()}
    for linia in sekcja(tekst, "Blokady"):
        for nr in re.findall(r"\(Phase\s+(\d+)\)", linia):
            if int(nr) in zamkniete:
                bledy.append(f"Phase {nr} jest complete, a ma wpis w „Blokady”: {linia.strip()}")
    if zamkniecie:
        for f in fazy:
            if "complete" not in (f["status"] or "").lower():
                bledy.append(f"zamknięcie: Phase {f['nr']}: {f['nazwa']} ma status „{f['status'] or 'brak'}” (nie complete)")
    print(f"Plan: {plan}\nFazy: {len(fazy)}, zamknięte: {len(zamkniete)}")
    if bledy:
        print(f"NARUSZENIA ({len(bledy)}):")
        for b in bledy:
            print(f"  - {b}")
        return 1
    print("OK: każda zamknięta faza ma dowód, żadna nie ma otwartych blokad.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv))
