#!/usr/bin/env python3
"""ustawienia_planu.py — jeden plik ustawień dla skryptów planu (acting-with-files).

Skrypty rdzenia (`sprawdz_dowody.py`, `gantt.py`, `harmonogram_faz.py`, `kolejnosc.py`) nie niosą nazw osób,
projektów ani ścieżek instalacji. Wszystko, co zależy od zespołu, czytają z pliku JSON:

  1. argument `--ustawienia PLIK` (każdy skrypt; `ustaw_z_argv` zdejmuje go z argumentów),
  2. zmienna środowiska `PLAN_USTAWIENIA` (dla modułów ładowanych przez inny program, np. serwer podglądu),
  3. plik `ustawienia_planu.json` obok skryptów,
  4. wartości domyślne z `DOMYSLNE` (neutralne: brak ścieżek instalacji, brak osób).

Klucze (wszystkie opcjonalne; brakujący = wartość domyślna):
  sekcja_czeka        tytuł sekcji planu z pytaniami do człowieka (`## <tytuł>`), liczonej przez kontrolę dowodów
  etykieta_czeka      napis w wierszu „Fazy: …” kontroli dowodów (domyślnie sekcja_czeka małymi literami)
  kanban_db           baza kart (SQLite, tylko odczyt); None = bez kart
  kolory_plik         plik z tabelą kolorów osób (wykres)
  wzorce_planow       lista wzorców glob katalogów planów (`--wszystkie`)
  projekt_regex       wyrażenie z jedną grupą: nazwa projektu ze ścieżki planu (`re.match` na „ścieżka/”)
  projekt_domyslny    nazwa projektu, gdy ścieżka nie pasuje do `projekt_regex`
  projekt_domyslny_prognoza   to samo dla prognozy czasu (`harmonogram_faz.py`)
  spec_glob           wzorzec glob specyfikacji projektu; `{projekt}` = nazwa projektu
  katalog_planu       szablon katalogu planu projektu; `{projekt}` i `{plan}`
  spec_potoku         plik specyfikacji z blokiem `potok-v2` (zależności między planami)
  szacunki_katalog    katalog z `szacunki-czasu.json` i `szacunki-reczne.json`
  klasy_planow        [[wyrażenie, klasa], …] — klasa planu z jego nazwy (kalibracja czasu)
  kalibracja          {"klasa|wykonawca": [praca_h, czas_h, p50_h, p80_h]}
  kalibracja_domyslna [praca_h, czas_h, p50_h, p80_h]
  czeka_h             {klucz osoby: godziny oczekiwania na odpowiedź}
  ludzie              [klucze wykonawców będących ludźmi]
  czekanie_w_tekscie  [[wyrażenie, klucz osoby], …] — osoba, na którą czeka faza, z jej tytułu
  recenzent           {"wykonawca": klucz, "fraza": tekst w tytule, "klucz": klucz w czeka_h}
  opis_czeka_czlowiek, opis_czeka_recenzent   teksty „zrodlo” szacunku
  limit_wykonawcy     {klucz wykonawcy: liczba równoległych slotów}
  komentarze_schematu {"projekt":…, "sciezka": katalog modułu, "modul": nazwa, "polecenie": tekst}; brak = pomijane

Biblioteka standardowa.
"""
import json
import os
import sys

SK = os.path.dirname(os.path.abspath(__file__))
PLIK_DOMYSLNY = os.path.join(SK, "ustawienia_planu.json")

DOMYSLNE = {
    "sekcja_czeka": "Czeka na człowieka",
    "etykieta_czeka": None,
    "kanban_db": None,
    "kolory_plik": None,
    "wzorce_planow": [".planning/*/"],
    "projekt_regex": r"(?:.*/)?([^/]+)/\.planning/",
    "projekt_domyslny": "projekt",
    "projekt_domyslny_prognoza": "projekt",
    "spec_glob": "{projekt}/kanon/**/SPEC*.md",
    "katalog_planu": "{projekt}/.planning/{plan}",
    "spec_potoku": None,
    "szacunki_katalog": None,
    "klasy_planow": [],
    "kalibracja": {},
    "kalibracja_domyslna": [1.0, 3.0, 0.5, 10.0],
    "czeka_h": {},
    "ludzie": [],
    "czekanie_w_tekscie": [],
    "recenzent": None,
    "opis_czeka_czlowiek": "człowiek: odpowiedź",
    "opis_czeka_recenzent": "recenzent: odpowiedź",
    "limit_wykonawcy": {},
    "komentarze_schematu": None,
}

_pamiec = {}


def ustaw_z_argv(argv):
    """Zdejmuje `--ustawienia PLIK` (albo `--ustawienia=PLIK`) z listy argumentów i ustawia PLAN_USTAWIENIA."""
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--ustawienia" and i + 1 < len(argv):
            os.environ["PLAN_USTAWIENIA"] = os.path.abspath(argv[i + 1])
            del argv[i:i + 2]
            continue
        if a.startswith("--ustawienia="):
            os.environ["PLAN_USTAWIENIA"] = os.path.abspath(a.split("=", 1)[1])
            del argv[i]
            continue
        i += 1
    _pamiec.clear()


def sciezka_pliku():
    """Plik, z którego czytane są ustawienia (None = tylko wartości domyślne)."""
    p = os.environ.get("PLAN_USTAWIENIA")
    if p:
        return p
    return PLIK_DOMYSLNY if os.path.isfile(PLIK_DOMYSLNY) else None


def wczytaj():
    """Słownik ustawień: DOMYSLNE nadpisane plikiem. Plik wskazany, a nieczytelny = wyjątek (nie cicha zmiana)."""
    p = sciezka_pliku()
    if p in _pamiec:
        return _pamiec[p]
    wynik = dict(DOMYSLNE)
    if p:
        with open(p, encoding="utf-8-sig") as f:
            dane = json.load(f)
        wynik.update({k: v for k, v in dane.items() if not k.startswith("_")})
    _pamiec[p] = wynik
    return wynik


def projekt_z_planu(sciezka, ust=None):
    """Nazwa projektu ze ścieżki planu wg `projekt_regex`; brak dopasowania = `projekt_domyslny`."""
    import re
    ust = ust or wczytaj()
    m = re.match(ust["projekt_regex"], str(sciezka) + "/")
    return m.group(1) if m else ust["projekt_domyslny"]


if __name__ == "__main__":
    print(json.dumps({"plik": sciezka_pliku(), "ustawienia": wczytaj()}, ensure_ascii=False, indent=1))
    sys.exit(0)
