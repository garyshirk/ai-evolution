"""In-memory experiment exports; no persistence or model side effects."""

import csv
from dataclasses import asdict, fields
import io
import json
import platform

from ... import __version__
from .metrics import MetricSample, distributions


CSV_COLUMNS = [field.name for field in fields(MetricSample)]


def experiment_report(simulation) -> dict:
    state = simulation.snapshot()
    reporting = simulation.metric_history()
    current = asdict(simulation.current_metrics())
    samples = list(reporting.pop("samples"))
    # A paused/active run may end between regular samples. Mark its final view
    # explicitly instead of changing the collector or pretending it was scheduled.
    if not samples or samples[-1]["step"] != state.step_count:
        samples.append(current)
    return {
        "schema_version": 1, "experiment": "R1", "milestone": "E",
        "seed": simulation.seed, "configuration": asdict(simulation.config),
        "engine_version": __version__, "python_version": platform.python_version(),
        "final_time": state.time, "final_step": state.step_count, "is_terminal": state.is_terminal,
        "final_statistics": {**asdict(state.statistics), **state.summary(), **current},
        "living_organisms": [
            {"id": org.id, "parent_id": org.parent_id,
             "founder_lineage_id": org.founder_lineage_id, "generation": org.generation,
             "speed": org.traits.speed, "vision_radius": org.traits.vision_radius,
             "age": org.age_at(state.time), "energy": org.energy,
             "offspring_count": org.offspring_count}
            for _, org in sorted(state.organisms.items())
        ],
        "histograms": distributions(state, simulation.config),
        "reporting": reporting, "measurements": samples,
    }


def export_json(simulation) -> str:
    return json.dumps(experiment_report(simulation), indent=2, sort_keys=True, allow_nan=False)


def export_csv(simulation) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(experiment_report(simulation)["measurements"])
    return output.getvalue()
