---
name: start-projektu
description: Zakłada nowy projekt zanim powstanie jakikolwiek kod — strukturę wiedzy (surowe wejście → koncepcja → kanon ze źródłami), konstytucję projektu, dokument projektu (np. GDD dla gry), tor planów i pierwszą listę funkcji do opisania. Używaj, gdy człowiek zaczyna nowy projekt, gdy projekt nie ma struktury wiedzy albo gdy wiedza projektu jest rozproszona.
rodzina: hybryda specyfikacji (rdzeń ogólny)
zastepuje: init-project
zrodla: kanon init-project (28.06.2026); schemat projektów zespołu (tory surówka / koncepcja / kanon / plany, decyzje 25.10.2026: „koncepcja zawsze na początku”, „mechanizm, nie reguła”); reguły Triady §8, §9, §11; SPEC-SKILLE-20261101 (decyzja właściciela zespołu 01.11.2026: start projektu z modelem katalogów, konstytucją, kanonem, odwołaniem do GDD)
---

# start-projektu

Najpierw nakładka (jak w `spec-driven`): ona może podać inne nazwy katalogów i narzędzie notatek. Poniżej wartości domyślne.

## Po co

Kod projektu wynika ze specyfikacji, a specyfikacja z przyjętej wiedzy. Ten skill zakłada miejsce na wiedzę i jej drogę, zanim padnie pierwsza linijka kodu.

## Struktura wiedzy (twarda)

```
<Projekt>/
  README.md            — po co projekt, dla kogo, gdzie co leży (mapa)
  KONSTYTUCJA.md       — zasady tego projektu: czego nie robimy, kto decyduje, język domeny, odstępstwa od zasad zespołu
  DECYZJE.md           — rejestr decyzji człowieka, tylko dopisywany
  surowka/             — surowe wejście: rozmowy, notatki, linki; RRRR-MM-DD-źródło-temat.md; tylko dopisywane;
                         duże pliki binarne i media poza repozytorium tekstowym, tu notatka z linkiem
  koncepcja/<temat>/   — pomysły i warianty jeszcze nieprzyjęte, z linkami do surówki
  kanon/<temat>/       — przyjęte i obowiązujące; każdy plik ma we frontmatterze `zrodla:` (skąd to wiemy)
  .planning/<id>/      — plany pracy (acting-with-files)
  kod/                 — (gdy projekt ma kod) osobne repozytorium; specyfikacje funkcji obok kodu albo w planie (nakładka)
```

Droga wiedzy jest jedna: surówka → koncepcja → kanon. Do kanonu przechodzi tylko to, co przyjął człowiek, ze źródłem. Dokument projektu (np. GDD gry, opis produktu) leży w kanonie i jest jego głównym spisem; specyfikacje funkcji odwołują się do jego rozdziałów, nie powtarzają ich.

Strukturę pilnuje mechanizm (szablon + bramka przy zapisie), nie pamięć agenta — jeśli nakładka go podaje, użyj go do założenia projektu.

## Kroki (kolejność swobodna, wynik twardy)

1. Załóż strukturę (polecenie z nakładki albo ręcznie według drzewa wyżej).
2. Zbierz wejście do `surowka/` — rozmowa z człowiekiem, materiały, które podał.
3. Z człowiekiem: cel i odbiorca projektu → `README.md`; zasady projektu → `KONSTYTUCJA.md`. Pytania z wariantami kanałem decyzji, po jednym temacie.
4. Szkic dokumentu projektu w `koncepcja/`; po akceptacji człowieka przenosi się do `kanon/` ze źródłami.
5. Gdy projekt ma warstwę techniczną: decyzje fundamentu (platforma, język, architektura, co musi współpracować) jako plan techniczny projektu (`write-tech-spec`, przypadek bez kodu), po akceptacji w kanonie.
6. Lista pierwszych funkcji do opisania, w kolejności z dokumentu projektu → kolejka planów.

## Gotowe, gdy

Struktura istnieje i przechodzi kontrolę nakładki (jeśli jest), `README.md` i `KONSTYTUCJA.md` przyjęte przez człowieka, dokument projektu przynajmniej w koncepcji, decyzje fundamentu w kanonie albo w kolejce decyzji, lista pierwszych funkcji zapisana.

## Punkty specjalizacji

Jak w `spec-driven`. Tu w praktyce: (1) nazwy i położenie katalogów, narzędzie notatek, polecenie zakładające projekt i bramka struktury; (3) kanał decyzji.
