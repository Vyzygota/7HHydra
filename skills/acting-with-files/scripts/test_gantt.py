#!/usr/bin/env python3
"""Testy gantt.py. Uruchomienie: python3 test_gantt.py   (inny modul: GANTT_MODUL=/sciezka/gantt.py)."""
import hashlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import date, datetime, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
MODUL = os.environ.get("GANTT_MODUL", os.path.join(AQUI, "gantt.py"))
spec = importlib.util.spec_from_file_location("gantt_pod_testem", MODUL)
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

DZIS = date(2026, 10, 29)
KOLORY_TXT = """# Kolory
| Kto | Rola | Notion | HEX (dashboard, Obsidian) |
|---|---|---|---|
| Piotr | czlowiek | red | #E53935 |
| Tadeusz (Tado) | czlowiek | orange | #FB8C00 |
| Tacyt | orkiestrator | purple | #8E24AA |
| Claudiusz | kod GT | green | #43A047 |
| Geminiusz | recenzja | yellow | #FDD835 |
| Imhotep | srodowisko | - | #00897B |
| nikt / zrobione | - | gray | #9E9E9E |

## Dalej
| Kto | Rola | Notion | HEX (dashboard, Obsidian) | HEX -j |
|---|---|---|---|---|
| Piotr | inny | red | #000001 | #000002 |
"""


def ts(rrrr, mm, dd, h=12, mi=0):
    return int(datetime(rrrr, mm, dd, h, mi, tzinfo=G.TZ).timestamp())


def faza(nr, tytul, status="complete", wyk="claudiusz", kanban="—", extra=""):
    return ("### Phase %s: %s\n**Status:** %s\n**Wykonawca:** %s\n**Kanban:** %s\n%s"
            "**Gotowe, gdy:** x\n**Dowod:** y\n\n" % (nr, tytul, status, wyk, kanban, extra))


class Baza:
    def __init__(self, katalog):
        self.sciezka = os.path.join(katalog, "kanban.db")
        con = sqlite3.connect(self.sciezka)
        con.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, status TEXT, created_at INTEGER,"
                    " started_at INTEGER, completed_at INTEGER)")
        con.commit()
        con.close()

    def karta(self, id_, created, started=None, completed=None, status="done"):
        con = sqlite3.connect(self.sciezka)
        con.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)", (id_, "t", status, created, started, completed))
        con.commit()
        con.close()


class Podstawa(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.kat = self.tmp.name
        self.plan = os.path.join(self.kat, "PLAN-1")
        os.makedirs(self.plan)
        self.baza = Baza(self.kat)
        with open(os.path.join(self.kat, "KOLORY.md"), "w", encoding="utf-8") as f:
            f.write(KOLORY_TXT)
        self.kolory = G.wczytaj_kolory(os.path.join(self.kat, "KOLORY.md"))

    def tearDown(self):
        self.tmp.cleanup()

    def zapisz(self, tresc, progress=None, crlf=False):
        if crlf:
            tresc = tresc.replace("\n", "\r\n")
        with open(os.path.join(self.plan, "task_plan.md"), "w", encoding="utf-8", newline="") as f:
            f.write(tresc)
        if progress is not None:
            with open(os.path.join(self.plan, "progress.md"), "w", encoding="utf-8") as f:
                f.write(progress)

    def licz(self):
        return G.przetworz_plan(self.plan, self.baza.sciezka, DZIS, self.kolory)

    def grep_c(self):
        return int(subprocess.run(["grep", "-c", "^### Phase", os.path.join(self.plan, "task_plan.md")],
                                  capture_output=True, text=True).stdout.strip())


class TestFazy(Podstawa):
    def plan7(self, ostatnia_status="in_progress"):
        t = "# Plan: X\n\n## Fazy\n\n"
        for n in range(1, 7):
            t += faza(n, "Faza %d" % n, "complete", kanban="t_%08x" % n)
        t += faza(7, "Faza 7", ostatnia_status, wyk="tacyt")
        return t

    def test_siedem_faz_zgodne_z_grep(self):
        self.zapisz(self.plan7())
        d = self.licz()
        self.assertEqual(len(d["fazy"]), 7)
        self.assertEqual(len(d["fazy"]), self.grep_c())
        self.assertEqual([f["nr"] for f in d["fazy"]], [str(i) for i in range(1, 8)])
        self.assertEqual(d["fazy"][6]["status"], "in_progress")

    def test_naglowek_h2_pod_ostatnia_faza(self):
        # sekcje `##` po ostatniej fazie (z polami i checkboxami) nie ucinaja ani nie psuja faz
        t = self.plan7() + ("## Blokady\n- [ ] punkt pod sekcja\n\n## Korekta 27.10.2026\n"
                            "**Status:** complete\n**Kanban:** t_deadbeef\n- [x] inny punkt\n")
        self.zapisz(t)
        d = self.licz()
        self.assertEqual(len(d["fazy"]), 7)
        self.assertEqual(len(d["fazy"]), self.grep_c())
        ost = d["fazy"][-1]
        self.assertEqual(ost["status"], "in_progress")
        self.assertEqual(ost["karty"], [])

    def test_pola_z_sekcji_h2_nie_wchodza_do_ostatniej_fazy(self):
        t = (faza(1, "A") + "### Phase 2: Ostatnia bez pol\nbrak pol\n\n"
             "## Korekta\n**Status:** complete\n**Kanban:** t_deadbeef\n**Wykonawca:** piotr\n")
        self.zapisz(t)
        f = self.licz()["fazy"][-1]
        self.assertEqual((f["status"], f["karty"], f["wykonawca"]), ("nieznany", [], None))

    def test_naglowek_h2_miedzy_fazami_nie_konczy_licznika(self):
        t = (faza(1, "A") + "## Przerwa miedzy fazami\n\n" + faza(2, "B", "in_progress")
             + "## Koniec\n\n" + faza(3, "C", "pending"))
        self.zapisz(t)
        d = self.licz()
        self.assertEqual([f["nr"] for f in d["fazy"]], ["1", "2", "3"])
        self.assertEqual(len(d["fazy"]), self.grep_c())

    def test_luki_i_litery_w_numerach(self):
        self.zapisz(faza(2, "A") + faza("4b", "B", "pending") + faza(10, "C", "pending"))
        self.assertEqual([f["nr"] for f in self.licz()["fazy"]], ["2", "4b", "10"])

    def test_crlf(self):
        self.zapisz(self.plan7(), crlf=True)
        d = self.licz()
        self.assertEqual(len(d["fazy"]), 7)
        self.assertEqual(d["fazy"][0]["status"], "complete")
        self.assertEqual(d["fazy"][0]["wykonawca"], "claudiusz")

    def test_plan_bez_faz(self):
        self.zapisz("# Plan\n\n## Cel\nnic\n")
        d = self.licz()
        self.assertEqual(d["fazy"], [])
        self.assertTrue(G.rysuj_svg(d, self.kolory).startswith("<svg"))


class TestDaty(Podstawa):
    def test_faza_bez_dat_to_null(self):
        self.zapisz(faza(1, "Bez dat", "in_progress"))
        f = self.licz()["fazy"][0]
        self.assertIsNone(f["start_real"])
        self.assertIsNone(f["koniec_real"])
        self.assertEqual(f["zrodlo_dat"], "brak")
        svg = G.rysuj_svg(self.licz(), self.kolory)
        self.assertIn('class="brak-dat', svg)
        self.assertNotIn('class="pasek-real"', svg)

    def test_faza_pending_bez_dat_bez_kreski_nie_wiem(self):
        self.zapisz(faza(1, "Jeszcze nie", "pending"))
        svg = G.rysuj_svg(self.licz(), self.kolory)
        self.assertNotIn('class="brak-dat', svg)

    def test_wiele_kart_min_start_max_koniec(self):
        self.baza.karta("t_aaaaaaaa", ts(2026, 10, 20), ts(2026, 10, 21, 9), ts(2026, 10, 22))
        self.baza.karta("t_bbbbbbbb", ts(2026, 10, 19), None, ts(2026, 10, 25, 18))  # bez started_at
        self.baza.karta("t_cccccccc", ts(2026, 10, 10), ts(2026, 10, 10), ts(2026, 10, 12))  # zaleznosc
        self.zapisz(faza(1, "Dwie karty", "complete",
                         kanban="t_aaaaaaaa; t_bbbbbbbb (po t_cccccccc, recenzja)"))
        f = self.licz()["fazy"][0]
        self.assertEqual(f["karty"], ["t_aaaaaaaa", "t_bbbbbbbb"])
        self.assertEqual(f["start_real"], "2026-10-19T12:00")  # created_at karty bez startu
        self.assertEqual(f["koniec_real"], "2026-10-25T18:00")
        self.assertEqual(f["zrodlo_dat"], "kanban")
        self.assertFalse(f["w_toku"])

    def test_karty_po_przecinku_i_zaleznosc_po_poza_nawiasem(self):
        self.assertEqual(G.wyciagnij_karty("t_11111111 (Claudiusz), t_22222222 (AG)"),
                         ["t_11111111", "t_22222222"])
        self.assertEqual(G.wyciagnij_karty("t_11111111 po t_33333333, t_44444444 -> AG t_22222222"),
                         ["t_11111111", "t_22222222"])
        self.assertEqual(G.wyciagnij_karty("—"), [])

    def test_niedomknieta_karta_koniec_null_w_toku(self):
        self.baza.karta("t_aaaaaaaa", ts(2026, 10, 20), ts(2026, 10, 21), ts(2026, 10, 22))
        self.baza.karta("t_bbbbbbbb", ts(2026, 10, 23), ts(2026, 10, 24), None, status="running")
        self.zapisz(faza(1, "W toku", "in_progress", kanban="t_aaaaaaaa; t_bbbbbbbb"))
        f = self.licz()["fazy"][0]
        self.assertEqual(f["start_real"], "2026-10-21T12:00")
        self.assertIsNone(f["koniec_real"])
        self.assertTrue(f["w_toku"])

    def test_karta_nieznana_w_bazie_zgloszona_nie_zgadywana(self):
        self.zapisz(faza(1, "Duch", "complete", kanban="t_99999999"))
        f = self.licz()["fazy"][0]
        self.assertEqual(f["karty_brak_w_bazie"], ["t_99999999"])
        self.assertIsNone(f["start_real"])
        self.assertEqual(f["zrodlo_dat"], "brak")

    def test_brak_bazy_nie_wywraca_przebiegu(self):
        self.zapisz(faza(1, "X", "complete", kanban="t_aaaaaaaa"))
        d = G.przetworz_plan(self.plan, os.path.join(self.kat, "nie-ma.db"), DZIS, self.kolory)
        self.assertEqual(len(d["fazy"]), 1)
        self.assertTrue(d["ostrzezenia"])

    def test_progress_md_dla_fazy_bez_karty(self):
        prog = ("# Postep\n\n- 2026-10-24 08:10 [Tacyt] Phase 3 start; Phase 30 inna\n"
                "- 2026-10-26 Phase 3 zamkniete\n- 2026-10-27 Phase 3b osobna\n"
                "2026-10-28 bez myslnika Phase 3\n- 2026-10-28 Phases 1-4 razem\n"
                "- 2026-10-30 Phase 30 dalej, Phase 3b osobna\n")
        self.zapisz(faza(3, "Bez karty", "complete") + faza(30, "Inna", "in_progress")
                    + faza(4, "Poza", "pending"), progress=prog)
        f3, f30, f4 = self.licz()["fazy"]
        self.assertEqual((f3["start_real"], f3["koniec_real"], f3["zrodlo_dat"]),
                         ("2026-10-24T00:00", "2026-10-28T00:00", "progress.md"))
        self.assertEqual(f30["start_real"], "2026-10-24T00:00")  # 'Phase 30' nie myli sie z 'Phase 3'
        self.assertIsNone(f30["koniec_real"])
        self.assertTrue(f30["w_toku"])
        self.assertIsNone(f4["start_real"])  # pending: wzmianka nie jest startem

    def test_kanban_ma_pierwszenstwo_przed_progress(self):
        self.baza.karta("t_aaaaaaaa", ts(2026, 10, 20), ts(2026, 10, 21), ts(2026, 10, 22))
        self.zapisz(faza(1, "K", "complete", kanban="t_aaaaaaaa"),
                    progress="- 2026-10-01 Phase 1 dawno\n")
        self.assertEqual(self.licz()["fazy"][0]["zrodlo_dat"], "kanban")


class TestTermin(Podstawa):
    def test_termin_w_przeszlosci_flaga(self):
        self.zapisz(faza(1, "Spozniona", "in_progress", extra="**Start:** 2026-10-10\n**Termin:** 2026-10-20\n")
                    + faza(2, "Zrobiona", "complete", extra="**Termin:** 2026-10-01\n")
                    + faza(3, "Przyszla", "pending", extra="**Termin:** 2026-11-05\n")
                    + faza(4, "W dniu", "pending", extra="**Termin:** 2026-10-29\n")
                    + faza(5, "Wczoraj", "pending", extra="**Termin:** 2026-10-28\n"))
        f = self.licz()["fazy"]
        self.assertEqual(f[0]["po_terminie_dni"], 9)
        self.assertEqual(f[0]["start_plan"], "2026-10-10")
        self.assertEqual(f[0]["termin_plan"], "2026-10-20")
        self.assertIsNone(f[1]["po_terminie_dni"])  # complete: nie flagujemy
        self.assertIsNone(f[2]["po_terminie_dni"])
        self.assertIsNone(f[3]["po_terminie_dni"])  # termin dzisiaj nie jest jeszcze po terminie
        self.assertEqual(f[4]["po_terminie_dni"], 1)

    def test_plan_bez_pol_start_termin(self):
        self.zapisz(faza(1, "A") + faza(2, "B", "in_progress"))
        for f in self.licz()["fazy"]:
            self.assertIsNone(f["start_plan"])
            self.assertIsNone(f["termin_plan"])
            self.assertIsNone(f["po_terminie_dni"])

    def test_zla_data_planu_to_null(self):
        self.zapisz(faza(1, "A", "pending", extra="**Termin:** 2026-13-45\n**Start:** jutro\n"))
        f = self.licz()["fazy"][0]
        self.assertIsNone(f["termin_plan"])
        self.assertIsNone(f["start_plan"])


class TestKoloryISvg(Podstawa):
    def test_kolory_z_pliku_nie_zaszyte(self):
        self.zapisz(faza(1, "A", "in_progress", wyk="antygrawiusz") + faza(2, "B", "in_progress", wyk="Tacyt + Piotr")
                    + faza(3, "C", "pending", wyk="imhotepprime") + faza(4, "D", "pending", wyk="ktos obcy"))
        f = self.licz()["fazy"]
        self.assertEqual([x["kolor"] for x in f], ["#FDD835", "#8E24AA", "#00897B", None])
        self.assertEqual([x["wykonawca_klucz"] for x in f], ["geminiusz", "tacyt", "imhotep", None])
        # zmiana pliku = zmiana koloru (nic nie zaszyte w kodzie); druga tabela pliku jest ignorowana
        with open(os.path.join(self.kat, "KOLORY.md"), "w", encoding="utf-8") as fh:
            fh.write(KOLORY_TXT.replace("#8E24AA", "#123456"))
        self.kolory = G.wczytaj_kolory(os.path.join(self.kat, "KOLORY.md"))
        self.assertEqual(self.licz()["fazy"][1]["kolor"], "#123456")
        self.assertEqual(self.kolory["piotr"], "#E53935")

    def test_kolory_z_ukladu_bazy_osob(self):
        # układ pliku generowanego z bazy osób Centrum: kolumna „Kolor” zamiast „HEX”, wiersza „nikt” brak (IP45.6)
        sciezka = os.path.join(self.kat, "OSOBY.md")
        with open(sciezka, "w", encoding="utf-8") as fh:
            fh.write("| Osoba | Rola | Rodzaj | Kolor | Kolor na ciemnym (-j) | Notion | Ikona | Aliasy |\n"
                     "|---|---|---|---|---|---|---|---|\n"
                     "| Tacyt | orkiestrator | agent | `#8e24aa` | `#C27BD6` | purple | `g-tacyt` | default |\n"
                     "| Antygrawiusz Geminiusz | recenzja | agent | `#FDD835` | `#FFE566` | yellow | `g-ag` | ag |\n")
        k = G.wczytaj_kolory(sciezka)
        self.assertEqual(k["tacyt"], "#8E24AA")
        self.assertEqual(k["geminiusz"], "#FDD835")
        self.assertNotIn("nikt", k)  # szary bierze się ze stałej KOLOR_REZERWOWY
        self.assertEqual(G.klucz_wykonawcy("antygrawiusz", k), "geminiusz")

    def test_svg_poprawny_xml_liczby_paskow_i_motyw(self):
        self.baza.karta("t_aaaaaaaa", ts(2026, 10, 20), ts(2026, 10, 21), ts(2026, 10, 22))
        self.baza.karta("t_bbbbbbbb", ts(2026, 10, 23), ts(2026, 10, 24), None, status="running")
        self.zapisz(faza(1, "Zrobiona <&>", "complete", kanban="t_aaaaaaaa",
                         extra="**Start:** 2026-10-20\n**Termin:** 2026-10-23\n")
                    + faza(2, "W toku", "in_progress", kanban="t_bbbbbbbb")
                    + faza(3, "Bez dat", "in_progress")
                    + faza(4, "Pending", "pending"))
        svg = G.rysuj_svg(self.licz(), self.kolory)
        kor = ET.fromstring(svg)  # poprawny XML (znaki specjalne w tytule)
        klasy = [e.get("class", "") for e in kor.iter()]
        self.assertEqual(sum(1 for k in klasy if k.split()[:1] == ["pasek-real"]), 2)
        self.assertEqual(sum(1 for k in klasy if k.split()[:1] == ["pasek-plan"]), 1)
        self.assertEqual(sum(1 for k in klasy if k.startswith("brak-dat")), 1)
        self.assertIn("var(--foreground", svg)
        self.assertNotIn("http://fonts", svg)
        self.assertNotIn("@import", svg)
        self.assertNotIn("<image", svg)

    def test_zapis_plikow_json_i_svg(self):
        self.zapisz(faza(1, "A", "complete"))
        wy = os.path.join(self.kat, "wy")
        G.zapisz(self.licz(), wy, self.kolory)
        with open(os.path.join(wy, "gantt.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        self.assertEqual(set(d), {"plan", "tytul", "sciezka", "wygenerowano", "dzis", "fazy", "ostrzezenia",
                                  "data", "links", "potok", "aktywnosc"})  # P3: + tytul i ksztalt DHTMLX (data, links); 31.10: + potok, aktywnosc
        for k in ("nr", "tytul", "status", "wykonawca", "karty", "start_plan", "termin_plan",
                  "start_real", "koniec_real", "zrodlo_dat", "po_terminie_dni"):
            self.assertIn(k, d["fazy"][0])
        ET.parse(os.path.join(wy, "gantt.svg"))

    def test_baza_tylko_do_odczytu(self):
        self.baza.karta("t_aaaaaaaa", ts(2026, 10, 20), ts(2026, 10, 21), ts(2026, 10, 22))
        self.zapisz(faza(1, "A", "complete", kanban="t_aaaaaaaa"))
        def sha():
            with open(self.baza.sciezka, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        przed = sha()
        wywolania = []
        oryg = G.sqlite3.connect

        def podglad(*a, **k):
            wywolania.append((a, k))
            return oryg(*a, **k)
        G.sqlite3.connect = podglad
        try:
            self.licz()
        finally:
            G.sqlite3.connect = oryg
        self.assertEqual(sha(), przed)
        self.assertTrue(wywolania)
        for a, k in wywolania:  # kazde polaczenie z kodu: URI z mode=ro
            self.assertIn("mode=ro", a[0])
            self.assertTrue(k.get("uri"))
        con = sqlite3.connect(wywolania[0][0][0], uri=True)
        with self.assertRaises(sqlite3.OperationalError):
            con.execute("DELETE FROM tasks")
        con.close()

    def test_cli_pojedynczy_plan_i_wyjscie(self):
        self.zapisz(faza(1, "A", "complete"))
        wy = os.path.join(self.kat, "wy2")
        rc = G.main([self.plan, "--wyjscie", wy, "--db", self.baza.sciezka, "--dzis", "2026-10-29",
                     "--kolory", os.path.join(self.kat, "KOLORY.md")])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(wy, "gantt.svg")))
        self.assertFalse(os.path.exists(os.path.join(self.plan, "gantt.json")))  # plan nietkniety


POLA_KONTRAKTU = {"start_plan", "termin_plan", "start_real", "koniec_real", "zrodlo_dat", "po_terminie_dni"}


class TestStemple(Podstawa):
    """Stemple `**Start:**` / `**Koniec:**` z planu wygrywaja z Kanbanem i progress.md."""

    def test_stempel_wygrywa_z_kanbanem(self):
        self.baza.karta("t_00000001", ts(2026, 10, 20), ts(2026, 10, 20), ts(2026, 10, 21), "done")
        self.zapisz(faza(1, "A", "complete", kanban="t_00000001",
                         extra="**Start:** 2026-10-25 09:15\n**Koniec:** 2026-10-27 18:40\n"))
        f = self.licz()["fazy"][0]
        self.assertEqual((f["start_real"], f["koniec_real"]), ("2026-10-25T09:15", "2026-10-27T18:40"))
        self.assertEqual((f["zrodlo_dat"], f["zrodlo_start"], f["zrodlo_koniec"]), ("stempel", "stempel", "stempel"))
        self.assertIsNone(f["start_plan"])  # Start z godzina to NIE plan

    def test_start_bez_godziny_to_plan_nie_stempel(self):
        self.zapisz(faza(1, "A", "in_progress", extra="**Start:** 2026-10-20\n**Termin:** 2026-10-22\n"))
        f = self.licz()["fazy"][0]
        self.assertEqual((f["start_plan"], f["start_real"]), ("2026-10-20", None))

    def test_start_plan_ma_pierwszenstwo(self):
        self.zapisz(faza(1, "A", "pending", extra="**Start plan:** 2026-11-01\n**Start:** 2026-10-20\n"))
        self.assertEqual(self.licz()["fazy"][0]["start_plan"], "2026-11-01")

    def test_koniec_tylko_przy_complete(self):
        self.zapisz(faza(1, "A", "in_progress", extra="**Start:** 2026-10-25 09:15\n**Koniec:** 2026-10-27 18:40\n"))
        f = self.licz()["fazy"][0]
        self.assertIsNone(f["koniec_real"])
        self.assertTrue(f["w_toku"])

    def test_sam_koniec_to_kamien_milowy(self):
        self.zapisz(faza(1, "A", "complete", extra="**Koniec:** 2026-10-27 18:40\n"))
        d = self.licz()
        z = d["data"][1]
        self.assertEqual((z["type"], z["start_date"], z["bez_daty"]), ("milestone", "2026-10-27 18:40", False))
        self.assertNotIn("end_date", z)

    def test_stempel_koniec_przed_startem_ostrzega(self):
        self.zapisz(faza(1, "A", "complete", extra="**Start:** 2026-10-27 18:40\n**Koniec:** 2026-10-25 09:15\n"))
        self.assertTrue(any("wczesniej niz start" in o for o in self.licz()["ostrzezenia"]))


class TestDhtmlx(Podstawa):
    def tekst_planu(self):
        return ("# Plan: Przyklad\n\n" + faza(1, "Zrobiona", "complete", extra="**Start:** 2026-10-25 09:15\n"
                                                    "**Koniec:** 2026-10-27 18:40\n")
                + faza(2, "W toku", "in_progress", extra="**Start:** 2026-10-28 08:00\n")
                + faza(3, "Plan", "pending", extra="**Start plan:** 2026-11-01\n**Termin:** 2026-11-05\n")
                + faza(4, "Bez dat", "pending"))

    def test_ksztalt_projekt_i_dzieci(self):
        self.zapisz(self.tekst_planu())
        d = self.licz()
        proj, *dzieci = d["data"]
        self.assertEqual((proj["id"], proj["type"], proj["parent"], proj["text"]), ("PLAN-1", "project", 0, "Przyklad"))
        self.assertEqual(len(dzieci), 4)
        self.assertEqual([x["parent"] for x in dzieci], ["PLAN-1"] * 4)
        self.assertEqual(len({x["id"] for x in d["data"]}), 5)  # id unikalne
        self.assertEqual(proj["progress"], 0.25)  # 1 z 4 faz complete
        self.assertEqual([x["progress"] for x in dzieci], [1.0, 0.5, 0.0, 0.0])
        self.assertTrue(all(0 <= x["progress"] <= 1 for x in d["data"]))
        self.assertEqual((proj["start_date"], proj["end_date"]), ("2026-10-25 09:15", "2026-11-06 00:00"))

    def test_daty_rzeczywiste_potem_planowane_potem_bez_daty(self):
        self.zapisz(self.tekst_planu())
        z1, z2, z3, z4 = self.licz()["data"][1:]
        self.assertEqual((z1["start_date"], z1["end_date"], z1["zrodlo_osi"]), ("2026-10-25 09:15", "2026-10-27 18:40", "real"))
        self.assertEqual((z2["start_date"], z2["end_date"]), ("2026-10-28 08:00", "2026-10-29 23:59"))  # w toku: do "teraz"
        self.assertEqual((z3["start_date"], z3["end_date"], z3["zrodlo_osi"]), ("2026-11-01 00:00", "2026-11-06 00:00", "plan"))
        self.assertEqual(z3["start_plan"], "2026-11-01")

    def test_faza_bez_daty_jawnie_bez_pol_dat(self):
        self.zapisz(self.tekst_planu())
        z4 = self.licz()["data"][4]
        self.assertTrue(z4["bez_daty"])
        self.assertTrue(z4["unscheduled"])
        self.assertNotIn("start_date", z4)  # brak klucza, nie null
        self.assertNotIn("end_date", z4)
        for z in self.licz()["data"]:
            for k in ("start_date", "end_date"):
                if k in z:
                    self.assertRegex(z[k], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

    def test_pending_z_karta_kanban_nie_ma_osi_rzeczywistej(self):
        self.baza.karta("t_00000009", ts(2026, 10, 28), None, None, "ready")
        self.zapisz(faza(1, "Czeka", "pending", kanban="t_00000009"))
        d = self.licz()
        self.assertEqual(d["fazy"][0]["start_real"], "2026-10-28T12:00")  # kontrakt: pole zostaje
        z = d["data"][1]
        self.assertTrue(z["bez_daty"])
        self.assertNotIn("start_date", z)

    def test_linki_typ_0_z_kolejnosci_faz(self):
        self.zapisz(self.tekst_planu())
        l = self.licz()["links"]
        self.assertEqual(len(l), 3)
        self.assertEqual([(x["source"], x["target"], x["type"]) for x in l],
                         [("PLAN-1:1", "PLAN-1:2", "0"), ("PLAN-1:2", "PLAN-1:3", "0"), ("PLAN-1:3", "PLAN-1:4", "0")])
        self.assertEqual([x["aktywny"] for x in l], [True, True, False])  # ostatnia faza bez dat
        self.assertEqual(len({x["id"] for x in l}), 3)

    def test_pola_kontraktu_zachowane_w_data_i_fazy(self):
        self.zapisz(self.tekst_planu())
        d = self.licz()
        for f in d["fazy"]:
            self.assertTrue(POLA_KONTRAKTU <= set(f), set(f))
        for z in d["data"][1:]:
            self.assertTrue(POLA_KONTRAKTU <= set(z), set(z))

    def test_plan_bez_faz_to_projekt_bez_dat_i_bez_linkow(self):
        self.zapisz("# Plan: Pusty\n\nbrak faz\n")
        d = self.licz()
        self.assertEqual(len(d["data"]), 1)
        self.assertEqual(d["links"], [])
        self.assertTrue(d["data"][0]["bez_daty"])
        self.assertEqual(d["data"][0]["progress"], 0.0)

    def test_powtorzony_numer_fazy_ma_unikalne_id(self):
        self.zapisz(faza(1, "A", "complete") + faza(1, "A2", "pending"))
        ids = [x["id"] for x in self.licz()["data"]]
        self.assertEqual(ids, ["PLAN-1", "PLAN-1:1", "PLAN-1:1#2"])

    def test_json_serializowalny_bez_nan(self):
        self.zapisz(self.tekst_planu())
        json.dumps(self.licz(), allow_nan=False)


class TestWspolnyParser(Podstawa):
    def test_naglowki_innej_formy_nie_sa_fazami_ale_ostrzegaja(self):
        t = ("# Plan: X\n\n## Faza 1: stara\n**Status:** complete\n\n### Faza 2: stara\n**Status:** pending\n\n"
             "## Phase 3: tez zle\n" + faza(1, "Dobra", "pending"))
        self.zapisz(t)
        d = self.licz()
        self.assertEqual(len(d["fazy"]), 1)
        self.assertEqual(len(d["fazy"]), self.grep_c())
        self.assertTrue(any("3 nagł" in o for o in d["ostrzezenia"]), d["ostrzezenia"])

    def test_gantt_i_plany_licza_to_samo(self):
        """gantt.parsuj_plan i fazy_planu.parsuj_plan to jedna funkcja (jeden parser)."""
        self.assertIs(G.parsuj_plan, G.fazy_planu.parsuj_plan)

    def test_status_ze_spacja_i_wielkimi_literami(self):
        self.zapisz(faza(1, "A", "In Progress"))
        self.assertEqual(self.licz()["fazy"][0]["status"], "in_progress")

    def test_tytul_po_myslniku(self):
        self.zapisz("### Phase 7 \u2014 porzadki\n**Status:** pending\n")
        self.assertEqual(self.licz()["fazy"][0]["tytul"], "porzadki")


class TestPrognoza(Podstawa):
    """GANTT-CZAS-20261111 Phase 40: prognoza czasu otwartych faz i lancuch zaleznosci (harmonogram_faz.py)."""
    CHWILA = datetime(2026, 10, 30, 8, 0)
    SZAC = {"PLAN-1:2": {"praca_h": 2.0, "czas_h": 2.0}, "PLAN-1:3": {"praca_h": 3.0, "czas_h": 3.0},
            "PLAN-2:1": {"praca_h": 1.0, "czas_h": 1.0}}

    def setUp(self):
        super().setUp()
        import harmonogram_faz as hf
        self.hf = hf
        self.plan2 = os.path.join(self.kat, "PLAN-2")
        os.makedirs(self.plan2)
        self._potok = hf.potok
        hf.potok = lambda spec=None: ({}, {})   # bez SPEC-GT: zaleznosci miedzyplanowe tylko tam, gdzie test je ustawia

    def tearDown(self):
        self.hf.potok = self._potok
        super().tearDown()

    def plan1(self, status2="pending"):
        return faza(1, "Zrobione", "complete") + faza(2, "Praca A", status2) + faza(3, "Praca B", "pending")

    def dane(self, szac=None, reka=None, chwila=None, plan1=None, katalog1=None):
        self.zapisz(plan1 or self.plan1())
        with open(os.path.join(self.plan2, "task_plan.md"), "w", encoding="utf-8") as f:
            f.write(faza(1, "Inny plan", "pending"))
        lista = [G.przetworz_plan(katalog1 or self.plan, self.baza.sciezka, DZIS, self.kolory),
                 G.przetworz_plan(self.plan2, self.baza.sciezka, DZIS, self.kolory)]
        return G.naloz_prognoze(lista, chwila or self.CHWILA, szac=self.SZAC if szac is None else szac,
                                reka={} if reka is None else reka)

    def zad(self, lista, plan, nr):
        d = next(x for x in lista if x["plan"] == plan)
        return next(t for t in d["data"][1:] if t["id"] == "%s:%s" % (plan, nr))

    def test_pending_dostaje_daty_z_prognozy_a_complete_zostaje(self):
        przed = G.przetworz_plan(self.plan, self.baza.sciezka, DZIS, self.kolory) if (self.zapisz(self.plan1()) or True) else None
        f1_przed = dict(przed["data"][1])
        d = self.dane()
        f1, f2 = self.zad(d, "PLAN-1", "1"), self.zad(d, "PLAN-1", "2")
        self.assertEqual(f1, f1_przed)   # complete: bez zmian (daty rzeczywiste)
        self.assertEqual((f2["zrodlo_osi"], f2["bez_daty"]), ("prognoza", False))
        self.assertNotIn("unscheduled", f2)
        self.assertEqual((f2["start_date"], f2["end_date"]), ("2026-10-30 08:00", "2026-10-30 10:00"))
        self.assertEqual(set(f2["prognoza"]["warianty"]), {"optymistyczny", "oczekiwany", "pesymistyczny"})
        self.assertEqual(f2["prognoza"]["praca_h"], 2.0)
        self.assertEqual(f2["status"], "pending")   # kontrakt: status i pola rzeczywiste nietkniete
        self.assertIsNone(f2["start_real"])

    def test_lancuch_faz_planu_i_strzalka_aktywna(self):
        d = self.dane()
        f3 = self.zad(d, "PLAN-1", "3")
        self.assertEqual((f3["start_date"], f3["end_date"]), ("2026-10-30 10:00", "2026-10-30 13:00"))
        pl = next(x for x in d if x["plan"] == "PLAN-1")
        # F1 complete bez dat (nie wymyslamy dat rzeczywistych) -> strzalka F1->F2 nieaktywna; F2->F3 (obie z prognozy) aktywna
        self.assertEqual([l["aktywny"] for l in pl["links"]], [False, True])
        self.assertEqual(pl["data"][0]["end_date"], "2026-10-30 13:00")
        self.assertEqual(pl["prognoza"]["koniec"]["oczekiwany"], "2026-10-30 13:00")

    def test_warianty_uporzadkowane(self):
        d = self.dane()
        k = self.zad(d, "PLAN-1", "3")["prognoza"]["warianty"]
        self.assertLess(k["optymistyczny"]["koniec"], k["oczekiwany"]["koniec"])
        self.assertLess(k["oczekiwany"]["koniec"], k["pesymistyczny"]["koniec"])

    def test_adaptacja_dzis_plus_doba_przesuwa_prognoze(self):
        a = self.dane(chwila=self.CHWILA)
        b = self.dane(chwila=self.CHWILA + timedelta(days=1))
        for nr in ("2", "3"):
            ta, tb = self.zad(a, "PLAN-1", nr), self.zad(b, "PLAN-1", nr)
            self.assertEqual(datetime.fromisoformat(tb["end_date"]) - datetime.fromisoformat(ta["end_date"]), timedelta(days=1))
            self.assertEqual(datetime.fromisoformat(tb["start_date"]) - datetime.fromisoformat(ta["start_date"]), timedelta(days=1))

    def test_adaptacja_zamkniecie_fazy_skraca_nastepnika_o_jej_czas(self):
        przed = self.dane()
        kopia = os.path.join(self.kat, "kopia", "PLAN-1")   # kopia planu: oryginalu nie ruszamy
        os.makedirs(kopia)
        with open(os.path.join(kopia, "task_plan.md"), "w", encoding="utf-8") as f:
            f.write(self.plan1("complete"))
        po = self.dane(plan1=self.plan1("pending"), katalog1=kopia)   # druga lista liczona z kopii z F2 complete
        k_przed = datetime.fromisoformat(self.zad(przed, "PLAN-1", "3")["end_date"])
        k_po = datetime.fromisoformat(self.zad(po, "PLAN-1", "3")["end_date"])
        self.assertEqual(k_przed - k_po, timedelta(hours=2))   # czas F2 z szacunku
        with open(os.path.join(self.plan, "task_plan.md"), encoding="utf-8") as f:
            self.assertIn("**Status:** pending", f.read())   # oryginal bez zmian

    def test_in_progress_zachowuje_start_rzeczywisty(self):
        self.zapisz(self.plan1("in_progress"), progress="- 2026-10-29 Phase 2 start\n")
        d = self.dane(plan1=self.plan1("in_progress"))
        f2 = self.zad(d, "PLAN-1", "2")
        przed = G.przetworz_plan(self.plan, self.baza.sciezka, DZIS, self.kolory)["data"][2]
        self.assertEqual((f2["zrodlo_osi"], f2["start_date"]), ("prognoza", przed["start_date"]))
        self.assertGreaterEqual(f2["end_date"], "2026-10-30 08:15")   # nie wczesniej niz teraz + 15 min

    def test_reczny_szacunek_wygrywa(self):
        d = self.dane(reka={"PLAN-1:2": {"praca_h": 10.0, "czas_h": 10.0}})
        f2 = self.zad(d, "PLAN-1", "2")
        self.assertEqual(f2["end_date"], "2026-10-30 18:00")
        self.assertEqual(f2["prognoza"]["znacznik"], "reczne")

    def test_faza_bez_wpisu_dostaje_szacunek_auto(self):
        d = self.dane(szac={})
        f2 = self.zad(d, "PLAN-1", "2")
        self.assertEqual(f2["prognoza"]["znacznik"], "auto")
        self.assertGreater(f2["prognoza"]["praca_h"], 0)

    def test_zaleznosc_miedzyplanowa_z_potoku(self):
        self.hf.potok = lambda spec=None: ({"001": {"kolejnosc": 1, "plan": "PLAN-1", "zalezy": "—"},
                                            "002": {"kolejnosc": 2, "plan": "PLAN-2", "zalezy": "001"}},
                                           {"001": "PLAN-1", "002": "PLAN-2"})
        d = self.dane()
        p2 = next(x for x in d if x["plan"] == "PLAN-2")
        self.assertEqual([(l["source"], l["target"]) for l in p2["links_x"]], [("PLAN-1:3", "PLAN-2:1")])
        self.assertEqual(self.zad(d, "PLAN-2", "1")["start_date"], "2026-10-30 13:00")   # po koncu ostatniej fazy PLAN-1
        self.assertEqual(self.zad(d, "PLAN-1", "3")["prognoza"]["warianty"]["oczekiwany"]["koniec"], "2026-10-30 13:00")
        # plan zalezny widoczny sam (poprzednik ukryty): strzalka znika, nic o ukrytym planie nie zostaje
        G.przytnij_odnosniki([p2])
        self.assertEqual(p2["links_x"], [])
        self.assertNotIn("PLAN-1", json.dumps(p2["links_x"]))

    def test_json_serializowalny_i_kontrakt_dhtmlx(self):
        d = self.dane()
        json.dumps(d, allow_nan=False)
        for x in d:
            for t in x["data"][1:]:
                self.assertIn("id", t)
                self.assertIn("start_date", t) if t["status"] != "complete" else None

    def test_czas_przeliczenia_218_faz_ponizej_5_s(self):
        import time
        lista = []
        for i in range(60):   # 60 planow x 4 fazy otwarte = 240 faz
            kat = os.path.join(self.kat, "P%02d" % i)
            os.makedirs(kat)
            with open(os.path.join(kat, "task_plan.md"), "w", encoding="utf-8") as f:
                f.write("# Plan: P%d\n\n" % i + faza(1, "z", "complete") + faza(2, "a", "pending") + faza(3, "b", "pending", wyk="tacyt")
                        + faza(4, "c", "pending", wyk="sokrates") + faza(5, "d", "in_progress"))
            lista.append(G.przetworz_plan(kat, self.baza.sciezka, DZIS, self.kolory))
        t0 = time.time()
        G.naloz_prognoze(lista, self.CHWILA, szac={}, reka={})
        self.assertLess(time.time() - t0, 5.0)



class TestKolejnoscZaparkowane(unittest.TestCase):
    """t_02a664f6: niezgodności „powyżej bramki” nie obejmują kart zaparkowanych (reguła 8)."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import kolejnosc
        self.k = kolejnosc

    def test_zaparkowane(self):
        z = self.k.zaparkowana
        self.assertTrue(z({"status": "scheduled"}))
        self.assertTrue(z({"status": "todo", "niespelnieni_rodzice": 2}))

    def test_nie_zaparkowane(self):
        z = self.k.zaparkowana
        for c in ({"status": "ready"}, {"status": "running"}, {"status": "todo"},
                  {"status": "blocked"}, {"status": "todo", "niespelnieni_rodzice": 0}):
            self.assertFalse(z(c), c)

    def test_ready_powyzej_bramki_zgloszona(self):
        k = self.k
        mp = {"spec": "x", "warstwy_gotowe": [], "linia_gotowosci": True, "rzeczy": [
            {"kolejnosc": 1, "rozdzial": "010", "rzecz": "r", "plan": "P", "wdrozenie": None, "warstwy": [3],
             "bramka": 3, "stan": "BRAK", "stan_opis": "BRAK"}]}
        plan = {"fazy": [{"nr": "10", "tytul": "f", "status": "pending",
                          "karty": ["t_a", "t_b", "t_c"]}]}
        karty = {"t_a": {"status": "ready", "priority": 0}, "t_b": {"status": "scheduled", "priority": 0},
                 "t_c": {"status": "todo", "priority": 0, "niespelnieni_rodzice": 1}}
        sm = (k.mapa, k.gantt.przetworz_plan, k.priorytety, k.fazy_rzeczy, os.path.isdir)
        try:
            k.mapa = lambda p: mp
            k.gantt.przetworz_plan = lambda d: plan
            k.priorytety = lambda ids: karty
            k.fazy_rzeczy = lambda rz, pl: pl["fazy"]
            os.path.isdir = lambda p: True
            w = k.kolejnosc("X")
        finally:
            k.mapa, k.gantt.przetworz_plan, k.priorytety, k.fazy_rzeczy, os.path.isdir = sm
        self.assertEqual([n["karta"] for n in w["niezgodnosci"]], ["t_a"])

    def test_adnotuj_gantt_warstwy(self):
        """t_af53c0ce: faza dostaje wiersz mapy (najniższa kolejność przy kilku), czeka = nieodblokowane warstwy; projekt bez mapy bez zmian."""
        k = self.k
        mp = {"spec": "x", "warstwy_gotowe": [0], "linia_gotowosci": True, "rzeczy": [
            {"kolejnosc": 1, "rozdzial": "010", "rzecz": "r1", "plan": "P", "wdrozenie": {"fazy": [10]}, "warstwy": [0],
             "bramka": 0, "stan": "BRAK", "stan_opis": "BRAK"},
            {"kolejnosc": 5, "rozdzial": "020", "rzecz": "r5", "plan": "P", "wdrozenie": {"fazy": [20, 10]}, "warstwy": [3],
             "bramka": 3, "stan": "BRAK", "stan_opis": "BRAK"}]}
        plan = {"fazy": [{"nr": "10", "tytul": "a", "status": "pending", "karty": []},
                         {"nr": "20", "tytul": "b", "status": "in_progress", "karty": []}]}
        def pl(sciezka, nr_ids):
            return {"plan": "P", "sciezka": sciezka, "data": [{"id": "P"}] + [{"id": "P:%s" % n} for n in nr_ids]}
        gt, inny = pl("/srv/projekty/X/.planning/P", ["10", "20", "30"]), pl("/srv/projekty/Y/.planning/P", ["10"])
        sm = (k.mapa, k.gantt.przetworz_plan, k.priorytety, os.path.isdir)
        try:
            k.mapa = lambda p: mp if p == "X" else None
            k.gantt.przetworz_plan = lambda d: plan
            k.priorytety = lambda ids: {}
            os.path.isdir = lambda p: True
            k.adnotuj_gantt([gt, inny])
        finally:
            k.mapa, k.gantt.przetworz_plan, k.priorytety, os.path.isdir = sm
        f = {x["id"]: x.get("warstwa") for x in gt["data"][1:]}
        self.assertEqual(f["P:10"]["kolejnosc"], 1)           # faza w dwóch wierszach → najniższa kolejność
        self.assertEqual(f["P:10"]["czeka"], [])
        self.assertEqual(f["P:20"]["kolejnosc"], 5)
        self.assertEqual(f["P:20"]["czeka"], [1, 2])          # warstwy 1–2 nie są gotowe (gotowa tylko 0)
        self.assertIsNone(f["P:30"])                          # faza bez wiersza: brak klucza
        self.assertEqual(gt["warstwy"]["gotowe"], [0])
        self.assertNotIn("warstwy", inny)                     # projekt bez mapy nietknięty
        self.assertNotIn("warstwa", inny["data"][1])

if __name__ == "__main__":
    unittest.main(verbosity=2)
