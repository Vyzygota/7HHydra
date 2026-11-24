#!/usr/bin/env python3
"""Testy regresji sprawdz_dowody.py. Użycie: python3 -I test_sprawdz_dowody.py

Przypadki z 29.10.2026 (karta t_ba7f236b; wzór: fikstury planning-with-files 3.25.2,
„a phase check must not accept a later subsection's status”). Biblioteka standardowa.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKRYPT = Path(__file__).resolve().parent / "sprawdz_dowody.py"
# Testy tytułu sekcji „Czeka na Piotra” biorą go z pliku ustawień podanego argumentem `--ustawienia` (jak w użyciu zespołu).
_KAT_UST = tempfile.TemporaryDirectory()
USTAWIENIA = Path(_KAT_UST.name) / "ustawienia_testu.json"
USTAWIENIA.write_text(json.dumps({"sekcja_czeka": "Czeka na Piotra", "etykieta_czeka": "czeka na Piotra"}), encoding="utf-8")
GOTOWE = "**Gotowe, gdy:** warunek opisany konkretnie\n"


def sprawdz(tekst):
    with tempfile.TemporaryDirectory() as tmp:
        plan = Path(tmp) / "task_plan.md"
        plan.write_text(tekst, encoding="utf-8")
        wynik = subprocess.run([sys.executable, "-I", str(SKRYPT), "--ustawienia", str(USTAWIENIA), str(plan)],
                               capture_output=True, text=True, encoding="utf-8", check=False)
        assert plan.read_text(encoding="utf-8") == tekst, "kontrola zmieniła plan"
        return wynik.returncode, wynik.stdout


class SprawdzDowodyTest(unittest.TestCase):
    def test_bom_nie_gubi_pierwszej_fazy(self):
        # PR #381 autora (3.29.0): plan z BOM UTF-8 zachowuje pierwszą fazę
        kod, out = sprawdz("\ufeff### Phase 1: X\n**Status:** complete\n" + GOTOWE)
        self.assertEqual(kod, 1, out)
        self.assertIn("Phase 1", out)

    def test_przyklad_w_bloku_kodu_nie_jest_faza(self):
        kod, out = sprawdz("### Phase 1: X\n**Status:** pending\n" + GOTOWE
                           + "```\n### Phase 9: Z\n**Status:** complete\n```\n")
        self.assertEqual(kod, 0, out)
        self.assertIn("Fazy: 1,", out)

    def test_status_z_podsekcji_nie_zdejmuje_wymogu_dowodu(self):
        kod, out = sprawdz("### Phase 1: X\n**Status:** complete\n" + GOTOWE
                           + "\n#### Podetap\n**Status:** pending\n")
        self.assertEqual(1, kod, out)
        self.assertIn("bez konkretnego dowodu", out)

    def test_dwa_statusy_w_fazie_to_naruszenie(self):
        kod, out = sprawdz("### Phase 1: X\n**Status:** complete\n**Status:** pending\n" + GOTOWE)
        self.assertEqual(1, kod, out)
        self.assertIn("2 pól **Status:**", out)

    def test_brak_statusu_to_naruszenie(self):
        kod, out = sprawdz("### Phase 1: X\n" + GOTOWE)
        self.assertEqual(1, kod, out)
        self.assertIn("0 pól **Status:**", out)

    def test_naglowek_h3_konczy_faze(self):
        kod, out = sprawdz("### Phase 1: X\n**Status:** complete\n" + GOTOWE
                           + "\n### Notatki\n**Status:** pending\n")
        self.assertEqual(1, kod, out)
        self.assertIn("bez konkretnego dowodu", out)

    def test_cytat_pola_w_tresci_nie_jest_statusem(self):
        kod, out = sprawdz("### Phase 1: X\n- parser czyta `- **Status:**`\n- **Status:** pending\n")
        self.assertEqual(0, kod, out)

    def test_poprawny_plan_przechodzi(self):
        kod, out = sprawdz("### Phase 1: X\n**Status:** in_progress\n" + GOTOWE
                           + "\n### Phase 2: Y\n**Status:** pending\n")
        self.assertEqual(0, kod, out)
        self.assertIn("Fazy: 2", out)

    def test_zero_faz_to_naruszenie(self):
        kod, out = sprawdz("# Plan\n\n## Phases\n- [x] coś zrobione\n")
        self.assertEqual(1, kod, out)

    # IP44.56 = c (29.10.2026): „—” w kolumnie # tabeli „Czeka na Piotra” = ostrzeżenie, nie błąd.
    CZEKA = ("## Czeka na Piotra\n\n| # | Pytanie | Warianty | Rekomendacja | Od |\n"
             "| --- | --- | --- | --- | --- |\n")
    FAZA = "\n## Fazy\n\n### Phase 1: X\n**Status:** pending\n"

    def test_myslnik_w_kolumnie_nr_to_ostrzezenie(self):
        kod, out = sprawdz(self.CZEKA + "| — | Zgoda na przeszczep (Phase 4) | a) tak / b) nie | a | IP |\n" + self.FAZA)
        self.assertEqual(0, kod, out)
        self.assertIn("OSTRZEŻENIA (1)", out)

    def test_pusty_nr_z_trescia_to_ostrzezenie(self):
        kod, out = sprawdz(self.CZEKA + "|   | Zgoda na przeszczep | a) tak | a | IP |\n" + self.FAZA)
        self.assertEqual(0, kod, out)
        self.assertIn("OSTRZEŻENIA (1)", out)

    def test_numer_z_rejestru_bez_ostrzezenia(self):
        kod, out = sprawdz(self.CZEKA + "| IP44.56 | Zgoda na przeszczep | a) tak | a | IP |\n" + self.FAZA)
        self.assertEqual(0, kod, out)
        self.assertNotIn("OSTRZEŻENIA", out)

    def test_licznik_czeka_pomija_zaslepke_i_pusty_wiersz(self):
        # 19.11.2026: „| — | (brak) |  |  |  |” było liczone jako 1 oczekujące pytanie.
        faza = "### Phase 1: X\n**Status:** pending\n" + GOTOWE
        nagl = "## Czeka na Piotra\n\n| # | Pytanie | Warianty | Rekomendacja | Od |\n| --- | --- | --- | --- | --- |\n"
        for wiersz, ile in (("| — | (brak) |  |  |  |", 0), ("|   |         |    |    |    |", 0), ("| - | brak | | | |", 0),
                            ("| IP47.48 | Czy dopisać? | a / b | a | 2026-11-19 |", 1)):
            kod, out = sprawdz(nagl + wiersz + "\n\n## Fazy\n\n" + faza)
            self.assertIn(f"czeka na Piotra: {ile}", out, wiersz)

    def test_pusty_wiersz_szablonu_bez_ostrzezenia(self):
        kod, out = sprawdz(self.CZEKA + "|   |         |          |              |    |\n"
                           + "| — | — | — | — | — |\n" + "| - | (brak; zgoda w zakresie planu) | — | — | — |\n"
                           + "| — | brak | | | |\n" + self.FAZA)
        self.assertEqual(0, kod, out)
        self.assertNotIn("OSTRZEŻENIA", out)


class OdroczonyZakresTest(unittest.TestCase):
    """IP44.70 = a (Piotr 29.10.2026): faza complete z „przesunięte/odroczone/nie wykonano/poza
    zakresem” w dowodzie → UWAGA, kod 0. Zdarzenie: PRZESZCZEP-BOTCHAT-20261028 task_plan.md:45."""

    @staticmethod
    def plan(dowod):
        return "### Phase 1: X\n**Status:** complete\n" + GOTOWE + f"**Dowód:** {dowod}\n"

    def test_przesuniecie_bez_opisu_to_uwaga(self):
        kod, out = sprawdz(self.plan("findings.md:12, przesunięto próbę bez bramy na później"))
        self.assertEqual(0, kod, out)
        self.assertIn("a Dowód mówi", out)
        self.assertIn("Phase 1", out)

    def test_opisane_bylo_jest_dlaczego_bez_uwagi(self):
        kod, out = sprawdz(self.plan("findings.md:12, przesunięto próbę bez bramy na później; "
                                     "było: próba w Phase 1 → jest: Phase 2 → dlaczego: brak kluczy"))
        self.assertEqual(0, kod, out)
        self.assertNotIn("a Dowód mówi", out)

    def test_formy_i_wielkosc_liter(self):
        for slowo in ("Przesunięta do Phase 4", "ODROCZONE do 01.11", "Nie wykonano kroku 3",
                      "krok 3 poza zakresem", "nie wykonana tura modelu", "odroczony test"):
            with self.subTest(slowo=slowo):
                kod, out = sprawdz(self.plan(f"findings.md:12 (3/3); {slowo}"))
                self.assertEqual(0, kod, out)
                self.assertIn("a Dowód mówi", out)

    def test_faza_niezamknieta_bez_uwagi(self):
        kod, out = sprawdz("### Phase 1: X\n**Status:** in_progress\n" + GOTOWE
                           + "**Dowód:** częściowy, tura przesunięta do Phase 2\n")
        self.assertEqual(0, kod, out)
        self.assertNotIn("a Dowód mówi", out)

    def test_zwykly_dowod_bez_uwagi(self):
        kod, out = sprawdz(self.plan("findings.md:12, testy 7/7, sha256 bez zmian"))
        self.assertEqual(0, kod, out)
        self.assertNotIn("a Dowód mówi", out)


# ---------------------------------------------------------------- stemplowanie dat (GANTT-20261029, Phase 3)
import hashlib
import json
import re
import shutil
from datetime import datetime, timedelta

PLAN_PRAWDZIWY = Path("/srv/projekty/Srodowisko/.planning/GANTT-20261029/task_plan.md")
STEMPEL = re.compile(r"^\*\*(Start|Koniec):\*\* (\d{4}-\d{2}-\d{2} \d{2}:\d{2})$", re.M)


def uruchom(plan, *flagi):
    w = subprocess.run([sys.executable, "-I", str(SKRYPT), "--ustawienia", str(USTAWIENIA), *flagi, str(plan)],
                       capture_output=True, text=True, encoding="utf-8", check=False)
    return w.returncode, w.stdout


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def plan_w_katalogu(tmp, tekst, nazwa="task_plan.md"):
    p = Path(tmp) / nazwa
    p.write_bytes(tekst.encode("utf-8"))
    return p


def faza(nr, status, extra=""):
    return (f"### Phase {nr}: F{nr}\n**Status:** {status}\n" + extra
            + "**Gotowe, gdy:** warunek opisany konkretnie\n**Dowód:** plik /tmp/x.txt zawiera wynik 12\n\n")


class StemplowanieTest(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = self._t.name

    def tearDown(self):
        self._t.cleanup()

    def zmien_status(self, plan, stary, nowy, nr):
        t = plan.read_text(encoding="utf-8")
        t2 = t.replace(f"### Phase {nr}: F{nr}\n**Status:** {stary}", f"### Phase {nr}: F{nr}\n**Status:** {nowy}")
        self.assertNotEqual(t, t2)
        plan.write_bytes(t2.encode("utf-8"))

    def test_pierwsze_uruchomienie_tylko_zapisuje_stan(self):
        plan = plan_w_katalogu(self.tmp, faza(1, "in_progress") + faza(2, "complete") + faza(3, "pending"))
        przed = md5(plan)
        kod, out = uruchom(plan)
        self.assertEqual(0, kod, out)
        self.assertEqual(przed, md5(plan), "pierwsze uruchomienie dopisało coś wstecz")
        self.assertEqual({"1": "in_progress", "2": "complete", "3": "pending"},
                         json.loads((Path(self.tmp) / ".stan.json").read_text())["fazy"])
        self.assertIsNone(STEMPEL.search(plan.read_text(encoding="utf-8")))

    def test_pending_in_progress_complete_i_idempotencja(self):
        plan = plan_w_katalogu(self.tmp, faza(1, "pending") + faza(2, "pending"))
        uruchom(plan)  # pierwszy przebieg: stan
        przed = datetime.now()
        self.zmien_status(plan, "pending", "in_progress", 1)
        kod, out = uruchom(plan)
        self.assertEqual(0, kod, out)
        self.assertIn("dopisano **Start:**", out)
        t = plan.read_text(encoding="utf-8")
        m = STEMPEL.findall(t)
        self.assertEqual([("Start",)], [(x[0],) for x in m], t)
        # stempel = zegar systemowy (do 2 min od teraz), nie wartość z głowy
        d = datetime.strptime(m[0][1], "%Y-%m-%d %H:%M")
        self.assertLess(abs((d - przed).total_seconds()), 120 + 60, m)
        self.assertIn("**Status:** in_progress\n**Start:** ", t)
        # idempotencja
        h = md5(plan)
        for _ in range(3):
            kod, out = uruchom(plan)
            self.assertEqual(0, kod, out)
            self.assertEqual(h, md5(plan))
        # in_progress -> complete
        self.zmien_status(plan, "in_progress", "complete", 1)
        kod, out = uruchom(plan)
        self.assertEqual(0, kod, out)
        t = plan.read_text(encoding="utf-8")
        self.assertEqual(["Start", "Koniec"], [x[0] for x in STEMPEL.findall(t)], t)
        self.assertRegex(t, r"\*\*Start:\*\* [^\n]+\n\*\*Koniec:\*\* ")  # Koniec pod Startem
        h = md5(plan)
        uruchom(plan)
        self.assertEqual(h, md5(plan))
        # faza 2 nietknięta
        self.assertEqual(2, len(re.findall(r"^### Phase", t, re.M)))
        self.assertEqual(2, len(STEMPEL.findall(t)))

    def test_pending_prosto_do_complete_dostaje_tylko_koniec(self):
        plan = plan_w_katalogu(self.tmp, faza(1, "pending"))
        uruchom(plan)
        self.zmien_status(plan, "pending", "complete", 1)
        kod, out = uruchom(plan)
        self.assertEqual(0, kod, out)
        self.assertEqual(["Koniec"], [x[0] for x in STEMPEL.findall(plan.read_text(encoding="utf-8"))])

    def test_istniejacy_stempel_nie_jest_nadpisany(self):
        plan = plan_w_katalogu(self.tmp, faza(1, "pending", "**Start:** 2026-01-02 03:04\n"))
        uruchom(plan)
        self.zmien_status(plan, "pending", "in_progress", 1)
        uruchom(plan)
        self.assertEqual(1, len(re.findall(r"\*\*Start:\*\*", plan.read_text(encoding="utf-8"))))
        self.assertIn("**Start:** 2026-01-02 03:04", plan.read_text(encoding="utf-8"))

    def test_start_bez_godziny_to_data_planowana_i_nie_jest_nadpisany(self):
        plan = plan_w_katalogu(self.tmp, faza(1, "pending", "**Start:** 2026-11-01\n"))
        uruchom(plan)
        self.zmien_status(plan, "pending", "in_progress", 1)
        kod, out = uruchom(plan)
        self.assertEqual(0, kod, out)
        self.assertIn("bez godziny", out)
        self.assertEqual(1, len(re.findall(r"\*\*Start:\*\*", plan.read_text(encoding="utf-8"))))

    def test_tylko_odczyt_nie_zmienia_niczego(self):
        plan = plan_w_katalogu(self.tmp, faza(1, "pending"))
        kod, out = uruchom(plan, "--tylko-odczyt")
        self.assertEqual(0, kod, out)
        self.assertFalse((Path(self.tmp) / ".stan.json").exists())
        uruchom(plan)
        self.zmien_status(plan, "pending", "in_progress", 1)
        przed, stan = md5(plan), md5(Path(self.tmp) / ".stan.json")
        kod, out = uruchom(plan, "--tylko-odczyt")
        self.assertEqual(0, kod, out)
        self.assertEqual(przed, md5(plan))
        self.assertEqual(stan, md5(Path(self.tmp) / ".stan.json"))

    def test_crlf_i_lista_punktowana_zachowane(self):
        tekst = ("### Phase 1: F1\r\n- **Status:** pending\r\n- **Gotowe, gdy:** warunek opisany konkretnie\r\n\r\n")
        plan = plan_w_katalogu(self.tmp, tekst)
        uruchom(plan)
        plan.write_bytes(tekst.replace("pending", "in_progress").encode("utf-8"))
        uruchom(plan)
        b = plan.read_bytes().decode("utf-8")
        self.assertIn("- **Status:** in_progress\r\n- **Start:** ", b)
        self.assertNotRegex(b.replace("\r\n", ""), r"[\r\n]")

    def test_uszkodzony_stan_nie_dopisuje_wstecz(self):
        plan = plan_w_katalogu(self.tmp, faza(1, "in_progress"))
        (Path(self.tmp) / ".stan.json").write_text("{nie json", encoding="utf-8")
        przed = md5(plan)
        kod, out = uruchom(plan)
        self.assertEqual(0, kod, out)
        self.assertEqual(przed, md5(plan))
        self.assertIn("uszkodzony", out)

    def test_kontrola_dowodow_dziala_po_stemplowaniu(self):
        plan = plan_w_katalogu(self.tmp, faza(1, "pending") + "### Phase 2: F2\n**Status:** pending\n")
        uruchom(plan)
        self.zmien_status(plan, "pending", "complete", 1)  # ma Dowód → OK
        kod, out = uruchom(plan)
        self.assertEqual(0, kod, out)
        t = plan.read_text(encoding="utf-8").replace("**Dowód:** plik /tmp/x.txt zawiera wynik 12", "**Dowód:** —")
        plan.write_bytes(t.encode("utf-8"))
        kod, out = uruchom(plan)
        self.assertEqual(1, kod, out)  # naruszenie nadal wykryte

    @unittest.skipUnless(PLAN_PRAWDZIWY.is_file(), "brak planu GANTT-20261029 na tym hoście")
    def test_na_kopii_prawdziwego_planu(self):
        """Miara odbioru karty t_ccc0679b: kopia planu, zmiana statusów, Start/Koniec, idempotencja."""
        plan = Path(self.tmp) / "task_plan.md"
        shutil.copy(PLAN_PRAWDZIWY, plan)
        t = plan.read_text(encoding="utf-8")
        n_faz = len(re.findall(r"^### Phase", t, re.M))
        # uzgodnij stan z kopią (pierwsze uruchomienie), potem ustaw znane statusy
        uruchom(plan)
        t = re.sub(r"(### Phase 3:[^\n]*\n\*\*Status:\*\*) \w+", r"\1 pending", t)
        plan.write_bytes(t.encode("utf-8"))
        uruchom(plan)  # stan: Phase 3 pending
        t = re.sub(r"(### Phase 3:[^\n]*\n\*\*Status:\*\*) \w+", r"\1 in_progress", t)
        plan.write_bytes(t.encode("utf-8"))
        uruchom(plan)
        t = plan.read_text(encoding="utf-8")
        self.assertRegex(t, r"### Phase 3:[^\n]*\n\*\*Status:\*\* in_progress\n\*\*Start:\*\* \d{4}-\d{2}-\d{2} \d{2}:\d{2}\n")
        t = re.sub(r"(### Phase 3:[^\n]*\n\*\*Status:\*\*) \w+", r"\1 complete", t)
        plan.write_bytes(t.encode("utf-8"))
        uruchom(plan)
        t = plan.read_text(encoding="utf-8")
        self.assertRegex(t, r"\*\*Start:\*\* [^\n]+\n\*\*Koniec:\*\* \d{4}-\d{2}-\d{2} \d{2}:\d{2}\n")
        h = md5(plan)
        uruchom(plan)
        self.assertEqual(h, md5(plan))
        self.assertEqual(n_faz, len(re.findall(r"^### Phase", plan.read_text(encoding="utf-8"), re.M)))


class TestTrybZamkniecia(unittest.TestCase):
    """`--zamkniecie` (IP47.53): kontrola odmawia, gdy któraś faza nie jest complete; bez flagi plan z fazą otwartą przechodzi."""
    DOWOD = "**Dowód:** plik /tmp/x istnieje, 12 wierszy\n"
    GOT = "**Gotowe, gdy:** plik istnieje\n"

    def plan(self, st2):
        return ("# P\n\n### Phase 1: A\n**Status:** complete\n" + self.GOT + self.DOWOD +
                "\n### Phase 2: B\n**Status:** " + st2 + "\n" + self.GOT)

    def test_otwarta_faza_odmowa_tylko_z_flaga(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = plan_w_katalogu(tmp, self.plan("pending"))
            self.assertEqual(uruchom(p, "--tylko-odczyt")[0], 0)
            kod, wyj = uruchom(p, "--tylko-odczyt", "--zamkniecie")
            self.assertEqual(kod, 1)
            self.assertIn("zamknięcie: Phase 2", wyj)

    def test_wszystkie_complete_przechodzi_z_flaga(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = plan_w_katalogu(tmp, self.plan("complete") + self.DOWOD)  # Dowód faz 2 za polem Gotowe, gdy
            self.assertEqual(uruchom(p, "--tylko-odczyt", "--zamkniecie")[0], 0)


class ZnacznikSprzedMetodyTest(unittest.TestCase):
    """`**Metoda:** sprzed-metody · RRRR-MM-DD` (karta t_04863db3, 24.11.2026): wyłącza kontrolę planu zamkniętego,
    nie kryje fazy otwartej, nie zmienia zachowania planów bez znacznika."""
    ZNACZNIK = "**Metoda:** sprzed-metody · 2026-11-24\n"
    ZLY_PLAN = "### Phase 1: A\n**Status:** complete\n"  # bez „Gotowe, gdy” i Dowodu: normalnie kod 1

    def kod(self, tekst, *flagi):
        with tempfile.TemporaryDirectory() as tmp:
            p = plan_w_katalogu(tmp, tekst)
            return uruchom(p, *flagi)

    def test_plan_zamkniety_ze_znacznikiem_przechodzi(self):
        self.assertEqual(self.kod("# P\n\n" + self.ZLY_PLAN)[0], 1)  # kontrola dodatnia: bez znacznika naruszenie
        kod, wyj = self.kod("# P\n\n" + self.ZNACZNIK + "\n" + self.ZLY_PLAN)
        self.assertEqual(kod, 0, wyj)
        self.assertIn("POMINIĘTY: plan sprzed metody (2026-11-24)", wyj)
        self.assertNotIn("NARUSZENIA", wyj)

    def test_plan_bez_faz_ze_znacznikiem_przechodzi(self):
        self.assertEqual(self.kod("# P\n\n- [x] F1\n")[0], 1)  # bez znacznika: „0 faz”
        self.assertEqual(self.kod("# P\n\n" + self.ZNACZNIK + "- [x] F1\n")[0], 0)

    def test_znacznik_z_faza_otwarta_to_naruszenie(self):
        for st in ("pending", "in_progress", "in_progress (05.10)"):
            kod, wyj = self.kod("# P\n\n" + self.ZNACZNIK + "\n" + self.ZLY_PLAN + "\n### Phase 2: B\n**Status:** " + st + "\n")
            self.assertEqual(kod, 1, (st, wyj))
            self.assertIn("znacznik sprzed metody na planie z otwartą fazą 2", wyj)
            self.assertNotIn("POMINIĘTY", wyj)

    def test_skreslony_in_progress_przy_complete_nie_jest_otwarty(self):
        kod, wyj = self.kod("# P\n\n" + self.ZNACZNIK + "\n### Phase 1: A\n**Status:** ~~in_progress (05.10)~~ **complete 06.10**\n")
        self.assertEqual(kod, 0, wyj)

    def test_znacznik_bez_daty_albo_z_zla_data_to_naruszenie(self):
        for pole in ("**Metoda:** sprzed-metody\n", "**Metoda:** sprzed-metody · 2026-13-40\n"):
            kod, wyj = self.kod("# P\n\n" + pole + "\n" + self.ZLY_PLAN)
            self.assertEqual(kod, 1, (pole, wyj))
            self.assertIn("znacznik sprzed metody", wyj)

    def test_inna_wartosc_metody_i_przyklad_w_bloku_nie_wlaczaja_pominiecia(self):
        for tekst in ("# P\n\n**Metoda:** acting-with-files\n\n" + self.ZLY_PLAN,
                      "# P\n\n```\n" + self.ZNACZNIK + "```\n\n" + self.ZLY_PLAN,
                      "# P\n\nTekst o **Metoda:** sprzed-metody · 2026-11-24 w środku zdania\n\n" + self.ZLY_PLAN):
            kod, wyj = self.kod(tekst)
            self.assertEqual(kod, 1, wyj)
            self.assertNotIn("POMINIĘTY", wyj)

    def test_znacznik_nie_stempluje_i_nie_pisze_stanu(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = "# P\n\n" + self.ZNACZNIK + "\n### Phase 1: A\n**Status:** complete\n" + GOTOWE + "**Dowód:** plik /tmp/x.txt zawiera wynik 12\n"
            p = plan_w_katalogu(tmp, t)
            h = md5(p)
            self.assertEqual(uruchom(p)[0], 0)  # bez --tylko-odczyt
            self.assertEqual(h, md5(p))
            self.assertEqual(sorted(x.name for x in Path(tmp).iterdir()), ["task_plan.md"])


if __name__ == "__main__":
    unittest.main()
