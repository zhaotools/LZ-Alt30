"use strict";

const COLORS = {alt30: "#7c3aed", btc: "#d97706", eth: "#2563b8"};
const SECTOR_COLORS = ["#367bc4", "#2694a4", "#6d90c0", "#b4894f", "#9478b7", "#57a38d", "#7c70ad"];
const svgNS = "http://www.w3.org/2000/svg";
let state = null;
let activeSector = "全部";
let visibleReferenceSeries = new Set(["alt30", "btc", "eth"]);

function $(id) { return document.getElementById(id); }

function svgEl(tag, attributes = {}) {
  const node = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatPoint(value) { return Number(value).toLocaleString("zh-CN", {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
function formatPercent(value, digits = 2) { return `${value >= 0 ? "+" : ""}${Number(value).toFixed(digits)}%`; }
function formatDate(value) { const [y, m, d] = value.split("-"); return `${y}.${m}.${d}`; }
function formatPrice(value) {
  const digits = value >= 100 ? 2 : value >= 1 ? 4 : 6;
  return Number(value).toLocaleString("en-US", {minimumFractionDigits: digits, maximumFractionDigits: digits});
}

function addText(parent, x, y, value, anchor = "start") {
  const node = svgEl("text", {x, y, "text-anchor": anchor});
  node.textContent = value;
  parent.append(node);
}

function renderChart(svg, tooltip, points, series, height = 330, options = {}) {
  svg.replaceChildren();
  if (!points.length || !series.length) return;
  const width = 900;
  const plot = {left: 55, right: 17, top: 18, bottom: height - 38};
  const chartWidth = width - plot.left - plot.right;
  const chartHeight = plot.bottom - plot.top;
  const values = points.flatMap(point => series.map(item => point[item.key])).filter(Number.isFinite);
  let low = Math.min(...values), high = Math.max(...values);
  const spread = high - low || Math.max(50, high * .08);
  low -= spread * .12;
  high += spread * .12;
  const xAt = index => plot.left + (points.length === 1 ? chartWidth / 2 : chartWidth * index / (points.length - 1));
  const yAt = value => plot.bottom - (value - low) / (high - low) * chartHeight;

  for (let index = 0; index < 5; index++) {
    const value = low + (high - low) * (4 - index) / 4;
    const y = plot.top + chartHeight * index / 4;
    svg.append(svgEl("line", {x1: plot.left, y1: y, x2: width - plot.right, y2: y, class: "grid-line"}));
    addText(svg, plot.left - 9, y + 4, String(Math.round(value)), "end");
  }
  svg.append(svgEl("line", {x1: plot.left, y1: plot.bottom, x2: width - plot.right, y2: plot.bottom, class: "axis-line"}));
  const tickIndexes = [...new Set([0, 1, 2, 3, 4].map(index => Math.round((points.length - 1) * index / 4)))];
  for (const index of tickIndexes) addText(svg, xAt(index), height - 12, points[index].date.slice(5).replace("-", "/"), "middle");

  if (options.phaseBoundaryDate) {
    const boundary = points.findIndex(point => point.date === options.phaseBoundaryDate);
    if (boundary >= 0 && boundary < points.length - 1) {
      const x = xAt(boundary);
      svg.append(svgEl("line", {x1: x, y1: plot.top, x2: x, y2: plot.bottom, class: "phase-divider"}));
      addText(svg, x - 7, plot.top + 14, "正式起算", "end");
    }
  }

  for (const item of series) {
    const path = points.map((point, index) => `${index ? "L" : "M"}${xAt(index).toFixed(2)} ${yAt(point[item.key]).toFixed(2)}`).join(" ");
    if (points.length > 1) svg.append(svgEl("path", {d: path, class: "chart-path", stroke: item.color}));
    else svg.append(svgEl("circle", {cx: xAt(0), cy: yAt(points[0][item.key]), r: 5, fill: item.color, class: "chart-point"}));
  }

  const hoverLine = svgEl("line", {x1: 0, x2: 0, y1: plot.top, y2: plot.bottom, class: "hover-line", visibility: "hidden"});
  svg.append(hoverLine);
  const markers = series.map(item => {
    const circle = svgEl("circle", {r: 5, fill: item.color, class: "chart-point", visibility: "hidden"});
    svg.append(circle);
    return circle;
  });
  const hit = svgEl("rect", {x: plot.left, y: plot.top, width: chartWidth, height: chartHeight, fill: "transparent"});
  svg.append(hit);
  hit.addEventListener("pointermove", event => {
    const bounds = svg.getBoundingClientRect();
    const viewX = (event.clientX - bounds.left) / bounds.width * width;
    const index = points.length === 1 ? 0 : Math.max(0, Math.min(points.length - 1, Math.round((viewX - plot.left) / chartWidth * (points.length - 1))));
    const x = xAt(index);
    hoverLine.setAttribute("x1", x);
    hoverLine.setAttribute("x2", x);
    hoverLine.setAttribute("visibility", "visible");
    markers.forEach((marker, seriesIndex) => {
      marker.setAttribute("cx", x);
      marker.setAttribute("cy", yAt(points[index][series[seriesIndex].key]));
      marker.setAttribute("visibility", "visible");
    });
    tooltip.replaceChildren();
    tooltip.append(el("strong", "", points[index].date));
    if (points[index].phase) tooltip.append(el("span", "tooltip-phase", points[index].phase === "reference" ? "历史回推参考" : "正式阶段 · 同起点对照值"));
    for (const item of series) tooltip.append(el("span", "", `${item.label}  ${formatPoint(points[index][item.key])}`));
    tooltip.hidden = false;
    tooltip.style.left = `${Math.max(70, Math.min(bounds.width - 70, x / width * bounds.width))}px`;
    tooltip.style.top = `${Math.max(42, Math.min(...series.map(item => yAt(points[index][item.key]))) / height * bounds.height)}px`;
  });
  hit.addEventListener("pointerleave", () => {
    hoverLine.setAttribute("visibility", "hidden");
    markers.forEach(marker => marker.setAttribute("visibility", "hidden"));
    tooltip.hidden = true;
  });
}

function renderStatus(latestDate) {
  const today = new Date().toISOString().slice(0, 10);
  const utcHour = new Date().getUTCHours();
  const daysBehind = Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${latestDate}T00:00:00Z`)) / 86400000);
  const status = $("data-status");
  status.className = "status-pill";
  if (daysBehind <= 0) status.textContent = "当日数据已更新";
  else if (daysBehind === 1 && utcHour < 2) { status.textContent = "等待今日更新"; status.classList.add("pending"); }
  else { status.textContent = "数据更新延迟"; status.classList.add("stale"); }
}

function renderOfficial(data) {
  const points = data.official;
  const latest = points.at(-1);
  $("official-value").textContent = formatPoint(latest.value);
  $("sample-date").textContent = formatDate(data.meta.latest_date);
  $("rebalance-date").textContent = formatDate(data.meta.next_rebalance_date);
  renderStatus(data.meta.latest_date);
  const change = $("official-change");
  if (points.length === 1) {
    change.textContent = "基日初始化 · 日涨跌暂无";
    $("official-chart-note").textContent = "当前只有基日的一个正式点位；后续每天增加一个有效采样点。";
  } else {
    const previous = points.at(-2);
    const percentage = (latest.value / previous.value - 1) * 100;
    change.textContent = `${formatPercent(percentage)}  较前次采样 · ${formatDate(previous.date)}`;
    change.className = `index-change ${percentage >= 0 ? "positive" : "negative"}`;
    $("official-chart-note").textContent = `同基日 1000 点起步；最近采样 ${formatDate(data.meta.latest_date)}。`;
  }
  renderChart($("official-chart"), $("official-tooltip"), points, [{key: "value", label: "LZ-Alt30", color: COLORS.alt30}], 300);
}

function renderReference(data) {
  const definitions = [{key: "alt30", label: "LZ-Alt30", color: COLORS.alt30}, {key: "btc", label: "BTC", color: COLORS.btc}, {key: "eth", label: "ETH", color: COLORS.eth}];
  $("comparison-range").textContent = `${data.meta.reference_start} — ${data.meta.latest_date}`;
  const legend = $("reference-legend");
  legend.replaceChildren();
  for (const item of definitions) {
    const button = el("button", "legend-button");
    button.type = "button";
    button.setAttribute("aria-pressed", visibleReferenceSeries.has(item.key) ? "true" : "false");
    const swatch = el("span", "legend-swatch");
    swatch.style.setProperty("--swatch", item.color);
    button.append(swatch, document.createTextNode(item.label));
    button.addEventListener("click", () => {
      if (visibleReferenceSeries.has(item.key) && visibleReferenceSeries.size === 1) return;
      if (visibleReferenceSeries.has(item.key)) visibleReferenceSeries.delete(item.key); else visibleReferenceSeries.add(item.key);
      renderReference(data);
    });
    legend.append(button);
  }
  renderChart($("reference-chart"), $("reference-tooltip"), data.comparison, definitions.filter(item => visibleReferenceSeries.has(item.key)), 330, {phaseBoundaryDate: data.meta.base_date});
  const stats = $("reference-stats");
  stats.replaceChildren();
  const first = data.comparison[0], last = data.comparison.at(-1);
  for (const item of definitions) {
    const box = el("div", `reference-stat ${item.key}`);
    box.append(el("span", "", item.label), el("strong", "", formatPercent((last[item.key] / first[item.key] - 1) * 100)));
    stats.append(box);
  }
}

function renderSectors(data) {
  const grid = $("sector-grid");
  grid.replaceChildren();
  data.sectors.forEach((sector, index) => {
    const card = el("div", "sector-card");
    card.style.setProperty("--bar", `${sector.weight_pct}%`);
    card.style.setProperty("--sector-color", SECTOR_COLORS[index % SECTOR_COLORS.length]);
    const top = el("div", "sector-top");
    top.append(el("h3", "", sector.name), el("span", "sector-count", `${sector.count} 个成分`));
    const weight = el("div", "sector-weight");
    weight.append(el("strong", "", `${sector.weight_pct.toFixed(2)}%`), document.createTextNode("当前权重"));
    card.append(top, weight);
    grid.append(card);
  });
}

function renderFilters(data) {
  const filters = $("sector-filters");
  filters.replaceChildren();
  for (const name of ["全部", ...data.sectors.map(item => item.name)]) {
    const button = el("button", "filter-button", name);
    button.type = "button";
    button.setAttribute("aria-pressed", name === activeSector ? "true" : "false");
    button.addEventListener("click", () => {
      activeSector = name;
      $("member-detail").hidden = true;
      renderFilters(data);
      renderMembers(data);
    });
    filters.append(button);
  }
}

function cell(row, text, label, extraClass = "") {
  const td = el("td", extraClass, text);
  td.dataset.label = label;
  row.append(td);
  return td;
}

function renderMembers(data) {
  const body = $("members-body");
  body.replaceChildren();
  for (const member of data.constituents.filter(item => activeSector === "全部" || item.sector === activeSector)) {
    const row = el("tr");
    const coinCell = cell(row, "", "资产");
    const coinButton = el("button", "coin-link", member.symbol);
    coinButton.type = "button";
    coinButton.setAttribute("aria-label", `查看 ${member.symbol} 的研究依据与风险`);
    coinButton.addEventListener("click", () => showMemberDetail(member));
    coinCell.append(coinButton);
    cell(row, member.sector, "赛道");
    const priorityCell = cell(row, "", "候选");
    priorityCell.append(el("span", `priority ${member.priority === "条件" ? "conditional" : ""}`, member.priority));
    cell(row, formatPrice(member.price), "价格", "numeric");
    const change = member.previous_sample_change_pct;
    cell(row, change === null ? "—" : formatPercent(change), "较前次采样", `numeric ${change === null ? "" : change >= 0 ? "change-up" : "change-down"}`);
    cell(row, `${member.current_weight_pct.toFixed(2)}%`, "当前权重", "numeric");
    cell(row, `${member.target_weight_pct.toFixed(2)}%`, "目标权重", "numeric");
    body.append(row);
  }
}

function showMemberDetail(member) {
  const detail = $("member-detail");
  detail.replaceChildren();
  const close = el("button", "detail-close", "×");
  close.type = "button";
  close.setAttribute("aria-label", "关闭成分详情");
  close.addEventListener("click", () => { detail.hidden = true; });
  detail.append(close, el("h4", "", `${member.symbol} · ${member.sector} · ${member.priority}候选`));
  const grid = el("div", "member-detail-grid");
  for (const [label, content] of [["业务依据", member.business], ["代币价值来源", member.mechanism], ["重点风险", member.risk]]) {
    const block = el("div");
    block.append(el("strong", "", label), el("p", "", content));
    grid.append(block);
  }
  detail.append(grid);
  const source = el("a", "", "查看研究来源 ↗");
  source.href = member.source;
  source.target = "_blank";
  source.rel = "noopener noreferrer";
  detail.append(source);
  detail.hidden = false;
  detail.scrollIntoView({block: "nearest", behavior: "smooth"});
}

async function start() {
  try {
    const response = await fetch(`./data/index.json?v=${Date.now()}`, {cache: "no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (!data.official?.length || !data.reference?.length || !data.comparison?.length || data.constituents?.length !== 30) throw new Error("指数数据不完整");
    state = data;
    renderOfficial(data);
    renderReference(data);
    renderSectors(data);
    renderFilters(data);
    renderMembers(data);
  } catch (error) {
    $("data-status").textContent = "数据读取失败";
    $("data-status").classList.add("stale");
    $("official-change").textContent = "请稍后重试；页面不显示未经核验的数值。";
    $("members-body").replaceChildren();
    const row = el("tr");
    const message = el("td", "", "成分数据暂时无法加载。");
    message.colSpan = 7;
    row.append(message);
    $("members-body").append(row);
    console.error("LZ-Alt30 data loading failed", error);
  }
}

start();
