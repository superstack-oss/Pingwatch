const KIND_ORDER = ["storage", "san", "network", "nas", "server", "other"];

function donut(percent) {
  const value = Math.max(0, Math.min(100, Number(percent) || 0));
  const r = 42;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  return `<svg viewBox="0 0 120 120" class="donut-svg" aria-hidden="true">
    <circle cx="60" cy="60" r="${r}" fill="none" stroke="currentColor" stroke-width="12" opacity="0.12"></circle>
    <circle cx="60" cy="60" r="${r}" fill="none" stroke="${value >= 99 ? "#16a34a" : value >= 80 ? "#16a34a" : "#d97706"}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${c.toFixed(1)}" stroke-dashoffset="${offset.toFixed(1)}" transform="rotate(-90 60 60)"></circle>
    <text class="pct" x="60" y="58" text-anchor="middle">${Math.round(value)}%</text>
    <text class="sub" x="60" y="74" text-anchor="middle">healthy</text>
  </svg>`;
}

function areaChart(points) {
  const usable = points.filter((item) => item.avg_rtt_ms != null);
    if (!usable.length) return emptyState({ title: "Not enough samples yet", body: "This trend uses real probe averages from the last 24 hours.", compact: true });
  const width = 920;
  const height = 280;
  const pad = { l: 48, r: 16, t: 16, b: 36 };
  const max = Math.max(...usable.map((item) => item.avg_rtt_ms), 1);
  const niceMax = Math.ceil(max / 20) * 20 || 20;
  const coords = usable.map((item, index) => {
    const x = pad.l + (index / Math.max(usable.length - 1, 1)) * (width - pad.l - pad.r);
    const y = height - pad.b - (item.avg_rtt_ms / niceMax) * (height - pad.t - pad.b);
    return [x, y];
  });
  const line = coords.map((pair) => `${pair[0].toFixed(1)},${pair[1].toFixed(1)}`).join(" ");
  const area = `${pad.l},${height - pad.b} ${line} ${coords[coords.length - 1][0].toFixed(1)},${height - pad.b}`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((frac) => {
    const y = height - pad.b - frac * (height - pad.t - pad.b);
    const label = Math.round(niceMax * frac);
    return `<line x1="${pad.l}" y1="${y}" x2="${width - pad.r}" y2="${y}" class="axis"></line>
      <text x="${pad.l - 8}" y="${y + 4}" text-anchor="end" font-size="11" fill="currentColor" opacity="0.55">${label}ms</text>`;
  });
  const labels = usable.filter((_, index) => index % 2 === 0 || index === usable.length - 1).map((item, _, all) => {
    const index = usable.indexOf(item);
    const x = pad.l + (index / Math.max(usable.length - 1, 1)) * (width - pad.l - pad.r);
    const parsed = parseDate(item.hour);
    const label = parsed
      ? parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: window.PINGWATCH_TZ })
      : "";
    return `<text x="${x}" y="${height - 10}" text-anchor="middle" font-size="11" fill="currentColor" opacity="0.55">${label}</text>`;
  });
  return `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Average response time trend">
    <defs>
      <linearGradient id="rttFill" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#16a34a" stop-opacity="0.28"></stop>
        <stop offset="100%" stop-color="#16a34a" stop-opacity="0.02"></stop>
      </linearGradient>
    </defs>
    ${ticks.join("")}
    <polygon class="area" points="${area}"></polygon>
    <polyline class="line" points="${line}"></polyline>
    ${labels.join("")}
  </svg>`;
}

async function renderAnalytics() {
  const data = await api("/api/analytics");
  const healthy = data.status.up - (data.status.warning || 0);
  document.querySelector("#summary-pills").innerHTML = `
    <span>Last refreshed ${relTime(new Date().toISOString())}</span>
    <span>${healthy} healthy services</span>
    <span>${data.status.down + (data.status.warning || 0)} active issues</span>`;
  document.querySelector("#overview-kpis").innerHTML = `
    <article>
      <span class="label">Monitored estate</span>
      <strong>${data.total}</strong>
      <p>${data.total} live monitored items</p>
    </article>
    <article>
      <span class="label">Global uptime</span>
      <strong class="up">${data.availability_24h == null ? "—" : `${Number(data.availability_24h).toFixed(1)}%`}</strong>
      <p>Blended availability over 24 hours</p>
    </article>
    <article>
      <span class="label">Active risks</span>
      <strong class="down">${data.status.down + (data.status.warning || 0)}</strong>
      <p>${data.open_incidents} open incidents</p>
    </article>
    <article>
      <span class="label">Avg response time</span>
      <strong>${ms(data.avg_rtt_ms)}</strong>
      <p>Across successful checks</p>
    </article>`;
  if (!data.total) {
    document.querySelector("#kind-grid").innerHTML = emptyState({
      title: t("dash.no_devices"),
      body: t("dash.no_devices_body"),
    });
    document.querySelector("#hourly").innerHTML = emptyState({
      title: "No response-time data yet",
      body: "Average latency is charted from real probe checks after the first sweep.",
      compact: true,
    });
    document.querySelector("#health-map").innerHTML = emptyState({
      title: "No CIs to map",
      body: "Each square is a monitored configuration item.",
      compact: true,
    });
    document.querySelector("#attention").innerHTML = emptyState({
      title: "Nothing needs attention",
      body: "Down or slow CIs will appear here from live probe results.",
      compact: true,
    });
    return;
  }
  const extraKinds = (data.kind_cards || [])
    .map((item) => item.kind)
    .filter((kind) => kind && !KIND_ORDER.includes(kind));
  const cards = KIND_ORDER.concat(extraKinds)
    .map((kind) => {
      const row = (data.kind_cards || []).find((item) => item.kind === kind);
      if (!row || !row.total) return "";
      const pctHealthy = Math.round((row.healthy / row.total) * 100);
      return `<article class="kind-card">
      <header>
        <h3>${kindLabel(kind)}</h3>
        <span class="count">${row.total}</span>
      </header>
      <p class="blurb">${row.total} ${kindLabel(kind).toLowerCase()} ${row.total === 1 ? "target" : "targets"}</p>
      <div class="donut">${donut(pctHealthy)}</div>
      <div class="kind-meta">
        <span>Healthy <b>${row.healthy}</b></span>
        <span>Attention <b>${row.attention}</b></span>
        <span>Unknown <b>${row.unknown}</b></span>
      </div>
    </article>`;
  })
    .filter(Boolean);
  document.querySelector("#kind-grid").innerHTML = cards.length
    ? cards.join("")
    : emptyState({
        title: t("dash.no_devices"),
        body: t("dash.no_devices_body"),
        compact: true,
      });
  document.querySelector("#hourly").innerHTML = areaChart(data.hourly || []);
  const map = document.querySelector("#health-map");
  if (!(data.health_map || []).length) {
    map.innerHTML = emptyState({ title: "No CIs to map", body: "Each square is a monitored configuration item.", compact: true });
  } else {
    map.innerHTML = data.health_map
      .map(
        (item) =>
          `<a class="health-sq ${item.status}" href="/devices/${item.id}" title="${item.name} · ${item.status}"></a>`
      )
      .join("");
  }
  const attention = document.querySelector("#attention");
  if (!(data.attention || []).length) {
    attention.innerHTML = emptyState({
      title: "Nothing needs attention",
      body: "Down or slow CIs will appear here from live probe results.",
      compact: true,
    });
  } else {
    attention.innerHTML = `<table class="attention-table">
      <thead><tr><th>Service</th><th>When</th><th>Reason</th></tr></thead>
      <tbody>${data.attention
        .map(
          (item) => `<tr>
            <td><a href="/devices/${item.id}">${escapeHtml(item.name)}</a><small class="muted"> ${escapeHtml(kindLabel(item.kind))}</small></td>
            <td>${relTime(item.last_checked_at)}</td>
            <td>${escapeHtml(item.reason || (item.status === "offline" ? "Unreachable" : ms(item.rtt_ms)))}</td>
          </tr>`
        )
        .join("")}</tbody></table>`;
  }
}

window.sessionReady.then(renderAnalytics);
window.addEventListener("pingwatch:refresh", () => renderAnalytics().catch(() => {}));
setInterval(() => renderAnalytics().catch(() => {}), 15000);
