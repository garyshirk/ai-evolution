export class WorldView {
  constructor(canvas, select) {
    this.canvas = canvas;
    this.select = select;
    this.report = null;
    this.selected = null;
    this.showVision = true;
    canvas.addEventListener("click", event => this.pick(event));
  }

  update(report, selected) { this.report = report; this.selected = selected; }

  draw() {
    if (!this.report) return;
    const {parameters: config, state} = this.report;
    const canvas = this.canvas;
    canvas.style.aspectRatio = `${config.world_width} / ${config.world_height}`;
    const rect = canvas.getBoundingClientRect();
    const ratio = window.devicePixelRatio || 1;
    const width = Math.round(rect.width * ratio), height = Math.round(rect.height * ratio);
    if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(canvas.width / config.world_width, 0, 0, canvas.height / config.world_height, 0, 0);
    ctx.clearRect(0, 0, config.world_width, config.world_height);
    const unit = config.world_width / rect.width;
    const circle = (x, y, radius, fill) => { ctx.beginPath(); ctx.arc(x, y, radius, 0, 2 * Math.PI); ctx.fillStyle = fill; ctx.fill(); };
    const selected = state.organisms[this.selected] || state.deaths[this.selected]?.organism;
    if (selected && this.showVision) circle(selected.position.x, selected.position.y, selected.traits.vision_radius, "#287f9918");
    for (const food of Object.values(state.food)) circle(food.position.x, food.position.y, 1.8 * unit, "#a97026");
    for (const org of Object.values(state.organisms)) {
      circle(org.position.x, org.position.y, 4 * unit, `hsl(${185 + org.id % 45} 52% 39%)`);
      if (String(org.id) === this.selected) {
        ctx.beginPath(); ctx.arc(org.position.x, org.position.y, 7 * unit, 0, 2 * Math.PI);
        ctx.lineWidth = 2 * unit; ctx.strokeStyle = "#183d37"; ctx.stroke();
      }
    }
    if (selected && state.deaths[this.selected]) {
      const {x, y} = selected.position;
      ctx.strokeStyle = "#862e17"; ctx.lineWidth = 2 * unit;
      ctx.beginPath(); ctx.moveTo(x - 5 * unit, y - 5 * unit); ctx.lineTo(x + 5 * unit, y + 5 * unit);
      ctx.moveTo(x - 5 * unit, y + 5 * unit); ctx.lineTo(x + 5 * unit, y - 5 * unit); ctx.stroke();
    }
  }

  pick(event) {
    if (!this.report) return;
    const rect = this.canvas.getBoundingClientRect(), config = this.report.parameters;
    const x = (event.clientX - rect.left) / rect.width * config.world_width;
    const y = (event.clientY - rect.top) / rect.height * config.world_height;
    const tolerance = 10 * config.world_width / rect.width;
    const hits = Object.values(this.report.state.organisms)
      .filter(org => Math.hypot(org.position.x - x, org.position.y - y) <= tolerance)
      .sort((a, b) => a.id - b.id).map(org => String(org.id));
    if (!hits.length) this.select("");
    else this.select(hits[(hits.indexOf(this.selected) + 1) % hits.length]);
  }
}
