# R1 reporting and exports — Milestone E

Reporting describes the model's outcomes. It does not change movement, energy, food, reproduction, mutation, death, or the random sequence. No fitness score, automatic causal conclusion, or calibration is included.

## Measurements

`metrics.py` is independent of Flask and the browser. `measure()` reads the authoritative world after the completed tick's reproduction phase. Initial measurements are taken after initialization; terminal measurements preserve the exact extinction time, including a partial last tick.

Current population includes living founders and offspring. Initial population is the configured founder count. Birth/death totals and highest generation reached are cumulative since reset. Starvation and maximum-age deaths retain their exclusive primary causes from the engine. Birth/death deltas compare consecutive originally recorded samples, not necessarily consecutive rows left after retention truncation.

Speed and vision means are unweighted arithmetic means across living organisms. Standard deviations are **population** standard deviations: `sqrt(sum((value - mean)^2) / N)`, using stable summation. A singleton has standard deviation zero. An empty population has unavailable (`null`) means and standard deviations, not zero-valued traits.

Histograms contain ten fixed bins across the configured allowed inherited-trait range. Bins include their lower edge and exclude their upper edge, except the final bin includes the maximum. Counts always sum to current living population. Empty histograms have ten zero counts and display “No living organisms.” Dead organisms are excluded.

## Sampling without influencing physics

`MetricsCollector` owns its reporting history separately from `WorldState`. It never writes organism state or consumes random numbers. The initial point is included, followed by periodic samples and a terminal point at extinction. An initially empty world has one initial point marked terminal. A terminal point on a periodic boundary is recorded once.

The requested default interval is **one simulated time unit**. At default `dt=0.1`, samples are exactly at 0, 1, 2, …, plus any off-grid extinction time. Sampling happens after individual physics ticks, even when advancement is requested in a batch. Pausing preserves history; resetting creates a new collector starting at time zero.

Custom dt values need not divide one unit. In that case the effective interval is `ceil(requested_interval / dt) * dt`, the next whole-tick interval at least as long as requested. For example, dt 0.3 yields a consistent interval of 1.2. Both requested and effective intervals, and the number of ticks per sample, are reported in metadata. This reporting-resolution limitation avoids inserting physics boundaries or fabricating interpolated populations. Biology and its outcomes remain unchanged.

The Python API accepts reporting-only `sampling_interval`, `history_limit`, and `collect_metrics` options on `Simulation`. They are not biological parameters. Tests compare runs with collection enabled and disabled, including exact model RNG states.

## Retention and performance

Default history retention is **10,000 samples**: the initial point plus the most recent 9,999 periodic/terminal samples. Immutable, slotted sample records and a bounded deque keep this history's memory bounded. The collector reports total/retained/dropped counts and monotonic sequence IDs. A dropped middle section is not recoverable from the application; export results before the desired window is lost. CSV exposes gaps through sequence IDs; JSON additionally includes retention metadata.

The browser requests history incrementally, with at most one history request in flight. If it falls behind the retained window, it replaces its cache with retained data. The browser cache has the same bound. Charts show gaps rather than joining the initial point across omitted history.

Canvas chart drawing and distribution refresh run at most four times per second, separately from world animation and physics. Closed reporting panels do not draw or fetch history. For long retained histories, chart rendering uses bucket first/last/minimum/maximum points and gap/null markers, retaining local extrema in the display. This decimation changes only drawing; retained samples and exports keep their original measurement values.

Existing organism/death snapshots are still part of the simulation API. The older death archive remains unbounded, and large living populations remain computationally expensive. Bounded reporting history does not solve those separate limitations. No population cap, biological rescue, database, or persistence system was added.

## Graphs and interpretation

- Population history plots living count versus simulated time, including zero at extinction.
- Mean inherited maximum speed and vision histories plot the means of the living population. Their vertical scales use configured trait limits; no unavailable value is drawn as zero.
- Current histograms show the current live distribution, not a historical snapshot. Their status line gives current measurement time and standard deviations.
- History status gives the last recorded time, interval birth/death counts, and any omitted history. Current numerical summaries can be newer than the last periodic graph point; both times are explicit.

Means and variation can change through mutation, drift, bottlenecks, population composition, and environmental selection. A trend alone does not establish its cause or identify a universal optimum. No automatic interpretation is generated.

Reports are in the existing independently scrolling control pane. The complete Environment remains fitted to its viewport with unchanged world aspect ratio; expanding reports does not enlarge the world pane.

## Export workflow

The browser's **Export CSV** and **Export JSON** buttons pause/drain the current short advancement batch, then download a stable snapshot. Resume continues the same experiment/history. Exports read the applied seed and configuration on the server, never pending UI edits. A stale run ID is rejected.

Headless usage:

```sh
.venv/bin/python -m ai_evolution headless --seed 42 --steps 100 \
  --export-csv /tmp/r1-measurements.csv --export-json /tmp/r1-report.json
```

The files are ordinary in-memory-generated exports written to the supplied paths, not saved simulations. Existing files at those paths are replaced. Exports do not contain RNG checkpoints and cannot resume a run. There is no database or automatic disk persistence.

### CSV schema (version 1)

Columns, in order:

```text
sequence,sample_type,time,step,terminal,population,initial_population,total_births,total_deaths,starvation_deaths,age_deaths,highest_generation,mean_speed,mean_vision,speed_stddev,vision_stddev,births_since_previous,deaths_since_previous,food_consumed
```

Unavailable numbers and an unsequenced current view use blank cells. `terminal` is `True`/`False`. Sample types are `initial`, `regular`, `terminal`, and optionally `current`. If export occurs between scheduled samples, an additional `current` row records the exact final snapshot without adding it to collector history. If export is at an already recorded step, no duplicate row is appended. Interval deltas on a current row cover only the time since the last recorded sample.

CSV contains retained time-series measurements. Use the companion JSON report for configuration/version metadata and explicit retention details. Sequence gaps mean data was omitted, not that the population stayed constant.

### JSON schema (version 1)

The report includes:

- Schema version, experiment/release milestone, seed, engine/software version, and Python version.
- Complete applied biological configuration.
- Final time/step, terminal status, cumulative and current statistics, and energy accounting.
- Current trait-distribution bin edges/counts.
- Reporting interval/resolution and retention metadata.
- Retained measurements, with the same optional final `current` row as CSV.

Unavailable values are JSON null; NaN/Infinity are not emitted. No wall-clock export timestamp is added, so identical seeded runs in the same runtime environment can produce byte-identical exports. Platform/Python-version reproducibility limits from the model documentation still apply.


## Paired traits and living-organism snapshot (Milestone E refinements)

The scatter plot places **each currently living organism** at (inherited maximum speed, inherited vision radius), directly from its authoritative snapshot. Axes use the configured trait bounds. Every organism is drawn, including singleton populations and identical trait pairs; translucent dots accumulate opacity at overlaps without jittering or altering values. Empty populations display “No living organisms.” Drawing is throttled with the other reports to four updates per second.

Hover within seven CSS pixels of a point to show its ID and full JavaScript numeric trait values in the status line/native tooltip. Nearby points are ordered by organism ID; repeated clicks cycle them and select the organism in the existing inspector. The inspector dropdown remains available for keyboard selection. Dense clusters may require many clicks; opacity is not a quantitative density scale. Trait combinations, clusters, or correlations do not prove natural selection. Offspring counts are lifetime-to-date counts, strongly affected by age and reproductive opportunity, not a definitive fitness measure.

JSON schema version 1 gains an additive `living_organisms` array, sorted by ID, at the report's `final_time`. All existing fields and time-series measurements remain present. Each entry contains:

| Field | Meaning |
| --- | --- |
| `id` | Organism's deterministic identifier |
| `parent_id` | Parent identifier; null for founders |
| `founder_lineage_id` | Identifier of the lineage's founder |
| `generation` | Founder = 0, parent generation + 1 thereafter |
| `speed` | Inherited maximum speed, distance per simulated time unit |
| `vision_radius` | Inherited vision radius, distance units |
| `age` | Final simulated time minus birth time |
| `energy` | Current energy reserve |
| `offspring_count` | Offspring produced so far by this organism |

The array contains only living organisms and is empty at extinction. It is a current snapshot, not an organism history, genealogy archive, or resumption checkpoint. CSV time-series columns remain unchanged. Export size and scatter work scale with the living population; no additional persistent individual history is collected. The scatter reuses the existing browser state payload, with no additional model reads or random draws.


For Milestone F.1 batch execution, aggregate denominators, retained run histories, and batch JSON exports, see `R1-batch.md`. The single-run export formats and biological measurements documented here are unchanged.
