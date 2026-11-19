---
name: acting-with-files
description: Plan faz na dysku z dowodami — każda faza ma „Gotowe, gdy” i „Dowód” przypięte do wersji i numerów wymagań; kolejka decyzji człowieka; dziennik działań z cofnięciem; role właściciel / wykonawca / recenzent; stan pracy wynika z tego, czego brakuje. Używaj przy zakładaniu, prowadzeniu, delegowaniu i zamykaniu faz planu oraz przy raporcie dla człowieka.
rodzina: hybryda specyfikacji (rdzeń ogólny)
rozszerza: planning-with-files (pliki planu, wstrzykiwanie, bramka ukończenia)
zrodla: acting-with-files zespołu (część ogólna, 01.11.2026); reguły Triady §6, §8; recenzje SPEC-SKILLE-20261101; Anthropic Prompting Claude Opus 5 (over-verification), Skill authoring best practices (degrees of freedom)
---

# acting-with-files — rdzeń ogólny

Planning-with-files trzyma plan na dysku; ten skill mówi, jak fazy zamykać, przekazywać i zostawiać ślad. Najpierw nakładka (jak w `spec-driven`).

Plik planu i osiem reguł są **twarde**: czytają je automaty i inni agenci, a od nich zależy, czy człowiek widzi prawdziwy stan pracy. **Swobodne** jest to, jak dzielisz pracę na fazy, ile ich jest, co i jak zapisujesz w `findings.md` i jak sprawdzasz własną pracę.

## Pliki planu (`.planning/<id>/`, katalog płaski)

| Plik | Co w nim | Tryb |
| --- | --- | --- |
| `task_plan.md` | Cel, Next Step, kolejka decyzji, fazy, blokady, decyzje, błędy | fazy i stan: aktualizowane; Decyzje i Błędy: tylko dopisywane |
| `findings.md` | ustalenia z adresem źródła (plik:linia, URL, polecenie) | dopisywany |
| `progress.md` | przebieg sesji, wyniki kontroli; na górze „Stan na RRRR-MM-DD” (5–10 linii) | dopisywany; wpisy starsze niż 7 dni zwijane do `progress-archiwum.md` |
| `dzialania.md` | działania poza planem z cofnięciem | dopisywany |

Znaczniki faz zostają w formie `### Phase N: <nazwa>` i `**Status:** pending | in_progress | complete` — liczy je bramka planning-with-files. Pola faz: `**Wykonawca:**`, `**Gotowe, gdy:**`, `**Dowód:**` (dokładnie tak, pogrubione). Każde pole to osobny punkt listy `- **Pole:** wartość` pod nagłówkiem fazy; jedna linia `- **Status:**` na fazę, zmieniana w miejscu, nie dopisywana. Pola kontraktu i sekcje stanu (Kolejka decyzji, Blokady, Błędy) **zostają w pliku także puste** — ze znacznikiem „—”; sprawdza je automat. (W specyfikacjach przeciwnie: puste sekcje się pomija.)

## Zanim napiszesz fazy

Sprawdź założenia, które mogą zmienić układ faz — np. czy parametr, który plan chce porównać, w ogóle wpływa na wynik; czy decyzja, na której stoi plan, jest wdrożona w kodzie, a nie tylko zapisana; czy pomiar, na którym ma stanąć werdykt, jest z wersji po zmianie, która go dotyczy. Wyniki do `findings.md` z adresem; zmiana planu wynikająca z kontroli do „Decyzje” jako decyzja agenta z uzasadnieniem.

## Osiem reguł

1. **Faza kończy się dowodem.** „Gotowe, gdy” to sprawdzalny warunek (test, liczba, plik, wynik polecenia), wskazujący numery wymagań (`#n`, `#Sn`, `#Tn`), gdy specyfikacja istnieje. „Dowód” to konkret przypięty do wersji: identyfikator jednostki zmiany + plik:linia, wynik testu, liczba. „Zrobione”, „OK”, „działa” nie są dowodem. Część zakresu przeniesiona gdzie indziej niesie zapis: co, dokąd, dlaczego.
2. **Raport mówi tylko o tym, co się stało.** Czego nie da się sprawdzić Twoimi narzędziami (licencja, kliknięcie człowieka, przyszły przebieg), to blokada w sekcji „Blokady”: faza, czego brakuje, kto to dostarczy — nie zastrzeżenie w raporcie. Intencji nie zapisujesz w formie wyniku („testy dodane” ≠ „testy przechodzą”).
3. **Decyzje człowieka mają osobną kolejkę.** „Kolejka decyzji”: pytanie, warianty z liczbami, rekomendacja, od kiedy czeka. Rozstrzygnięcie przechodzi do „Decyzje” ze źródłem `[człowiek] <kto>, RRRR-MM-DD`; decyzja agenta `[agent] <kto>` nie zastępuje decyzji człowieka. Temat pracy wybiera człowiek; Twój audyt daje ustalenia, nie mandat.
4. **Każde działanie poza planem zostawia ślad.** Wiersz w `dzialania.md` przed wykonaniem: co, gdzie, czy odwracalne, jak cofnąć; po wykonaniu wynik polecenia. Usunięcie tylko za zgodą człowieka; zamiast usuwać — przenieś do archiwum.
5. **Faza delegowana ma kartę na tablicy zadań.** Karta niesie `<id>` planu, numer fazy i „Gotowe, gdy”. Wykonawca oddaje raport z dowodem; właściciel przelicza główne liczby z surowych wyników własnym sposobem (nie skryptem wykonawcy), wpisuje dowód i zamyka fazę. Status zakończenia procesu wykonawcy nie jest wynikiem pracy — czytasz, co faktycznie oddał.
6. **Trwałe przekazanie przed sprzątaniem.** Praca żyjąca tylko w tymczasowej kopii roboczej ginie przy jej usunięciu: najpierw jednostka zmiany, wypchnięcie albo jawny artefakt WIP, potem sprzątanie. Gdy nie ma czego zachować — napisz to.
7. **Przed raportem: kontrola dowodów.** Automat bramki dowodów przechodzi (kod 0); wynik do `progress.md`. Automat sprawdza co najmniej: każda faza ma pola z reguły 1, faza `complete` ma „Dowód” niepusty i konkretny (nie „OK/zrobione/działa”), blokada ma właściciela i warunek. Automat: `scripts/sprawdz_dowody.py <katalog planu>` (tylko odczyt, kod 0 = przechodzi); pliki planu zakładasz z `templates/`. Bez automatu przechodzisz tę listę ręcznie, faza po fazie, i wpisujesz wynik. Plan, którego nie jesteś właścicielem, sprawdzasz w trybie tylko do odczytu.
8. **Stan pracy wynika z tego, czego brakuje.** Zablokowana = brakuje wiedzy (do ustalenia albo do rozstrzygnięcia przez człowieka) albo narzędzia; termin, zależność, recenzja i brak uprawnienia blokadą nie są. Zamknięta lista: czeka na inną kartę → zależność karta→karta; czeka na datę → zaplanowana; czeka na recenzję → recenzja; brak wiedzy → zablokowana `[wiedza]` + zlecenie rozpoznania; rozstrzyga człowiek → zablokowana `[decyzja <nr>]`; brak narzędzia → zablokowana `[narzędzie]`; brak uprawnienia, które ma ktoś w zespole → zlecenie dla niego, nie blokada; zależy od kogoś spoza zespołu → zablokowana `[poza zespołem] <kto>`. Każda blokada ma właściciela i warunek odblokowania.

## Role

| Rola | Co robi |
| --- | --- |
| Właściciel planu | pisze `task_plan.md`, otwiera i zamyka fazy, prowadzi kolejkę decyzji |
| Wykonawca | robi fazę, oddaje raport z dowodem, prowadzi dziennik działań; nie zmienia statusu faz — proponuje zamknięcie |
| Recenzent (= „drugi czytelnik” w `verify-against-spec`) | ocenia krok wykonawcy werdyktem PRZYJĘTE / DO POPRAWY; z innej rodziny modeli niż autor; planu nie zmienia |

## Cykl fazy

0. Założenia (wyżej). 1. Otwarcie: właściciel wpisuje fazę (`pending`), wykonawcę, „Gotowe, gdy”; uaktualnia Next Step. 2. Start: `in_progress`; przy delegowaniu karta (reguła 5). 3. Praca: ustalenia → `findings.md`, działania → `dzialania.md`, błędy → tabela błędów (trzy próby, potem zmiana podejścia, potem człowiek). 4. Raport wykonawcy z dowodem dla każdego warunku. 5. Recenzja kroków kodu (reguła recenzenta). 6. Zamknięcie: dowód w planie, automat przechodzi, `complete`, nowy Next Step.

## Raport dla człowieka

Najpierw wynik z liczbą, potem to, co czeka na niego (jedna decyzja naraz, z pełną treścią pytania i wariantami), potem reszta. Daty zamiast „dziś/wczoraj”.

## Punkty specjalizacji

Jak w `spec-driven` (zamknięta lista 6). Tu w praktyce: miejsce planu (1), kanał decyzji i format numerów pytań (3), tablica zadań i jej stany (4), automat bramki dowodów (5), recenzent (6). Nakładka dopisuje imiona ról, ścieżki i polecenia — nie zmienia ośmiu reguł.
