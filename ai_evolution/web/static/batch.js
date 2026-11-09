import {request} from "./api.js";
import {line} from "./charts.js";
import {setupLibrary} from "./experiments.js";

const $ = id => document.getElementById(id);
const display = value => value === null || value === undefined ? "unavailable" :
  typeof value === "number" && !Number.isInteger(value) ? value.toFixed(3) : String(value);
const label = name => name.replaceAll("_", " ").replace(/^./, text => text.toUpperCase());

export async function setupBatch({pause, replay, replayExperiment}) {
  let status, selectedRun = null, loading = false, selectedBatch = null;
  const settings = await request("/api/batch/settings");
  const integers = new Set(settings.integer_parameters);
  const primary = new Set(["founder_age_mode", "initial_population", "initial_food", "food_spawn_rate", "movement_cost", "vision_cost",
    "speed_mutation_probability", "vision_mutation_probability", "speed_mutation_magnitude", "vision_mutation_magnitude"]);
  const inputs = new Map();
  function input(name, value, parent, integer = false) {
    const wrapper = document.createElement("label"), field = document.createElement(name === "founder_age_mode" ? "select" : "input");
    wrapper.textContent = name === "founder_age_mode" ? "Founder ages" : label(name);
    if (name === "founder_age_mode") {
      field.append(new Option("Randomized (uniform)", "uniform"), new Option("All zero (legacy)", "zero"));
    } else { field.type = "number"; field.step = integer ? "1" : "any"; }
    field.id = `batch-${name}`; field.value = value; field.required = true;
    if (name !== "starting_seed") field.min = "0";
    wrapper.append(field); $(parent).append(wrapper); inputs.set(name, field);
  }
  for (const name of ["runs", "duration", "starting_seed"]) input(name, settings.defaults[name], "batch-settings", name !== "duration");
  for (const [name, value] of Object.entries(settings.defaults.simulation)) {
    input(name, value, primary.has(name) ? "batch-settings" : "batch-advanced", integers.has(name));
  }
  inputs.get("runs").max = settings.limits.max_runs;
  inputs.get("duration").max = settings.limits.max_duration;
  inputs.get("initial_population").max = settings.limits.max_initial_population;
  inputs.get("food_cap").max = settings.limits.max_food_cap;
  $("batch-limits").textContent = `Limits: ${settings.limits.max_runs} runs; duration ${settings.limits.max_duration}; ${settings.limits.max_total_steps} total ticks; initial population ${settings.limits.max_initial_population}; food cap ${settings.limits.max_food_cap}; retained measurement budget ${settings.limits.max_retained_samples}. Duration must be a whole number of dt ticks. Resource limits may stop an oversized run with an error.`;

  async function tab(batch) {
    if (batch && !await pause()) return;
    $("single-panel").hidden = batch; $("batch-panel").hidden = !batch;
    $("single-tab").setAttribute("aria-selected", String(!batch));
    $("batch-tab").setAttribute("aria-selected", String(batch));
    $("single-tab").tabIndex = batch ? -1 : 0; $("batch-tab").tabIndex = batch ? 0 : -1;
    draw();
  }
  $("single-tab").addEventListener("click", () => tab(false));
  $("batch-tab").addEventListener("click", () => tab(true));
  for (const id of ["single-tab", "batch-tab"]) $(id).addEventListener("keydown", event => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      event.preventDefault(); const batch = event.key === "End" || event.key !== "Home" && id === "single-tab";
      tab(batch).then(() => $(batch ? "batch-tab" : "single-tab").focus());
    }
  });
  function error(error) { $("batch-error").textContent = error.message; $("batch-error").hidden = false; }
  function draw() {
    if (!selectedRun || $("batch-panel").hidden) return;
    const run = selectedRun, config = run.configuration;
    const rows = run.measurements.map((row, index, all) => ({...row,
      breakBefore: index > 0 && row.sequence !== null && all[index - 1].sequence !== null && row.sequence !== all[index - 1].sequence + 1}));
    const peak = Math.max(1, ...rows.map(row => row.population));
    line($("batch-population"), rows, "population", 0, Math.ceil(peak * 1.1), "#245d4b");
    line($("batch-speed"), rows, "mean_speed", config.speed_min, config.speed_max, "#287f99");
    line($("batch-vision"), rows, "mean_vision", config.vision_min, config.vision_max, "#986421");
    for (const [id, key] of [["batch-population", "population"], ["batch-speed", "mean_speed"], ["batch-vision", "mean_vision"]]) {
      $(id).setAttribute("aria-label", `Run ${run.run_number}, seed ${run.seed}: ${rows.length} measurements; final ${key}: ${display(run.final_statistics[key])}`);
    }
  }
  async function inspect() {
    const batchId = status?.batch_id, number = $("batch-result").value;
    selectedRun = null; $("batch-detail").hidden = true;
    if (!number) return;
    try {
      const run = await request(`/api/batch/${encodeURIComponent(batchId)}/runs/${number}`);
      if (status?.batch_id !== batchId || $("batch-result").value !== number) return;
      selectedRun = run; selectedBatch = batchId; $("batch-detail").hidden = false;
      $("batch-run-title").textContent = `Run ${run.run_number} · seed ${run.seed} · ${run.stop_reason}`;
      $("batch-run-config").textContent = JSON.stringify(run.configuration, null, 2);
      const stats = run.final_statistics;
      const details = [["Final simulated time", run.final_time], ["Final population", stats.population],
        ["Mean inherited maximum speed", stats.mean_speed], ["Mean inherited vision", stats.mean_vision],
        ["Births", stats.total_births], ["Deaths", stats.total_deaths], ["Starvation deaths", stats.starvation_deaths],
        ["Age deaths", stats.age_deaths], ["Highest generation", stats.highest_generation]];
      $("batch-run-stats").replaceChildren(...details.flatMap(([label, value]) => {
        const dt = document.createElement("dt"), dd = document.createElement("dd"); dt.textContent = label; dd.textContent = display(value); return [dt, dd];
      }));
      $("batch-history-note").textContent = `Sampled every ${display(run.reporting.effective_interval)} simulated units. ${run.reporting.dropped_samples} older samples omitted; graphs mark retained-history gaps. Final endpoint included.`;
      draw();
    } catch (reason) { error(reason); }
  }
  function render(next) {
    const changed = status?.batch_id !== next.batch_id;
    status = next;
    if (changed) {
      selectedRun = null; selectedBatch = null; $("batch-detail").hidden = true;
      if (status.configuration) {
        const {simulation, ...batchConfig} = status.configuration;
        for (const [key, value] of Object.entries({...simulation, ...batchConfig})) inputs.get(key).value = value;
      }
    }
    const active = ["running", "cancelling"].includes(status.status);
    $("batch-fields").disabled = active; $("batch-run").disabled = active;
    $("batch-cancel").disabled = status.status !== "running";
    $("batch-export").disabled = !status.batch_id || active;
    $("batch-progress-bar").max = status.total_runs || 1;
    $("batch-progress-bar").value = status.completed_runs;
    $("batch-progress").textContent = `${status.status} · ${status.completed_runs} / ${status.total_runs} completed` +
      (status.current ? ` · current run ${status.current.run_number}, seed ${status.current.seed}, time ${display(status.current.time)}` : "");
    const summary = status.summary;
    const keys = ["completed_runs", "surviving_populations", "extinct_populations", "survival_percentage",
      "average_final_population", "average_final_speed", "average_final_vision", "trait_mean_run_count"];
    $("batch-summary").replaceChildren(...keys.map(key => {
      const box = document.createElement("div"), name = document.createElement("span"), value = document.createElement("strong");
      box.className = "metric"; name.textContent = label(key); value.textContent = display(summary[key]); box.append(name, value); return box;
    }));
    $("batch-definitions").textContent = summary.definitions;
    if (status.error || status.library_error) error(new Error(status.error || status.library_error));
    const menu = $("batch-result"), key = `${status.batch_id}:${status.completed_runs}`;
    if (menu.dataset.key !== key) {
      const previous = changed ? "" : menu.value;
      menu.replaceChildren(new Option("Select a completed run", ""), ...status.runs.map(run =>
        new Option(`Run ${run.run_number} · seed ${run.seed} · ${run.stop_reason} · population ${run.final_population}`, run.run_number)));
      menu.dataset.key = key; menu.value = previous || (status.runs.length ? "1" : "");
      if (menu.value && !selectedRun) inspect();
    }
  }
  async function poll() {
    if (loading) return;
    loading = true;
    try { render(await request("/api/batch")); }
    catch (reason) { error(reason); }
    finally { loading = false; setTimeout(poll, 750); }
  }
  $("batch-form").addEventListener("submit", async event => {
    event.preventDefault(); $("batch-run").disabled = true;
    try {
      const values = Object.fromEntries([...inputs].map(([key, input]) => {
        if (key === "founder_age_mode") return [key, input.value];
        const value = Number(input.value);
        if (!input.value.trim() || !Number.isFinite(value)) throw new Error(`Enter a finite ${label(key)}.`);
        if ((integers.has(key) || ["runs", "starting_seed"].includes(key)) && !Number.isSafeInteger(value)) throw new Error(`${label(key)} must be a safe integer.`);
        return [key, value];
      }));
      const {runs, duration, starting_seed, ...simulation} = values;
      await request("/api/batch", {runs, duration, starting_seed, simulation});
      $("batch-error").hidden = true; render(await request("/api/batch"));
    } catch (reason) { error(reason); $("batch-run").disabled = false; }
  });
  $("batch-cancel").addEventListener("click", async () => {
    try { render(await request("/api/batch/cancel", {batch_id: status.batch_id})); }
    catch (reason) { error(reason); }
  });
  $("batch-result").addEventListener("change", inspect);
  $("batch-replay").addEventListener("click", async () => {
    if (!selectedRun) return;
    $("batch-replay").disabled = true;
    try {
      if (await replay(selectedBatch, selectedRun.run_number)) await tab(false);
      else throw new Error("Replay could not be opened; see the Single Simulation error.");
    } catch (reason) { error(reason); }
    finally { $("batch-replay").disabled = false; }
  });
  $("batch-export").addEventListener("click", () => {
    const link = document.createElement("a");
    link.href = `/api/batch/export.json?batch_id=${encodeURIComponent(status.batch_id)}`;
    link.download = "ai-evolution-batch.json"; document.body.append(link); link.click(); link.remove();
  });
  new ResizeObserver(draw).observe($("batch-panel"));
  setupLibrary({replay: replayExperiment, openSingle: () => tab(false)});
  poll();
}
