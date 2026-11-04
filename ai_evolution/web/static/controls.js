import {request} from "./api.js";
import {WorldView} from "./world.js";

const $ = id => document.getElementById(id);
let report, selected = "", playing = false, busy = false, pending = null;
let credit = 0, previousTime = performance.now();
const view = new WorldView($("world"), id => { selected = id; refresh(); });
const format = value => Number(value).toFixed(3);

function showError(error) { $("error").textContent = error.message; $("error").hidden = false; }
function accept(next) { report = next; refresh(); }
function refresh() {
  if (!report) return;
  view.update(report, selected);
  const state = report.state;
  $("status").textContent = busy ? "Waiting…" : report.is_terminal ? "Empty population" : playing ? "Running" : state.step_count ? "Paused" : "Ready · paused";
  $("start").disabled = busy || playing || report.is_terminal;
  $("pause").disabled = busy || !playing;
  $("step").disabled = busy || playing || report.is_terminal;
  $("reset").disabled = busy;
  const rows = [["Seed", report.seed], ["Simulated time", format(report.time)], ["Steps", state.step_count],
    ["Living orgs", Object.keys(state.organisms).length], ["Food", Object.keys(state.food).length], ["Playback", `${$("speed").value}×`]];
  $("metrics").replaceChildren(...rows.map(([label, value]) => {
    const box = document.createElement("div"); box.className = "metric";
    const name = document.createElement("span"), number = document.createElement("strong");
    name.textContent = label; number.textContent = value; box.append(name, number); return box;
  }));
  const menu = $("organism");
  if (menu.dataset.run !== report.run_id) {
    menu.replaceChildren(new Option("None selected", ""), ...Object.values(state.organisms).map(org => new Option(`Org ${org.id}`, org.id)));
    menu.dataset.run = report.run_id;
  }
  menu.value = selected;
  const org = state.organisms[selected];
  const details = org ? [["Org ID", org.id], ["Parent ID", org.parent_id ?? "—"], ["Generation", org.generation],
    ["Position", `${format(org.position.x)}, ${format(org.position.y)}`], ["Max speed", format(org.traits.speed)],
    ["Vision radius", format(org.traits.vision_radius)], ["Movement mode", org.movement_mode],
    ["Current speed", format(org.actual_speed)], ["Energy", format(org.energy)], ["Age", format(report.time - org.birth_time)],
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
  // A reloaded page explicitly pauses the existing local run before scheduling.
  await command("pause");
} catch (error) { showError(error); }
requestAnimationFrame(frame);
