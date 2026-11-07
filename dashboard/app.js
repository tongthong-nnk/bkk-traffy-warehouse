const SVG = "http://www.w3.org/2000/svg";

const numberFormat = new Intl.NumberFormat("en-US");
const dayFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const monthFormat = new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
const bangkokFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Bangkok",
});

const count = (n) => numberFormat.format(Math.round(n));
const percent = (x) => (x == null || Number.isNaN(x) ? "–" : `${Math.round(x * 100)}%`);
const days = (x) => (x == null ? "–" : x < 10 ? x.toFixed(1) : String(Math.round(x)));
const share = (part, whole) => (whole > 0 ? part / whole : null);
const utcDate = (text) => new Date(`${text.slice(0, 10)}T00:00:00Z`);

function el(name, attrs = {}, parent = null) {
  const node = document.createElementNS(SVG, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (parent) parent.append(node);
  return node;
}

function html(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

// ---- tooltip -------------------------------------------------------------

const tooltip = document.getElementById("tooltip");

function showTooltip(x, y, title, rows) {
  tooltip.replaceChildren(html("div", { className: "when", textContent: title }));
  for (const row of rows) {
    const line = html(
      "div",
      { className: row.color ? "row keyed" : "row" },
      html("strong", { textContent: row.value }),
      html("span", { className: "name", textContent: row.label }),
    );
    if (row.color) line.style.setProperty("--key", row.color);
    tooltip.append(line);
  }
  tooltip.hidden = false;
  const { offsetWidth: w, offsetHeight: h } = tooltip;
  let left = x + 14;
  if (left + w > window.innerWidth - 8) left = x - w - 14;
  let top = y - h - 12;
  if (top < 8) top = y + 16;
  tooltip.style.left = `${Math.max(8, left)}px`;
  tooltip.style.top = `${top}px`;
}

function hideTooltip() {
  tooltip.hidden = true;
}

// ---- scales and axes -------------------------------------------------------

function ticksUpTo(max, target = 4) {
  if (!(max > 0)) return [0, 1];
  const raw = max / target;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw);
  const ticks = [];
  for (let value = 0; value < max + step; value += step) ticks.push(value);
  return ticks;
}

function tickFormatter(ticks, kind) {
  if (kind === "percent") return (v) => `${Math.round(v * 100)}%`;
  const top = ticks[ticks.length - 1];
  if (top >= 10000) return (v) => (v === 0 ? "0" : `${numberFormat.format(v / 1000)}K`);
  return (v) => numberFormat.format(v);
}

function yearStarts(first, last) {
  const starts = [];
  for (let year = first.getUTCFullYear(); year <= last.getUTCFullYear(); year += 1) {
    const start = new Date(Date.UTC(year, 0, 1));
    if (start >= first && start <= last) starts.push(start);
  }
  return starts;
}

function frame(svg, { width, height, margin, yTicks, yFormat }) {
  const plotHeight = height - margin.top - margin.bottom;
  const y = (v) => margin.top + plotHeight - (v / yTicks[yTicks.length - 1]) * plotHeight;
  for (const tick of yTicks) {
    const line = tick === 0 ? "baseline" : "gridline";
    el("line", { class: line, x1: margin.left, x2: width - margin.right, y1: y(tick), y2: y(tick) }, svg);
    el("text", { x: margin.left - 8, y: y(tick) + 4, "text-anchor": "end" }, svg).textContent = yFormat(tick);
  }
  return y;
}

function xAxisYears(svg, starts, x, baseY) {
  for (const start of starts) {
    el("text", { x: x(start), y: baseY + 18, "text-anchor": "middle" }, svg).textContent = start.getUTCFullYear();
  }
}

function legend(container, series) {
  const box = html("div", { className: "legend" });
  for (const s of series) {
    const item = html("span", { textContent: s.label });
    item.style.setProperty("--key", s.color);
    box.append(item);
  }
  container.append(box);
}

function tableView(container, caption, columns, rows) {
  const details = html("details", { className: "table-view" }, html("summary", { textContent: "Show the numbers" }));
  details.addEventListener(
    "toggle",
    () => {
      const head = html("tr", {}, ...columns.map((c) => html("th", { scope: "col", textContent: c.label })));
      const body = rows.map((r) => html("tr", {}, ...columns.map((c) => html("td", { textContent: c.value(r) }))));
      const table = html("table", {}, html("caption", { className: "sr-only", textContent: caption }), html("thead", {}, head), html("tbody", {}, ...body));
      details.append(html("div", { className: "scroll" }, table));
    },
    { once: true },
  );
  container.append(details);
}

function whenResized(container, render) {
  let width = 0;
  new ResizeObserver(() => {
    if (container.clientWidth !== width) {
      width = container.clientWidth;
      render();
    }
  }).observe(container);
}

// ---- charts ----------------------------------------------------------------

/**
 * Lines over time with a crosshair. points: [{x: Date, ...values}],
 * series: [{key, label, color}].
 */
function lineChart(container, { points, series, kind = "count", title, period = "day" }) {
  const plot = html("div");
  container.append(plot);
  if (series.length > 1) legend(plot, series);
  const svgBox = html("div");
  plot.append(svgBox);

  const label = period === "day" ? (d) => dayFormat.format(d) : (d) => monthFormat.format(d);
  const format = kind === "percent" ? percent : count;

  const render = () => {
    svgBox.replaceChildren();
    const width = svgBox.clientWidth;
    const height = 240;
    const margin = { top: 10, right: 64, bottom: 26, left: 44 };
    const max = Math.max(...points.flatMap((p) => series.map((s) => p[s.key] ?? 0)));
    const yTicks = kind === "percent" ? [0, 0.25, 0.5, 0.75, 1] : ticksUpTo(max);
    const svg = el("svg", { width, height, role: "img", "aria-label": title, tabindex: 0 }, svgBox);
    const y = frame(svg, { width, height, margin, yTicks, yFormat: tickFormatter(yTicks, kind) });
    const first = points[0].x;
    const last = points[points.length - 1].x;
    const span = last - first || 1;
    const x = (d) => margin.left + ((d - first) / span) * (width - margin.left - margin.right);
    xAxisYears(svg, yearStarts(first, last), x, height - margin.bottom);

    for (const s of series) {
      const d = points
        .filter((p) => p[s.key] != null)
        .map((p, i) => `${i ? "L" : "M"}${x(p.x).toFixed(1)},${y(p[s.key]).toFixed(1)}`)
        .join("");
      el("path", { class: "series-line", d, style: `stroke: ${s.color}` }, svg);
    }

    // direct labels at the right end, unless two of them would overlap
    const ends = series.map((s) => ({ s, value: points[points.length - 1][s.key] }));
    const ys = ends.map((e) => y(e.value));
    const apart = ys.every((a, i) => ys.every((b, j) => i === j || Math.abs(a - b) >= 14));
    for (const [i, e] of ends.entries()) {
      if (e.value == null) continue;
      el("circle", { class: "end-dot", cx: x(last), cy: ys[i], r: 4, style: `fill: ${e.s.color}` }, svg);
      if (apart) {
        el("text", { class: "end-label", x: x(last) + 8, y: ys[i] + 4 }, svg).textContent = format(e.value);
      }
    }

    const cross = el("g", { visibility: "hidden" }, svg);
    const line = el("line", { class: "crosshair", y1: margin.top, y2: height - margin.bottom }, cross);
    const dots = series.map((s) => el("circle", { class: "end-dot", r: 4, style: `fill: ${s.color}` }, cross));
    let index = points.length - 1;

    const show = (i, clientX, clientY) => {
      index = i;
      const p = points[i];
      line.setAttribute("x1", x(p.x));
      line.setAttribute("x2", x(p.x));
      series.forEach((s, k) => {
        const on = p[s.key] != null;
        dots[k].setAttribute("visibility", on ? "visible" : "hidden");
        if (on) {
          dots[k].setAttribute("cx", x(p.x));
          dots[k].setAttribute("cy", y(p[s.key]));
        }
      });
      cross.setAttribute("visibility", "visible");
      showTooltip(
        clientX,
        clientY,
        label(p.x),
        series.map((s) => ({ value: p[s.key] == null ? "–" : format(p[s.key]), label: s.label, color: s.color })),
      );
    };
    const hide = () => {
      cross.setAttribute("visibility", "hidden");
      hideTooltip();
    };
    const nearest = (clientX) => {
      const left = svg.getBoundingClientRect().left;
      const target = clientX - left;
      let lo = 0;
      let hi = points.length - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (x(points[mid].x) < target) lo = mid;
        else hi = mid;
      }
      return Math.abs(x(points[lo].x) - target) <= Math.abs(x(points[hi].x) - target) ? lo : hi;
    };

    const hit = el("rect", { x: margin.left, y: margin.top, width: width - margin.left - margin.right, height: height - margin.top - margin.bottom, fill: "transparent" }, svg);
    hit.addEventListener("pointermove", (event) => show(nearest(event.clientX), event.clientX, event.clientY));
    hit.addEventListener("pointerleave", hide);
    const showAtIndex = (i) => {
      const box = svg.getBoundingClientRect();
      show(i, box.left + x(points[i].x), box.top + margin.top + 20);
    };
    svg.addEventListener("focus", () => showAtIndex(index));
    svg.addEventListener("blur", hide);
    svg.addEventListener("keydown", (event) => {
      const step = event.shiftKey ? 30 : 1;
      if (event.key === "ArrowLeft") showAtIndex(Math.max(0, index - step));
      else if (event.key === "ArrowRight") showAtIndex(Math.min(points.length - 1, index + step));
      else return;
      event.preventDefault();
    });
  };
  whenResized(svgBox, render);
}

/** One column per month, rounded at the top, with a tooltip per column. */
function columnChart(container, { points, title, valueLabel }) {
  const svgBox = html("div");
  container.append(svgBox);

  const render = () => {
    svgBox.replaceChildren();
    const width = svgBox.clientWidth;
    const height = 240;
    const margin = { top: 10, right: 12, bottom: 26, left: 44 };
    const yTicks = ticksUpTo(Math.max(...points.map((p) => p.value)));
    const svg = el("svg", { width, height, role: "img", "aria-label": title, tabindex: 0 }, svgBox);
    const y = frame(svg, { width, height, margin, yTicks, yFormat: tickFormatter(yTicks, "count") });
    const band = (width - margin.left - margin.right) / points.length;
    const barWidth = Math.max(1, Math.min(24, band - 2));
    const base = height - margin.bottom;
    const x = (i) => margin.left + i * band + (band - barWidth) / 2;

    const bars = points.map((p, i) => {
      const top = y(p.value);
      const r = Math.min(4, barWidth / 2, base - top);
      const left = x(i);
      const d = `M${left},${base}V${top + r}Q${left},${top} ${left + r},${top}H${left + barWidth - r}Q${left + barWidth},${top} ${left + barWidth},${top + r}V${base}Z`;
      return el("path", { class: "column", d }, svg);
    });
    points.forEach((p, i) => {
      if (p.x.getUTCMonth() === 0) {
        el("text", { x: x(i) + barWidth / 2, y: base + 18, "text-anchor": "middle" }, svg).textContent = p.x.getUTCFullYear();
      }
    });

    let index = points.length - 1;
    const show = (i, clientX, clientY) => {
      bars[index].classList.remove("active");
      index = i;
      bars[i].classList.add("active");
      showTooltip(clientX, clientY, monthFormat.format(points[i].x), [{ value: count(points[i].value), label: valueLabel }]);
    };
    const hide = () => {
      bars[index].classList.remove("active");
      hideTooltip();
    };
    points.forEach((p, i) => {
      const hit = el("rect", { x: margin.left + i * band, y: margin.top, width: band, height: base - margin.top, fill: "transparent" }, svg);
      hit.addEventListener("pointerenter", (event) => show(i, event.clientX, event.clientY));
      hit.addEventListener("pointermove", (event) => show(i, event.clientX, event.clientY));
      hit.addEventListener("pointerleave", hide);
    });
    const showAtIndex = (i) => {
      const box = svg.getBoundingClientRect();
      show(i, box.left + x(i) + barWidth / 2, box.top + y(points[i].value));
    };
    svg.addEventListener("focus", () => showAtIndex(index));
    svg.addEventListener("blur", hide);
    svg.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") showAtIndex(Math.max(0, index - 1));
      else if (event.key === "ArrowRight") showAtIndex(Math.min(points.length - 1, index + 1));
      else return;
      event.preventDefault();
    });
  };
  whenResized(svgBox, render);
}

/** Ranked horizontal bars in HTML, value at the tip of each bar. */
function barList(container, rows) {
  const max = Math.max(...rows.map((r) => r.value));
  const grid = html("div", { className: "bars" });
  for (const r of rows) {
    const name = html("div", { className: "name", textContent: r.label });
    if (r.note) name.append(html("small", { textContent: r.note }));
    const bar = html("div", { className: "bar" });
    bar.style.width = `${(r.value / max) * 85}%`;
    grid.append(name, html("div", { className: "track" }, bar, html("span", { className: "num", textContent: count(r.value) })));
  }
  container.append(grid);
}

// ---- sections --------------------------------------------------------------

// `monthly` starts at the first complete month.
function renderTiles(summary, monthly, districts) {
  const lastYear = monthly.slice(-12);
  const start = utcDate(summary.first_complete_month);
  const builtAt = new Date(summary.built_at);
  const reported = sum(monthly, "reported");
  const daysCovered = (builtAt - start) / 86400000;
  const oldOpen = districts.reduce((sum, d) => sum + d.open_30_days_or_more, 0);
  const tiles = [
    {
      label: `Tickets since ${monthFormat.format(start)}`,
      value: count(reported),
      sub: `about ${count(reported / daysCovered)} a day`,
    },
    { label: "Open now", value: count(summary.open_tickets), sub: `${count(oldOpen)} of them for 30 days or more` },
    {
      label: "Finished within 7 days",
      value: percent(share(sum(lastYear, "finished_within_7_days"), sum(lastYear, "reported_7_days_ago_or_more"))),
      sub: "tickets reported in the last 12 months",
    },
    {
      label: "Median days to finish",
      value: days(summary.median_days_to_finish_past_year),
      sub: "finished tickets reported in the last year",
    },
  ];
  const box = document.getElementById("tiles");
  for (const t of tiles) {
    box.append(
      html(
        "div",
        { className: "tile" },
        html("div", { className: "label", textContent: t.label }),
        html("div", { className: "value", textContent: t.value }),
        html("div", { className: "sub", textContent: t.sub }),
      ),
    );
  }
  const asOf = document.getElementById("as-of");
  asOf.textContent =
    `Updated ${bangkokFormat.format(builtAt)} Bangkok time. History starts in ${monthFormat.format(start)}, ` +
    `the first month the API still holds in full; hourly collection began ${dayFormat.format(new Date(summary.collection_started_at))}.`;
}

function sum(rows, key) {
  return rows.reduce((total, r) => total + (r[key] ?? 0), 0);
}

function renderDistricts(rows) {
  const columns = [
    { key: "name_en", label: "District", text: true },
    { key: "tickets", label: "Tickets", format: count },
    { key: "open_tickets", label: "Open now", format: count },
    { key: "open_30_days_or_more", label: "Open 30+ days", format: count, bar: true },
    { key: "finished_7", label: "Finished in 7 days", format: percent },
    { key: "median_days_to_finish", label: "Median days to finish", format: days },
  ];
  const named = rows
    .filter((r) => r.district_code !== -1)
    .map((r) => ({ ...r, finished_7: share(r.finished_within_7_days, r.reported_7_days_ago_or_more) }));
  const unnamed = rows.filter((r) => r.district_code === -1);
  const barMax = Math.max(...named.map((r) => r.open_30_days_or_more));
  let sortKey = "open_30_days_or_more";
  let ascending = false;
  let showAll = false;
  const SHOWN = 10;

  const table = html("table");
  const headRow = html("tr");
  const tbody = html("tbody");
  table.append(html("caption", { className: "sr-only", textContent: "Tickets by district" }), html("thead", {}, headRow), tbody);

  const cell = (r, c) => {
    if (c.text) {
      const td = html("td", { textContent: r.district_code === -1 ? "No district in the address" : r.name_en });
      if (r.district_code !== -1) td.append(html("span", { className: "th-name", textContent: r.name_th }));
      return td;
    }
    const td = html("td", { textContent: c.format(r[c.key]) });
    if (c.bar && r.district_code !== -1) {
      const bar = html("span", { className: "inline-bar" });
      bar.style.width = `${barMax ? (r[c.key] / barMax) * 60 : 0}px`;
      td.append(bar);
    }
    return td;
  };

  const draw = () => {
    const sorted = [...named].sort((a, b) => {
      const av = a[sortKey] ?? -Infinity;
      const bv = b[sortKey] ?? -Infinity;
      const order = typeof av === "string" ? av.localeCompare(bv) : av - bv;
      return ascending ? order : -order;
    });
    const visible = showAll ? [...sorted, ...unnamed] : sorted.slice(0, SHOWN);
    tbody.replaceChildren(...visible.map((r) => html("tr", {}, ...columns.map((c) => cell(r, c)))));
    more.textContent = showAll ? "Show the first ten" : `Show all ${named.length} districts`;
    for (const th of headRow.children) {
      if (th.dataset.key === sortKey) th.setAttribute("aria-sort", ascending ? "ascending" : "descending");
      else th.removeAttribute("aria-sort");
    }
  };

  for (const c of columns) {
    const button = html("button", { type: "button", textContent: c.label });
    button.addEventListener("click", () => {
      ascending = sortKey === c.key ? !ascending : Boolean(c.text);
      sortKey = c.key;
      draw();
    });
    const th = html("th", { scope: "col" }, button);
    th.dataset.key = c.key;
    headRow.append(th);
  }
  const more = html("button", { type: "button", className: "more" });
  more.addEventListener("click", () => {
    showAll = !showAll;
    draw();
  });
  draw();
  document.getElementById("districts").append(html("div", { className: "table-wrap" }, table), more);
}

function renderStates(rows) {
  const open = rows.filter((r) => r.is_open).sort((a, b) => b.tickets - a.tickets);
  const closed = rows.filter((r) => !r.is_open).sort((a, b) => b.tickets - a.tickets);
  const closedText = closed.map((r) => `${count(r.tickets)} ${r.name_en.toLowerCase()}`).join(" and ");
  document.getElementById("states-note").textContent =
    `${count(sum(open, "tickets"))} tickets are open now. The other ${count(sum(closed, "tickets"))} are closed: ${closedText}.`;
  barList(
    document.getElementById("states"),
    open.map((r) => ({ label: r.name_en, note: r.name_th, value: r.tickets })),
  );
}

function renderCategories(rows) {
  const container = document.getElementById("categories");
  const sorted = [...rows].sort((a, b) => b.tickets - a.tickets);
  barList(
    container,
    sorted.map((r) => ({
      label: r.name_en,
      note: r.name_en === r.problem_type ? "" : r.problem_type,
      value: r.tickets,
    })),
  );
}

function renderDataQuality(rows) {
  const list = document.getElementById("data-quality");
  const find = (name) => rows.find((r) => r.check_name === name);
  const item = (strong, rest) => list.append(html("li", {}, html("strong", { textContent: strong }), ` ${rest}`));
  const ticketCheck = (name, text) => {
    const r = find(name);
    if (r) item(`${percent(share(r.affected, r.out_of))} of tickets`, `(${count(r.affected)} of ${count(r.out_of)}) ${text}`);
  };
  ticketCheck("ticket_without_category", "name no category.");
  ticketCheck("address_without_district", "have an address that names no Bangkok district, so they count under no district.");
  const before = find("activity_before_report");
  if (before && before.affected > 0) item(`${count(before.affected)} tickets`, "show a latest activity earlier than their report time.");
  const unlisted = rows.filter((r) => r.check_name === "state_not_in_seed");
  if (unlisted.length) {
    item(
      `${count(sum(unlisted, "affected"))} tickets`,
      `are in states the model does not list yet (${unlisted.map((r) => r.detail).join(", ")}), so they count as open.`,
    );
  }
  const runs = find("run_short_of_api_total");
  const missing = find("tickets_short_of_api_total");
  if (runs && missing) {
    item(
      `${count(runs.affected)} of ${count(runs.out_of)} pulls`,
      `returned fewer tickets than the total the API reported on their first page: ${count(missing.affected)} of ${count(missing.out_of)} in all.`,
    );
  }
}

async function load(name) {
  const response = await fetch(`data/${name}.json`);
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  return response.json();
}

async function main() {
  const [summaryRows, allMonths, allDays, districts, states, categories, quality] = await Promise.all(
    ["rpt_summary", "rpt_monthly", "rpt_backlog_daily", "rpt_district", "rpt_state", "rpt_problem_type", "rpt_data_quality"].map(load),
  );
  const summary = summaryRows[0];
  // Months before this one are missing the tickets the API no longer returns.
  const start = utcDate(summary.first_complete_month);
  const monthly = allMonths.filter((r) => utcDate(r.month_start) >= start);
  const backlog = allDays.filter((r) => utcDate(r.snapshot_date) >= start);
  const blue = "var(--series-1)";
  const orange = "var(--series-2)";

  renderTiles(summary, monthly, districts);

  const backlogPoints = backlog.map((r) => ({ x: utcDate(r.snapshot_date), open: r.open_tickets, old: r.open_30_days_or_more }));
  const backlogBox = document.getElementById("backlog");
  lineChart(backlogBox, {
    points: backlogPoints,
    title: "Open tickets at the end of each day",
    series: [
      { key: "open", label: "Open", color: blue },
      { key: "old", label: "Open 30 days or more", color: orange },
    ],
  });
  tableView(backlogBox, "Open tickets at the end of each day", [
    { label: "Day", value: (r) => dayFormat.format(r.x) },
    { label: "Open", value: (r) => count(r.open) },
    { label: "Open 30 days or more", value: (r) => count(r.old) },
  ], [...backlogPoints].reverse());

  const months = monthly.map((r) => ({
    x: utcDate(r.month_start),
    reported: r.reported,
    within7: share(r.finished_within_7_days, r.reported_7_days_ago_or_more),
    category: share(r.with_category, r.reported),
    median: r.median_days_to_finish,
  }));
  const reportedBox = document.getElementById("monthly-reported");
  columnChart(reportedBox, { points: months.map((m) => ({ x: m.x, value: m.reported })), title: "Tickets reported each month", valueLabel: "tickets" });
  const within7Box = document.getElementById("monthly-7-days");
  lineChart(within7Box, {
    points: months.filter((m) => m.within7 != null),
    title: "Share of each month's tickets finished within 7 days",
    series: [{ key: "within7", label: "finished within 7 days", color: blue }],
    kind: "percent",
    period: "month",
  });
  const categoryBox = document.getElementById("monthly-category");
  lineChart(categoryBox, {
    points: months,
    title: "Share of each month's tickets that name a category",
    series: [{ key: "category", label: "name a category", color: blue }],
    kind: "percent",
    period: "month",
  });
  const newestFirst = [...months].reverse();
  const month = { label: "Month", value: (r) => monthFormat.format(r.x) };
  tableView(reportedBox, "Tickets reported each month", [month, { label: "Reported", value: (r) => count(r.reported) }], newestFirst);
  tableView(within7Box, "Share of each month's tickets finished within 7 days", [
    month,
    { label: "Finished in 7 days", value: (r) => percent(r.within7) },
    { label: "Median days to finish", value: (r) => days(r.median) },
  ], newestFirst);
  tableView(categoryBox, "Share of each month's tickets that name a category", [
    month,
    { label: "Reported", value: (r) => count(r.reported) },
    { label: "Name a category", value: (r) => percent(r.category) },
  ], newestFirst);

  renderStates(states);
  renderDistricts(districts);
  renderCategories(categories);
  renderDataQuality(quality);
}

main().catch((error) => {
  document.getElementById("as-of").textContent = `The data could not be loaded (${error.message}).`;
});
