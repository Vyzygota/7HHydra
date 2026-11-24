#!/usr/bin/env python3
"""Testy fazy_planu.py (jeden parser faz; stemplowanie dat: test_daty_faz.py). Uruchomienie: python3 test_fazy_planu.py"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fazy_planu as F

T0 = datetime(2026, 10, 29, 14, 7)
PLAN = ("# Plan: X\n\n### Phase 1: A\n**Status:** pending\n**Gotowe, gdy:** x\n\n"
        "### Phase 2 \u2014 B\n- **Status:** In Progress \u2014 uwaga\n\n## Blokady\n(brak)\n")


class Podstawa(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.kat = self._t.name
        self.plan = os.path.join(self.kat, "task_plan.md")

    def tearDown(self):
        self._t.cleanup()

    def zapisz(self, tekst):
        with open(self.plan, "w", encoding="utf-8", newline="") as f:
            f.write(tekst)

    def czytaj(self):
        with open(self.plan, encoding="utf-8", newline="") as f:
            return f.read()


class TestParser(Podstawa):
    def test_liczba_faz_jak_grep(self):
        self.zapisz(PLAN)
        grep = int(subprocess.run(["grep", "-c", "^### Phase", self.plan], capture_output=True, text=True).stdout)
        self.assertEqual(len(F.wczytaj_plan(self.plan)), grep)
        self.assertEqual(grep, 2)

    def test_status_znormalizowany(self):
        self.zapisz(PLAN)
        f = F.wczytaj_plan(self.plan)
        self.assertEqual([x["status_norm"] for x in f], ["pending", "in_progress"])
        self.assertEqual([x["status"] for x in f], ["pending", "in_progress"])
        self.assertEqual(f[1]["tytul"], "B")

    def test_status_nieznany_i_brak(self):
        f = F.parsuj_plan(["### Phase 1: A", "**Status:** partial", "### Phase 2: B"])
        self.assertEqual([(x["status"], x["status_norm"]) for x in f], [("nieznany", "partial"), ("nieznany", "")])

    def test_nieznormalizowane_naglowki(self):
        linie = ["## Phase 1: a", "### Faza 2: b", "### Phase 3: c", "#### Phase 4: d", "tekst Phase 5"]
        self.assertEqual([n for n, _ in F.nieznormalizowane_naglowki(linie)], [1, 2, 4])
        self.assertEqual(len(F.parsuj_plan(linie)), 1)
        self.assertEqual(len(F.ostrzezenia_formatu(linie, F.parsuj_plan(linie))), 1)
        self.assertEqual(F.ostrzezenia_formatu(["### Phase 1: a"], F.parsuj_plan(["### Phase 1: a"])), [])

    def test_klucze_powtorzonych_numerow(self):
        f = F.parsuj_plan(["### Phase 1: a", "### Phase 1: b", "### Phase 2: c", "### Phase 1: d"])
        self.assertEqual(F.klucze_faz(f), ["1", "1#2", "2", "1#3"])

    def test_daty_pola(self):
        self.assertEqual(F.parsuj_date_godz("2026-10-29 14:07"), (date(2026, 10, 29), datetime(2026, 10, 29, 14, 7)))
        self.assertEqual(F.parsuj_date_godz("2026-10-29"), (date(2026, 10, 29), None))
        self.assertEqual(F.parsuj_date_godz("2026-13-45"), (None, None))
        self.assertEqual(F.parsuj_date_godz("jutro"), (None, None))
        self.assertEqual(F.parsuj_date_godz(None), (None, None))

    def test_pola_po_naglowku_h2_ignorowane(self):
        f = F.parsuj_plan(["### Phase 1: a", "**Status:** pending", "## Korekta", "**Status:** complete", "**Start:** 2026-10-29 10:00"])
        self.assertEqual((f[0]["status"], f[0]["start_stempel"]), ("pending", None))


if __name__ == "__main__":
    unittest.main(verbosity=1)
