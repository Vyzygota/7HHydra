#!/usr/bin/env python3
"""kolejnosc.py — co budować teraz według mapy warstw projektu (31.10.2026; plan KOLEJNOSC-MCP-20261031).

Orkiestrator czyta szeregowanie z mapy warstw (SPEC projektu, Dodatek A) i działa według niego; ten sam rdzeń obsługuje
serwer MCP i konsolę zespołu. Tylko odczyt: SPEC projektu, plany (.planning, przez gantt.py), baza kart (mode=ro).
Ścieżki i wzorce z pliku ustawień (`--ustawienia PLIK`, ustawienia_planu.py).

Źródła (Dodatek A specyfikacji projektu, rev 148+):
  <!-- mapa-warstw:poczatek --> | kolejność | rozdział | rzecz | plan | warstwy | bramka | stan | <!-- mapa-warstw:koniec -->
  <!-- warstwy-gotowe: 0,1 -->  — ogłoszone przez właścicieli projektu (rejestr decyzji); brak albo „—” = żadna
  stan: pierwsze słowo GOTOWE / CZĘŚCIOWE / BRAK (audyt kodu ↔ SPEC); inne = „nieaudytowane”.
Reguły (Dodatek A, zasady 1, 4, 5): kod rzeczy wolno pisać, gdy wszystkie warstwy niższe od bramki są gotowe;
priorytet karty kodu = 8 − bramka; naprawa fundamentu = 9 (narzędzie jej nie rozpoznaje — oznacza orkiestrator).

Użycie: kolejnosc.py <projekt> [--json] [--ustawienia PLIK]
"""
import glob, json, os, re, sqlite3, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ustawienia_planu  # noqa: E402

if __name__ == "__main__":
    ustawienia_planu.ustaw_z_argv(sys.argv)  # `--ustawienia PLIK` przed odczytem stałych poniżej
import gantt  # noqa: E402  (ten sam katalog skilla: przetworz_plan, stan faz i kart)

_UST = ustawienia_planu.wczytaj()
KANBAN = _UST["kanban_db"]
STANY = ("GOTOWE", "CZĘŚCIOWE", "BRAK")


def spec_projektu(projekt):
    for plik in sorted(glob.glob(_UST["spec_glob"].format(projekt=projekt), recursive=True)):
        tekst = open(plik, encoding="utf-8").read()
        if "<!-- mapa-warstw:poczatek -->" in tekst:
            return plik, tekst
    return None, ""


def wiersze_tabeli(blok):
    out = []
    for w in blok.splitlines():
        k = [x.strip() for x in w.strip().strip("|").split("|")]
        if len(k) >= 7 and k[0].isdigit():
            out.append(k)
    return out


def _znacznik_wdrozenia(projekt, stan):
    """14.11.2026 (t_54d1be03): jawny znacznik w komórce „stan” — `Wdrożenie: Phase <nn>[, <nn>] [(SPEC-NNN)]`.
    Wiąże wiersz mapy z fazami planu (numer § w opisie rzeczy już nie wystarcza dla wierszy bez §); plan z nawiasu
    rozwiązywany po prefiksie katalogu (.planning/SPEC-NNN-*), gdy kolumna `plan` jest pusta."""
    m = re.search(r"Wdrożenie:\s*Phase\s*(\d+(?:\s*[,+]\s*\d+)*)(?:\s*\((SPEC-\d+[^)]*)\))?", stan)
    if not m:
        return None
    plan = None
    if m.group(2):
        trafienia = sorted(glob.glob(_UST["katalog_planu"].format(projekt=projekt, plan=m.group(2).strip()) + "*"))
        trafienia = [t for t in trafienia if os.path.isdir(t)]
        if len(trafienia) == 1:
            plan = os.path.basename(trafienia[0])
    return {"fazy": [int(x) for x in re.findall(r"\d+", m.group(1))], "plan": plan}


def mapa(projekt):
    plik, tekst = spec_projektu(projekt)
    if not plik:
        return None
    m = re.search(r"<!-- mapa-warstw:poczatek -->(.*?)<!-- mapa-warstw:koniec -->", tekst, re.S)
    g = re.search(r"<!--\s*warstwy-gotowe:\s*([^>]*?)\s*-->", tekst)
    gotowe = sorted({int(x) for x in re.findall(r"\d+", g.group(1))}) if g else []
    rzeczy = []
    for k in wiersze_tabeli(m.group(1) if m else ""):
        stan = k[6]
        # werdykt audytu wielkimi literami na początku komórki („brak szkicu v2” sprzed audytu to NIE werdykt BRAK)
        slowo = next((s for s in STANY if re.match(r"%s\b" % s, stan)), "nieaudytowane")
        plan_k = k[3] if k[3] not in ("—", "-", "") else None
        wdr = _znacznik_wdrozenia(projekt, stan)
        if wdr and not plan_k:
            plan_k = wdr["plan"]
        rzeczy.append({"kolejnosc": int(k[0]), "rozdzial": k[1], "rzecz": k[2], "plan": plan_k, "wdrozenie": wdr,
                       "warstwy": [int(x) for x in re.findall(r"\d+", k[4])], "bramka": int(k[5]) if k[5].isdigit() else 0,
                       "stan": slowo, "stan_opis": stan})
    return {"spec": plik, "warstwy_gotowe": gotowe, "linia_gotowosci": bool(g), "rzeczy": rzeczy}


def priorytety(ids):
    if not ids or not KANBAN or not os.path.exists(KANBAN):
        return {}
    con = sqlite3.connect("file:%s?mode=ro" % KANBAN, uri=True, timeout=10)
    try:
        q = "SELECT id, priority, status, assignee, title FROM tasks WHERE id IN (%s)" % ",".join("?" * len(ids))
        out = {r[0]: {"priority": r[1], "status": r[2], "assignee": r[3], "title": r[4]} for r in con.execute(q, list(ids))}
        # 14.11.2026 (t_02a664f6): rodzice niespełnieni (status ≠ done/archived) — do rozpoznania kart zaparkowanych
        ql = ("SELECT l.child_id, COUNT(*) FROM task_links l JOIN tasks p ON p.id = l.parent_id "
              "WHERE p.status NOT IN ('done','archived') AND l.child_id IN (%s) GROUP BY l.child_id" % ",".join("?" * len(ids)))
        for cid, n in con.execute(ql, list(ids)):
            if cid in out:
                out[cid]["niespelnieni_rodzice"] = n
        return out
    finally:
        con.close()


def zaparkowana(c):
    """Karta już „czeka” wg reguły 8: `scheduled` (termin) albo `todo` z niespełnionym rodzicem — dyspozytor jej nie uruchomi."""
    return c.get("status") == "scheduled" or (c.get("status") == "todo" and c.get("niespelnieni_rodzice", 0) > 0)


def fazy_rzeczy(rz, plan):
    """Fazy planu, których dotyczy rzecz: §NNN.PP w opisie → Phase PP; „cały rozdział” albo brak § → wszystkie fazy."""
    if not plan:
        return []
    if rz.get("wdrozenie"):  # jawny znacznik „Wdrożenie: Phase” ma pierwszeństwo
        return [f for f in plan["fazy"] if int(f["nr"]) in rz["wdrozenie"]["fazy"]]
    numery = re.findall(r"§%s\.(\d+)" % re.escape(rz["rozdzial"]), rz["rzecz"])
    if "cały rozdział" in rz["rzecz"]:
        return plan["fazy"]
    # 14.11.2026: sama kolumna `plan` nie wiąże faz — bez znacznika i bez § wiersz nie dostaje żadnej fazy
    # (wcześniej dostawał wszystkie, także „w toku” z cudzych podrozdziałów, np. wiersze 3–4 ↔ Phase 60)
    return [f for f in plan["fazy"] if str(f["nr"]) in numery]


def kolejnosc(projekt):
    mp = mapa(projekt)
    if mp is None:
        return {"projekt": projekt, "blad": "brak SPEC z blokiem mapa-warstw"}
    gotowe = set(mp["warstwy_gotowe"])
    plany = {}
    for rz in mp["rzeczy"]:
        if rz["plan"] and rz["plan"] not in plany:
            k = _UST["katalog_planu"].format(projekt=projekt, plan=rz["plan"])
            plany[rz["plan"]] = gantt.przetworz_plan(k) if os.path.isdir(k) else None
    ids = {c for p in plany.values() if p for f in p["fazy"] for c in f["karty"]}
    karty = priorytety(sorted(ids))
    teraz, czeka, niezgodnosci, gotowe_rz, gotowe_poz = [], [], [], [], []
    for rz in mp["rzeczy"]:
        plan = plany.get(rz["plan"])
        brakujace = [w for w in range(rz["bramka"]) if w not in gotowe]
        dozwolona = not brakujace
        nalezny = 8 - rz["bramka"]
        fz = [f for f in fazy_rzeczy(rz, plan) if f["status"] != "complete"]
        poz = {"kolejnosc": rz["kolejnosc"], "rozdzial": rz["rozdzial"], "rzecz": rz["rzecz"], "plan": rz["plan"],
               "bramka": rz["bramka"], "warstwy": rz["warstwy"], "stan": rz["stan"], "priorytet_nalezny": nalezny,
               "fazy": [{"nr": f["nr"], "tytul": f["tytul"], "status": f["status"],
                         "karty": [dict(id=c, **karty.get(c, {})) for c in f["karty"]]} for f in fz],
               # 06.11.2026 („Karty tego miejsca” puste po zamknięciu faz): WSZYSTKIE fazy elementu z kartami, także zakończone — do wyświetlania
               # (Schemat: lista kart i „Kanban·N”). Pole `fazy` zostaje tylko otwarte (kolejność, niezgodności, MCP bez zmian).
               "fazy_wszystkie": [{"nr": f["nr"], "tytul": f["tytul"], "status": f["status"],
                                   "karty": [dict(id=c, **karty.get(c, {})) for c in f["karty"]]} for f in fazy_rzeczy(rz, plan)]}
        if rz["stan"] == "GOTOWE":
            gotowe_rz.append(rz["kolejnosc"])
            gotowe_poz.append(poz)  # 11.11.2026 (t_4b5a7643): Schemat ma pokazać także rzeczy gotowe (warstwy W0–W1 nie mogą być puste)
            continue
        if not rz["plan"] or plan is None:
            poz["uwaga"] = "brak planu wdrożenia"
        elif rz.get("wdrozenie") and not fz and not poz["fazy_wszystkie"]:
            poz["uwaga"] = "brak fazy %s w planie %s" % (rz["wdrozenie"]["fazy"], rz["plan"])
        karty_rz = [c for f in poz["fazy"] for c in f["karty"] if c.get("status") not in (None, "done", "archived")]
        if dozwolona:
            teraz.append(poz)
            if poz["fazy"] and not karty_rz:
                niezgodnosci.append({"rodzaj": "brak karty", "kolejnosc": rz["kolejnosc"], "rzecz": rz["rzecz"], "plan": rz["plan"]})
            for c in karty_rz:
                if c.get("priority") != nalezny:
                    niezgodnosci.append({"rodzaj": "priorytet", "karta": c["id"], "jest": c.get("priority"), "nalezny": nalezny,
                                         "rzecz": rz["rzecz"]})
        else:
            poz["czeka_na_warstwy"] = brakujace
            czeka.append(poz)
            for c in karty_rz:
                if zaparkowana(c):
                    continue
                niezgodnosci.append({"rodzaj": "w toku powyżej bramki — dokończyć, nie zaczynać nowych" if c.get("status") == "running"
                                     else "karta powyżej bramki — nie zaczynać", "karta": c["id"], "status": c.get("status"),
                                     "rzecz": rz["rzecz"], "czeka_na_warstwy": brakujace})
    return {"projekt": projekt, "spec": mp["spec"], "warstwy_gotowe": sorted(gotowe), "linia_gotowosci": mp["linia_gotowosci"],
            "rzeczy": len(mp["rzeczy"]), "gotowe": len(gotowe_rz),
            "nieaudytowane": sum(1 for r in mp["rzeczy"] if r["stan"] == "nieaudytowane"),
            "do_kodu_teraz": teraz, "czeka_na_warstwe": czeka, "gotowe_lista": gotowe_poz, "niezgodnosci": niezgodnosci,
            "komentarze_schematu": _komentarze_schematu(projekt)}


def adnotuj_gantt(plany):
    """14.11.2026 (t_af53c0ce: sortowanie „wg warstw” obok „wg potoku”): dopisuje do wyników przetworz_plan() to, czego
    CSW potrzebuje do widoku „wg warstw” — nic nie zmienia w stanie faz ani kart tylko pokazuje.
    Dla projektów z mapą warstw: faza → `warstwa` {kolejnosc, bramka, rzecz, czeka} (faza w kilku wierszach = wiersz o najniższej
    kolejności; `czeka` = warstwy niższe od bramki, które nie są gotowe); plan → `warstwy` {projekt, gotowe, niezgodnosci}
    (lista `niezgodnosci` bez zmian, jak w kolejnosc()). Faza bez klucza `warstwa` w planie z `warstwy` = „bez wiersza”.
    Projekt bez mapy (Srodowisko, DarkEdenDigital…) zostaje bez zmian."""
    po_projekcie = {}
    for pl in plany:
        m = re.match(_UST["projekt_regex"], (pl.get("sciezka") or "") + "/")
        if m:
            po_projekcie.setdefault(m.group(1), []).append(pl)
    for projekt, lista in po_projekcie.items():
        try:
            if mapa(projekt) is None:
                continue
            w = kolejnosc(projekt)
        except Exception as ex:   # widok „wg potoku” ma działać także wtedy, gdy mapa albo kanban.db chwilowo zawodzą
            print("kolejnosc: adnotacje warstw pominięte dla %s: %r" % (projekt, ex), file=sys.stderr)
            continue
        if "blad" in w:
            continue
        najlepsza = {}   # (plan, nr) → wiersz o najniższej kolejności
        for poz in w["do_kodu_teraz"] + w["czeka_na_warstwe"] + w["gotowe_lista"]:
            for f in poz["fazy_wszystkie"]:
                k = (poz["plan"], str(f["nr"]))
                if k not in najlepsza or poz["kolejnosc"] < najlepsza[k]["kolejnosc"]:
                    najlepsza[k] = poz
        info = {"projekt": projekt, "gotowe": w["warstwy_gotowe"], "niezgodnosci": w["niezgodnosci"]}
        for pl in lista:
            pl["warstwy"] = info
            for f in pl["data"][1:]:
                poz = najlepsza.get((pl["plan"], str(f["id"]).rsplit(":", 1)[-1]))
                if poz:
                    f["warstwa"] = {"kolejnosc": poz["kolejnosc"], "bramka": poz["bramka"], "rzecz": poz["rzecz"],
                                    "czeka": poz.get("czeka_na_warstwy", [])}
    return plany


def _komentarze_schematu(projekt):
    """01.11.2026: otwarte wątki komentarzy ze Schematu konsoli — tylko dla projektu z ustawienia `komentarze_schematu`
    ({projekt, sciezka, polecenie}); bez ustawienia pusto. Orkiestrator może dopytać autora w wątku."""
    ks = _UST["komentarze_schematu"]
    if not ks or projekt != ks["projekt"]:
        return []
    try:
        sys.path.insert(0, ks["sciezka"])
        import schemat_kom
        return [{"klucz": k, "miejsce": "%s · %s" % (v["poziom"], v["tyt"]), "wpisy": v["n"],
                 "ostatni": "%s %s: %s" % (v["wpisy"][-1]["kiedy"], v["wpisy"][-1]["kto"], v["wpisy"][-1]["tresc"][:200])}
                for k, v in schemat_kom.watki().items() if v["otwarty"]]
    except Exception as ex:
        return [{"blad": "komentarze Schematu niedostępne: %r" % ex}]


def tekst(w):
    if "blad" in w:
        return "%s: %s" % (w["projekt"], w["blad"])
    out = ["%s — warstwy gotowe: %s%s · rzeczy %d (gotowe %d, nieaudytowane %d)" % (
        w["projekt"], ",".join(map(str, w["warstwy_gotowe"])) or "żadna",
        "" if w["linia_gotowosci"] else " (brak linii <!-- warstwy-gotowe: … --> w SPEC)", w["rzeczy"], w["gotowe"], w["nieaudytowane"])]
    out.append("\nDO KODU TERAZ (%d):" % len(w["do_kodu_teraz"]))
    for p in w["do_kodu_teraz"]:
        otw = {c["id"]: c for f in p["fazy"] for c in f["karty"] if c.get("status") not in (None, "done", "archived")}
        k = ", ".join("%s %s p%s" % (c["id"], c.get("status", "?"), c.get("priority", "?")) for c in otw.values()) or "brak otwartej karty"
        out.append("  %2d. [%s] %s · bramka %d → priorytet %d · %s · %s" % (p["kolejnosc"], p["rozdzial"], p["rzecz"][:70], p["bramka"],
                                                                    p["priorytet_nalezny"], p["stan"], k))
        if p["fazy"]:  # 31.10: otwarte fazy wprost — „cały rozdział” bez listy faz nie mówi, od czego zacząć
            out.append("      otwarte fazy: " + "; ".join("F%s %s (%s)" % (f["nr"], f["tytul"][:50], f["status"]) for f in p["fazy"]))
    out.append("\nCZEKA NA WARSTWĘ (%d): " % len(w["czeka_na_warstwe"]) + "; ".join(
        "%d.[%s] czeka na %s" % (p["kolejnosc"], p["rozdzial"], ",".join(map(str, p["czeka_na_warstwy"]))) for p in w["czeka_na_warstwe"][:12])
        + (" …" if len(w["czeka_na_warstwe"]) > 12 else ""))
    out.append("\nNIEZGODNOŚCI (%d):" % len(w["niezgodnosci"]))
    for n in w["niezgodnosci"][:25]:
        out.append("  - " + ", ".join("%s=%s" % (k, v) for k, v in n.items()))
    ks = w.get("komentarze_schematu") or []
    if ks:  # K3: orkiestrator dopytuje autora w wątku albo zakłada kartę
        out.append("\nKOMENTARZE SCHEMATU OTWARTE (%d) — odpowiedź: %s odpowiedz <klucz> \"<treść>\":" % (
            len(ks), _UST["komentarze_schematu"]["polecenie"]))
        for k in ks[:20]:
            out.append("  - " + (k.get("blad") or "%s (klucz: %s) — %s" % (k["miejsce"], k["klucz"], k["ostatni"])))
    return "\n".join(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    w = kolejnosc(sys.argv[1])
    print(json.dumps(w, ensure_ascii=False, indent=1) if "--json" in sys.argv else tekst(w))
