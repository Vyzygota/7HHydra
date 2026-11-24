#!/usr/bin/env python3
"""Testy daty_faz.py (stemplowanie `**Start:**`/`**Koniec:**`) i jego związku z kontrolą dowodów.
Uruchomienie: python3 test_daty_faz.py"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime

SK = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SK)
import fazy_planu as F
import daty_faz as D

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


class TestStempluj(Podstawa):
    def test_pierwsze_uruchomienie_nic_nie_dopisuje(self):
        self.zapisz(PLAN)
        msg = D.stempluj_plan(self.plan, T0)
        self.assertEqual(self.czytaj(), PLAN)
        with open(os.path.join(self.kat, ".stan.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["fazy"], {"1": "pending", "2": "in_progress"})
        self.assertTrue(any("pierwsze uruchomienie" in m for m in msg))

    def test_start_pod_statusem_z_zegara_testu_i_koniec_pod_startem(self):
        self.zapisz(PLAN)
        D.stempluj_plan(self.plan, T0)
        self.zapisz(PLAN.replace("**Status:** pending", "**Status:** in_progress"))
        D.stempluj_plan(self.plan, T0)
        self.assertIn("**Status:** in_progress\n**Start:** 2026-10-29 14:07\n**Gotowe, gdy:**", self.czytaj())
        self.zapisz(self.czytaj().replace("**Status:** in_progress\n**Start", "**Status:** complete\n**Start"))
        D.stempluj_plan(self.plan, datetime(2026, 10, 30, 9, 1))
        self.assertIn("**Status:** complete\n**Start:** 2026-10-29 14:07\n**Koniec:** 2026-10-30 09:01\n", self.czytaj())

    def test_idempotencja_wielokrotna(self):
        self.zapisz(PLAN)
        D.stempluj_plan(self.plan, T0)
        self.zapisz(PLAN.replace("**Status:** pending", "**Status:** complete"))
        D.stempluj_plan(self.plan, T0)
        po = self.czytaj()
        for _ in range(5):
            self.assertEqual(D.stempluj_plan(self.plan, datetime(2030, 1, 1, 1, 1)), [])
            self.assertEqual(self.czytaj(), po)

    def test_zapisuj_false_nie_pisze_nic(self):
        self.zapisz(PLAN)
        D.stempluj_plan(self.plan, T0, zapisuj=False)
        self.assertFalse(os.path.exists(os.path.join(self.kat, ".stan.json")))
        D.stempluj_plan(self.plan, T0)
        self.zapisz(PLAN.replace("**Status:** pending", "**Status:** in_progress"))
        przed = self.czytaj()
        msg = D.stempluj_plan(self.plan, T0, zapisuj=False)
        self.assertEqual(self.czytaj(), przed)
        self.assertTrue(any("dopisano" in m for m in msg))  # raportuje, co by dopisal

    def test_nowa_faza_dodana_po_stanie_liczy_sie_jako_pending(self):
        self.zapisz(PLAN)
        D.stempluj_plan(self.plan, T0)
        self.zapisz(PLAN + "\n### Phase 3: C\n**Status:** in_progress\n")
        D.stempluj_plan(self.plan, T0)
        self.assertIn("### Phase 3: C\n**Status:** in_progress\n**Start:** 2026-10-29 14:07", self.czytaj())

    def test_zmiana_dwoch_faz_naraz(self):
        self.zapisz(PLAN)
        D.stempluj_plan(self.plan, T0)
        self.zapisz(PLAN.replace("**Status:** pending", "**Status:** in_progress")
                    .replace("**Status:** In Progress", "**Status:** complete"))
        D.stempluj_plan(self.plan, T0)
        t = self.czytaj()
        self.assertEqual(t.count("**Start:**"), 1)
        self.assertEqual(t.count("**Koniec:**"), 1)
        f = F.wczytaj_plan(self.plan)
        self.assertEqual((f[0]["start_stempel"], f[0]["koniec_stempel"]), (T0, None))
        self.assertEqual((f[1]["start_stempel"], f[1]["koniec_stempel"]), (None, T0))


PLAN_ZAMKNIETY = ("# Plan: X\n\n### Phase 1: A\n**Status:** %s\n**Gotowe, gdy:** plik istnieje\n"
                  "**Dowód:** plik /tmp/x istnieje, 12 wierszy\n")


class TestKontrolaBezDat(Podstawa):
    """Kontrola dowodów działa bez daty_faz.py, a gdy leży obok, zapisuje daty jak dotąd (Phase 22 planu wydania)."""

    def kopia_skryptow(self, z_datami):
        cel = os.path.join(self.kat, "skrypty")
        os.makedirs(cel)
        pliki = ["sprawdz_dowody.py", "fazy_planu.py", "ustawienia_planu.py"] + (["daty_faz.py"] if z_datami else [])
        for p in pliki:
            shutil.copy(os.path.join(SK, p), cel)
        return os.path.join(cel, "sprawdz_dowody.py")

    def uruchom(self, skrypt, *arg):
        env = {k: v for k, v in os.environ.items() if k != "PLAN_USTAWIENIA"}
        return subprocess.run([sys.executable, "-I", skrypt, *arg, self.plan], capture_output=True, text=True, env=env)

    def test_bez_daty_faz_kontrola_dziala_i_nic_nie_stempluje(self):
        skrypt = self.kopia_skryptow(False)
        self.zapisz(PLAN_ZAMKNIETY % "pending")
        self.assertEqual(self.uruchom(skrypt).returncode, 0)
        self.zapisz(PLAN_ZAMKNIETY % "complete")
        w = self.uruchom(skrypt)
        self.assertEqual(w.returncode, 0, w.stdout)
        self.assertNotIn("**Koniec:**", self.czytaj())
        self.assertFalse(os.path.exists(os.path.join(self.kat, ".stan.json")))
        self.assertNotIn("STEMPLE", w.stdout)

    def test_z_daty_faz_zapisuje_daty_jak_dotad(self):
        skrypt = self.kopia_skryptow(True)
        self.zapisz(PLAN_ZAMKNIETY % "pending")
        self.assertEqual(self.uruchom(skrypt).returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.kat, ".stan.json")))
        self.zapisz(PLAN_ZAMKNIETY % "complete")
        w = self.uruchom(skrypt)
        self.assertEqual(w.returncode, 0, w.stdout)
        self.assertIn("**Koniec:** 20", self.czytaj())
        self.assertIn("STEMPLE", w.stdout)

    def test_tylko_odczyt_nie_zmienia_planu_nawet_z_daty_faz(self):
        skrypt = self.kopia_skryptow(True)
        self.zapisz(PLAN_ZAMKNIETY % "pending")
        self.uruchom(skrypt)
        self.zapisz(PLAN_ZAMKNIETY % "complete")
        przed = self.czytaj()
        self.uruchom(skrypt, "--tylko-odczyt")
        self.assertEqual(self.czytaj(), przed)

    def test_samodzielne_daty_faz_cli(self):
        self.zapisz(PLAN_ZAMKNIETY % "pending")
        sk = os.path.join(SK, "daty_faz.py")
        self.assertEqual(subprocess.run([sys.executable, "-I", sk, self.plan], capture_output=True).returncode, 0)
        self.zapisz(PLAN_ZAMKNIETY % "complete")
        w = subprocess.run([sys.executable, "-I", sk, self.plan], capture_output=True, text=True)
        self.assertEqual(w.returncode, 0)
        self.assertIn("dopisano **Koniec:**", w.stdout)
        self.assertEqual(subprocess.run([sys.executable, "-I", sk], capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
