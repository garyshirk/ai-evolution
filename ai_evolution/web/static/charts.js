import {request} from "./api.js";

const number = value => Number.isInteger(value) ? String(value) : Number(value).toFixed(2);

// Retain each bucket's first/last/extrema and gap markers for drawing only.
// Server measurements and exports are never downsampled by the browser.
function envelope(rows, key, buckets = 200) {
  if (rows.length <= buckets * 4) return rows;
  const chosen = new Set([0, rows.length - 1]);
  const stride = Math.ceil(rows.length / buckets);
  for (let start = 0; start < rows.length; start += stride) {
    const end = Math.min(rows.length, start + stride);
    let low = start, high = start;
    chosen.add(start); chosen.add(end - 1);
    for (let i = start; i < end; i++) {
      const row = rows[i];
      if (row.breakBefore || row[key] === null) { chosen.add(i); if (i) chosen.add(i - 1); }
      if (row[key] !== null) {
        if (rows[low][key] === null || row[key] < rows[low][key]) low = i;
        if (rows[high][key] === null || row[key] > rows[high][key]) high = i;
      }
    }
    chosen.add(low); chosen.add(high);
  }
  return [...chosen].sort((a, b) => a - b).map(i => rows[i]);
}

function surface(canvas) {
  const rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
  if (rect.width < 1 || rect.height < 1) return null;
  const width = Math.round(rect.width * dpr), height = Math.round(rect.height * dpr);
  if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  ctx.font = "10px system-ui"; ctx.lineWidth = 1;
  return {ctx, width:rect.width, height:rect.height};
}

function axes(ctx, width, height, xMin, xMax, yMin, yMax, xLabel) {
  const box = {left:42, top:12, width:Math.max(1, width - 54), height:Math.max(1, height - 46)};
  ctx.textAlign = "right";
  for (const fraction of [0, 0.5, 1]) {
    const y = box.top + box.height * (1 - fraction);
    ctx.strokeStyle = "#e2e8e1"; ctx.beginPath(); ctx.moveTo(box.left, y); ctx.lineTo(box.left + box.width, y); ctx.stroke();
    ctx.fillStyle = "#57716b"; ctx.fillText(number(yMin + fraction * (yMax - yMin)), box.left - 5, y + 3);
  }
  ctx.fillStyle = "#57716b"; ctx.textAlign = "left";
  ctx.fillText(number(xMin), box.left, box.top + box.height + 15);
  ctx.textAlign = "right"; ctx.fillText(number(xMax), box.left + box.width, box.top + box.height + 15);
  ctx.textAlign = "center"; ctx.fillText(xLabel, box.left + box.width / 2, height - 4);
  return box;
}

export function line(canvas, rows, key, min, max, color) {
  const target = surface(canvas); if (!target) return;
  const {ctx, width, height} = target;
  const first = rows[0]?.time ?? 0, last = rows.at(-1)?.time ?? 0;
  const box = axes(ctx, width, height, first, last, min, max, "Simulated time");
  const span = Math.max(last - first, 1);
  ctx.strokeStyle = color; ctx.lineWidth = 1.8; ctx.beginPath();
  let drawing = false;
  for (const row of envelope(rows, key)) {
    if (row[key] === null) { drawing = false; continue; }
    const x = box.left + (row.time - first) / span * box.width;
    const y = box.top + (1 - (row[key] - min) / (max - min)) * box.height;
    if (!drawing || row.breakBefore) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    drawing = true;
  }
  ctx.stroke();
  // A one-point initial history is still visible.
  for (const row of [rows[0], rows.at(-1)]) {
    if (!row || row[key] === null) continue;
    ctx.beginPath(); ctx.arc(box.left + (row.time - first) / span * box.width,
      box.top + (1 - (row[key] - min) / (max - min)) * box.height, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.fill();
  }
}

function histogram(canvas, data, color) {
  const target = surface(canvas); if (!target) return;
  const {ctx, width, height} = target;
  const maximum = Math.max(1, ...data.counts);
  const box = axes(ctx, width, height, data.edges[0], data.edges.at(-1), 0, maximum, "Inherited trait value");
  const barWidth = box.width / data.counts.length;
  ctx.fillStyle = color;
  for (let i = 0; i < data.counts.length; i++) {
    const barHeight = data.counts[i] / maximum * box.height;
    ctx.fillRect(box.left + i * barWidth + 1, box.top + box.height - barHeight, Math.max(1, barWidth - 2), barHeight);
  }
  if (!data.counts.some(Boolean)) {
    ctx.fillStyle = "#57716b"; ctx.textAlign = "center";
    ctx.fillText("No living organisms", box.left + box.width / 2, box.top + box.height / 2);
  }
}

// Project paired traits without jitter or sampling: one authoritative org per point.
function scatter(canvas, report) {
  const target = surface(canvas); if (!target) return [];
  const {ctx, width, height} = target, config = report.parameters;
  const box = axes(ctx, width, height, config.speed_min, config.speed_max,
    config.vision_min, config.vision_max, "Inherited maximum speed");
  const points = Object.values(report.state.organisms).sort((a, b) => a.id - b.id).map(org => ({
    id: org.id, speed: org.traits.speed, vision: org.traits.vision_radius,
    x: box.left + (org.traits.speed - config.speed_min) / (config.speed_max - config.speed_min) * box.width,
    y: box.top + (1 - (org.traits.vision_radius - config.vision_min) / (config.vision_max - config.vision_min)) * box.height,
  }));
  ctx.fillStyle = "#287f9966";
  for (const point of points) {
    ctx.beginPath(); ctx.arc(point.x, point.y, 3.5, 0, Math.PI * 2); ctx.fill();
  }
  if (!points.length) {
    ctx.fillStyle = "#57716b"; ctx.textAlign = "center";
    ctx.fillText("No living organisms", box.left + box.width / 2, box.top + box.height / 2);
  }
  canvas.setAttribute("aria-label", `Inherited maximum speed (x) versus inherited vision radius (y); ${points.length} living organisms`);
  return points;
}

export class Reports {
  constructor(select) {
    this.select = select; this.points = []; this.hover = null;
    this.picked = null;
    const canvas = document.getElementById("trait-scatter");
    canvas.addEventListener("pointermove", event => { this.hover = event; this.describeScatter(); });
    canvas.addEventListener("pointerleave", () => { this.hover = null; this.describeScatter(); });
    canvas.addEventListener("click", event => {
      const hits = this.scatterHits(event);
      if (!hits.length) return;
      const index = hits.findIndex(point => point.id === this.picked);
      this.picked = hits[(index + 1) % hits.length].id;
      this.select(this.picked);
      this.describeScatter();
    });
    this.report = null; this.runId = null; this.rows = []; this.sequence = -1;
    this.pending = null; this.lastDraw = -Infinity; this.error = "";
  }

  update(report) {
    if (this.runId !== report.run_id) {
      this.runId = report.run_id; this.rows = []; this.sequence = -1; this.error = "";
      this.points = []; this.picked = null; this.hover = null;
    }
    this.report = report;
  }

  scatterHits(event) {
    const rect = document.getElementById("trait-scatter").getBoundingClientRect();
    return this.points.filter(point =>
      Math.hypot(point.x - (event.clientX - rect.left), point.y - (event.clientY - rect.top)) <= 7 &&
      this.report.state.organisms[point.id]);
  }

  describeScatter() {
    const hits = this.hover ? this.scatterHits(this.hover) : [];
    const point = hits.find(point => point.id === this.picked) || hits[0];
    const message = point ? `Org ${point.id} · maximum speed ${point.speed} · vision radius ${point.vision}` +
      (hits.length > 1 ? ` · ${hits.length} nearby points; click repeatedly to cycle.` : " · Click to inspect.") :
      `Current time ${this.report ? number(this.report.time) : 0} · ${this.points.length} living orgs. Hover for exact traits; click to inspect. Repeated clicks cycle overlapping points.`;
    document.getElementById("scatter-status").textContent = message;
    document.getElementById("trait-scatter").title = message;
  }

  async loadHistory() {
    const runId = this.runId, cursor = this.sequence;
    try {
      const data = await request(`/api/history?run_id=${encodeURIComponent(runId)}&after=${cursor}`);
      if (this.runId !== runId) return;
      this.rows = data.replace ? data.samples : [...this.rows, ...data.samples];
      if (this.rows.length > data.history_limit) {
        this.rows = [this.rows[0], ...this.rows.slice(-(data.history_limit - 1))];
      }
      this.sequence = data.latest_sequence; this.error = "";
    } catch (error) {
      if (this.runId === runId) this.error = error.message;
    }
  }

  tick(now) {
    if (!this.report || !document.getElementById("reports").open || now - this.lastDraw < 250) return;
    this.lastDraw = now;
    if (!this.pending && this.sequence < this.report.reporting.latest_sequence) {
      this.pending = this.loadHistory().finally(() => {this.pending = null;});
    }
    const {parameters: config, measurement: current, histograms, reporting} = this.report;
    const rows = this.rows.map((row, i) => ({...row,
      breakBefore: i > 0 && row.sequence !== this.rows[i - 1].sequence + 1}));
    const peak = Math.max(1, ...rows.map(row => row.population));
    line(document.getElementById("population-chart"), rows, "population", 0, Math.ceil(peak * 1.1), "#245d4b");
    line(document.getElementById("speed-chart"), rows, "mean_speed", config.speed_min, config.speed_max, "#287f99");
    line(document.getElementById("vision-chart"), rows, "mean_vision", config.vision_min, config.vision_max, "#986421");
    histogram(document.getElementById("speed-histogram"), histograms.speed, "#287f99");
    histogram(document.getElementById("vision-histogram"), histograms.vision, "#986421");
    this.points = scatter(document.getElementById("trait-scatter"), this.report);
    this.describeScatter();
    const latest = this.rows.at(-1);
    document.getElementById("history-status").textContent = this.error ||
      `Every ${number(reporting.effective_interval)} simulated time units · ${reporting.retained_samples} retained of ${reporting.total_samples} samples${reporting.dropped_samples ? ` · ${reporting.dropped_samples} older samples omitted` : ""}. Latest recorded time: ${latest ? number(latest.time) : "loading"}.${latest ? ` Latest interval: ${latest.births_since_previous} births, ${latest.deaths_since_previous} deaths.` : ""}`;
    document.getElementById("distribution-status").textContent =
      `Current time ${number(current.time)} · standard deviation: speed ${current.speed_stddev === null ? "unavailable" : number(current.speed_stddev)}, vision ${current.vision_stddev === null ? "unavailable" : number(current.vision_stddev)}.`;
    for (const [id, key] of [["population-chart", "population"], ["speed-chart", "mean_speed"], ["vision-chart", "mean_vision"]]) {
      document.getElementById(id).setAttribute("aria-label", `${key} over simulated time; ${this.rows.length} retained samples; latest value ${latest?.[key] ?? "unavailable"}`);
    }
    for (const [id, key] of [["speed-histogram", "speed"], ["vision-histogram", "vision"]]) {
      document.getElementById(id).setAttribute("aria-label", `Current ${key} distribution; counts by increasing fixed bin: ${histograms[key].counts.join(", ")}`);
    }
  }
}
