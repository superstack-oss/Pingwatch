const rows = document.querySelector("#rows");
const state = document.querySelector("#table-state");
const hint = document.querySelector("#hint");
const pager = document.querySelector("#pager");
const pageLabel = document.querySelector("#page-label");
const modal = document.querySelector("#modal");
const form = document.querySelector("#add-form");
const formError = document.querySelector("#form-error");

const UPTIME_PAGE_SIZE = 25;
const query = {
  q: "",
  status: "",
  kind: "",
  monitor_type: "",
  sort: "name",
  order: "asc",
  page: 1,
  page_size: UPTIME_PAGE_SIZE,
};

let timer = null;

function spark(history) {
  const values = (history || []).filter((item) => item != null);
  const max = Math.max(...values, 1);
  const bars = (history || [])
    .map((item) => {
      const height = item == null ? 3 : Math.max(4, Math.round((item / max) * 18));
      const cls = item == null ? "miss" : "ok";
      return `<i class="bar ${cls}" style="height:${height}px"></i>`;
    })
    .join("");
  return `<span class="spark">${bars || '<i class="bar miss" style="height:3px"></i>'}</span>`;
}

function skeleton() {
  const cols = currentUser?.role === "admin" ? 7 : 6;
  rows.innerHTML = Array.from({ length: 6 })
    .map(
      () =>
        `<tr class="skeleton-row">${"<td><span class='sk'></span></td>".repeat(cols)}</tr>`
    )
    .join("");
  state.hidden = true;
}

function showState(title, body, retry, action) {
  rows.innerHTML = "";
  document.querySelector(".table-wrap").hidden = true;
  state.hidden = false;
  if (retry) {
    state.innerHTML = emptyState({
      title,
      body,
      actionLabel: t("common.retry"),
      actionId: "retry",
    });
    document.querySelector("#retry")?.addEventListener("click", () => load());
    return;
  }
  const canAdd = action === "add" && currentUser && currentUser.role === "admin";
  state.innerHTML = emptyState({
    title,
    body,
    actionLabel: canAdd ? t("dash.add_first") : "",
    actionId: canAdd ? "empty-add-device" : "",
  });
  document.querySelector("#empty-add-device")?.addEventListener("click", () => {
    document.querySelector("#open-modal")?.click();
  });
}

function params() {
  const search = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== "" && value != null) search.set(key, value);
  });
  return search.toString();
}

async function load() {
  hint.textContent = t("dash.refreshing");
  try {
    const fleet = await api(`/api/devices?${params()}`);
    document.querySelector('[data-kpi="up"]').textContent = fleet.up;
    document.querySelector('[data-kpi="down"]').textContent = fleet.down;
    document.querySelector('[data-kpi="warning"]').textContent = fleet.warning;
    document.querySelector('[data-kpi="unknown"]').textContent = fleet.unknown;
    hint.textContent = fleet.last_sweep_at
      ? t("dash.last_sweep", { time: relTime(fleet.last_sweep_at) })
      : t("dash.waiting_sweep");
    render(fleet);
  } catch (error) {
    showState(t("dash.load_error"), error.message, true);
    setTableBreakdown({});
    hint.textContent = t("dash.connection_error");
  }
}

let deviceIndex = {};

function siteUrl(host) {
  if (!host) return "#";
  if (/^https?:\/\//i.test(host)) return host;
  return `http://${host}`;
}

function rowHtml(device) {
  const status = device.display_status;
  const paused = Boolean(device.service_mode);
  const select = currentUser?.role === "admin" ? checkCell(device.id) : "";
  return `<tr data-id="${device.id}" class="${paused ? "is-paused" : ""}">
        ${select}
        <td class="item-id"><span class="mono">${escapeHtml(device.ci || device.item_id || "")}</span></td>
        <td>
          <a class="entity" href="/devices/${device.id}">${escapeHtml(device.name)}<small>${escapeHtml(
            device.target_display || device.host
          )} · ${escapeHtml(kindLabel(device.kind))}</small></a>
        </td>
        <td><span class="pill ${status}"><i></i>${statusLabel(status)}</span></td>
        <td class="response"><div class="response-inner">${spark(device.history)}<span title="${escapeHtml(
          device.insight
            ? [device.insight.summary, device.insight.where, device.insight.likely_cause].filter(Boolean).join(" ")
            : device.last_error || ""
        )}"><strong>${
          paused
            ? t("dash.paused")
            : device.status === "up"
              ? ms(device.rtt_ms)
              : escapeHtml((device.insight && device.insight.title) || device.last_error || t("dash.timeout"))
        }</strong><small>${clock(device.last_checked_at)}${
          !paused && device.status !== "up" && device.last_error
            ? ` · ${escapeHtml(device.last_error)}`
            : !paused && device.display_status === "warning" && device.insight
              ? ` · ${escapeHtml(device.insight.title)}`
              : ""
        }</small></span></div></td>
        <td class="muted type-cell">${escapeHtml(device.monitor_label || monitorLabel(device.monitor_type))}</td>
        <td class="actions">
          <button type="button" class="row-menu-btn" data-id="${device.id}" aria-haspopup="menu" aria-expanded="false" title="Actions">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
        </td>
      </tr>`;
}

function setTableCount(total, page, pageSize) {
  const node = document.querySelector("#table-count");
  if (!node) return;
  const count = Number(total) || 0;
  if (!count || count <= pageSize) {
    node.textContent = t("dash.items", { count });
    return;
  }
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, count);
  node.textContent = t("dash.showing", { start, end, total: count });
}

const MONITOR_ORDER = ["ping", "tcp", "dns", "websocket", "grpc", "game"];

function monitorCountsFromFleet(fleet) {
  if (fleet.monitor_counts && typeof fleet.monitor_counts === "object") {
    return fleet.monitor_counts;
  }
  const counts = {};
  (fleet.devices || []).forEach((device) => {
    const key = device.monitor_type || "ping";
    counts[key] = (counts[key] || 0) + 1;
  });
  return counts;
}

function setTableBreakdown(fleet) {
  const node = document.querySelector("#table-breakdown");
  if (!node) return;
  const counts = monitorCountsFromFleet(fleet || {});
  const chips = MONITOR_ORDER.filter((key) => counts[key] > 0)
    .concat(Object.keys(counts).filter((key) => !MONITOR_ORDER.includes(key) && counts[key] > 0))
    .map((key) => `<span class="count-chip">${counts[key]} ${escapeHtml(monitorLabel(key))}</span>`);
  node.innerHTML = chips.join("");
  node.hidden = !chips.length;
}

function render(fleet) {
  closeDeviceMenu();
  const total = fleet.filtered_total || 0;
  setTableCount(total, fleet.page || 1, fleet.page_size || UPTIME_PAGE_SIZE);
  setTableBreakdown(fleet);
  if (!total) {
    const empty = query.q || query.status || query.kind || query.monitor_type;
    showState(
      empty ? t("dash.no_matches") : t("dash.no_devices"),
      empty ? t("dash.no_matches_body") : t("dash.no_devices_body"),
      false,
      empty ? "" : "add"
    );
    pager.hidden = true;
    deviceIndex = {};
    syncDeviceSelection();
    return;
  }
  state.hidden = true;
  document.querySelector(".table-wrap").hidden = false;
  document.querySelector(".entity-table").hidden = false;
  deviceIndex = {};
  const selected = new Set(selectedRowIds(deviceTable));
  rows.innerHTML = fleet.devices
    .map((device) => {
      deviceIndex[String(device.id)] = device;
      return rowHtml(device);
    })
    .join("");
  restoreRowChecks(deviceTable, selected);
  const pages = Math.max(1, fleet.pages || 1);
  pager.hidden = pages <= 1;
  pageLabel.textContent = t("dash.page", { page: fleet.page, pages });
  document.querySelector("#prev-page").disabled = fleet.page <= 1;
  document.querySelector("#next-page").disabled = fleet.page >= pages;
  query.page = fleet.page;
  syncDeviceSelection();
}

function replaceRow(device) {
  deviceIndex[String(device.id)] = device;
  const tr = rows.querySelector(`tr[data-id="${device.id}"]`);
  if (!tr) {
    load();
    return;
  }
  const checked = tr.querySelector(".row-check")?.checked;
  tr.outerHTML = rowHtml(device);
  if (checked) {
    const next = rows.querySelector(`tr[data-id="${device.id}"] .row-check`);
    if (next) next.checked = true;
  }
  syncDeviceSelection();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

let searchTimer = null;
document.querySelector("#search").addEventListener("input", (event) => {
  query.q = event.target.value.trim();
  query.page = 1;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(load, 220);
});
document.querySelector("#status-filter").addEventListener("change", (event) => {
  query.status = event.target.value;
  query.page = 1;
  load();
});
document.querySelector("#kind-filter").addEventListener("change", (event) => {
  query.kind = event.target.value;
  query.page = 1;
  load();
});
document.querySelector("#monitor-filter")?.addEventListener("change", (event) => {
  query.monitor_type = event.target.value;
  query.page = 1;
  load();
});
window.addEventListener("pingwatch:refresh", () => load());
window.addEventListener("pingwatch:i18n", () => load());
document.querySelector("#prev-page").addEventListener("click", () => {
  query.page = Math.max(1, query.page - 1);
  load();
});
document.querySelector("#next-page").addEventListener("click", () => {
  query.page += 1;
  load();
});

document.querySelectorAll("th[data-sort]").forEach((header) => {
  header.addEventListener("click", () => {
    const key = header.dataset.sort;
    if (query.sort === key) query.order = query.order === "asc" ? "desc" : "asc";
    else {
      query.sort = key;
      query.order = "asc";
    }
    load();
  });
});

rows.addEventListener("click", (event) => {
  if (event.target.closest(".col-check")) return;
  const menuBtn = event.target.closest(".row-menu-btn");
  if (!menuBtn) return;
  event.stopPropagation();
  if (menuBtn.getAttribute("aria-expanded") === "true") closeDeviceMenu();
  else {
    closeDeviceMenu();
    openDeviceMenu(menuBtn);
  }
});

const deviceMenu = document.querySelector("#device-menu");
let menuDeviceId = null;

function closeDeviceMenu() {
  if (!deviceMenu) return;
  deviceMenu.hidden = true;
  document.querySelectorAll(".row-menu-btn[aria-expanded='true']").forEach((btn) => {
    btn.setAttribute("aria-expanded", "false");
  });
  menuDeviceId = null;
}

function menuIcon(name) {
  const stroke = `viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"`;
  if (name === "open") {
    return `<svg ${stroke}><path d="M14 5h7v7"/><path d="M10 14L21 5"/><rect x="3" y="8" width="11" height="11" rx="2"/></svg>`;
  }
  if (name === "details") {
    return `<svg ${stroke}><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><circle cx="12" cy="8" r="0.8" fill="currentColor" stroke="none"/></svg>`;
  }
  if (name === "refresh") {
    return `<svg ${stroke}><path d="M21 12a9 9 0 1 1-2.6-6.3"/><path d="M21 3v6h-6"/></svg>`;
  }
  if (name === "edit") {
    return `<svg ${stroke}><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>`;
  }
  if (name === "pause") {
    return `<svg ${stroke}><circle cx="12" cy="12" r="9"/><path d="M10 9v6"/><path d="M14 9v6"/></svg>`;
  }
  if (name === "play") {
    return `<svg ${stroke}><circle cx="12" cy="12" r="9"/><path d="M10 8l7 4-7 4z" fill="currentColor" stroke="none"/></svg>`;
  }
  return `<svg ${stroke}><path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="M6 7l1 12h10l1-12"/></svg>`;
}

function openDeviceMenu(button) {
  const id = button.dataset.id;
  const device = deviceIndex[String(id)] || { id, host: "", service_mode: false };
  const paused = Boolean(device.service_mode);
  const admin = currentUser?.role === "admin";
  menuDeviceId = id;
  deviceMenu.innerHTML = `
    <a href="${escapeHtml(siteUrl(device.host))}" target="_blank" rel="noopener" role="menuitem">${menuIcon("open")} ${t("dash.open_site")}</a>
    <a href="/devices/${id}" role="menuitem">${menuIcon("details")} ${t("dash.details")}</a>
    <button type="button" role="menuitem" data-action="refresh">${menuIcon("refresh")} ${t("dash.refresh")}</button>
    ${
      admin
        ? `<button type="button" role="menuitem" data-action="edit">${menuIcon("edit")} ${t("common.edit")}</button>`
        : ""
    }
    <button type="button" role="menuitem" class="menu-service" data-action="service">${paused ? menuIcon("play") : menuIcon("pause")} ${
      paused ? t("dash.resume") : t("dash.service_mode")
    }</button>
    ${
      admin
        ? `<div class="menu-sep"></div>
    <button type="button" role="menuitem" class="danger-text" data-action="delete">${menuIcon("trash")} ${t("dash.delete")}</button>`
        : ""
    }
  `;
  deviceMenu.hidden = false;
  const rect = button.getBoundingClientRect();
  const width = Math.max(deviceMenu.offsetWidth, 210);
  const left = Math.min(Math.max(8, rect.right - width), window.innerWidth - width - 8);
  deviceMenu.style.left = `${left}px`;
  deviceMenu.style.top = `${rect.bottom + 6}px`;
  button.setAttribute("aria-expanded", "true");
}

deviceMenu?.addEventListener("click", async (event) => {
  const actionBtn = event.target.closest("[data-action]");
  if (!actionBtn || !menuDeviceId) return;
  const id = menuDeviceId;
  const action = actionBtn.dataset.action;
  closeDeviceMenu();
  if (action === "refresh") {
    try {
      const device = await api(`/api/devices/${id}/probe`, { method: "POST" });
      replaceRow(device);
    } catch (error) {
      hint.textContent = error.message || "Refresh failed";
    }
    return;
  }
  if (action === "service") {
    const current = deviceIndex[String(id)] || {};
    try {
      const device = await api(`/api/devices/${id}/service-mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !current.service_mode }),
      });
      replaceRow(device);
    } catch (error) {
      hint.textContent = error.message || "Could not update service mode";
    }
    return;
  }
  if (action === "edit") {
    const device = deviceIndex[String(id)];
    if (device) openModal(device);
    return;
  }
  if (action === "delete") {
    if (!confirm(t("dash.confirm_delete"))) return;
    try {
      await api(`/api/devices/${id}`, { method: "DELETE" });
      const tr = rows.querySelector(`tr[data-id="${id}"]`);
      tr?.remove();
      delete deviceIndex[String(id)];
      if (!rows.querySelector("tr")) load();
    } catch (error) {
      hint.textContent = error.message || "Delete failed";
    }
  }
});

document.addEventListener("click", (event) => {
  if (!event.target.closest("#device-menu") && !event.target.closest(".row-menu-btn")) {
    closeDeviceMenu();
  }
});
document.querySelector(".workspace")?.addEventListener("scroll", closeDeviceMenu, { passive: true });
window.addEventListener("resize", closeDeviceMenu);

async function openModal(device) {
  modal.hidden = false;
  formError.hidden = true;
  await bindMonitorForm(form);
  const title = document.querySelector("#modal h2");
  const submit = document.querySelector("#add-submit");
  const bulk = document.querySelector(".add-bulk");
  const idInput = form.querySelector("[name=id]");
  if (device) {
    if (idInput) idInput.value = device.id;
    await fillMonitorForm(form, device);
    if (title) {
      title.setAttribute("data-i18n", "admin.update_device");
      title.textContent = t("admin.update_device");
    }
    if (submit) {
      submit.setAttribute("data-i18n", "common.save");
      submit.textContent = t("common.save");
    }
    if (bulk) bulk.hidden = true;
  } else {
    form.reset();
    if (idInput) idInput.value = "";
    form.querySelector("[name=kind][value=server]").checked = true;
    if (form.monitor_type) form.monitor_type.value = "ping";
    syncMonitorFields(form);
    if (title) {
      title.setAttribute("data-i18n", "dash.add_title");
      title.textContent = t("dash.add_title");
    }
    if (submit) {
      submit.setAttribute("data-i18n", "dash.add_and_ping");
      submit.textContent = t("dash.add_and_ping");
    }
    if (bulk) bulk.hidden = false;
  }
  form.querySelector("[name=name]").focus();
}
function closeModal() {
  modal.hidden = true;
  formError.hidden = true;
}

document.querySelector("#open-modal")?.addEventListener("click", () => openModal());
document.querySelector("#close-modal")?.addEventListener("click", closeModal);
modal.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});
document.querySelector("#csv-upload-btn")?.addEventListener("click", () => {
  document.querySelector("#device-file")?.click();
});
document.querySelector("#device-file")?.addEventListener("change", async (event) => {
  const input = event.target;
  const file = input.files && input.files[0];
  input.value = "";
  if (!file) return;
  formError.hidden = true;
  const body = new FormData();
  body.append("file", file);
  try {
    const result = await api("/api/devices/upload", { method: "POST", body });
    const skipped = result.skipped || 0;
    hint.textContent =
      skipped > 0
        ? t("dash.imported_skipped", { count: result.imported, skipped })
        : t("dash.imported", { count: result.imported });
    if (result.warnings && result.warnings.length) {
      hint.textContent += ` · ${result.warnings[0]}`;
    }
    form.reset();
    form.querySelector("[name=kind][value=server]").checked = true;
    if (form.monitor_type) form.monitor_type.value = "ping";
    syncMonitorFields(form);
    closeModal();
    query.page = 1;
    load();
  } catch (error) {
    formError.textContent = error.message;
    formError.hidden = false;
  }
});
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.hidden = true;
  const data = monitorFieldsPayload(form);
  const id = form.querySelector("[name=id]")?.value;
  try {
    if (id) {
      await api(`/api/devices/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    } else {
      await api("/api/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
    }
    form.reset();
    form.querySelector("[name=kind][value=server]").checked = true;
    if (form.monitor_type) form.monitor_type.value = "ping";
    syncMonitorFields(form);
    closeModal();
    load();
  } catch (error) {
    formError.textContent = error.message;
    formError.hidden = false;
  }
});

const deviceTable = document.querySelector(".entity-table");
const deviceBulk = document.querySelector("#device-bulk");

function deviceBulkActions(ids) {
  return bulkBarHtml(ids.length, [
    { id: "pause", label: t("dash.pause_selected") },
    { id: "resume", label: t("dash.resume_selected") },
    { id: "delete", label: t("dash.delete"), danger: true },
  ]);
}

function syncDeviceSelection() {
  if (currentUser?.role !== "admin") {
    if (deviceBulk) {
      deviceBulk.hidden = true;
      deviceBulk.innerHTML = "";
    }
    return [];
  }
  return syncTableSelection(deviceTable, deviceBulk, deviceBulkActions);
}

async function bulkUpdateDevices(action, ids) {
  if (action === "delete" && !confirm(t("dash.confirm_delete_many", { count: ids.length }))) return;
  const errors = await runOnIds(ids, async (id) => {
    if (action === "delete") {
      await api(`/api/devices/${id}`, { method: "DELETE" });
      return;
    }
    await api(`/api/devices/${id}/service-mode`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: action === "pause" }),
    });
  });
  if (errors.length) hint.textContent = errors[0];
  await load();
}

bindTableSelection(deviceTable, {
  bar: deviceBulk,
  renderActions: deviceBulkActions,
  onAction: bulkUpdateDevices,
});

window.sessionReady.then(() => {
  skeleton();
  bindMonitorForm(form);
  load();
  timer = setInterval(load, 8000);
});
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeModal();
    closeDeviceMenu();
  }
});
