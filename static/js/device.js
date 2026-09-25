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

function hopRtt(hop) {
  const match = String(hop.raw || "").match(/([\d.]+)\s*ms/i);
  return match ? `${match[1]}ms` : "";
}

function chartPoints(history) {
  const points = history.points || [];
  if (historyRange !== "recent") return points;
  return points.slice(-48);
}

function severity(device) {
  if (device.display_status === "offline" || device.status === "down") return { label: "Critical", cls: "crit" };
  if (device.display_status === "warning") return { label: "Warn", cls: "warn" };
  if (device.display_status === "paused") return { label: "Paused", cls: "info" };
  return { label: "Info", cls: "info" };
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
  document.querySelector("#device-host").textContent = device.target_display || device.host;
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
}

function renderDiagnostics(device, extraInsight) {
  const insight = extraInsight || device.insight;
  const sev = severity(device);
  const up = device.status === "up" && device.display_status !== "warning";
  const probe = device.monitor_label || monitorLabel(device.monitor_type) || "Ping";
  document.querySelector("#diag-badges").innerHTML = `
    <span class="chip ${sev.cls}">Severity: ${sev.label}</span>
    <span class="chip">Monitor status: ${statusLabel(device.display_status)}</span>
    <span class="chip">Probe: ${escapeHtml(probe)} · ${escapeHtml(kindLabel(device.kind))}</span>`;
  document.querySelector("#diag-cause").innerHTML = `<strong>Probable cause:</strong> ${escapeHtml(
    insight
      ? insight.summary
      : up
        ? "Endpoint is healthy. Probe replies are within the warning threshold."
        : device.last_error || "No reply from this monitor."
  )}`;
  const host = document.querySelector("#insight");
  if (!insight) {
    host.innerHTML = `
      <p class="diag-box-title">Error details and troubleshooting</p>
      <div class="diag-facts">
        <div><span>Error</span><strong>${escapeHtml(device.last_error || "None")}</strong></div>
        <div><span>Error code</span><strong>—</strong></div>
        <div><span>Scope</span><strong>${escapeHtml(kindLabel(device.kind))} / ${escapeHtml(probe)}</strong></div>
      </div>
      <p class="diag-box-title">Troubleshooting steps</p>
      <ul class="diag-list">
        <li>Confirm the ping target is the management address, not a data-plane port.</li>
        <li>Try SSH or the vendor HTTPS UI from a jump host on the same VLAN.</li>
        <li>If several endpoints in the same subnet fail together, inspect the shared gateway first.</li>
      </ul>`;
    return;
  }
  const causes = insight.likely_cause ? [insight.likely_cause] : [];
  const checks = insight.checks || [];
  host.innerHTML = `
    <p class="diag-box-title">Error details and troubleshooting</p>
    <div class="diag-facts">
      <div><span>Error</span><strong>${escapeHtml(insight.title || device.last_error || "—")}</strong></div>
      <div><span>Error code</span><strong>${escapeHtml(insight.code || "—")}</strong></div>
      <div><span>Scope</span><strong>${escapeHtml(kindLabel(device.kind))} / ${escapeHtml(probe)}</strong></div>
    </div>
    ${insight.where ? `<p class="diag-where"><span>Where</span> ${escapeHtml(insight.where)}</p>` : ""}
    ${
      causes.length
        ? `<p class="diag-box-title">Likely causes</p><ul class="diag-list">${causes
            .map((item) => `<li>${escapeHtml(item)}</li>`)
            .join("")}</ul>`
        : ""
    }
    ${
      checks.length
        ? `<p class="diag-box-title">Troubleshooting steps</p><ul class="diag-list">${checks
            .map((item) => `<li>${escapeHtml(item)}</li>`)
            .join("")}</ul>`
        : ""
    }`;
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
  renderDiagnostics(device);
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

async function loadOutages() {
  const payload = await api(`/api/devices/${id}/outages?range=30d`);
  const host = document.querySelector("#outages");
  if (!payload.outages.length) {
    host.innerHTML = emptyState({ title: "No downtime recorded", body: "Outages are created from consecutive failed probes.", compact: true });
    return;
  }
  host.innerHTML = `<p class="muted">30d availability ${pct(payload.availability)}</p>
    <ul class="outage-list">${payload.outages
      .map((item) => {
        return `<li>
          <strong>${item.ongoing ? "Ongoing" : "Recovered"}</strong>
          <span>Down ${relTime(item.started_at)}</span>
          <span>${duration(item.duration_seconds)}</span>
          <span>${escapeHtml(item.last_error || "No error detail")}</span>
        </li>`;
      })
      .join("")}</ul>`;
}

async function loadDns(refresh) {
  const host = document.querySelector("#dns");
  host.innerHTML = `<p class="muted">Checking DNS…</p>`;
  try {
    const dns = await api(`/api/devices/${id}/dns${refresh ? "?refresh=true" : ""}`);
    if (!dns.ok) {
      host.innerHTML = `<p class="empty">DNS error: ${escapeHtml(dns.error || "lookup failed")}</p>`;
      return;
    }
    host.innerHTML = `
      <p><span class="dns-ok">Valid</span> <span class="mono">${escapeHtml(dns.host)}</span></p>
      <p>A: <span class="mono">${escapeHtml((dns.addresses || []).join(", ") || "—")}</span></p>
      <p>${dns.reverse?.length ? "Reverse" : "No reverse DNS"}</p>
      <p class="mono">${escapeHtml((dns.reverse || []).join(", ") || "—")}</p>
      <p class="muted">${dns.elapsed_ms} ms · ${relTime(dns.checked_at)}</p>`;
  } catch (error) {
    host.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function renderTcp(tcp) {
  const host = document.querySelector("#tcp-ports");
  if (!tcp || !tcp.length) {
    host.innerHTML = emptyState({
      title: "No port results yet",
      body: "Run Investigate to probe management TCP ports for this CI from Pingwatch.",
      compact: true,
    });
    return;
  }
  host.innerHTML = `<ul class="port-list">${tcp
    .map(
      (item) =>
        `<li><span class="mono">${item.port}</span><span class="pill soft ${item.open ? "online" : "offline"}"><i></i>${
          item.open ? "Open" : "Closed"
        }</span><span class="muted">${item.open ? ms(item.elapsed_ms) : item.error || "no answer"}</span></li>`
    )
    .join("")}</ul>`;
}

function renderTrace(result) {
  const host = document.querySelector("#traceroute");
  if (!result) {
    host.innerHTML = emptyState({
      title: "Trace path on demand",
      body: "Hop-by-hop results appear here after you run a traceroute. It is not part of the regular sweep.",
      compact: true,
    });
    return;
  }
  const hops = result.hops || [];
  if (!hops.length) {
    host.innerHTML = `<p class="empty">${escapeHtml(result.error || "No hops returned")}</p>`;
    return;
  }
  host.innerHTML = `<p class="muted">${hops.length} hops</p>
    <ol class="trace-list">${hops
      .map((hop) => {
        const rtt = hopRtt(hop);
        return `<li><span class="mono">${hop.hop}.</span> ${escapeHtml(hop.host || "*")}${
          rtt ? ` <span class="muted">— ${rtt}</span>` : ""
        }</li>`;
      })
      .join("")}</ol>`;
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

async function runDiagnostics(traceroute) {
  const waitOn = traceroute ? document.querySelector("#traceroute") : document.querySelector("#tcp-ports");
  waitOn.innerHTML = `<p class="muted">${traceroute ? "Tracing path…" : "Running extra diagnostics…"}</p>`;
  try {
    const result = await api(`/api/devices/${id}/diagnostics${traceroute ? "?traceroute=true" : ""}`);
    renderTcp(result.tcp);
    if (result.traceroute) renderTrace(result.traceroute);
    if (current) {
      if (result.insight) renderDiagnostics({ ...current, insight: result.insight }, result.insight);
      else if (!result.ping?.is_up) {
        renderDiagnostics({ ...current, status: "down", display_status: "offline", last_error: result.ping.error });
      }
    }
  } catch (error) {
    waitOn.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
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
document.querySelector("#remove").addEventListener("click", async () => {
  if (!confirm("Remove this device?")) return;
  await api(`/api/devices/${id}`, { method: "DELETE" });
  window.location.href = "/";
});
document.querySelector("#refresh-dns").addEventListener("click", () => loadDns(true));
document.querySelector("#run-diag").addEventListener("click", () => runDiagnostics(false));
document.querySelector("#run-trace").addEventListener("click", () => runDiagnostics(true));
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
  await Promise.all([loadHistory(), loadOutages(), loadDns(false), loadChecks()]);
}

window.sessionReady.then(() => {
  renderTrace(null);
  renderTcp(null);
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
