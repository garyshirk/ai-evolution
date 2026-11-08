import {surface, axes} from "./charts.js";

// Rendering only: exact means/percentiles/counts arrive from Python unchanged.
function envelope(rows, metric) {
  if (rows.length <= 1000) return rows;
  const indices = new Set([0, rows.length - 1]), stride = Math.ceil(rows.length / 180);
  for (let first = 0; first < rows.length; first += stride) {
    const end = Math.min(rows.length, first + stride);
    indices.add(first); indices.add(end - 1);
    for (const [key, minimum] of [["p10", true], ["p90", false], ["mean", true], ["mean", false]]) {
      let chosen = first;
      for (let i = first; i < end; i++) {
        if (rows[i][metric][key] === null) { indices.add(i); if (i) indices.add(i - 1); continue; }
        if (rows[chosen][metric][key] === null || (minimum ? rows[i][metric][key] < rows[chosen][metric][key] : rows[i][metric][key] > rows[chosen][metric][key])) chosen = i;
      }
      indices.add(chosen);
    }
  }
  return [...indices].sort((a, b) => a - b).map(i => rows[i]);
}

export function drawTrajectory(canvas, series, metric, bounds) {
  const target = surface(canvas); if (!target) return;
  const {ctx, width, height} = target;
  if (!series.length) {
    canvas.setAttribute("aria-label", "Trajectory unavailable; see explanation above.");
    ctx.fillStyle = "#57716b"; ctx.fillText("Trajectory unavailable; see explanation above.", 14, 28); return;
  }
  let ymax = bounds[1];
  if (metric === "population") {
    ymax = 1;
    for (const entry of series) for (const row of entry.rows) ymax = Math.max(ymax, row[metric].mean ?? 0, row[metric].p90 ?? 0);
    ymax = Math.ceil(ymax * 1.05);
  }
  const end = series[0].rows.at(-1)?.time ?? 1;
  const box = axes(ctx, width, height, 0, end, bounds[0], ymax, "Simulated time");
  const x = row => box.left + row.time / Math.max(end, 1e-12) * box.width;
  const y = value => box.top + (1 - (value - bounds[0]) / (ymax - bounds[0])) * box.height;
  for (const entry of series) {
    const rows = envelope(entry.rows, metric);
    let segment = [];
    function band() {
      if (!segment.length) return;
      ctx.beginPath();
      segment.forEach((row, i) => i ? ctx.lineTo(x(row), y(row[metric].p90)) : ctx.moveTo(x(row), y(row[metric].p90)));
      [...segment].reverse().forEach(row => ctx.lineTo(x(row), y(row[metric].p10)));
      ctx.closePath(); ctx.fillStyle = entry.color + "28"; ctx.fill(); segment = [];
    }
    for (const row of rows) { if (row[metric].mean === null) band(); else segment.push(row); }
    band();
    ctx.beginPath(); ctx.strokeStyle = entry.color; ctx.lineWidth = 2;
    let drawing = false;
    for (const row of rows) {
      if (row[metric].mean === null) { drawing = false; continue; }
      if (drawing) ctx.lineTo(x(row), y(row[metric].mean)); else ctx.moveTo(x(row), y(row[metric].mean));
      drawing = true;
    }
    ctx.stroke();
  }
  canvas.setAttribute("aria-label", `${metric} versus simulated time; mean lines and 10th–90th percentile bands for ${series.map(s => s.name).join(" and ")}. Run counts available below.`);
}
