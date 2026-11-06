# R1 implemented model — Milestone C

The approved architecture remains authoritative. This document records the implemented survival mechanics and numerical conventions. Reproduction and mutation remain deferred.

## Tick and event ordering

Decision ticks have fixed duration dt (default 0.1). At tick start, living organisms choose nearest food whose center is within inherited vision radius, using food ID for exact distance ties. They pursue at inherited maximum speed, stopping at the consumption circle. Otherwise they search at half maximum speed, retaining heading unless a seeded turn occurs with probability `1 - exp(-dt / search_turn_interval)` (mean interval 2). New headings are uniform in radians. Organisms do not detect or collide with each other.

Decisions remain fixed through a tick. A lost target does not trigger immediate replanning: the loser continues to the previously planned consumption-circle entry position and waits until the next tick. Incidental encounters are possible during this movement.

The resolver repeatedly finds the next wall contact, planned pursuit stop, food arrival, food encounter, energy depletion, lifespan expiry, or tick end across all organisms. It advances every living organism by the same elapsed time at its current constant velocity, integrating expenses, then resolves:

1. Deaths (starvation before age when both are simultaneous).
2. Scheduled food arrival, applying the cap before same-time consumption.
3. Food consumption, using chronological first arrival and seeded exact ties.
4. Reflected directions or planned stops for outgoing movement.

A meal stops movement for the rest of the tick and makes that organism ineligible for further meals until the next tick. Baseline and vision upkeep continue while stationary. The next tick replans normally.

Walls split paths into straight segments. Each candidate food disk is intersected analytically against the entire current segment, including search motion, tangency, initial overlap, and the tick endpoint. Reflect both velocity components at a corner; permit multiple wall contacts per tick. An expanded bounding box excludes distant food before solving disk intersections. It does not replace swept geometry with endpoint checks.

All candidates are recomputed after each event. A food item cannot be consumed before its actual spawn time. Incoming food can immediately feed an eligible overlapping organism. Death always wins over a same-time meal, including an organism depleting exactly upon arrival. Expenses and movement stop at death; a meal before depletion immediately changes the next depletion prediction.

## Competition and randomness

Distinct arrival times determine food ownership without a random draw. At an exact conflict, sort candidate IDs and choose uniformly with the run generator. When simultaneous food claims share contenders, shuffle the canonically sorted food IDs with the seeded generator, then award each item after rechecking one-meal eligibility. Disjoint simultaneous food claims do not need random ordering. No storage iteration order gives a competitive advantage.

Initialization draws each founder's x, y, speed, vision, and heading, in ID order; then each initial food's x and y. After initialization, schedule the first food arrival. Subsequent random draws occur in documented event order: tick-start search decisions in organism ID order, spawn position if accepted, next arrival wait whether accepted or discarded, and genuine encounter ties. Accepted and capped arrivals therefore need not share future random draws across different parameter sets. Same-seed parameter comparisons do not promise matching ecological events.

## Energy equations and units

Distance, simulated time, and energy use consistent arbitrary model units. For inherited vision v and actual constant segment speed u:

```text
baseline rate = b
vision rate   = kv * (v / vref)^2
movement rate = km * u * (u / uref)^2
```

Integrate each rate over the actual alive duration of each segment. Equivalently, movement expense is `km * actual_distance * (u / uref)^2`. The travel speed is not distance divided by the entire tick if an organism stops early. Searching at half speed costs one quarter as much movement energy per distance as pursuit at maximum speed (one eighth per moving time). Vision and baseline expenses apply at rest.

The next depletion deadline at constant rate is current time plus energy divided by total rate. Zero total rate has no depletion deadline. At depletion, final energy is zero and final position is limited to the affordable distance. No retrospective food credit or negative-energy borrowing is allowed.

The cumulative ledger is:

```text
living energy = initial organism energy + consumed food energy
                - baseline spent - vision spent - movement spent
                - reserve removed at death
```

Starvation and age have exclusive primary counts. Simultaneous starvation/age uses primary cause starvation plus a simultaneous-age flag. Age death removes any positive reserve, recorded in the ledger. Death snapshots include final position, energy, inherited traits, lineage, and precise death time. Records currently retain at most the founder population because reproduction is absent; revisit retention limits before unbounded birth histories become possible.

## Food process

Independent exponential waits implement a Poisson process. Sample U uniformly from the open interval (0, 1), retrying zero, and use `-log(U) / rate`. Zero rate disables new arrivals. Accepted items have uniform random positions and configured energy; they do not regenerate where an item was consumed. At cap, count and discard the arrival without queuing a backlog; schedule the next wait regardless. Record attempts, accepted spawns, and discarded spawns.

If a positive waiting time rounds to the current absolute timestamp, use the next representable larger float for strict clock progress. Initial food is separate from spawn counters. IDs increase only for actually created items and are never reused.

## Time, termination, and numerical constraints

Normal tick boundaries derive from integer tick indices times dt. Sub-tick event geometry uses times relative to the current tick. Age expiry is birth time plus configured lifespan. Extinction ends processing immediately, even in a partial final tick; do not spawn or spend energy after it. Count that terminal tick once, preserve the exact extinction time, and make later step requests no-ops. An initially empty world is terminal at time zero.

Physics uses double precision. Compare computed event times strictly; do not merge nearly simultaneous arrivals into a time bin. For a directly pursued target, planned stopping and consumption share the analytic radial entry time `(distance - radius) / speed`; using two independently rounded roots can otherwise strand a pursuer just outside the circle. Incidental circle intersection repairs only ulp-scale negative discriminants or roots just beyond a segment endpoint (eight ulps); this is geometric roundoff repair, not a general race tie tolerance. The conservative broad phase and wall-coordinate clamp keep positions within the rectangle. Ledger comparisons allow floating-point rounding error; they do not represent an energy source. A zero-time progress guard raises an explicit error if events repeatedly fail to change state; it never silently skips physics.

Mathematically equal geometries can yield slightly different computed arrival times across platforms. Exact computed equality uses seeded randomness. Replay is promised in the supported same-version/runtime environment, not arbitrary-platform bit identity. One-meal-per-tick limits, once-per-tick sensing, and mutation/reproduction when later introduced remain dt-sensitive model assumptions. Continuous encounters remove tunneling but do not imply all outcomes are invariant to changing dt.

The simple resolver scans candidate organisms and foods, with an exact segment-box rejection filter. Large populations/food caps or requested fast-forward may exceed real-time compute capacity. Playback falls behind instead of changing physics; spatial indexing is deferred until profiling justifies additional complexity.

## Milestone scope

Defaults remain the architecture's starting values. No calibration has been attempted, no population is artificially stabilized, and no food/energy rescue rule exists. With no reproduction and lifespan 200, all founder-only default runs must become extinct by simulated time 200; survival over 1,000 units is not a Milestone C target. No evolutionary-fitness score, births, mutation, social behavior, or LLM agents are implemented.
