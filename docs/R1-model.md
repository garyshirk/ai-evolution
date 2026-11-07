# R1 implemented model — Milestone D

The approved architecture remains authoritative. This document records survival, reproduction, inheritance, mutation, and numerical conventions. Full evolutionary reporting and calibration remain deferred.

## Tick and event ordering

Decision ticks have fixed duration dt (default 0.1). At tick start, living organisms choose nearest food whose center is within inherited vision radius, using food ID for exact distance ties. They pursue at inherited maximum speed, stopping at the consumption circle. Otherwise they search at half maximum speed, retaining heading unless a seeded turn occurs with probability `1 - exp(-dt / search_turn_interval)` (mean interval 2). New headings are uniform in radians. Organisms do not detect or collide with each other.

Decisions remain fixed through a tick. A lost target does not trigger immediate replanning: the loser continues to the previously planned consumption-circle entry position and waits until the next tick. Incidental encounters are possible during this movement.

The resolver repeatedly finds the next wall contact, planned pursuit stop, food arrival, food encounter, energy depletion, lifespan expiry, or tick end across all organisms. It advances every living organism by the same elapsed time at its current constant velocity, integrating expenses, then resolves:

1. Deaths (starvation before age when both are simultaneous).
2. Scheduled food arrival, applying the cap before same-time consumption.
3. Food consumption, using chronological first arrival and seeded exact ties.
4. Reflected directions or planned stops for outgoing movement.

After the complete tick's events and death resolution, process a snapshot of surviving parents in increasing ID order for reproduction. Insert all newborns only after this phase. Their birth time is the tick endpoint, age is zero, movement mode is idle, and actual speed is zero. They do not sense, eat, move, spend upkeep, or reproduce until the following tick. If extinction ends a tick early, no reproduction occurs.

A meal stops movement for the rest of the tick and makes that organism ineligible for further meals until the next tick. Baseline and vision upkeep continue while stationary. The next tick replans normally.

Walls split paths into straight segments. Each candidate food disk is intersected analytically against the entire current segment, including search motion, tangency, initial overlap, and the tick endpoint. Reflect both velocity components at a corner; permit multiple wall contacts per tick. An expanded bounding box excludes distant food before solving disk intersections. It does not replace swept geometry with endpoint checks.

All candidates are recomputed after each event. A food item cannot be consumed before its actual spawn time. Incoming food can immediately feed an eligible overlapping organism. Death always wins over a same-time meal, including an organism depleting exactly upon arrival. Expenses and movement stop at death; a meal before depletion immediately changes the next depletion prediction.

## Competition and randomness

Distinct arrival times determine food ownership without a random draw. At an exact conflict, sort candidate IDs and choose uniformly with the run generator. When simultaneous food claims share contenders, shuffle the canonically sorted food IDs with the seeded generator, then award each item after rechecking one-meal eligibility. Disjoint simultaneous food claims do not need random ordering. No storage iteration order gives a competitive advantage.

Initialization draws each founder's x, y, speed, vision, and heading, in ID order; then each initial food's x and y. After initialization, schedule the first food arrival. Subsequent random draws occur in documented event order: tick-start search decisions in organism ID order, spawn position if accepted, next arrival wait whether accepted or discarded, genuine encounter ties, and tick-end births in parent ID order. Accepted and capped arrivals therefore need not share future random draws across different parameter sets. Same-seed parameter comparisons do not promise matching ecological events.

For each eligible parent, draw the speed mutation test and its delta if selected, then the vision mutation test and its delta if selected, then a radial uniform draw, placement angle, and newborn heading. Always draw the per-trait probability test, even at probability zero or one. Placement and heading draws occur even for a zero placement radius. Noneligible parents draw nothing for reproduction. Inspection, summary calculations, and birth highlights never consume model randomness.

## Reproduction, inheritance, and mutation

The default reproduction threshold is energy strictly greater than 60. The parent must also retain strictly positive energy after transferring 25 to the child and paying 5 overhead. Test eligibility after all tick costs, meals, and deaths. Each parent produces at most one offspring per tick regardless of its excess reserve. There is no reproduction-count death, fitness score, population-size target, or inherited energy efficiency.

Each child gets a new monotonic organism ID, parent ID, generation plus one, unchanged founder lineage ID, its own birth time, and its configured energy reserve. Its position is uniform within the placement disk of radius 1: radius `R * sqrt(U)` and uniform angle. Reflect displaced coordinates at the world edges, allowing multiple overshoots. Its initial heading is a separate seeded uniform angle. Organisms can overlap without collisions.

Heading is not genetic and is never copied from the parent or forced to differ. A newborn's first active tick can replace that heading with pursuit of nearby food, so common food targets can make parent and offspring travel in the same direction even though their initial heading draws were independent.

For each trait independently, with probability 0.05 add a uniform delta in `[-m * range, +m * range]`, with default m = 0.05. Thus default speed deltas range from -0.375 to +0.375 and vision deltas from -1.45 to +1.45. Probability and magnitude are independently configurable for speed and vision. When mutation does not occur, copy the exact floating-point trait value. A selected zero-magnitude mutation event also leaves the trait unchanged; diagnostic mutation counters count events, not guaranteed nonzero numerical changes.

Reflect mutations into speed [0.5, 8] and vision [1, 30]. Reflection uses a triangular fold modulo twice the valid range, handling repeated overshoots without clamping. Perturbation ranges that would overflow are rejected in configuration. Reflection near bounds affects the resulting trait distribution; it does not represent knowledge of advantageous traits. There is no trait adjustment during an individual's lifetime.

Statistics count total births, highest generation ever reached, transferred offspring reserves, reproduction overhead, and mutation events. Current mean speed and vision describe living individuals with equal weight; an empty population has null means. These summaries do not establish a universal optimum or separate chance from selection by themselves.

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
                - reproduction overhead
```

Child reserves are internal transfers and cancel in the population ledger. `offspring_energy_transferred` records those transfers for diagnostics but is not added to population energy. Parents lose exactly the allocation plus overhead per birth. Only overhead is a new reproduction expense; no energy is created.

Starvation and age have exclusive primary counts. Simultaneous starvation/age uses primary cause starvation plus a simultaneous-age flag. Age death removes any positive reserve, recorded in the ledger. Death snapshots include final position, energy, inherited traits, lineage, offspring count, and precise death time. The summary reports living energy minus the ledger's expected energy as a floating-point residual. Long-run totals accumulate rounding error; inspect this relative to the run's energy scale.

Death records are retained for inspection in memory. With births now enabled, long runs can grow that archive without bound. No silent biological culling, fixed population size, or arbitrary history truncation is introduced. History retention/performance should be addressed before extensive long-run analysis; the current smoke tests do not exercise unbounded workloads.

## Food process

Independent exponential waits implement a Poisson process. Sample U uniformly from the open interval (0, 1), retrying zero, and use `-log(U) / rate`. Zero rate disables new arrivals. Accepted items have uniform random positions and configured energy; they do not regenerate where an item was consumed. At cap, count and discard the arrival without queuing a backlog; schedule the next wait regardless. Record attempts, accepted spawns, and discarded spawns.

The rate is a real-valued count per simulated time unit, not rounded to an integer: rates such as 0.05 or 0.1 are supported. Initial Food is an independent integer initialization count, validated against the food cap and exposed in Advanced settings. Initial Food 10 with rate 0.1 places ten seeded items at initialization and schedules later random arrivals at mean interval 10 simulated time units. Both settings apply only on Reset. Defaults remain initial count 200 and rate 8.

If a positive waiting time rounds to the current absolute timestamp, use the next representable larger float for strict clock progress. Initial food is separate from spawn counters. IDs increase only for actually created items and are never reused.

## Time, termination, and numerical constraints

Normal tick boundaries derive from integer tick indices times dt. Sub-tick event geometry uses times relative to the current tick. Age expiry is birth time plus configured lifespan. Extinction ends processing immediately, even in a partial final tick; do not spawn or spend energy after it. Count that terminal tick once, preserve the exact extinction time, and make later step requests no-ops. An initially empty world is terminal at time zero.

Physics uses double precision. Compare computed event times strictly; do not merge nearly simultaneous arrivals into a time bin. For a directly pursued target, planned stopping and consumption share the analytic radial entry time `(distance - radius) / speed`; using two independently rounded roots can otherwise strand a pursuer just outside the circle. Incidental circle intersection repairs only ulp-scale negative discriminants or roots just beyond a segment endpoint (eight ulps); this is geometric roundoff repair, not a general race tie tolerance. The conservative broad phase and wall-coordinate clamp keep positions within the rectangle. Ledger comparisons allow floating-point rounding error; they do not represent an energy source. A zero-time progress guard raises an explicit error if events repeatedly fail to change state; it never silently skips physics.

Mathematically equal geometries can yield slightly different computed arrival times across platforms. Exact computed equality uses seeded randomness. Replay is promised in the supported same-version/runtime environment, not arbitrary-platform bit identity. One-meal-per-tick limits, once-per-tick sensing, and once-per-tick reproduction remain dt-sensitive model assumptions. Continuous encounters remove tunneling but do not imply all outcomes are invariant to changing dt.

The simple resolver scans candidate organisms and foods, with an exact segment-box rejection filter. Large populations/food caps or requested fast-forward may exceed real-time compute capacity. Playback falls behind instead of changing physics; spatial indexing is deferred until profiling justifies additional complexity.

## Milestone scope

Defaults remain the architecture's starting values. No calibration has been attempted, no population is artificially stabilized, and no food/energy rescue rule exists. Descendants may survive after the founders' lifespan, but persistence is not guaranteed. Only initial smoke observations are reported, not the later multi-seed 1,000-unit calibration target. Milestone E adds descriptive evolutionary charts and exports, documented in `R1-reporting.md`. No explicit fitness score, social behavior, or LLM agents are implemented.
