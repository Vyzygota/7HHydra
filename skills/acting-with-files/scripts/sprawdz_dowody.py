#!/usr/bin/env python3
"""Kontrola dowodów planu (acting-with-files, reguły 1, 2, 3, 7).

Użycie: python sprawdz_dowody.py [--tylko-odczyt] [--zamkniecie] [--ustawienia PLIK] <katalog planu albo ścieżka task_plan.md>
Kod wyjścia: 0 = plan spójny, 1 = naruszenia, 2 = brak pliku.

Stemplowanie dat faz jest opcjonalne i leży w osobnym skrypcie `daty_faz.py` (plan GANTT-20261029, Phase 3; wydzielone
w planie WYDANIE-PRZEROBKA, Phase 22): kontrola działa bez niego. Gdy `daty_faz.py` leży obok, przed kontrolą porównuje
statusy faz z poprzednim stanem w `.stan.json` (katalog planu) i dopisuje pod `**Status:**` pole `**Start:**`
(zmiana na in_progress) albo `**Koniec:**` (zmiana na complete). Szczegóły: daty_faz.py.
`--tylko-odczyt` wyłącza stemplowanie i zapis stanu (kontrola nie zmienia żadnego pliku).
`--zamkniecie` (IP47.53): oprócz kontroli odmawia (kod 1), gdy któraś faza nie jest complete — wołasz je tuż przed
ogłoszeniem pracy za skończoną.
`--ustawienia PLIK` wskazuje plik ustawień zespołu (tytuł sekcji pytań do człowieka); zob. ustawienia_planu.py.

Sprawdza:
  - plan ma co najmniej jedną fazę `### Phase N:` i żadnego nagłówka Phase na innym poziomie,
  - każda faza ma dokładnie jedno pole `**Status:**` (liczy się pierwsze; podsekcja go nie nadpisze),
  - faza `complete` ma konkretny „Dowód:” (nie puste, nie „—”, nie „ok/zrobione/działa”),
  - faza `in_progress` albo `complete` ma wypełnione „Gotowe, gdy:”,
  - żaden wpis „(Phase N)” w „Nie sprawdziłem” nie dotyczy fazy `complete`,
  - liczy otwarte pozycje sekcji pytań do człowieka (ustawienie `sekcja_czeka`; informacyjnie),
  - OSTRZEGA (bez zmiany kodu wyjścia), gdy wiersz tej sekcji ma treść, a w kolumnie #
    zamiast numeru pytania z rejestru stoi „—”, „-” albo nic (IP44.56 = c, 29.10.2026),
  - OSTRZEGA (UWAGA, bez zmiany kodu wyjścia), gdy pole `**Rewizja:** rev N · DDMMRR` ma datę starszą
    niż ostatnia zmiana pliku o więcej niż 1 dzień (mtime; git log, jeśli plan leży w repo) — 31.10.2026,
    D-2026-10-31-REWIZJA-Z-DATA; plan bez pola rewizji nie dostaje nic,
  - OSTRZEGA (UWAGA, bez zmiany kodu wyjścia), gdy faza `complete` ma w „Dowód:” „przesunięte”,
    „odroczone”, „nie wykonano” albo „poza zakresem”, a nie ma zapisu „było … → …” (IP44.70 = a).
  - OSTRZEGA (UWAGA, bez zmiany kodu wyjścia), gdy faza `complete` nie ma pola `**Koniec:**` — Gantt w CSW
    pokazuje wtedy „nie wiem, brak daty” (31.10.2026, karta t_90703f7d); datę odtwarza się ze źródła
    i zapisuje z adnotacją w nawiasie, nie zgaduje.
  - Znacznik planu „sprzed metody” (24.11.2026, karta t_04863db3): pole nagłówka `**Metoda:** sprzed-metody · RRRR-MM-DD`
    (data nadania znacznika) wyłącza kontrolę planu — „POMINIĘTY: plan sprzed metody (RRRR-MM-DD)”, kod 0, bez
    stemplowania i bez zapisu. Znacznik nie kryje pracy: plan ze znacznikiem i fazą pending/in_progress → kod 1;
    pole `Metoda` z wartością „sprzed-metody” bez poprawnej daty też → kod 1. Inne wartości `Metoda` są ignorowane.
Poza stemplowaniem (jw.) tylko odczyt. Biblioteka standardowa.
"""
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # także pod `python -I`
import ustawienia_planu  # noqa: E402  (tytuł sekcji pytań do człowieka z pliku ustawień)
try:
    import fazy_planu  # jeden parser faz (ostrzeżenia o datach)
except ImportError:  # stare wdrożenie bez fazy_planu.py: kontrola działa, ostrzeżeń o datach nie ma
    fazy_planu = None
try:
    import daty_faz  # opcjonalne stemplowanie `**Start:**`/`**Koniec:**`
except ImportError:  # bez daty_faz.py kontrola działa, dat nie dopisuje
    daty_faz = None

PUSTE = {"", "—", "-", "–", "brak", "ok", "zrobione", "działa", "dziala", "done", "tak", "n/a"}
MIN_DLUGOSC_DOWODU = 8


def _wartosc(linia, etykieta):
    m = re.search(r"\*\*" + re.escape(etykieta) + r"\*\*\s*(.*)$", linia)
    return m.group(1).strip() if m else None


def _pusta(w):
    if w is None:
        return True
    w2 = w.strip().strip(".").lower()
    return w2 in PUSTE or (w2.startswith("[") and w2.endswith("]")) or len(w2) < MIN_DLUGOSC_DOWODU


def wczytaj_fazy(tekst):
    fazy, biezaca = [], None
    w_bloku = False  # ogrodzony blok kodu (```/~~~): przykłady nie są fazami ani statusami (PR #381 autora)
    for linia in tekst.lstrip("\ufeff").splitlines():
        s = linia.strip()
        if s.startswith(("```", "~~~")):
            w_bloku = not w_bloku
            continue
        if w_bloku:
            continue
        if s.startswith("### Phase"):
            m = re.match(r"### Phase\s+(\d+)\s*[:\-—]?\s*(.*)", s)
            biezaca = {"nr": int(m.group(1)) if m else len(fazy) + 1,
                       "nazwa": (m.group(2) if m else s).strip(),
                       "status": None, "statusow": 0, "gotowe": None, "dowod": None}
            fazy.append(biezaca)
            continue
        # Faza kończy się na każdym nagłówku #, ## albo ### innym niż Phase (jak check-complete.sh
        # --validate w planning-with-files 3.25.2); #### to podsekcja fazy.
        if re.match(r"#{1,3}\s", s):
            biezaca = None
            continue
        if biezaca is None:
            continue
        # Status = pole na początku linii, nie cytat w treści; liczy się PIERWSZE pole fazy.
        # 29.10.2026: ostatnie wygrywało, więc „pending” z późniejszej podsekcji zdejmowało
        # z fazy complete wymóg dowodu (fałszywe OK, wyjście 0).
        m = re.match(r"(?:[-*+]\s+)?\*\*Status:\*\*\s*(.*)$", s)
        if m:
            biezaca["statusow"] += 1
            if biezaca["status"] is None:
                biezaca["status"] = m.group(1).strip()
        for etykieta, klucz in (("Gotowe, gdy:", "gotowe"), ("Dowód:", "dowod")):
            w = _wartosc(s, etykieta)
            if w is not None:
                biezaca[klucz] = w
    return fazy


def sekcja(tekst, tytul):
    linie, w_sekcji = [], False
    for linia in tekst.splitlines():
        if linia.startswith("## "):
            w_sekcji = linia[3:].strip().lower().startswith(tytul.lower())
            continue
        if w_sekcji:
            linie.append(linia)
    return linie


def _komorki(linia):
    return [c.strip() for c in linia.strip().strip("|").split("|")]


def _tresc_wiersza(komorki, pomin=None):
    """Komórki wiersza sekcji pytań do człowieka niosące treść: bez pustych, samych myślników/pauz i zaślepki „(brak)”."""
    return [c for i, c in enumerate(komorki) if i != pomin and c.strip("—–- ")
            and not re.match(r"\(?brak\b", c, re.IGNORECASE)]


def ostrzezenia_czeka(tekst):
    """Wiersz sekcji pytań do człowieka z treścią, a w kolumnie # „—” albo nic (IP44.56 = c).

    Zdarzenie 28.10.2026: PRZESZCZEP-BOTCHAT-20261028 task_plan.md:9,15 — Phase 4 czekała
    na zgodę, kolumna # = —, w rejestrze brak pytania; człowiek nie miał o czym decydować.
    Numer nadaje wyłącznie pytanie.py — ta kontrola nie sprawdza, czy numer istnieje w rejestrze.
    """
    wynik, kol = [], 0
    tytul = ustawienia_planu.wczytaj()["sekcja_czeka"]
    for linia in sekcja(tekst, tytul):
        if not linia.strip().startswith("|"):
            continue
        komorki = _komorki(linia)
        if all(re.fullmatch(r":?-{3,}:?", c) for c in komorki if c):
            continue  # separator nagłówka | --- |
        if "#" in komorki and not any(re.search(r"\d", c) for c in komorki):
            kol = komorki.index("#")  # nagłówek tabeli
            continue
        nr = komorki[kol] if kol < len(komorki) else ""
        # Zaślepka „| — | (brak) | — |” znaczy „nic nie czeka” — to nie wiersz do decyzji.
        reszta = _tresc_wiersza(komorki, kol)
        if reszta and nr.strip("—–- ") == "":
            wynik.append(f"„{tytul}”: wiersz bez numeru pytania z rejestru w kolumnie # "
                         f"(jest „{nr or 'puste'}”) — załóż pytanie przez pytanie.py: {linia.strip()}")
    return wynik


# IP44.70 = a (29.10.2026). Formy fleksyjne, wielkość liter bez znaczenia.
ODROCZENIE = re.compile(r"przesuni[ęe]t\w*|odroczon\w*|nie\s+wykona(?:n\w*|no)|poza\s+zakres\w*",
                        re.IGNORECASE)


def ostrzezenia_odroczenia(fazy):
    """Faza complete, której dowód mówi, że część zakresu poszła gdzie indziej (IP44.70 = a).

    Zdarzenie 28.10.2026: PRZESZCZEP-BOTCHAT-20261028 task_plan.md:45 — Phase 3 complete,
    w dowodzie „Tura modelu przesunięta do Phase 4”; „Gotowe, gdy:” wymagało tej tury.
    Brak UWAGI, gdy dowód niesie opis zmiany zakresu („było” i „→”).
    """
    wynik = []
    for f in fazy:
        dowod = f["dowod"] or ""
        if "complete" not in (f["status"] or "").lower():
            continue
        m = ODROCZENIE.search(dowod)
        if not m or ("było" in dowod.lower() and "→" in dowod):
            continue
        wynik.append(f"UWAGA: Phase {f['nr']}: {f['nazwa']} jest complete, a Dowód mówi „{m.group(0)}” — "
                     f"część „Gotowe, gdy:” mogła nie zostać spełniona. Popraw: albo faza wraca do "
                     f"in_progress z wpisem w „Blokady”, albo w Dowodzie zapis zmiany zakresu "
                     f"„było → jest → dlaczego” i nazwa fazy, która przejęła resztę (reguła 1 SKILL.md)")
    return wynik


def ostrzezenia_rewizji(plan, tekst):
    """UWAGA, gdy data w `**Rewizja:** rev N · DDMMRR` jest starsza niż ostatnia zmiana pliku o >1 dzień."""
    m = re.search(r"^\**Rewizja:?\**:?\s*rev\s+(\d+)\s*·\s*(\d{2})(\d{2})(\d{2})\b", tekst, re.M)
    if not m:
        return []
    try:
        data = datetime(2000 + int(m.group(4)), int(m.group(3)), int(m.group(2)))
    except ValueError:
        return [f"UWAGA: pole Rewizja ma niepoprawną datę „{m.group(0).strip()}” (format: rev N · DDMMRR)"]
    zmiana = None
    try:
        w = subprocess.run(["git", "-C", str(plan.parent), "log", "-1", "--format=%ct", "--", plan.name],
                           capture_output=True, text=True, timeout=10)
        if w.returncode == 0 and w.stdout.strip():
            zmiana = datetime.fromtimestamp(int(w.stdout.strip()))
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    zrodlo = "ostatni commit"
    if zmiana is None:
        zmiana, zrodlo = datetime.fromtimestamp(plan.stat().st_mtime), "mtime pliku"
    if (zmiana.date() - data.date()).days > 1:
        return [f"UWAGA: Rewizja „rev {m.group(1)} · {m.group(2)}{m.group(3)}{m.group(4)}” jest starsza niż "
                f"{zrodlo} ({zmiana:%d%m%y}) o {(zmiana.date() - data.date()).days} dni — podbij N i datę "
                f"(`teraz`) przy zmianie treści"]
    return []


_METODA = re.compile(r"^\**Metoda:?\**:?[ \t]*(.*)$", re.M)
_METODA_SPRZED = re.compile(r"sprzed-metody(?:\s*·\s*(\d{4})-(\d{2})-(\d{2}))?\s*$")


def znacznik_sprzed_metody(tekst):
    """Pole `**Metoda:** sprzed-metody · RRRR-MM-DD` (wzorzec jak `Rewizja`; poza blokami kodu).

    Zwraca None (brak znacznika), (data, None) albo (None, błąd) przy polu bez poprawnej daty.
    """
    bez_blokow = re.sub(r"^(```|~~~).*?^\1[^\n]*$", "", tekst.lstrip("\ufeff"), flags=re.M | re.S)
    for m in _METODA.finditer(bez_blokow):
        w = _METODA_SPRZED.fullmatch(m.group(1).strip())
        if not w:
            continue  # inna wartość pola Metoda: nie nasz znacznik
        if w.group(1) is None:
            return None, f"znacznik sprzed metody bez daty: „{m.group(0).strip()}” (format: `**Metoda:** sprzed-metody · RRRR-MM-DD`)"
        try:
            datetime(int(w.group(1)), int(w.group(2)), int(w.group(3)))
        except ValueError:
            return None, f"znacznik sprzed metody z niepoprawną datą: „{m.group(0).strip()}”"
        return f"{w.group(1)}-{w.group(2)}-{w.group(3)}", None
    return None


def fazy_otwarte(fazy):
    """Fazy pending/in_progress; skreślone `~~in_progress~~` przy `complete` się nie liczą."""
    wynik = []
    for f in fazy:
        st = re.sub(r"~~.*?~~", "", f["status"] or "").lower()
        if "complete" not in st and re.search(r"pending|in_progress", st):
            wynik.append(f)
    return wynik


def ostrzezenia_dat(plan):
    """UWAGA dla fazy complete bez `**Koniec:**` (stempel dopisuje stempluj_plan przy zmianie statusu; ta kontrola łapie fazy historyczne)."""
    if fazy_planu is None:
        return []
    wynik = []
    for f in fazy_planu.wczytaj_plan(str(plan)):
        if f["status"] == "complete" and not f["ma_koniec"]:
            wynik.append(f"UWAGA: Phase {f['nr']}: {f['tytul']} jest complete bez `**Koniec:**`"
                         f"{'' if f['ma_start'] else ' i bez `**Start:**`'} — Gantt pokaże „nie wiem, brak daty” "
                         "(dopisz datę ze źródła z adnotacją, np. `(odtworzone z progress.md 2026-10-18)`)")
    return wynik


def main(argv):
    argv = list(argv)
    ustawienia_planu.ustaw_z_argv(argv)
    arg = [a for a in argv[1:] if a not in ("--tylko-odczyt", "--zamkniecie")]
    tylko_odczyt = "--tylko-odczyt" in argv[1:]
    zamkniecie = "--zamkniecie" in argv[1:]
    if len(arg) != 1:
        print(__doc__)
        return 2
    p = Path(arg[0])
    plan = p / "task_plan.md" if p.is_dir() else p
    if not plan.is_file():
        print(f"BRAK PLIKU: {plan}")
        return 2
    znacznik = znacznik_sprzed_metody(plan.read_text(encoding="utf-8-sig"))
    if znacznik is not None:
        data, blad = znacznik
        fazy_z = wczytaj_fazy(plan.read_text(encoding="utf-8-sig"))
        print(f"Plan: {plan}")
        otwarte = fazy_otwarte(fazy_z)
        if blad or otwarte:
            print("NARUSZENIA (%d):" % (1 if blad else len(otwarte)))
            if blad:
                print(f"  - {blad}")
            for f in otwarte:
                print(f"  - znacznik sprzed metody na planie z otwartą fazą {f['nr']}: {f['nazwa']} "
                      f"(status „{f['status']}”) — dokończ albo zamknij fazę, albo zdejmij znacznik")
            return 1
        print(f"POMINIĘTY: plan sprzed metody ({data}) — kontrola dowodów nie dotyczy; nic nie zapisano.")
        return 0
    stemple = []
    if daty_faz is not None:
        try:
            stemple = daty_faz.stempluj_plan(plan, zapisuj=not tylko_odczyt)
        except Exception as e:  # stemplowanie nie może przewrócić kontroli dowodów
            stemple = [f"UWAGA: stemplowanie dat nie powiodło się: {e}"]
    tekst = plan.read_text(encoding="utf-8-sig")
    fazy = wczytaj_fazy(tekst)
    bledy = []
    # Fałszywe zero (28.10.2026): plan bez nagłówków `### Phase` dawał „Fazy: 0 … OK” i wyjście 0,
    # a wtyczka planning-with-files i bramka ukończenia też go wtedy nie widzą.
    zly_poziom = [l.strip() for l in tekst.splitlines()
                  if re.match(r"^#{1,6}\s*Phase\b", l.strip()) and not l.strip().startswith("### Phase")]
    for l in zly_poziom:
        bledy.append(f"nagłówek fazy na złym poziomie (ma być `### Phase N:`): {l}")
    if not fazy:
        bledy.append("0 faz `### Phase N:` — planu nie policzy ani ta kontrola, ani wtyczka, ani bramka")

    for f in fazy:
        st = (f["status"] or "").lower()
        etyk = f"Phase {f['nr']}: {f['nazwa']}"
        if f["statusow"] != 1:
            bledy.append(f"{etyk} ma {f['statusow']} pól **Status:** (ma być dokładnie jedno)")
        if "complete" in st and _pusta(f["dowod"]):
            bledy.append(f"{etyk} jest complete bez konkretnego dowodu (Dowód: {f['dowod'] or 'brak pola'})")
        if ("complete" in st or "in_progress" in st) and _pusta(f["gotowe"]):
            bledy.append(f"{etyk} nie ma warunku „Gotowe, gdy:”")

    zamkniete = {f["nr"] for f in fazy if "complete" in (f["status"] or "").lower()}
    for linia in sekcja(tekst, "Blokady") + sekcja(tekst, "Nie sprawdziłem"):
        for nr in re.findall(r"\(Phase\s+(\d+)\)", linia):
            if int(nr) in zamkniete:
                bledy.append(f"Phase {nr} jest complete, a ma wpis w „Blokady”: {linia.strip()}")

    if zamkniecie:
        for f in fazy:
            if "complete" not in (f["status"] or "").lower():
                bledy.append(f"zamknięcie: Phase {f['nr']}: {f['nazwa']} ma status „{f['status'] or 'brak'}” (nie complete)")

    # 19.11.2026: zaślepka „| — | (brak) |” i pusty wiersz szablonu to „nic nie czeka” — wcześniej licznik znał
    # tylko ASCII „-” na początku wiersza i liczył zaślepkę z pauzą „—” jako oczekujące pytanie.
    ust = ustawienia_planu.wczytaj()
    czeka = [l for l in sekcja(tekst, ust["sekcja_czeka"])
             if l.strip().startswith("|") and not re.match(r"^\|\s*(:?-{3,}|#)", l.strip())
             and _tresc_wiersza(_komorki(l))]
    ostrzezenia = ostrzezenia_czeka(tekst) + ostrzezenia_odroczenia(fazy) + ostrzezenia_rewizji(plan, tekst) + ostrzezenia_dat(plan)

    print(f"Plan: {plan}")
    print(f"Fazy: {len(fazy)}, zamknięte: {len(zamkniete)}, {ust.get('etykieta_czeka') or ust['sekcja_czeka'].lower()}: {len(czeka)}")
    if stemple:
        print(f"STEMPLE ({len(stemple)}):")
        for komunikat in stemple:
            print(f"  - {komunikat}")
    if ostrzezenia:
        print(f"OSTRZEŻENIA ({len(ostrzezenia)}):")
        for o in ostrzezenia:
            print(f"  - {o}")
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
