import {request} from "./api.js";
import {WorldView} from "./world.js";

const $ = id => document.getElementById(id);
let report, selected = "", playing = false, busy = false, pending = null;
let credit = 0, previousTime = performance.now();
const view = new WorldView($("world"), id => { selected = id; refresh(); });
const format = value => Number(value).toFixed(3);
const parameterFields = [
  ["initial-food", "initial_food"],
  ["food-rate", "food_spawn_rate"], ["movement-cost", "movement_cost"], ["vision-cost", "vision_cost"],
  ["speed-mutation-probability", "speed_mutation_probability"],
  ["vision-mutation-probability", "vision_mutation_probability"],
  ["speed-mutation-magnitude", "speed_mutation_magnitude"],
  ["vision-mutation-magnitude", "vision_mutation_magnitude"],
];

function showError(error) { $("error").textContent = error.message; $("error").hidden = false; }
function accept(next) { report = next; refresh(); }
function refresh() {
  if (!report) return;
  view.update(report, selected);
  const state = report.state;
  $("status").textContent = busy ? "Waiting…" : report.is_terminal ? "Population extinct · paused" : playing ? "Running" : state.step_count ? "Paused" : "Ready · paused";
  $("extinction").hidden = !report.is_terminal;
  $("start").disabled = busy || playing || report.is_terminal;
  $("pause").disabled = busy || !playing;
  $("step").disabled = busy || playing || report.is_terminal;
  $("reset").disabled = busy;
  const rows = [["Seed", report.seed], ["Simulated time", format(report.time)], ["Steps", state.step_count],
    ["Living orgs", Object.keys(state.organisms).length], ["Food", Object.keys(state.food).length],
    ["Births", report.summary.births], ["Highest generation", report.summary.highest_generation],
    ["Mean speed", report.summary.mean_speed === null ? "—" : format(report.summary.mean_speed)],
    ["Mean vision", report.summary.mean_vision === null ? "—" : format(report.summary.mean_vision)],
    ["Food consumed", state.statistics.food_consumed],
    ["Deaths", state.statistics.starvation_deaths + state.statistics.age_deaths],
    ["Starvation / age", `${state.statistics.starvation_deaths} / ${state.statistics.age_deaths}`],
    ["Playback", `${$("speed").value}×`]];
  $("metrics").replaceChildren(...rows.map(([label, value]) => {
    const box = document.createElement("div"); box.className = "metric";
    const name = document.createElement("span"), number = document.createElement("strong");
    name.textContent = label; number.textContent = value; box.append(name, number); return box;
  }));
  const menu = $("organism");
  const menuKey = `${report.run_id}:${state.statistics.births}:${Object.keys(state.deaths).length}`;
  if (menu.dataset.run !== menuKey) {
    menu.replaceChildren(new Option("None selected", ""),
      ...Object.values(state.organisms).map(org => new Option(`Org ${org.id}`, org.id)),
      ...Object.values(state.deaths).map(death => new Option(`Org ${death.organism.id} · ${death.cause}`, death.organism.id)));
    menu.dataset.run = menuKey;
  }
  menu.value = selected;
  const death = state.deaths[selected];
  const org = state.organisms[selected] || death?.organism;
  const details = org ? [["Org ID", org.id], ["Life status", death ? `Dead · ${death.cause}` : "Living"],
    ...(death ? [["Death time", format(death.time)]] : []), ["Parent ID", org.parent_id ?? "—"], ["Generation", org.generation],
    ["Founder lineage", org.founder_lineage_id], ["Birth time", format(org.birth_time)],
    ["Position", `${format(org.position.x)}, ${format(org.position.y)}`], ["Max speed", format(org.traits.speed)],
    ["Vision radius", format(org.traits.vision_radius)], ["Movement mode", org.movement_mode],
    ["Current speed", format(org.actual_speed)], ["Energy", format(org.energy)], ["Age", format((death?.time ?? report.time) - org.birth_time)],
    ["Offspring", org.offspring_count]] : [["No selection", "Click an org or use the list."]];
  $("inspection").replaceChildren(...details.flatMap(([label, value]) => {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = label; dd.textContent = value; return [dt, dd];
  }));
}
function control(action, extra = {}) {
  return request("/api/control", {action, run_id: report.run_id, expected_step: report.state.step_count, ...extra});
}
async function command(action) {
  if (busy || !report) return;
  busy = true; playing = false; credit = 0; refresh();
  try {
    if (pending) await pending;
    const extra = {};
    if (action === "reset") {
      const text = $("seed").value.trim();
      if (!/^-?\d+$/.test(text) || !Number.isSafeInteger(Number(text))) throw new Error("Enter a safe integer seed; it takes effect on Reset.");
      extra.seed = Number(text);
      extra.parameters = {};
      for (const [id, name] of parameterFields) {
        const textValue = $(id).value.trim();
        const value = Number(textValue);
        if (!textValue || !Number.isFinite(value) || value < 0) throw new Error("Model settings must be finite nonnegative numbers.");
        if (name.endsWith("probability") && value > 1) throw new Error("Mutation probabilities must be between 0 and 1.");
        if (name === "initial_food" && (!Number.isSafeInteger(value) || value > report.parameters.food_cap)) {
          throw new Error(`Initial Food must be a nonnegative integer at most ${report.parameters.food_cap}.`);
        }
        extra.parameters[name] = value;
      }
    }
    accept(await control(action, extra));
    if (action === "reset") { selected = ""; $("seed").value = report.seed; }
    playing = report.running;
    $("error").hidden = true;
  } catch (error) {
    showError(error);
    try {
      accept(await request("/api/state"));
      if (report.running) accept(await control("pause"));
    } catch { /* Keep last authoritative snapshot; scheduling remains stopped. */ }
  } finally { busy = false; previousTime = performance.now(); refresh(); }
}
for (const action of ["start", "pause", "step", "reset"]) $(action).addEventListener("click", () => command(action));
$("speed").addEventListener("change", () => { credit = 0; previousTime = performance.now(); refresh(); });
$("organism").addEventListener("change", event => { selected = event.target.value; refresh(); });
$("vision").addEventListener("change", event => { view.showVision = event.target.checked; });

function frame(now) {
  const elapsed = Math.min((now - previousTime) / 1000, 0.25); previousTime = now;
  if (playing && !busy && report) {
    credit += elapsed * Number($("speed").value) / report.parameters.dt;
    if (!pending && credit >= 1) {
      const steps = Math.min(Math.floor(credit), 20); credit -= steps;
      pending = control("advance", {steps}).then(next => {
        accept(next); if (next.is_terminal) playing = false;
      }).catch(error => { playing = false; showError(error); }).finally(() => { pending = null; refresh(); });
    }
  }
  view.draw(); requestAnimationFrame(frame);
}
try {
  accept(await request("/api/state")); $("seed").value = report.seed;
  for (const [id, name] of parameterFields) $(id).value = report.parameters[name];
  $("initial-food").max = report.parameters.food_cap;
  // A reloaded page explicitly pauses the existing local run before scheduling.
  await command("pause");
} catch (error) { showError(error); }
requestAnimationFrame(frame);
