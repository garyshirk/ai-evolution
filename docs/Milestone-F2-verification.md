# Milestone F.2 verification

Verified November 8, 2026 against the uncommitted software version 0.7.0, using the existing Python 3.13.5 environment and in-app browser.

## Automated verification

```sh
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/python -m pip check
git diff --check
```

The final complete suite passed **190 tests in 9.896 seconds**, including all 164 F.1 tests and 26 new statistical/library/API regression tests. Dependency integrity and whitespace checks passed. Pip's sandbox-cache warning is unchanged; no packages were installed.

Hand-calculated fixtures use three final populations [8, 0, 4]: mean/median 4, sample SD 4, minimum 0, maximum 8. Surviving speed means [4, 8] have mean 6 and sample SD sqrt(8); vision means [6, 14] have mean 10 and sample SD sqrt(32). Observed post-initial minima [4, 0, 4] and a recorded exact-one event test the denominators independently. Expected time-one population [4,1,6] has mean 11/3 and p90 5.6. Final population p10 is 0.8; surviving speed p10 is 4.4. Paired population differences [2,0,−2] have mean 0 and sample SD 2; trait differences [1,−1] use two valid pairs.

Tests cover:

- Multiple library entries, independent internal IDs, rename, removal, reference ownership, capacity protection, completed-batch auto-retention and survival of earlier batches after replacement.
- F.1 schema imports, malformed JSON/single-run/incompatible schema rejection, count/config/endpoint/trait validation, missing fields, nonfinite/oversized input, and safe string-name handling.
- Means, sample SD, medians/ranges, singleton/empty/all-extinct observations, extinction percentages, initial-measurement exclusion, observed bottlenecks, unknown minima and explicit denominators.
- Percentiles, contributor counts, extinction zero extension, unavailable traits, float-time tolerance, missing/retained/irregular schedule rejection without interpolation, and bounded pathological time grids, and sub-nanosecond time grids without merging adjacent observations.
- Configuration differences, matching/nonmatching seed sets, paired surviving-only traits, duration incompatibility, zero/overflowing relative-change denominators.
- Native and imported replay from the library after current-batch replacement, exact initial single-engine state, unchanged Single Simulation reads, unknown engine/Python version refusal, and stale/malformed identifiers.
- Library-capacity exhaustion leaves a newly executed batch completed and exportable rather than discarding existing entries or changing biology.

## Browser verification

Against localhost port 5056, then the final preview on port 5057:

1. Executed a small native batch: three seeds 0–2, duration 3, initial population 5 and initial food 20, other parameters standard. Results auto-added it, displayed final statistics, observed minima, initial/endpoint histories and a selectable individual run. Renamed it “A food 8.”
2. Imported an available F.1-compatible schema-1 fixture with engine version 0.6.0, three seeds 10–12 and full native-engine results. It coexisted with the native batch, used its filename as name, and required no rerunning. An initial attempt referenced a historical Downloads file that was no longer present; choosing an available file resolved the file-read failure.
3. Selected imported run 2 and opened it in Single Simulation: seed 11, Initial Population 5, ready/paused at time zero. The library persisted when returning to Batch Experiments.
4. Executed a second native three-seed batch with the same seeds/duration/configuration except food rate 1. Both native experiments and the import remained separately available.
5. Compared the two native batches: configuration differences highlighted food replenishment, matching seed sets enabled paired B−A statistics, speed metric showed blue/orange mean lines and translucent 10th–90th percentile bands with the common time axis. These short runs are UI smoke tests, not evidence of evolutionary selection or a food-rate outcome.
6. Compared against the imported nonmatching seed set: paired comparison became explicitly unavailable while aggregate comparisons remained usable.
7. Imported an unsupported-schema file: a useful error appeared and existing experiments remained intact. Removed only the temporary imported entry and verified both native experiments remained.
8. Exported the retained native library experiment through the browser. Parsed and revalidated the downloaded file: schema 1, three complete results, 12 original samples, and full food-rate-8 configuration preserved.
9. No JavaScript console errors were observed. Canvas charts resized in the existing independently scrolling Batch pane. At 1280×640, the complete Single Simulation world fit between y=185.8 and y=589.7; at 390×700 it fit between y=144.5 and y=440.6. No horizontal page overflow was observed, and viewport overrides were removed. No biological/default/world-layout code changed.

A synthetic performance fixture with **100 runs × 2,001 recorded points = 200,100 measurements** was validated and analyzed into 2,001 exact aggregate points in approximately **1.104 seconds** locally. No simulation was run for that benchmark; it measures reporting throughput, not biological runtime, a frame-rate guarantee, or memory under concurrent imports. Long-series drawing uses display-only envelopes and a time-index contributor-count slider, avoiding thousands of DOM chart elements.

The illustrative 50-run × 2,000-unit food-8/food-1 acceptance experiment was not executed in full; it is not required to establish biological outcomes in F.2. Its sample budget fits the configured library/import limits. No calibration or F.3–F.5 work was performed.

## Manual review checklist

- Launch `.venv/bin/python -m ai_evolution serve --port 5057`; open http://127.0.0.1:5057/. Use an unused port or stop an older server first.
- Verify Single Simulation controls, Initial Population, inspection and existing charts/exports still work.
- Batch → Run: begin with 3 runs, duration 3, seed 0, population 5, food 20. Check progress/cancel/current-run export and automatic completed retention in Results.
- Results: import a saved F.1 batch JSON, then another. Confirm filename names, separate run sets and configuration summaries. Rename one with ordinary text, remove a test entry, and verify remaining entries/results are unchanged. Export before removal/server restart.
- Try a single-simulation export, malformed JSON, unsupported schema or inconsistent fields; confirm useful rejection without losing existing experiments.
- Check descriptive values and sample counts against a small known dataset. Confirm singleton sample SD is N/A and extinct traits are unavailable; inspect observed-minimum counts and threshold-5 caveat.
- Switch aggregate metrics, inspect bands and the expandable recorded-time contributor slider. Import a history with missing/incompatible samples and confirm a reason replaces misleading aggregate trajectories.
- Select individual runs from both native and imported entries. Expand the configuration and replay; verify seed, Initial Population and zero simulated time. Unknown engine/Python versions should disable replay with a reason.
- Compare two distinct experiments, inspect highlighted configurations, B−A/percentage-change labels, valid paired-trait counts, actual seed sets and all three overlay metrics. Check nonmatching seeds, different durations and multiple parameter changes produce warnings/disabled paired or trajectory features as appropriate.
- Resize to a compact laptop window and a narrow viewport. Ensure complete Environment visibility, pane scrolling, resized charts and readable tables. Browse while a background batch runs.
- For the illustrative acceptance scenario, use 50 runs, duration 2,000, seeds 0–49 for A and B, changing only food rate 8 versus 1. Export both and import for analysis without rerunning. Expect substantial execution time; no survival or directional-trait outcome is guaranteed.

## Limits and review decisions

See `R1-statistics.md` for precise formulas and policy. The library is temporary server memory; files are permanent storage. Limits are 8 experiments, 1,000,000 retained samples and 256 MiB per request/file. Incompatible or incomplete schedules disable aggregate trajectories rather than interpolate. Bottleneck percentages use only runs with post-initial observations and expose missing-observation counts; sampled minima can miss transient events. Trait statistics/bands condition on survival.

Replay permits known unchanged-model releases 0.6.0/0.7.0 with the exact same Python version; other data remains analyzable. This is conservative runtime compatibility, not a cross-platform bit-identity guarantee. The model, biological defaults, RNG and simulation steps were not modified. F.2 remains uncommitted and unpushed for review.

## Post-F.2 Repository Workflow Verification

November 8, 2026: A post-F.2 workflow smoke test confirmed access to `/Users/garyshirk/Projects/ai-evolution`.
Verified the GitHub remote `https://github.com/garyshirk/ai-evolution.git` and synchronized `main` after fetching.
Confirmed that F.2 commit `ec051c855bd496da631815fc5fedfb3c771d2220` remained in branch history.
This documentation-only update was committed and pushed to verify the existing development workflow.
