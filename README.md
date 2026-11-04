# 7HHydra

Siedem skilli dla agentów AI do pracy „od specyfikacji”: od pomysłu, przez opis zachowania i plan techniczny, do sprawdzonej zmiany. Siedem głów jednej hydry — każda robi jedno, razem prowadzą pracę od początku do końca.

*Seven skills for AI agents doing spec-driven work. English below.*

## Misja

**Najpierw podziękowanie.** 7HHydra nie powstała z niczego. Stoi na pracy ludzi, którzy pokazali swoje podejście otwarcie, i chcemy to powiedzieć na samym początku:

- **Warp — [`warpdotdev/common-skills`](https://github.com/warpdotdev/common-skills)** (MIT, © 2026 Denver Technologies, Inc.). Od nich wzięliśmy układ i podejście skilli specyfikacji: przewodnik pracy od specyfikacji, opis zachowania, plan techniczny, wykonanie i sprawdzenie zgodności. Nasze skille to ich przetłumaczone i mocno przerobione pochodne.
- **Ahmad Adi — [`OthmanAdi/planning-with-files`](https://github.com/OthmanAdi/planning-with-files)** (MIT, © 2026 Ahmad Adi). Od niego pochodzi pomysł planu trzymanego w plikach na dysku (`task_plan.md`, `findings.md`, `progress.md`) i format faz. Nasz `acting-with-files` rozwija ten pomysł o dowody, kolejkę decyzji człowieka i dziennik działań.
- **Anthropic — dokumentacja** ([Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5), [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)). Wzięliśmy pomysły — m.in. o stopniach swobody w instrukcjach i o nadmiernym sprawdzaniu — własnymi słowami, bez kopiowania tekstu.
- **Jesse Vincent — [`obra/superpowers`](https://github.com/obra/superpowers)** (MIT). Inspiracja dla izolowanej kopii roboczej i testów najpierw w `implement-specs`.

Noty licencyjne źródeł są w pliku [`NOTICE`](NOTICE). 7HHydra jest projektem nieoficjalnym — nie jest powiązana z Warp, z Anthropic ani z autorami źródeł.

**Po co to robimy.** Agent AI pisze kod szybko, ale bez opisu tego, co ma powstać, i bez dowodu, że powstało, łatwo o pracę „prawie zrobioną”. 7HHydra pilnuje trzech rzeczy:

1. Najpierw ustalamy, co ma powstać i po czym poznamy, że jest — dopiero potem kod.
2. Każdy etap kończy się dowodem (test, liczba, wynik polecenia przypięty do wersji), nie deklaracją.
3. Decyzje należą do człowieka i mają osobną kolejkę; agent wykonuje i zgłasza, czego nie wie.

## Siedem głów

| Skill | Co robi |
|---|---|
| [`spec-driven`](skills/spec-driven/SKILL.md) | Przewodnik: rozstrzyga, ile dokumentów potrzebuje praca, i prowadzi kolejność całego procesu. |
| [`start-projektu`](skills/start-projektu/SKILL.md) | Zakłada nowy projekt przed kodem: struktura wiedzy, konstytucja, dokument projektu, pierwsza lista funkcji. |
| [`write-product-spec`](skills/write-product-spec/SKILL.md) | Opis zachowania funkcji (`PRODUCT.md`) — ponumerowane, sprawdzalne wymagania. |
| [`write-tech-spec`](skills/write-tech-spec/SKILL.md) | Plan techniczny (`TECH.md`) — budowa, tabela testów przypięta do wymagań, podział na kawałki. |
| [`acting-with-files`](skills/acting-with-files/SKILL.md) | Plan faz na dysku z dowodami, kolejką decyzji człowieka i dziennikiem działań. |
| [`implement-specs`](skills/implement-specs/SKILL.md) | Wykonanie zaakceptowanej specyfikacji faza po fazie, w izolowanej kopii roboczej. |
| [`verify-against-spec`](skills/verify-against-spec/SKILL.md) | Przegląd zgodności wykonania ze specyfikacją: lekka bramka albo rozstrzyganie rozjazdów z człowiekiem. |

Kolejność: `start-projektu` → `spec-driven` → `write-product-spec` → `write-tech-spec` → `acting-with-files` → `implement-specs` → `verify-against-spec`.

## Jak użyć

Skopiuj katalogi z `skills/` do katalogu skilli swojego agenta (np. `~/.claude/skills/` albo `.agents/skills/` w repozytorium). Każdy skill to jeden plik `SKILL.md` z nagłówkiem `name` / `description`, więc agent wczytuje go, gdy opis pasuje do zadania. Skille są napisane po polsku; modele językowe czytają je bez problemu także przy pracy po angielsku.

## Projekty pokrewne

Przejrzeliśmy je przy budowie; nie kopiowaliśmy z nich tekstu: [`github/spec-kit`](https://github.com/github/spec-kit), [`Fission-AI/OpenSpec`](https://github.com/Fission-AI/OpenSpec), [`bmad-code-org/BMAD-METHOD`](https://github.com/bmad-code-org/BMAD-METHOD), [`genkovich/sdd`](https://github.com/genkovich/sdd), [`anthropics/skills`](https://github.com/anthropics/skills). Żaden z naszych pomysłów osobno nie jest unikalny — wartość 7HHydry jest w ich połączeniu.

## Licencja

[MIT](LICENSE) © 2026 Vyzygota. Noty źródeł: [`NOTICE`](NOTICE).

---

# 7HHydra (English)

Seven skills for AI agents doing spec-driven work: from an idea, through a behaviour spec and a technical plan, to a verified change. Seven heads of one hydra — each does one thing, together they carry the work end to end. The skills themselves are written in Polish.

## Mission

**Thanks first.** 7HHydra stands on work others shared openly, and we want to say so up front:

- **Warp — [`warpdotdev/common-skills`](https://github.com/warpdotdev/common-skills)** (MIT, © 2026 Denver Technologies, Inc.): the structure and approach of the spec skills (spec-driven guide, product spec, tech spec, implementation, conformance check). Our skills are translated and heavily reworked derivatives.
- **Ahmad Adi — [`OthmanAdi/planning-with-files`](https://github.com/OthmanAdi/planning-with-files)** (MIT, © 2026 Ahmad Adi): the idea of a plan kept in files on disk and the phase format; our `acting-with-files` extends it with evidence, a human decision queue and an action log.
- **Anthropic — documentation** ([Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5), [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)): ideas only, in our own words, no text copied.
- **Jesse Vincent — [`obra/superpowers`](https://github.com/obra/superpowers)** (MIT): inspiration for the isolated worktree and test-first steps in `implement-specs`.

Source licence notices are in [`NOTICE`](NOTICE). 7HHydra is unofficial and not affiliated with Warp, Anthropic or the source authors.

**Why.** An AI agent writes code fast, but without a description of what should exist and proof that it does, "almost done" work slips through. 7HHydra enforces three things: decide what to build and how you will know it is built before coding; finish every phase with evidence (a test, a number, a command result pinned to a version), not a claim; keep decisions with the human in a separate queue.

## The seven heads

`spec-driven` (guide and order), `start-projektu` (project setup before code), `write-product-spec` (behaviour spec, numbered testable requirements), `write-tech-spec` (technical plan, test table mapped to requirements), `acting-with-files` (on-disk phase plan with evidence and a decision queue), `implement-specs` (phase-by-phase execution in an isolated worktree), `verify-against-spec` (conformance review).

## Use

Copy the folders from `skills/` into your agent's skills directory (e.g. `~/.claude/skills/` or `.agents/skills/`). Each skill is a single `SKILL.md` with `name` / `description` frontmatter.

## Licence

[MIT](LICENSE) © 2026 Vyzygota. Source notices: [`NOTICE`](NOTICE).
