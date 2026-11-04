---
name: write-tech-spec
description: Plan techniczny (TECH.md) — jak zbudować funkcję albo fundament projektu: kontekst (istniejący kod albo, w nowym projekcie, decyzje i ograniczenia), proponowana budowa, tabela testów przypisana do numerów wymagań, podział na niezależne kawałki pracy. Używaj po akceptacji opisu zachowania, przy zmianie czysto technicznej i przy decyzjach fundamentu nowego projektu.
rodzina: hybryda specyfikacji (rdzeń ogólny)
zrodla: warpdotdev/common-skills write-tech-spec (01.11.2026); kanon write-tech-spec (28.06.2026); recenzje SPEC-SKILLE-20261101; decyzja właściciela zespołu 01.11.2026 (nowy projekt nie ma kodu); Anthropic Skill authoring best practices
---

# write-tech-spec — plan techniczny

Najpierw nakładka (jak w `spec-driven`). `<id>` ten sam co opisu zachowania.

## Skąd kontekst

- **Kod istnieje** — czytasz kod, którego dotyczy zmiana; twierdzenia o stanie obecnym mają adres przypięty do wersji (identyfikator jednostki zmiany + plik:linia).
- **Kodu nie ma** (nowy projekt, nowy moduł) — kontekstem są opis zachowania, kanon, decyzje człowieka i ograniczenia (platforma, język, wydajność, z czym ma współpracować); adresy przypinasz do wersji tych dokumentów. Proponujesz budowę od zera: moduły, granice, dane, pierwszy szkielet.

## Twarde

- **Tabela testów**: numer wymagania (`#n`, `#Sn`) → jak sprawdzone → gdzie. Każde wymaganie ma wiersz; wymaganie bez sposobu sprawdzenia to pytanie do człowieka. Bez opisu zachowania (zmiana czysto techniczna, fundament) numerujesz wymagania techniczne `#T1 … #Tn` tutaj.
- **Bezpieczeństwo**: dla każdego `#Sn` mechanizm i test negatywny.
- **Podział pracy**: kawałki z granicami (pliki, moduły) i zależnościami — z tego powstają fazy planu; dwóch wykonawców w tych samych plikach naraz to konflikt.
- **Cofnięcie**: jak wrócić do stanu sprzed zmiany.

## Domyślny układ (dostosuj)

Kontekst · Proponowane zmiany / budowa (z odrzuconymi alternatywami, jednym zdaniem) · Diagram, gdy przepływ jest nieoczywisty · Testy · Bezpieczeństwo · Podział pracy · Ryzyka i cofnięcie. Szczegółowość dopasuj do zmiany.

## Utrzymanie

Plan opisuje to, co faktycznie wchodzi: zmianę podejścia przepisujesz tu w tej samej jednostce zmiany co kod, powód dopisujesz do rejestru decyzji planu.
