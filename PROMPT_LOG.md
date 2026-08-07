# AI Prompt Log — FleetPulse

**Student:** Hafsa Aqeel · **Roll Number:** 53317
**Course deliverable:** required by *Part D — Anti-Cheating Rules*: “All AI prompts must be submitted as proof.”

This log records **every** prompt used to produce this project, in chronological order. Two kinds of
prompts appear here and are labelled as such:

- **[S] Student prompt** — typed verbatim by Hafsa Aqeel into the AI assistant.
- **[A] Assistant-generated prompt** — the engineered sub-prompt the AI wrote for itself to carry out
  a specific SDLC task (requirements elicitation, diagram generation, test generation, …). These are
  included because the student instructed the AI to record its own prompts too.

Nothing in this file is edited or deleted after the fact; new entries are appended.

---

## Session 1 — 2026-08-06 · Phase: Project Planning (Problem Definition)

### P-01 · [S] Student
> Read this document and take our inputs to decide the project. Record every prompt we give and required to generate the product and act as per document

**Result:** The AI parsed `Final Term Project.docx` and extracted the assignment structure — Part A
(theme formula: Birth Month + Last Digit of Roll Number + Favorite Technology), Part B (AI usage
across all five SDLC phases), Part C (seven deliverables), Part D (anti-cheating rules). It created
this prompt log and requested the three personalization inputs.

### P-02 · [S] Student
> Birth month is July

**Result:** Resolved **Domain Theme = Transportation** (Part A §1: Jul → Transportation).

### P-03 · [S] Student
> Last digit of roll number is 7. Techology python can be used. Now ask anything you need, tell me the project and finalise what to do

**Result:** Resolved **Application Type = Monitoring System** (Part A §2: 7 → Monitoring System) and
**Mandatory AI Constraint = AI must auto-generate tests** (Part A §3: Python). Proposed the concrete
product “FleetPulse — a real-time transportation fleet monitoring system” and asked four scoping
questions (fleet type, UI technology, data source, student identity).

### P-04 · [S] Student
> 1. both
> 2. I think we need UI so React SPA
> 3. Simulator. Add optional GTFS reader
> 4. Name: Hafsa Aqeel - Roll Number: 53317
>
> Yes in /Users/aqeel/Downloads/hafsa-gen-ai-final/
> Record all prompts from us and you generate yourself for the project

**Result:** Scope frozen — mixed fleet (city buses **and** delivery trucks), React SPA dashboard,
built-in telemetry simulator with an optional GTFS-Realtime reader, project rooted at
`/Users/aqeel/Downloads/hafsa-gen-ai-final/` as a git repository. Roll number 53317 confirmed
consistent with the declared last digit 7.

### P-05 · [A] Assistant → *Problem definition*
> Apply the Part A formula to the inputs (July, 7, Python) and write a Personalized Problem Sheet that
> states the derived theme, the problem statement, the target users, the project scope with explicit
> in-scope/out-of-scope lists, the mandatory AI constraint and how it will be satisfied and evidenced,
> and a uniqueness justification explaining why this combination cannot collide with another student’s.

**Result:** `docs/01-problem-sheet.md` (Deliverable 1).

---

## Session 1 — Phase: Project Planning (Requirements)

### P-06 · [A] Assistant → *Requirements elicitation*
> Acting as a business analyst for FleetPulse, a Python transportation monitoring system for a mixed
> fleet of city buses and delivery trucks: produce numbered functional requirements (FR-xx) and
> non-functional requirements (NFR-xx). Cover telemetry ingestion, vehicle registry, route and
> geofence definition, the monitoring rule engine, alert lifecycle, live dashboard, historical query,
> and the simulator. Give every requirement a priority (MUST/SHOULD/COULD) and make each one testable.

**Result:** `docs/02-requirements.md` §1–§2.

### P-07 · [A] Assistant → *User stories & acceptance criteria*
> Convert the FleetPulse functional requirements into agile user stories in the form
> “As a &lt;role&gt;, I want &lt;goal&gt;, so that &lt;benefit&gt;” for the roles Fleet Operator, Dispatcher,
> Maintenance Engineer and System Administrator. For each story write Given/When/Then acceptance
> criteria that a pytest test could assert directly, and map each story back to its FR id.

**Result:** `docs/02-requirements.md` §3.

### P-08 · [A] Assistant → *Use cases*
> Write fully-dressed use case specifications for the five highest-value FleetPulse use cases
> (ingest telemetry, evaluate monitoring rules, raise and deduplicate an alert, acknowledge/resolve an
> alert, view the live fleet dashboard). Include actors, preconditions, main success scenario,
> extensions and postconditions, plus a UML use case diagram in Mermaid.

**Result:** `docs/02-requirements.md` §4 and the use case diagram.

---

## Session 1 — Phase: System Design

### P-09 · [A] Assistant → *Architecture diagrams*
> Design the FleetPulse architecture and express it as Mermaid diagrams: (a) a C4-style container
> diagram showing simulator, optional GTFS reader, FastAPI service, rule engine, SQLite/SQLAlchemy
> store, WebSocket hub and React SPA; (b) a telemetry-to-alert sequence diagram; (c) the alert
> lifecycle state machine; (d) the deployment view. Justify each significant architectural decision
> and record the rejected alternatives.

**Result:** `docs/03-architecture.md`.

### P-10 · [A] Assistant → *Database design*
> Design the relational schema for FleetPulse supporting both buses and delivery trucks with a shared
> vehicle table. Include vehicles, routes, route waypoints, stops, telemetry readings, alerts, alert
> rules and deliveries. Give an ERD in Mermaid, column-level definitions with types and constraints,
> the indexing strategy for time-series telemetry queries, and the retention policy.

**Result:** `docs/04-database-design.md`.

### P-11 · [A] Assistant → *UI/UX design*
> Produce the UI/UX design for the FleetPulse React dashboard: information architecture, ASCII
> wireframes for the fleet overview, vehicle detail and alert centre screens, the colour semantics for
> alert severity, the live-update interaction model, and the accessibility rules (contrast, keyboard
> navigation, colour-blind-safe status encoding).

**Result:** `docs/05-ui-ux-design.md`.

---

## Session 1 — Phase: Implementation

### P-12 · [A] Assistant → *Data layer boilerplate*
> Generate SQLAlchemy 2.0 declarative models and Pydantic v2 schemas for the FleetPulse schema
> defined in docs/04-database-design.md. Use typed `Mapped[...]` columns, enums for vehicle type,
> alert severity and alert status, and separate Create/Read schemas. No business logic in the models.

**Result:** `backend/app/models.py`, `backend/app/schemas.py`.

### P-13 · [A] Assistant → *Monitoring rule engine*
> Write a pure-function rule engine for FleetPulse. Each rule takes a telemetry reading plus vehicle
> context and returns zero or more alert candidates. Implement: overspeed vs the route speed limit,
> engine overheating, low fuel, geofence/route deviation using haversine distance, vehicle-offline
> heartbeat timeout, harsh braking, schedule delay (buses) and cargo temperature excursion (trucks).
> Rules must be side-effect free and independently unit-testable, with thresholds injected via config.

**Result:** `backend/app/rules/`, `backend/app/services/monitoring.py`.

### P-14 · [A] Assistant → *API routes*
> Implement the FastAPI routers for FleetPulse: vehicle CRUD, route CRUD, telemetry ingestion
> (single + batch), fleet snapshot, telemetry history, alert list/filter/acknowledge/resolve, health
> and stats endpoints, and a `/ws/live` WebSocket broadcasting fleet updates and new alerts. Use
> dependency-injected sessions, Pydantic response models and correct HTTP status codes.

**Result:** `backend/app/routers/`, `backend/app/main.py`.

### P-15 · [A] Assistant → *Simulator + GTFS reader*
> Write a deterministic, seedable telemetry simulator that drives buses along polyline routes with
> dwell time at stops and trucks along delivery legs, injecting configurable fault scenarios
> (overheating, fuel drain, route deviation, dropout, cargo temperature spike). Separately write an
> optional GTFS-Realtime reader that maps `VehiclePosition` entities onto the FleetPulse telemetry
> model and degrades gracefully when the feed or the protobuf dependency is unavailable.

**Result:** `backend/app/services/simulator.py`, `backend/app/services/gtfs.py`.

### P-16 · [A] Assistant → *React component boilerplate*
> Generate the React 18 + Vite SPA for FleetPulse: an API client, a `useLiveFleet` hook wrapping the
> WebSocket with polling fallback, and the components FleetMap, KpiTiles, AlertFeed, VehicleTable,
> VehicleDetail with telemetry charts, and RuleThresholdPanel. Functional components with hooks, no
> class components, a single stylesheet, no UI framework dependency. The map and the charts must be
> **inline SVG with no external library and no remote tiles** — the demo has to run on a machine with
> no internet, so Leaflet (as the UI/UX design originally specified) is not usable.

**Result:** `frontend/src/`. The SPA's only runtime dependencies are `react` and `react-dom`.
The deviation from the design document is recorded in `docs/05-ui-ux-design.md` §11.

---

## Session 1 — Phase: Testing *(mandatory AI constraint — Python: AI must auto-generate tests)*

### P-17 · [A] Assistant → *Unit test generation*
> Auto-generate a pytest unit test suite for every FleetPulse rule function. For each rule cover the
> below-threshold, at-threshold and above-threshold cases, missing/None sensor fields, and the
> vehicle-type gating (bus-only and truck-only rules). Use parametrised tests and fixtures, assert on
> alert code, severity and message content, and target ≥90% statement coverage of `app/rules/`.

**Result:** `backend/tests/test_rules_*.py`.

### P-18 · [A] Assistant → *Integration test generation*
> Auto-generate pytest integration tests against the FastAPI app using `TestClient` and an in-memory
> SQLite database: vehicle and route CRUD, telemetry ingestion raising an alert end-to-end, alert
> deduplication within the cooldown window, acknowledge/resolve transitions and their invalid
> transitions, filtering and pagination, and the WebSocket broadcast on a new alert.

**Result:** `backend/tests/test_api_*.py`.

### P-19 · [A] Assistant → *AI-assisted bug detection*
> Review the FleetPulse implementation adversarially for defects the happy-path tests would miss:
> timezone-naive datetime comparisons, division by zero in speed/ETA maths, haversine edge cases at
> the antimeridian, unbounded telemetry growth, alert-storm risk without cooldown, and WebSocket
> client leaks. For each defect found, report it, add a regression test that fails, then fix it.

**Result:** `docs/09-test-report.md` §5 (defect log) and the corresponding fixes.

---

## Session 1 — Phase: Documentation

### P-20 · [A] Assistant → *Documentation set*
> Write the FleetPulse documentation set: a README with badges, quick start and architecture summary;
> an API reference documenting every endpoint with request/response examples and error codes; an
> installation guide covering macOS/Linux/Windows, the virtualenv, npm and the optional GTFS extra;
> and a user manual written for a non-technical fleet operator, organised by task.

**Result:** `README.md`, `docs/06-api-reference.md`, `docs/07-installation-guide.md`,
`docs/08-user-manual.md`.

### P-21 · [A] Assistant → *Reflection & demo*
> Draft a 1–2 page reflection essay for Hafsa Aqeel covering where AI accelerated the work, where its
> output was wrong or had to be rewritten by hand, how the Python “AI must auto-generate tests”
> constraint changed the way the code was designed, and what was learned about verifying AI output.
> Also write a timed final demonstration script.

**Result:** `docs/10-reflection-essay.md`, `docs/11-demo-script.md`.

---

## Session 1 — Phase: Testing / Implementation *(second pass — findings from running the system)*

These prompts came after the first full end-to-end run. They are logged separately because they
were driven by **observed behaviour**, not by the plan — which is itself one of the findings of
the reflection essay.

### P-22 · [A] Assistant → *Demo realism of the simulator*
> The first end-to-end run produced two problems that are simulator artefacts rather than system
> faults: every bus tripped HARSH_BRAKING because dwelling at a stop snapped the reported speed from
> 34 kph to 0 in one tick, and all twelve vehicles started stacked on the first waypoint. Fix both:
> smooth the reported speed towards its target so braking into a stop looks like braking, and spread
> the vehicles sharing a route evenly along it using an index-based offset that preserves
> determinism. Also tune the fault ramp rates so each armed scenario crosses its threshold 60–120 s
> into a run at the default 5-second tick.

**Result:** `backend/app/services/simulator.py` — `SPEED_SMOOTHING`, the named ramp constants, and
the stagger in `build_from_routes`. Determinism (FR-34) re-verified by the existing tests.

### P-23 · [A] Assistant → *Diagnose the fleet-wide false schedule alerts*
> During the end-to-end run every bus raised a critical SCHEDULE_DELAY on arrival at each stop,
> claiming a delay of 10–19 minutes, while all fourteen schedule unit tests passed. Work out why,
> decide the correct behaviour, add the failing regression test first, then fix it.

**Result:** Defect **D-07**. The ETA projection `remaining / speed` is numerically meaningless at
the ~1.5 kph of a bus easing into a stop. `schedule_min_speed_kph` raised from 1.0 to 5.0; below the
floor the rule falls back to the delay already accrued. Two regression tests added
(`test_a_bus_crawling_at_a_stop_does_not_project_a_false_delay`,
`test_above_the_speed_floor_the_projection_is_used_again`).

### P-24 · [A] Assistant → *Alert message staleness*
> An alert deduplicated 23 times still displayed the value from its first firing, so the dashboard
> showed 105.7 °C while the engine was at 141.7 °C. Decide whether the message should track the
> latest reading, and justify the choice against the existing rule that severity must never
> de-escalate.

**Result:** `services/alerts.py` — the message now always tracks the latest reading, while severity
continues to ratchet upward only. The two rules serve different purposes: the message answers "what
is happening now", the severity answers "how bad has this got".

### P-25 · [A] Assistant → *Seed data sanity*
> The seed back-dated each bus's `trip_started_at` by several minutes, which made the whole fleet
> late against the timetable from its very first reading and buried every other alert type. Fix the
> seed so a demo starts from a clean, explainable state.

**Result:** `app/seed.py` — all buses start their trip at seed time.

---

## Session 2 — 2026-08-06 · Phase: Deployment / Verification

### P-26 · [S] Student
> Let's create a docker container and run it so that i can verify

**Result:** Containerised the whole stack so the project can be verified on a machine with
neither Python nor Node installed. Sub-prompt below; outcome in `docs/12-docker-guide.md`.

### P-27 · [A] Assistant → *Containerisation*
> Containerise FleetPulse as a two-stage image: Node builds the React bundle, a Python slim
> runtime serves both the API and those built assets from one origin so CORS never applies. Add a
> compose file with an `api` service, an opt-in `simulator` service gated behind a profile and
> waiting on the API's healthcheck, and a one-shot `tests` service. Seeding must be idempotent so
> restarting mid-demo does not wipe raised alerts, the SQLite file must live on a shared volume so
> the simulator can read the fleet, and the whole thing must build and run offline.

**Result:** `Dockerfile`, `docker-compose.yml`, `docker/entrypoint.sh`, `.dockerignore`, plus one
production change: `FLEETPULSE_SERVE_STATIC` and the new `/api/meta` identity endpoint in
`app/main.py`. Verified — image 239 MB, all five fault scenarios reproduced in the container,
279 tests passing inside it.

**One test had to change.** `test_index_identifies_the_project` asserted JSON at `/`, which the
container now serves the SPA from. Rather than weaken the assertion, `conftest.py` now *forces*
`FLEETPULSE_SERVE_STATIC=0` so the suite behaves identically on a laptop and in the container, and
a second test covers the always-present `/api/meta`. 278 → 279 tests.

### P-28 · [S] Student
> show me the dashboard

**Result:** Opened the running container's dashboard and captured it. Comparing two captures
nine minutes apart showed the live behaviour (engine 151.7 → 218.9 °C, fuel 11% → 0%, offline
3.2 → 6.8 min) — and exposed a long-run defect described below.

### P-29 · [S] Student
> fix it and take the other screenshots

### P-30 · [A] Assistant → *Long-run schedule drift*
> After ten minutes of continuous simulation, `SCHEDULE_DELAY` spreads across the bus fleet with
> delays of 14–18 minutes, even though the D-07 speed-floor fix is in place. Diagnose the real
> cause rather than suppressing the symptom, fix it, and update the tests that encode the old
> behaviour.

**Result:** Defect **D-08**. Not a rule bug — a modelling mismatch in the simulator. Buses
*shuttled* back along their route at the terminus, but a timetable is defined in one direction
only, so a reversing bus kept matching stops it had already served while its `trip_started_at`
never moved. Two changes: buses now re-run the route from the start ("next service from the
terminus") instead of reversing, and the simulator raises a `trip_restarted` flag that the CLI
turns into `PATCH /api/vehicles/{code}` with a fresh `trip_started_at`. The `direction` field and
its reversal logic were deleted; the odometer and stop-dwell logic were corrected for the wrap.
Three new tests; 279 → 282.

### P-31 · [A] Assistant → *Capture the remaining dashboard views*
> The SPA switches screens through React state rather than URL routes, so a plain headless
> screenshot can only ever capture the overview. Drive Chrome over the DevTools Protocol to click
> through the navigation and the vehicle table, and capture the fleet overview, a vehicle detail
> page with its telemetry charts, the alert centre and the settings panel.

**Result:** `docs/images/` — four screenshots, captured from the running container.

### P-32 · [A] Assistant → *The D-08 fix did not hold*
> A 14-minute continuous watch on the containerised demo, run specifically to confirm the D-08 fix,
> reported `SCHEDULE_DELAY` again — BUS-01 critical at 11.6 min, BUS-05 warning at 7.7 min — while
> the whole test suite stayed green. Reconcile the stored `measured_value` against the route
> geometry to identify the real mechanism before changing anything, then fix the mechanism rather
> than the threshold.

**Result:** Defect **D-09**. The arithmetic showed a 2 km leg projected from a momentary **6 kph**
— the speed a bus reads accelerating away from a stop. D-07 had only raised the floor on
*instantaneous* speed from 1 to 5 kph, moving the failure a few kph up the scale rather than
removing it. The rule now projects from the **average speed since the trip began**, which has dwell
time and acceleration already baked in. The schedule test module was rewritten to control position
and elapsed time instead of the speedometer, with two new tests asserting the instantaneous reading
cannot change the verdict. The module's test count is unchanged at 14. Confirmed by an
**18-minute uninterrupted container run with zero `SCHEDULE_DELAY`** — the same check that had
failed for D-08 and D-09 (test report §6c).

### P-33 · [S] Student
> browser back button not working to go back to back page

### P-34 · [A] Assistant → *Browser history integration*
> The dashboard switches screens through React state, so the browser's Back button leaves the app
> instead of returning to the previous screen. Bind the screen to the URL with the History API —
> push an entry per navigation, restore on `popstate`, and make the back arrow on the vehicle detail
> page use real history. Then add a history-API fallback to the static mount so that a refresh or a
> shared deep link still serves the app, while a genuinely missing asset still returns 404.

**Result:** `frontend/src/App.jsx` (`pathFor` / `viewFromPath` / `go`), `SpaStaticFiles` in
`backend/app/main.py`, with `tests/test_spa_fallback.py` (282 → 290 tests). Verified over the DevTools Protocol: nav → Back → Back → Forward all land on
the right screen, and `/vehicles/BUS-03` survives a hard refresh while `/assets/nope.js` still 404s.

---

## Prompt Summary

| Phase | Prompts | Artefacts produced |
|---|---|---|
| Problem definition | P-01…P-05 | `docs/01-problem-sheet.md`, this log |
| Planning / requirements | P-06…P-08 | `docs/02-requirements.md` |
| System design | P-09…P-11 | `docs/03`, `docs/04`, `docs/05` |
| Implementation | P-12…P-16, P-22, P-24, P-25 | `backend/app/`, `frontend/src/` |
| Testing | P-17…P-19, P-23 | `backend/tests/`, `docs/09-test-report.md` |
| Documentation | P-20 | `README.md`, `docs/06`, `docs/07`, `docs/08` |
| Reflection | P-21 | `docs/10`, `docs/11` |
| Deployment | P-26, P-27 | `Dockerfile`, `docker-compose.yml`, `docs/12` |
| Verification (2nd pass) | P-28…P-32 | D-08 and D-09 fixes, `docs/images/` |
| Usability fix | P-33, P-34 | browser history integration, SPA fallback |

**34 prompts total** — 8 from the student, 26 engineered by the assistant. All five SDLC phases
required by Part B are represented, plus deployment and post-deployment verification.
