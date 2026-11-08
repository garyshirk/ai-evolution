import {request} from "./api.js";
import {line} from "./charts.js";
import {drawTrajectory} from "./statistical-chart.js";

const $ = id => document.getElementById(id);
const fmt = value => value === null || value === undefined ? "N/A" : typeof value === "object" ? JSON.stringify(value) :
  typeof value === "number" && !Number.isInteger(value) ? Number(value.toPrecision(6)).toString() : String(value);
const label = key => key.replaceAll("_", " ");
function table(parent, headers, rows, different = []) {
  const wrap = document.createElement("div"), element = document.createElement("table"), head = document.createElement("thead"), body = document.createElement("tbody"), hr = document.createElement("tr");
  wrap.className = "table-scroll";
  for (const text of headers) { const th = document.createElement("th"); th.textContent = text; hr.append(th); }
  head.append(hr);
  rows.forEach((row, index) => {
    const tr = document.createElement("tr"); if (different[index]) tr.className = "different";
    for (const value of row) { const td = document.createElement("td"); td.textContent = fmt(value); tr.append(td); }
    body.append(tr);
  });
  element.append(head, body); wrap.append(element); parent.replaceChildren(wrap);
}
function statisticsRows(stats) {
  const rows = [];
  for (const key of ["population", "speed", "vision", "minimum_observed_population"]) {
    for (const field of ["count", "mean", "stddev", "median", "minimum", "maximum"]) rows.push([`${label(key)} · ${field}`, stats[key][field]]);
  }
  rows.push(["Extinct runs", stats.extinct_runs], ["Extinction percentage", stats.extinction_percentage],
    ["Bottleneck ≤5 observed count", stats.bottlenecks.at_most_5], ["Bottleneck ≤5 percentage of observed runs", stats.bottlenecks.at_most_5_percentage],
    ["Exactly 1 observed count", stats.bottlenecks.exactly_1], ["Exactly 1 percentage of observed runs", stats.bottlenecks.exactly_1_percentage],
    ["Runs with post-initial observations", stats.bottlenecks.observed_runs], ["Runs without post-initial observations", stats.bottlenecks.unobserved_runs]);
  return rows;
}
function counts(parent, series, metric) {
  parent.replaceChildren(); if (!series.length || !series[0].rows.length) return;
  const slider = document.createElement("input"), wrapper = document.createElement("label"), output = document.createElement("p");
  wrapper.textContent = "Recorded time index"; slider.type = "range"; slider.min = 0; slider.max = series[0].rows.length - 1; slider.step = 1; slider.value = slider.max;
  wrapper.append(slider);
  const update = () => { output.textContent = series.map(entry => {
    const row = entry.rows[Number(slider.value)];
    return `${entry.name}: time ${fmt(row.time)}, ${row[metric].count} contributing runs`;
  }).join(" · "); };
  slider.addEventListener("input", update); parent.append(wrapper, output); update();
}
const bounds = (config, metric) => metric === "population" ? [0, 1] : metric === "speed" ? [config.speed_min, config.speed_max] : [config.vision_min, config.vision_max];

export function setupLibrary({replay, openSingle}) {
  let entries = [], listKey = "", selected = null, run = null, comparison = null, view = "run";
  const fail = reason => { $("experiment-error").textContent = reason.message; $("experiment-error").hidden = false; };
  for (const name of ["run", "results", "compare"]) $("view-" + name).addEventListener("click", () => {
    view = name;
    for (const key of ["run", "results", "compare"]) { $(key + "-view").hidden = name !== key; $("view-" + key).setAttribute("aria-pressed", String(name === key)); }
    redraw(); refresh().catch(fail);
  });
  async function refresh() {
    const data = await request("/api/experiments");
    const key = JSON.stringify(data.experiments);
    if (key === listKey) return;
    listKey = key; entries = data.experiments;
    for (const id of ["experiment-select", "compare-a", "compare-b"]) {
      const menu = $(id), previous = menu.value;
      menu.replaceChildren(new Option("Select an experiment", ""), ...entries.map(entry => new Option(`${entry.name} · ${entry.completed_runs}/${entry.configuration.runs} runs · duration ${entry.configuration.duration} · seed ${entry.configuration.starting_seed} · food ${entry.configuration.simulation.food_spawn_rate}`, entry.id)));
      menu.value = entries.some(entry => entry.id === previous) ? previous : "";
    }
    if (!$("experiment-select").value && entries.length) $("experiment-select").value = entries.at(-1).id;
    if (!$("compare-a").value && entries.length) $("compare-a").value = entries[0].id;
    if (!$("compare-b").value && entries.length > 1) $("compare-b").value = entries[1].id;
    if (selected && !entries.some(entry => entry.id === selected.id)) { selected = null; run = null; $("experiment-content").hidden = true; }
    comparison = null; $("comparison-content").hidden = true;
    if ($("experiment-select").value) await inspect();
  }
  async function inspect() {
    const id = $("experiment-select").value;
    const previousRun = selected?.id === id ? $("experiment-run").value : "";
    selected = null; run = null; $("experiment-content").hidden = true; $("experiment-run-detail").hidden = true;
    if (!id) return;
    const data = await request(`/api/experiments/${id}`);
    if ($("experiment-select").value !== id) return;
    selected = data; $("experiment-content").hidden = false;
    $("experiment-name").value = data.name;
    $("experiment-info").textContent = `${data.name} · ${data.completed_runs}/${data.configuration.runs} runs · duration ${data.configuration.duration} · starting seed ${data.configuration.starting_seed} · food rate ${data.configuration.simulation.food_spawn_rate} · initial population ${data.configuration.simulation.initial_population} · status ${data.status} · engine ${data.engine_version}`;
    table($("experiment-statistics"), ["Metric", "Value"], statisticsRows(data.statistics));
    table($("experiment-minima"), ["Seed", "Minimum observed population after initialization"], data.statistics.minimum_populations.map(row => [row.seed, row.minimum]));
    $("experiment-trajectory-note").textContent = data.statistics.notes.join(" ") + " " + (data.trajectories.reason || data.trajectories.note);
    $("experiment-run").replaceChildren(new Option("Select a run", ""), ...data.runs.map(row => new Option(`Run ${row.run_number} · seed ${row.seed} · ${row.stop_reason} · population ${row.final_population}`, row.run_number)));
    if (data.runs.length) { $("experiment-run").value = previousRun || "1"; await inspectRun(); }
    drawAggregate();
  }
  async function inspectRun() {
    const id = selected?.id, number = $("experiment-run").value;
    run = null; $("experiment-run-detail").hidden = true; if (!id || !number) return;
    const data = await request(`/api/experiments/${id}/runs/${number}`);
    if (selected?.id !== id || $("experiment-run").value !== number) return;
    run = data; $("experiment-run-detail").hidden = false;
    $("experiment-run-title").textContent = `Run ${data.run_number} · seed ${data.seed} · ${data.stop_reason} · final time ${fmt(data.final_time)}`;
    $("experiment-run-config").textContent = JSON.stringify(data.configuration, null, 2);
    $("experiment-replay").disabled = Boolean(data.replay_issue);
    $("experiment-replay-note").textContent = data.replay_issue || "Fresh replay starts paused at time zero and replaces the current Single Simulation.";
    const stats = data.final_statistics;
    const details = [["Final population", stats.population], ["Mean speed", stats.mean_speed], ["Mean vision", stats.mean_vision], ["Births", stats.total_births], ["Deaths", stats.total_deaths], ["Highest generation", stats.highest_generation]];
    $("experiment-run-stats").replaceChildren(...details.flatMap(([key, value]) => {
      const dt = document.createElement("dt"), dd = document.createElement("dd"); dt.textContent = key; dd.textContent = fmt(value); return [dt, dd];
    }));
    drawRun();
  }
  function drawRun() {
    if (!run || view !== "results" || $("batch-panel").hidden) return;
    const rows = run.measurements.map((row, i, all) => ({...row, breakBefore: i > 0 && row.sequence !== null && row.sequence !== all[i-1].sequence + 1}));
    const peak = Math.max(1, ...rows.map(row => row.population));
    for (const [key, field, color] of [["population", "population", "#245d4b"], ["speed", "mean_speed", "#287f99"], ["vision", "mean_vision", "#986421"]]) {
      const limits = bounds(run.configuration, key);
      line($("experiment-run-" + key), rows, field, limits[0], key === "population" ? Math.ceil(peak * 1.1) : limits[1], color);
      $("experiment-run-" + key).setAttribute("aria-label", `Seed ${run.seed}: ${rows.length} recorded observations; final ${key} ${fmt(run.final_statistics[field])}`);
    }
  }
  function drawAggregate() {
    if (!selected || view !== "results" || $("batch-panel").hidden) return;
    const metric = $("experiment-metric").value;
    const series = selected.trajectories.available ? [{name: selected.name, rows: selected.trajectories.rows, color: "#287f99"}] : [];
    drawTrajectory($("experiment-chart"), series, metric, bounds(selected.configuration.simulation, metric));
    counts($("experiment-counts"), series, metric);
  }
  function drawComparison() {
    if (!comparison || view !== "compare" || $("batch-panel").hidden) return;
    const metric = $("comparison-metric").value;
    const a = entries.find(entry => entry.id === $("compare-a").value), b = entries.find(entry => entry.id === $("compare-b").value);
    if (!a || !b) return;
    const ba = bounds(a.configuration.simulation, metric), bb = bounds(b.configuration.simulation, metric);
    const series = comparison.trajectory_compatible ? [{name: "A: " + a.name, rows: comparison.trajectory_a.rows, color: "#287f99"}, {name: "B: " + b.name, rows: comparison.trajectory_b.rows, color: "#a15425"}] : [];
    drawTrajectory($("comparison-chart"), series, metric, [Math.min(ba[0], bb[0]), Math.max(ba[1], bb[1])]);
    counts($("comparison-counts"), series, metric);
  }
  function redraw() { drawAggregate(); drawRun(); drawComparison(); }
  async function compare() {
    const a = $("compare-a").value, b = $("compare-b").value;
    const data = await request(`/api/experiments/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
    if ($("compare-a").value !== a || $("compare-b").value !== b) return;
    comparison = data; $("comparison-content").hidden = false;
    $("comparison-warnings").textContent = data.warnings.join(" ");
    table($("comparison-config"), ["Parameter", "A", "B"], data.configuration.map(row => [row.parameter, row.a, row.b]), data.configuration.map(row => row.different));
    const rowsA = statisticsRows(data.statistics_a), rowsB = statisticsRows(data.statistics_b);
    table($("comparison-statistics"), ["Statistic", "A", "B"], rowsA.map((row, i) => [...row, rowsB[i][1]]));
    table($("comparison-differences"), ["Metric", "A", "B", "Absolute B − A (rates: percentage points)", "Change relative to A (%)"], Object.entries(data.differences).map(([key, row]) => [label(key), row.a, row.b, row.difference_b_minus_a, row.percentage_change_from_a]));
    $("comparison-paired-note").textContent = data.paired.reason || "Matching completed seed sets. Trait pairs require survival in both experiments. Differences are B − A, not significance tests.";
    table($("comparison-paired"), ["Metric", "Valid pairs", "Mean B − A", "Sample SD", "Median", "Minimum", "Maximum"], data.paired.available ? Object.entries(data.paired.statistics).map(([key, row]) => [key, row.count, row.mean, row.stddev, row.median, row.minimum, row.maximum]) : []);
    table($("comparison-pairs"), ["Seed", "Population B − A", "Speed B − A", "Vision B − A"], data.paired.available ? data.paired.rows.map(row => [row.seed, row.population, row.speed, row.vision]) : []);
    const ea = entries.find(entry => entry.id === a), eb = entries.find(entry => entry.id === b);
    $("comparison-legend").textContent = `Blue: A — ${ea.name}. Orange: B — ${eb.name}. Lines: means; shading: 10th–90th percentiles.`;
    $("comparison-trajectory-note").textContent = data.trajectory_compatible ? "Compatible recorded time axes; no interpolation. Trait contributions exclude extinct runs." : "Direct trajectory comparison disabled: different durations, missing observations, or incompatible sampling schedules.";
    drawComparison();
  }
  const handle = action => () => action().catch(fail);
  $("experiment-select").addEventListener("change", handle(inspect));
  $("experiment-run").addEventListener("change", handle(inspectRun));
  $("experiment-metric").addEventListener("change", drawAggregate);
  $("comparison-metric").addEventListener("change", drawComparison);
  $("compare-show").addEventListener("click", handle(compare));
  for (const id of ["compare-a", "compare-b"]) $(id).addEventListener("change", () => { comparison = null; $("comparison-content").hidden = true; });
  $("experiment-rename").addEventListener("click", handle(async () => { await request(`/api/experiments/${selected.id}/name`, {name: $("experiment-name").value}); await refresh(); }));
  $("experiment-remove").addEventListener("click", handle(async () => {
    const response = await fetch(`/api/experiments/${selected.id}`, {method:"DELETE"});
    if (!response.ok) throw new Error((await response.json()).error); await refresh();
  }));
  $("experiment-export").addEventListener("click", () => {
    if (!selected) return;
    const link = document.createElement("a"); link.href = `/api/experiments/${selected.id}/export.json`; link.download = "ai-evolution-experiment.json"; document.body.append(link); link.click(); link.remove();
  });
  $("experiment-import").addEventListener("click", handle(async () => {
    const files = $("experiment-file").files;
    if (!files.length) throw new Error("Choose a batch JSON file first.");
    $("experiment-import").disabled = true;
    try {
      for (const file of files) {
        if (file.size > 256 * 1024 * 1024) throw new Error("File exceeds 256 MiB import limit.");
        const response = await fetch(`/api/experiments/import?name=${encodeURIComponent(file.name)}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:file});
        const result = await response.json(); if (!response.ok) throw new Error(result.error);
        await refresh(); $("experiment-select").value = result.id; await inspect();
      }
      $("experiment-error").hidden = true;
    } finally { $("experiment-import").disabled = false; }
  }));
  $("experiment-replay").addEventListener("click", handle(async () => {
    if (!run || !selected) return;
    $("experiment-replay").disabled = true;
    try { if (await replay(selected.id, run.run_number)) await openSingle(); else throw new Error("Replay rejected; see Single Simulation status."); }
    finally { $("experiment-replay").disabled = Boolean(run?.replay_issue); }
  }));
  new ResizeObserver(redraw).observe($("batch-panel"));
  async function poll() { try { await refresh(); } catch (reason) { fail(reason); } finally { setTimeout(poll, 3000); } }
  poll();
}
