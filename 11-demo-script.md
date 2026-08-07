# Deliverable 7 — Final Demonstration Script

**Project:** FleetPulse · **Student:** Hafsa Aqeel (53317)
**Total running time:** 12 minutes + questions

---

## Option A — Docker (recommended if the examiner's machine is unknown)

```bash
cd hafsa-gen-ai-final
docker compose down -v                    # clean slate
docker compose --profile sim up --build   # everything, one command
```

Dashboard, API and Swagger all on **<http://localhost:8000>**. Skip to Act I; the terminals
below collapse into `docker compose logs -f simulator`. Run the tests with
`docker compose run --rm tests`. See `docs/12-docker-guide.md`.

---

## Option B — local processes (more to show, four terminals)

### Before the examiner arrives (10 minutes, off camera)

```bash
cd hafsa-gen-ai-final
source .venv/bin/activate

# Clean state — the demo must start from nothing and build up live
cd backend && rm -f fleetpulse.db && python -m app.seed --reset
```

Open **four** terminals and one browser window:

| # | Command | Purpose |
|---|---|---|
| 1 | `cd backend && uvicorn app.main:app --reload` | API |
| 2 | `cd frontend && npm run dev` | Dashboard |
| 3 | *(ready, not yet run)* the simulator command from Act II | Telemetry |
| 4 | `cd backend && pytest` — run it once now to warm the cache | Tests |

Browser tabs, in order: **dashboard** (`localhost:5173`), **Swagger** (`localhost:8000/docs`),
**`PROMPT_LOG.md`**, **`docs/09-test-report.md`**.

Sanity check: `curl localhost:8000/api/health` returns `"status":"ok"`.

**Have a fallback.** If the live demo fails, `docs/09-test-report.md` §6 contains the full
recorded output of a successful run — show that and keep talking.

---

## Act I — The theme, 90 seconds

> "My project theme comes from the Part A formula. I was born in **July**, which gives the
> **Transportation** domain. My roll number is 533**17**, and the last digit 7 gives
> **Monitoring System**. My technology is **Python**, which imposes the constraint that
> **AI must auto-generate the tests**.
>
> So: FleetPulse, a transportation monitoring system in Python, with an AI-generated test
> suite. It monitors a **mixed fleet** — city buses and refrigerated delivery trucks — which
> matters because it forces rules that apply to one vehicle type and not the other."

Show `docs/01-problem-sheet.md` §1, then scroll `PROMPT_LOG.md`.

> "Part D requires every AI prompt as proof. This is all of them — my prompts marked **[S]**,
> and the sub-prompts the AI wrote for itself marked **[A]**, in order, twenty-one of them,
> each tied to the artefact it produced."

---

## Act II — Bring the fleet to life, 2 minutes

Show the dashboard first, deliberately empty.

> "Twelve vehicles are registered — eight buses on two timetabled routes, four refrigerated
> trucks. Nothing has reported yet, so everything reads **offline**. Nothing here is
> pre-cooked; you will watch it fill in."

Terminal 3:

```bash
cd backend && python -m app.simulate \
  --scenario BUS-03=overheat \
  --scenario TRK-01=cargo_spike \
  --scenario BUS-05=deviation \
  --scenario BUS-07=dropout \
  --scenario BUS-02=fuel_drain
```

Within one tick the map populates.

> "Circles are buses, squares are trucks, solid lines are bus routes, dashed is the truck
> run, small dots are timetabled stops. Top right says **live (ws)** — that is a WebSocket,
> not polling. And note the counters: eleven reporting out of twelve. I have armed five
> faults; four vehicles are simply healthy and stay quiet. A monitoring system that alerts
> on everything is as useless as one that alerts on nothing."

**Leave this running for the rest of the demo.**

---

## Act III — The architecture, 2 minutes *(while faults ramp)*

Open `docs/03-architecture.md`, show the container diagram.

> "The governing idea is a **pure core with I/O at the edges**. Everything that decides
> whether something is wrong is a side-effect-free function. Everything that touches a
> database, a socket or the clock sits outside it."

Open `backend/app/rules/engine_temp.py`.

> "This is a whole rule. No database, no clock — even 'now' is passed in. And this shape is
> a **direct consequence of the AI constraint**. My first design had rules as methods on the
> ORM model; when I asked the AI to generate tests for it, every test needed a database
> session and a patched clock. So I inverted the design. The requirement to auto-generate
> tests is what produced the architecture."

Open `backend/tests/test_rules_engine_temp.py`.

> "Which is why a test looks like this — three lines, no mocks. Two hundred and seventy-eight
> of them run in 1.4 seconds."

---

## Act IV — Alerts appear live, 3 minutes

By now (~60–90 s in) the first alerts are on screen.

**1. Overheating — watch it climb.** Click **BUS-03**.

> "The dashed lines on this chart are the thresholds. The temperature curve is walking up
> towards them. A chart without its limit is a record; a chart *with* its limit is a
> prediction — that is the difference between reporting a breakdown and preventing one."

Back to the overview; point at the BUS-03 card as it escalates from ⚠ to ⛔.

> "It first fired as a **warning** at 105 °C and has now escalated to **critical** past
> 115 °C — same alert, ratcheted up. Severity increases but never decreases on its own:
> an operator who has seen 'critical' must not find it quietly downgraded."

**2. Deduplication — the number that matters.**

> "Look at **×27** on this card. That is twenty-seven readings collapsed into one alert. At
> a five-second interval, one alert per firing would be 720 alerts an hour from a single hot
> engine. This is the difference between a usable screen and an unusable one — and it is a
> design decision I made, not something the AI produced."

**3. Truck-only rule.** Point at TRK-01's `CARGO_TEMP_EXCURSION`.

> "Cargo temperature only applies to trucks. Buses reporting the same value raise nothing —
> the gating is data on the rule, not a branch in the engine."

**4. Route deviation.** Point at BUS-05 drifting off its corridor line on the map.

**5. The offline vehicle** *(should appear around the 2.5-minute mark)*.

> "**BUS-07** has gone silent. This is the interesting one: 'no data arrived' cannot be
> detected by looking at data that arrived. A background sweeper raises it — and when the
> vehicle comes back, that alert closes itself, because recovery is directly observable."

**6. Work the queue.** Acknowledge one alert, then resolve it.

> "Acknowledge means 'I am handling this'. Resolve closes it. A resolved alert is terminal —
> if the fault recurs it raises a *new* alert, so the history stays honest."

---

## Act V — Tune a rule without touching code, 90 seconds

Go to **Settings**. Change **Overspeed tolerance** from 5 to 25. Save.

> "That took effect on the very next reading — no restart, no code change, no deployment.
> Requirement FR-22, and it is why every threshold is injected into the rules rather than
> written as a constant."

Change **Engine critical** to 90 (below the warning value) and save.

> "And it refuses that: critical must be above warning, otherwise one of the two bands
> becomes unreachable. A cross-field invariant Pydantic cannot express field by field."

Press **Reset defaults**.

---

## Act VI — The tests and the defects, 2 minutes

Terminal 4:

```bash
pytest
```

> "290 passed. Rule-engine coverage 98.8% against a 90% target. Every one of these was
> AI-generated — prompts P-17, P-18 and P-19 in the log."

Open `docs/09-test-report.md` §5.

> "But the honest part of this project is the defect log. The adversarial prompt found seven
> real bugs, and two of them are the ones I would want you to ask about.
>
> **D-06:** the ingestion endpoint is synchronous, so FastAPI runs it in a worker thread,
> where `asyncio.get_running_loop()` raises. Every WebSocket broadcast was being silently
> dropped. **The full suite passed** — because the AI generated tests for the behaviour it
> had written, including the broken part.
>
> **D-07:** the schedule rule projects `distance / speed`. Tests covered zero speed and
> cruising speed. Nobody tested **1.5 kph** — a bus easing into a stop. At that speed it
> projects an arrival an hour late, and the entire bus fleet went critical at every stop.
> Green suite, visibly broken system.
>
> Both were caught by running the whole thing. A generated suite proves the code matches its
> own assumptions. It cannot tell you the assumptions were wrong."

---

## Closing, 30 seconds

> "Every SDLC phase used AI and every prompt is logged. What I did myself was every
> architectural decision, the deduplication semantics, all seven defect diagnoses, and the
> judgement about what an operator actually needs at two in the morning.
>
> And it is not finished: there is no authentication, the throughput target was never load
> tested, and the accessibility work has not been audited. Those are written down as
> unverified in the report rather than claimed."

Stop the simulator with `Ctrl+C`.

---

## Timing summary

| Act | Content | Minutes |
|---|---|---|
| I | Theme derivation and prompt log | 1.5 |
| II | Start the fleet | 2 |
| III | Architecture and the constraint's effect | 2 |
| IV | Live alerts, escalation, dedup, offline, lifecycle | 3 |
| V | Runtime threshold tuning | 1.5 |
| VI | Tests and the defect log | 2 |
| — | Closing | 0.5 |
| | **Total** | **12.5** |

---

## Likely questions, with short answers

| Question | Answer |
|---|---|
| *How is this unique to you?* | Formula gives 1,200 base combinations; this is (Transportation, Monitoring, Python). Beyond that: mixed bus+truck fleet forcing type-gated rules, React SPA on a Python backend, and a deterministic simulator with an optional GTFS path. |
| *Did you write any of the code?* | I wrote every architectural decision and the semantics that make it usable — deduplication, severity ratcheting, offline detection strategy, the alert-value snapshotting. AI drafted implementations from those decisions; the prompts are all logged. |
| *Why SQLite?* | Portability. The demo must run on any machine with no server. The schema is Postgres-compatible — change one environment variable. |
| *Why no map library?* | Leaflet needs raster tiles from a remote host. The demo has to run offline, so the map is an SVG projection I draw myself. |
| *Why is coverage 87% and not higher?* | The gap is two CLI entry points and a background loop. Excluding those, it is 93%; the rule engine is 98.8%. The uncovered lines are itemised and justified in §4 of the test report. |
| *Is 200 readings/second real?* | No — that target was never load-tested, and it is marked unverified in the report. |
| *Show me an AI prompt and what it produced.* | `PROMPT_LOG.md` P-13 → `app/rules/`; P-17 → `tests/test_rules_*.py`; P-19 → the defect log. |
| *What would you do next?* | Authentication, a real load test, and alert delivery beyond the dashboard — an alert nobody is looking at is not monitoring. |
