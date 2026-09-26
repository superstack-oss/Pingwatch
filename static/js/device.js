const root = document.querySelector(".detail");
const id = root.dataset.deviceId;
let historyRange = "recent";
let checkPage = 1;
let current = null;

function apiRange() {
  return historyRange === "recent" ? "24h" : historyRange;
}

function intervalSeconds() {
  return Number(window.PINGWATCH_INTERVAL || 30);
}

function prettySpan(fromIso) {
  const parsed = parseDate(fromIso);
  if (!parsed) return "—";
  let sec = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 1000));
  const days = Math.floor(sec / 86400);
  sec %= 86400;
  const hours = Math.floor(sec / 3600);
  sec %= 3600;
  const mins = Math.floor(sec / 60);
  sec %= 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  if (mins > 0) return `${mins}m ${sec}s`;
  return `${sec}s`;
}

function formatCheckTime(value) {
  const parsed = parseDate(value);
  if (!parsed) return "—";
  const opts = { timeZone: window.PINGWATCH_TZ };
  try {
    const date = parsed.toLocaleDateString([], {
      weekday: "short",
      month: "long",
      day: "numeric",
      year: "numeric",
      ...opts,
    });
    const time = parsed.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
      ...opts,
    });
    return `${date} at ${time}`;
  } catch (err) {
    return parsed.toLocaleString();
  }
}

function chartPoints(history) {
  const points = history.points || [];
  if (historyRange !== "recent") return points;
  return points.slice(-48);
}

function rttGrade(value) {
  if (value == null) return { label: "No data", tone: "muted" };
  if (value < 50) return { label: "Excellent", tone: "up" };
  if (value < 100) return { label: "Good", tone: "up" };
  if (value < 200) return { label: "Fair", tone: "warn" };
  return { label: "Slow", tone: "down" };
}

function renderHero(device) {
  document.querySelector("#device-name").textContent = device.name;
  document.querySelector("#device-host").textContent = device.host;
  const ip = device.resolved_ip || (device.resolved_ips && device.resolved_ips[0]) || "";
  const ipNode = document.querySelector("#device-ip");
  const ipSep = document.querySelector("#device-ip-sep");
  if (ip && ip !== device.host) {
    ipNode.hidden = false;
    ipSep.hidden = false;
    ipNode.textContent = ip;
  } else {
    ipNode.hidden = true;
    ipSep.hidden = true;
    ipNode.textContent = "";
  }
  document.querySelector("#device-kind").textContent = `${device.monitor_label || monitorLabel(device.monitor_type)} · ${kindLabel(device.kind)}`;
  document.querySelector("#device-interval").textContent = `Checking every ${intervalSeconds()} seconds`;
  document.title = `${device.name} · Pingwatch`;
  const dot = document.querySelector("#device-dot");
  dot.className = `live-dot ${device.display_status}`;

  const down = device.status === "down" || device.display_status === "offline";
  const paused = Boolean(device.service_mode);
  const hero = document.querySelector("#kpi-span");
  hero.className = `kpi-hero ${paused ? "paused" : down ? "down" : device.display_status === "warning" ? "warn" : "up"}`;
  const since = down
    ? (device.last_outage && device.last_outage.started_at) || device.last_change_at || device.last_down_at
    : device.last_change_at || device.last_up_at || device.created_at;
  document.querySelector("#kpi-span-label").textContent = paused ? "Paused for" : down ? "Down for" : "Active for";
  document.querySelector("#kpi-span-value").textContent = prettySpan(since);
  document.querySelector("#kpi-check").textContent = relTime(device.last_checked_at);
  document.querySelector("#kpi-rtt").textContent = device.status === "up" ? ms(device.rtt_ms).replace(" ms", "ms") : "—";
  document.querySelector("#kpi-avail").textContent = pct(device.uptime_24h);
  const sub = [];
  if (device.uptime_30d != null) sub.push(`30d ${pct(device.uptime_30d)}`);
  if (device.ci || device.item_id) sub.push(`CI ${device.ci || device.item_id}`);
  document.querySelector("#kpi-avail-sub").textContent = sub.join(" · ");
  renderSsl(device);
}

let sslLookupInFlight = false;
let sslLookupDone = false;

async function lookupSsl(force) {
  if (sslLookupInFlight) return;
  if (!force && sslLookupDone) return;
  sslLookupInFlight = true;
  const button = document.querySelector("#ssl-refresh");
  if (button) button.disabled = true;
  try {
    const ssl = await api(`/api/devices/${id}/ssl`, { method: "POST" });
    sslLookupDone = true;
    if (current) {
      current = { ...current, ssl };
      renderSsl(current, { skipLookup: true });
    }
  } catch (error) {
    sslLookupDone = true;
    const meta = document.querySelector("#ssl-status-meta");
    if (meta) {
      meta.hidden = false;
      meta.textContent = error.message;
    }
  } finally {
    sslLookupInFlight = false;
    if (button) button.disabled = false;
  }
}

function renderSsl(device, options) {
  const ssl = device.ssl;
  renderSslCards(ssl, device.host);
  if (!(options && options.skipLookup) && sslNeedsLookup(ssl)) {
    lookupSsl(false);
  } else if (ssl && (ssl.cert || ssl.domain || !sslNeedsLookup(ssl))) {
    sslLookupDone = true;
  }
}

function drawUptimeBars(points) {
  const host = document.querySelector("#uptime-bars");
  const sample = points.slice(-40);
  if (!sample.length) {
    host.innerHTML = emptyState({ title: "No checks in this range", body: "Response samples appear after probes run.", compact: true });
    return;
  }
  host.innerHTML = sample
    .map((point) => {
      const up = Boolean(point.is_up);
      const h = up ? 28 + Math.min(36, (point.rtt_ms || 0) / 8) : 10;
      return `<i class="ub ${up ? "ok" : "miss"}" style="height:${h}px" title="${up ? ms(point.rtt_ms) : point.error || "down"}"></i>`;
    })
    .join("");
}

function drawDowntime(points) {
  const host = document.querySelector("#downtime-fill");
  const down = points.filter((point) => !point.is_up);
  document.querySelector("#downtime-meta").textContent = `Total checks: ${down.length}`;
  if (!down.length) {
    host.innerHTML = emptyState({ title: "No downtime in this range", body: "This card fills when checks fail.", compact: true });
    return;
  }
  host.innerHTML = `<div class="downtime-block" role="img" aria-label="${down.length} failed checks"></div>`;
}

function drawGauge(avg) {
  const host = document.querySelector("#rtt-gauge");
  if (avg == null) {
    host.innerHTML = emptyState({
      title: "No response time yet",
      body: "The gauge uses the latest successful probe sample for this CI.",
      compact: true,
    });
    return;
  }
  const grade = rttGrade(avg);
  const max = 400;
  const value = Math.max(0, Math.min(max, Number(avg) || 0));
  const r = 72;
  const c = Math.PI * r;
  const offset = c - (value / max) * c;
  host.innerHTML = `<svg viewBox="0 0 200 130" class="gauge-svg" aria-hidden="true">
      <path d="M28 110 A72 72 0 0 1 172 110" fill="none" stroke="currentColor" stroke-width="16" opacity="0.12" stroke-linecap="round"></path>
      <path d="M28 110 A72 72 0 0 1 172 110" fill="none" stroke="${
        grade.tone === "down" ? "#e11d48" : grade.tone === "warn" ? "#d97706" : "#22c55e"
      }" stroke-width="16" stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${offset.toFixed(
        1
      )}"></path>
    </svg>
    <div class="gauge-copy">
      <strong class="${grade.tone}">${grade.label}</strong>
      <span>${avg == null ? "—" : ms(avg).replace(" ms", "ms")}</span>
    </div>`;
}

function drawChart(points) {
  const host = document.querySelector("#chart");
  const usable = points.filter((point) => point.rtt_ms != null);
  if (!usable.length) {
    host.innerHTML = emptyState({ title: "No response-time samples", body: "The chart is drawn from real ping results for this CI.", compact: true });
    return;
  }
  const width = 920;
  const height = 220;
  const pad = { l: 16, r: 16, t: 16, b: 36 };
  const max = Math.max(...usable.map((point) => point.rtt_ms), 1);
  const coords = usable.map((point, index) => {
    const x = pad.l + (index / Math.max(usable.length - 1, 1)) * (width - pad.l - pad.r);
    const y = height - pad.b - (point.rtt_ms / max) * (height - pad.t - pad.b);
    return [x, y];
  });
  const line = coords.map((pair) => `${pair[0].toFixed(1)},${pair[1].toFixed(1)}`).join(" ");
  const area = `${pad.l},${height - pad.b} ${line} ${coords[coords.length - 1][0].toFixed(1)},${height - pad.b}`;
  const labels = usable
    .filter((_, index) => index === 0 || index === usable.length - 1 || index % Math.ceil(usable.length / 8) === 0)
    .map((point) => {
      const index = usable.indexOf(point);
      const x = pad.l + (index / Math.max(usable.length - 1, 1)) * (width - pad.l - pad.r);
      return `<text x="${x}" y="${height - 10}" text-anchor="middle" font-size="11" fill="currentColor" opacity="0.5">${clock(
        point.checked_at
      )}</text>`;
    });
  host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Response time history">
    <defs>
      <linearGradient id="detailRtt" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.28"></stop>
        <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.02"></stop>
      </linearGradient>
    </defs>
    <polygon class="detail-area" points="${area}"></polygon>
    <polyline class="line detail-line" points="${line}"></polyline>
    ${labels.join("")}
  </svg>`;
}

async function loadDevice() {
  const device = await api(`/api/devices/${id}`);
  current = device;
  renderHero(device);
}

async function loadHistory() {
  const history = await api(`/api/devices/${id}/history?range=${apiRange()}`);
  lastHistory = history;
  const points = chartPoints(history);
  const upCount = points.filter((point) => point.is_up).length;
  const label = historyRange === "recent" ? "Recent" : historyRange === "24h" ? "Day" : historyRange === "7d" ? "Week" : "Month";
  document.querySelector("#snapshot-count").textContent = `${history.sample_count} checks in ${label}`;
  document.querySelector("#uptime-meta").textContent = `Total checks: ${upCount}`;
  drawUptimeBars(points);
  drawDowntime(points);
  drawGauge(history.avg_rtt_ms);
  drawChart(points);
}

async function loadChecks() {
  const payload = await api(`/api/devices/${id}/checks?range=${apiRange()}&page=${checkPage}&page_size=${PAGE_SIZE}`);
  const rows = document.querySelector("#check-rows");
  const pager = document.querySelector("#check-pager");
  const table = document.querySelector(".checks-table");
  const empty = document.querySelector("#check-empty");
  if (!payload.checks.length) {
    rows.innerHTML = "";
    table.hidden = true;
    pager.hidden = true;
    empty.hidden = false;
    empty.innerHTML = emptyState({
      title: "No checks in this range",
      body: "Each row is a real probe for this CI.",
      compact: true,
    });
    return;
  }
  table.hidden = false;
  empty.hidden = true;
  rows.innerHTML = payload.checks
    .map((item) => {
      const up = Boolean(item.is_up);
      return `<tr>
        <td><span class="pill soft ${up ? "online" : "offline"}"><i></i>${up ? "Up" : "Down"}</span></td>
        <td>${formatCheckTime(item.checked_at)}</td>
        <td>${escapeHtml(item.error || (up ? "" : "Request timeout"))}</td>
        <td>${up ? ms(item.rtt_ms) : "—"}</td>
      </tr>`;
    })
    .join("");
  pager.hidden = payload.pages <= 1;
  const start = (payload.page - 1) * payload.page_size + 1;
  const end = start + payload.checks.length - 1;
  document.querySelector("#check-range-label").textContent = `Showing ${start}–${end} of ${payload.total}`;
  document.querySelector("#check-page-label").textContent = t("dash.page", { page: payload.page, pages: payload.pages });
  document.querySelector("#check-prev").disabled = payload.page <= 1;
  document.querySelector("#check-next").disabled = payload.page >= payload.pages;
  checkPage = payload.page;
}

document.querySelector("#history-range").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-range]");
  if (!button) return;
  historyRange = button.dataset.range;
  checkPage = 1;
  document.querySelectorAll("#history-range button").forEach((node) => node.classList.toggle("active", node === button));
  Promise.all([loadHistory(), loadChecks()]).catch((error) => {
    document.querySelector("#chart").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  });
});

document.querySelector("#probe").addEventListener("click", async () => {
  await api(`/api/devices/${id}/probe`, { method: "POST" });
  await refreshAll();
});
document.querySelector("#ssl-refresh")?.addEventListener("click", () => {
  lookupSsl(true);
});
document.querySelector("#remove")?.addEventListener("click", async () => {
  if (!currentUser || currentUser.role !== "admin") return;
  const ok = await confirmAction({
    title: t("dash.confirm_delete"),
    body: t("common.confirm_delete_body"),
    danger: true,
    confirmLabel: t("dash.delete"),
  });
  if (!ok) return;
  await api(`/api/devices/${id}`, { method: "DELETE" });
  window.location.href = "/";
});
document.querySelector("#check-prev").addEventListener("click", () => {
  checkPage = Math.max(1, checkPage - 1);
  loadChecks().catch(() => {});
});
document.querySelector("#check-next").addEventListener("click", () => {
  checkPage += 1;
  loadChecks().catch(() => {});
});

async function refreshAll() {
  await loadDevice();
  await Promise.all([loadHistory(), loadChecks()]);
}

window.sessionReady.then(() => {
  refreshAll().catch((error) => {
    document.querySelector("#device-name").textContent = "Unable to load device";
    const box = document.querySelector("#device-error");
    box.hidden = false;
    box.textContent = error.message;
  });
  setInterval(() => {
    refreshAll().catch(() => {});
  }, 12000);
});
window.addEventListener("pingwatch:refresh", () => refreshAll().catch(() => {}));
