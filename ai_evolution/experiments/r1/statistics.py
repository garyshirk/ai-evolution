"""Descriptive statistics over completed simulation replicates, never organisms."""

import math
from statistics import mean, median, stdev


def close_time(a, b, scale=None):
    tolerance = min(1e-9, scale * 1e-6) if scale is not None else 1e-9
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=tolerance)


def describe(values):
    values = list(values)
    return {"count": len(values), "mean": mean(values) if values else None,
            "stddev": stdev(values) if len(values) > 1 else None,
            "median": median(values) if values else None,
            "minimum": min(values) if values else None, "maximum": max(values) if values else None}


def percentile(values, fraction):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def experiment_statistics(data):
    runs = data["results"]
    survivors = [run for run in runs if run["survived"]]
    minima, low, one = [], 0, 0
    for run in runs:
        after = [row["population"] for row in run["measurements"] if row["time"] > 0]
        if after:
            minima.append(min(after))
            low += min(after) <= 5
            one += 1 in after
    extinct = len(runs) - len(survivors)
    def rate(count, denominator):
        return 100 * count / denominator if denominator else None
    return {
        "completed_runs": len(runs), "requested_runs": data["configuration"]["runs"],
        "population": describe(run["final_statistics"]["population"] for run in runs),
        "speed": describe(run["final_statistics"]["mean_speed"] for run in survivors),
        "vision": describe(run["final_statistics"]["mean_vision"] for run in survivors),
        "extinct_runs": extinct, "extinction_percentage": rate(extinct, len(runs)),
        "minimum_observed_population": describe(minima),
        "minimum_populations": [{"seed": run["seed"], "minimum": min(values) if values else None}
            for run in runs for values in [[row["population"] for row in run["measurements"] if row["time"] > 0]]],
        "bottlenecks": {"threshold": 5, "observed_runs": len(minima), "unobserved_runs": len(runs) - len(minima),
                        "at_most_5": low, "at_most_5_percentage": rate(low, len(minima)),
                        "exactly_1": one, "exactly_1_percentage": rate(one, len(minima))},
        "notes": ["Each completed simulation is one observation; SD uses N-1 (N/A below two observations).",
                  "Final population includes extinct runs as zero. Traits include surviving-run means only; counts are explicit.",
                  "Bottlenecks are observed after initialization, not continuous minima. Threshold 5 is exploratory. Percentages use runs with post-initial measurements; exact-one events between samples can be missed.",
                  "Retained-history gaps can hide bottlenecks; minima describe only exported samples."] +
                 (["Incomplete batch: partial/cancelled/failed runs are not observations; summaries may be biased."] if len(runs) != data["configuration"]["runs"] else []),
    }


def trajectories(data):
    """Align actual samples to one schedule; only extinct population gets carry-zero."""
    runs = data["results"]
    def unavailable(reason):
        return {"available": False, "reason": reason, "rows": []}
    if not runs:
        return unavailable("No completed runs to align.")
    interval = runs[0]["reporting"]["effective_interval"]
    same_time = lambda a, b: close_time(a, b, interval)
    if any(not same_time(run["reporting"]["effective_interval"], interval) for run in runs):
        return unavailable("Sampling intervals differ between runs; no interpolation was performed.")
    if any(run["reporting"]["dropped_samples"] for run in runs):
        return unavailable("Exported histories contain retention gaps; aggregate trajectories are unavailable.")
    duration = data["configuration"]["duration"]
    ratio = duration / interval
    if not math.isfinite(ratio) or ratio > 20000:
        return unavailable("Aggregate time grid exceeds the supported 20,000-point limit.")
    count = math.floor(ratio)
    times = [index * interval for index in range(count + 1)]
    if same_time(times[-1], duration):
        times[-1] = duration
    else:
        times.append(duration)
    # Reject extra nonterminal times instead of silently discarding an irregular schedule.
    for run in runs:
        for sample in run["measurements"]:
            time = sample["time"]
            if sample["terminal"]:
                continue
            nearest = round(time / interval) * interval
            if not same_time(time, nearest) and not same_time(time, duration):
                return unavailable("Recorded nonterminal times do not share a regular sampling schedule.")
    pointers = [0] * len(runs)
    rows = []
    for time in times:
        values = {"population": [], "speed": [], "vision": []}
        for index, run in enumerate(runs):
            if not run["survived"] and (time > run["final_time"] or same_time(time, run["final_time"])):
                values["population"].append(0)
                continue
            samples = run["measurements"]
            pointer = pointers[index]
            while pointer < len(samples) and samples[pointer]["time"] < time and not same_time(samples[pointer]["time"], time):
                pointer += 1
            pointers[index] = pointer
            if pointer >= len(samples) or not same_time(samples[pointer]["time"], time):
                return unavailable("A living run is missing a scheduled observation; no interpolation was performed.")
            sample = samples[pointer]
            values["population"].append(sample["population"])
            for metric, field in (("speed", "mean_speed"), ("vision", "mean_vision")):
                if sample[field] is not None:
                    values[metric].append(sample[field])
        row = {"time": time}
        for metric, observations in values.items():
            row[metric] = {"mean": mean(observations) if observations else None,
                           "p10": percentile(observations, 0.1), "p90": percentile(observations, 0.9),
                           "count": len(observations)}
        rows.append(row)
    return {"available": True, "reason": None, "interval": interval, "rows": rows,
            "note": "Mean and 10th–90th percentiles across runs, not confidence intervals. Traits exclude extinct runs; counts accompany every time. Extinct population carries zero through planned duration; all other values are recorded observations."}


def compare_experiments(a, b, stats_a=None, stats_b=None, trajectory_a=None, trajectory_b=None):
    stats_a = stats_a or experiment_statistics(a)
    stats_b = stats_b or experiment_statistics(b)
    ca, cb = a["configuration"], b["configuration"]
    configuration = []
    for key in ("runs", "duration", "starting_seed"):
        configuration.append({"parameter": key, "a": ca[key], "b": cb[key], "different": ca[key] != cb[key]})
    sa, sb = [row["seed"] for row in a["results"]], [row["seed"] for row in b["results"]]
    configuration.append({"parameter": "completed_seed_set", "a": sa, "b": sb, "different": set(sa) != set(sb)})
    for key in ca["simulation"]:
        configuration.append({"parameter": key, "a": ca["simulation"][key], "b": cb["simulation"][key],
                              "different": ca["simulation"][key] != cb["simulation"][key]})
    differences = {}
    fields = {"population": (stats_a["population"]["mean"], stats_b["population"]["mean"]),
              "speed": (stats_a["speed"]["mean"], stats_b["speed"]["mean"]),
              "vision": (stats_a["vision"]["mean"], stats_b["vision"]["mean"]),
              "extinction_percentage": (stats_a["extinction_percentage"], stats_b["extinction_percentage"]),
              "minimum_population": (stats_a["minimum_observed_population"]["mean"], stats_b["minimum_observed_population"]["mean"]),
              "bottleneck_percentage": (stats_a["bottlenecks"]["at_most_5_percentage"], stats_b["bottlenecks"]["at_most_5_percentage"]),
              "exactly_one_percentage": (stats_a["bottlenecks"]["exactly_1_percentage"], stats_b["bottlenecks"]["exactly_1_percentage"])}
    for key, (x, y) in fields.items():
        change = 100 * (y - x) / x if x not in (None, 0) and y is not None else None
        differences[key] = {"a": x, "b": y, "difference_b_minus_a": y - x if x is not None and y is not None else None,
                            "percentage_change_from_a": change if change is not None and math.isfinite(change) else None}
    matched = bool(sa) and set(sa) == set(sb)
    paired = {"available": matched, "reason": None if matched else "Completed seed sets do not match; paired comparison unavailable."}
    if matched:
        b_by_seed = {row["seed"]: row for row in b["results"]}
        pairs = []
        for row in a["results"]:
            other = b_by_seed[row["seed"]]
            both = row["survived"] and other["survived"]
            pairs.append({"seed": row["seed"], "population": other["final_statistics"]["population"] - row["final_statistics"]["population"],
                          "speed": other["final_statistics"]["mean_speed"] - row["final_statistics"]["mean_speed"] if both else None,
                          "vision": other["final_statistics"]["mean_vision"] - row["final_statistics"]["mean_vision"] if both else None})
        paired.update(rows=pairs, statistics={key: describe(row[key] for row in pairs if row[key] is not None) for key in ("population", "speed", "vision")})
    ta, tb = trajectory_a or trajectories(a), trajectory_b or trajectories(b)
    same_duration = close_time(ca["duration"], cb["duration"], min(ca["duration"], cb["duration"]))
    compatible = (same_duration and ta["available"] and tb["available"] and len(ta["rows"]) == len(tb["rows"]) and
                  all(close_time(x["time"], y["time"], min(ta["interval"], tb["interval"])) for x, y in zip(ta["rows"], tb["rows"])))
    warnings = []
    if not same_duration:
        warnings.append("Durations differ: final outcomes have different endpoints; direct trajectory overlay is disabled.")
    if sum(row["different"] for row in configuration if row["parameter"] != "completed_seed_set") > 1:
        warnings.append("Multiple configuration parameters differ; effects cannot be isolated to one parameter.")
    if a.get("engine_version") != b.get("engine_version") or a.get("python_version") != b.get("python_version"):
        warnings.append("Engine or Python versions differ; runtime/model compatibility may affect comparisons.")
    if not compatible:
        warnings.append("Direct trajectory comparison requires equal durations and compatible complete sampling axes.")
    warnings.append("Matched seeds are controls, not identical random-event sequences after configurations diverge. Descriptive differences are not significance tests.")
    return {"configuration": configuration, "statistics_a": stats_a, "statistics_b": stats_b,
            "differences": differences, "paired": paired, "warnings": warnings,
            "trajectory_compatible": compatible, "trajectory_a": ta if compatible else None, "trajectory_b": tb if compatible else None}
