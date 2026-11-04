---
name: implement-specs
description: Wykonanie zaakceptowanej specyfikacji faza po fazie — w izolowanej kopii roboczej, testy z tabeli planu technicznego, specyfikacja poprawiana razem z kodem, praca utrwalona przed sprzątaniem. Używaj po akceptacji opisu zachowania i planu technicznego.
rodzina: hybryda specyfikacji (rdzeń ogólny)
zrodla: kanon implement-specs (28.06.2026, izolacja i TDD — inspiracja obra/superpowers); warpdotdev/common-skills implement-specs (01.11.2026); reguły Triady §3, §6(b); Anthropic Prompting Claude Opus 5 (task scope, over-verification)
---

# implement-specs — wykonanie

Najpierw nakładka (jak w `spec-driven`).

## Warunek wejścia

Opis zachowania przyjęty przez człowieka (albo przewodnik uznał go za zbędny), plan techniczny z tabelą testów, faza planu `in_progress` z „Gotowe, gdy”. Czegoś brakuje → wracasz do `spec-driven`, nie zgadujesz.

## Twarde

- Pracujesz w izolowanej kopii roboczej, nie na gałęzi głównej; na gałąź główną nie wypychasz bezpośrednio.
- Każde wymaganie z tabeli testów ma sprawdzenie, które przechodzi; tam, gdzie projekt ma testy automatyczne, test powstaje razem z kodem wymagania i przed jego oddaniem nie przechodzi bez tego kodu. W pustym projekcie najpierw szkielet, na którym test da się uruchomić.
- Zmiana zachowania, której człowiek nie przyjął, to pytanie przed jednostką zmiany, nie po. Zakresu fazy nie poszerzasz po cichu: lepszy pomysł zgłaszasz jednym zdaniem i robisz fazę, jak jest opisana.
- Specyfikację poprawiasz w tej samej jednostce zmiany co kod; powód do rejestru decyzji planu.
- Jednostka zmiany niesie `Session-Id`, `<id>` planu i numer fazy.
- Przed usunięciem kopii roboczej praca jest utrwalona (jednostka zmiany, wypchnięcie albo jawny artefakt WIP); gdy nie ma czego utrwalić — napisz to.

## Swobodne

Kolejność i wielkość kroków, styl testów, sposób sprawdzania własnej pracy.

## Oddanie

Raport: dla każdego warunku „Gotowe, gdy” dowód z tej sesji, przypięty do końcowej wersji; czego nie uruchomiłeś (np. szerokie pokrycie bez CI), nazwij wprost. Przegląd zgodności ze specyfikacją robi recenzent (`verify-against-spec`), nie osobny przebieg wykonawcy.
