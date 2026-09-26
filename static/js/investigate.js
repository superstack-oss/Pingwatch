const root = document.querySelector(".detail");
const id = root.dataset.deviceId;
let current = null;
let diagInFlight = false;

function intervalSeconds() {
  return Number(window.PINGWATCH_INTERVAL || 30);
}

function hopRtt(hop) {
  const match = String(hop.raw || "").match(/([\d.]+)\s*ms/i);
  return match ? `${match[1]}ms` : "";
}

function severity(device) {
  if (device.display_status === "offline" || device.status === "down") return { label: "Critical", cls: "crit" };
  if (device.display_status === "warning") return { label: "Warn", cls: "warn" };
  if (device.display_status === "paused") return { label: "Paused", cls: "info" };
  return { label: "Info", cls: "info" };
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
  document.title = `${t("device.investigate")} · ${device.name} · Pingwatch`;
  document.querySelector("#device-dot").className = `live-dot ${device.display_status}`;
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

async function loadDevice() {
  const device = await api(`/api/devices/${id}`);
  current = device;
  renderHero(device);
  if (!diagInFlight) renderDiagnostics(device);
}

async function loadOutages() {
  const host = document.querySelector("#outages");
  const payload = await api(`/api/devices/${id}/outages?range=30d`);
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
  host.innerHTML = `<p class="muted">${t("device.dns_checking")}</p>`;
  try {
    const dns = await api(`/api/devices/${id}/dns${refresh ? "?refresh=true" : ""}`);
    if (!dns.ok) {
      host.innerHTML = `<p class="empty">DNS error: ${escapeHtml(dns.error || "lookup failed")}</p>`;
      return;
    }
    const addrs = (dns.ipv4 && dns.ipv4.length ? dns.ipv4 : dns.addresses) || [];
    host.innerHTML = `
      <p>Name: <span class="mono">${escapeHtml(dns.host)}</span></p>
      ${
        addrs.length
          ? addrs.map((address) => `<p>Address: <span class="mono">${escapeHtml(address)}</span></p>`).join("")
          : `<p class="empty">No A records</p>`
      }
      ${dns.reverse && dns.reverse.length ? `<p>Reverse: <span class="mono">${escapeHtml(dns.reverse.join(", "))}</span></p>` : ""}
      <p class="muted">${dns.elapsed_ms} ms · ${relTime(dns.checked_at)}</p>`;
  } catch (error) {
    host.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function renderTcp(tcp) {
  const host = document.querySelector("#tcp-ports");
  if (!tcp || !tcp.length) {
    host.innerHTML = emptyState({
      title: t("device.ports_pending_title"),
      body: t("device.ports_pending_body"),
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
      title: t("device.path_pending_title"),
      body: t("device.path_pending_body"),
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

async function runDiagnostics() {
  if (diagInFlight) return;
  diagInFlight = true;
  const button = document.querySelector("#run-diag");
  const label = button && button.querySelector("span");
  const tcpHost = document.querySelector("#tcp-ports");
  const traceHost = document.querySelector("#traceroute");
  const cause = document.querySelector("#diag-cause");
  if (button) {
    button.disabled = true;
    button.classList.add("is-busy");
  }
  if (label) label.textContent = t("device.investigating");
  if (tcpHost) tcpHost.innerHTML = `<p class="muted">${t("device.diag_tcp")}</p>`;
  if (traceHost) traceHost.innerHTML = `<p class="muted">${t("device.diag_trace")}</p>`;
  if (cause) cause.innerHTML = `<strong>${t("device.diag_running")}</strong>`;
  try {
    const result = await api(`/api/devices/${id}/diagnostics?traceroute=true`);
    renderTcp(result.tcp);
    renderTrace(result.traceroute);
    if (current) {
      if (result.insight) renderDiagnostics({ ...current, insight: result.insight }, result.insight);
      else if (result.ping && !result.ping.is_up) {
        renderDiagnostics({ ...current, status: "down", display_status: "offline", last_error: result.ping.error });
      }
    }
  } catch (error) {
    if (traceHost) traceHost.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    if (cause) cause.textContent = error.message;
  } finally {
    diagInFlight = false;
    if (button) {
      button.disabled = false;
      button.classList.remove("is-busy");
    }
    if (label) label.textContent = t("device.run_again");
  }
}

document.querySelector("#run-diag").addEventListener("click", () => {
  runDiagnostics().catch(() => {});
});
document.querySelector("#run-trace").addEventListener("click", () => {
  runDiagnostics().catch(() => {});
});
document.querySelector("#refresh-dns").addEventListener("click", () => loadDns(true));

window.sessionReady.then(() => {
  renderTrace(null);
  renderTcp(null);
  loadDevice()
    .then(() => Promise.all([loadDns(false), loadOutages(), runDiagnostics()]))
    .catch((error) => {
      document.querySelector("#device-name").textContent = "Unable to load device";
      const box = document.querySelector("#device-error");
      box.hidden = false;
      box.textContent = error.message;
    });
});
window.addEventListener("pingwatch:refresh", () => {
  loadDevice().catch(() => {});
  loadDns(true).catch(() => {});
  loadOutages().catch(() => {});
});
