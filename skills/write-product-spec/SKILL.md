---
name: write-product-spec
description: Opis zachowania funkcji (PRODUCT.md) jako ponumerowane, sprawdzalne wymagania — co widzi i czego doświadcza użytkownik, bez architektury i bez planu testów. Używaj, gdy przewodnik spec-driven wskazał opis zachowania albo człowiek prosi o specyfikację produktu, PRD, opis działania.
rodzina: hybryda specyfikacji (rdzeń ogólny)
zrodla: warpdotdev/common-skills write-product-spec (01.11.2026); kanon write-product-spec (28.06.2026); recenzje SPEC-SKILLE-20261101; Anthropic Skill authoring best practices (template pattern: flexible)
---

# write-product-spec — opis zachowania

Najpierw nakładka (jak w `spec-driven`).

## Twarde

- **Wymagania ponumerowane** `#1 … #N`: każde opisuje jedno obserwowalne zachowanie i da się je sprawdzić bez czytania kodu. Numer jest stały; usunięte wymaganie zostaje przekreślone z powodem.
- **Bezpieczeństwo** osobno, `#S1 … #Sn`, gdy funkcja dotyka danych, uprawnień, wejścia z zewnątrz: co ma być dozwolone, co odrzucone, co nie może wyciec.
- **Źródła**: zachowanie wynika z kanonu i decyzji człowieka — odwołuj się do rozdziałów dokumentu projektu zamiast je powtarzać; twierdzenie o istniejącym zachowaniu sprawdzasz w kodzie, jeśli kod jest.
- Bez planu testów i bez architektury — to plan techniczny.
- Akceptuje człowiek, zanim powstanie plan techniczny. Niejasność w źródle → pytanie z wariantami, nie domysł.

## Domyślny układ (dostosuj)

Podsumowanie (kto jest użytkownikiem — gracz, operator, inny moduł — i co się dla niego zmienia) · Problem · Cele i poza zakresem · **Zachowanie** · Bezpieczeństwo · Otwarte pytania. Sekcji, które nic nie wnoszą, nie zakładasz. Długość wynika z liczby wymagań, nie z prozy.

## Utrzymanie

Dokument opisuje stan obecny: gdy wykonanie zmienia zachowanie (za zgodą człowieka), przepisujesz wymaganie w tej samej jednostce zmiany co kod, a powód dopisujesz do rejestru decyzji planu.
