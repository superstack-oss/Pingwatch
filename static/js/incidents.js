const PRIORITY_PILL = {
  P1: "p1",
  P2: "p2",
  P3: "p3",
};

let incidentIndex = {};
let menuIncidentId = null;
let incidentPage = 1;
const incidentMenu = document.querySelector("#incident-menu");
const isArchive = Boolean(document.querySelector(".archive-page"));
const incidentPager = document.querySelector("#incident-pager");
const filterDeviceId = (document.querySelector("#incident-scope")?.dataset.deviceId || "").trim();

function menuIcon(name) {
  const stroke = `viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"`;
  if (name === "ack") {
    return `<svg ${stroke}><path d="M20 6 9 17l-5-5"/></svg>`;
  }
  if (name === "resolve") {
    return `<svg ${stroke}><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>`;
  }
  return `<svg ${stroke}><path d="M4 7h16"/><path d="M9 7V5h6v2"/><path d="M6 7l1 12h10l1-12"/></svg>`;
}

function closeIncidentMenu() {
  if (!incidentMenu) return;
  incidentMenu.hidden = true;
  document.querySelectorAll(".row-menu-btn[aria-expanded='true']").forEach((btn) => {
    btn.setAttribute("aria-expanded", "false");
  });
  menuIncidentId = null;
}

function openIncidentMenu(button) {
  const id = button.dataset.id;
  const item = incidentIndex[String(id)] || { id, actions: {} };
  menuIncidentId = id;
  const rows = [];
  if (item.actions?.delete) {
    rows.push(
      `<button type="button" role="menuitem" class="danger-text" data-action="delete">${menuIcon("trash")} ${t("incidents.delete")}</button>`
    );
  }
  incidentMenu.innerHTML = rows.join("") || `<p class="muted" style="padding:8px 12px;margin:0">${t("incidents.no_actions")}</p>`;
  incidentMenu.hidden = false;
  const rect = button.getBoundingClientRect();
  const width = Math.max(incidentMenu.offsetWidth, 210);
  const left = Math.min(Math.max(8, rect.right - width), window.innerWidth - width - 8);
  incidentMenu.style.left = `${left}px`;
  incidentMenu.style.top = `${rect.bottom + 6}px`;
  button.setAttribute("aria-expanded", "true");
}

function incidentActions(item) {
  return `<button type="button" class="row-menu-btn" data-id="${item.id}" aria-haspopup="menu" aria-expanded="false" title="${t("dash.actions")}">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  </button>`;
}

function listQuery() {
  const params = new URLSearchParams();
  params.set("scope", isArchive ? "archive" : "live");
  params.set("page", String(incidentPage));
  params.set("page_size", String(PAGE_SIZE));
  const status = document.querySelector("#incident-status")?.value;
  if (status) params.set("status", status);
  if (filterDeviceId) params.set("device_id", filterDeviceId);
  return `/api/incidents?${params.toString()}`;
}

async function loadIncidents() {
  closeIncidentMenu();
  const empty = document.querySelector("#incident-empty");
  const rows = document.querySelector("#incident-rows");
  const toolbar = document.querySelector(".toolbar");
  if (!incidentsEnabled()) {
    if (toolbar) toolbar.hidden = true;
    document.querySelector(".table-wrap").hidden = true;
    setPager(incidentPager, 1, 1);
    empty.hidden = false;
    empty.innerHTML = incidentsDisabledState();
    rows.innerHTML = "";
    syncIncidentSelection();
    return;
  }
  if (toolbar) toolbar.hidden = false;
  const data = await api(listQuery());
  const hint = document.querySelector("#incident-hint");
  if (hint) {
    hint.textContent = isArchive
      ? t("incidents.archive_hint", { total: data.total })
      : t("incidents.hint", { open: data.open, total: data.total });
  }
  if (!data.incidents.length) {
    rows.innerHTML = "";
    incidentIndex = {};
    document.querySelector(".table-wrap").hidden = true;
    setPager(incidentPager, 1, 1);
    empty.hidden = false;
    empty.innerHTML = emptyState({
      title: t(isArchive ? "incidents.archive_none" : filterDeviceId ? "incidents.none_device" : "incidents.none"),
      body: t(isArchive ? "incidents.archive_none_body" : filterDeviceId ? "incidents.none_device_body" : "incidents.none_body"),
    });
    syncIncidentSelection();
    return;
  }
  empty.hidden = true;
  document.querySelector(".table-wrap").hidden = false;
  document.querySelector(".incidents-table").hidden = false;
  incidentIndex = {};
  const selected = new Set(selectedRowIds(incidentTable));
  const render = () => {
    rows.innerHTML = data.incidents
      .map((item) => {
        incidentIndex[String(item.id)] = item;
        const priority = item.priority || "P3";
        const short = item.short_description || item.last_error || "—";
        return `<tr data-id="${item.id}">
        ${currentUser?.role === "admin" ? checkCell(item.id) : ""}
        <td class="mono"><a class="incident-link" href="/incidents/${item.id}">${escapeHtml(item.number)}</a></td>
        <td><span class="pill ${PRIORITY_PILL[priority] || "p3"}"><i></i>${escapeHtml(priority)}</span></td>
        <td class="issue-cell" title="${escapeHtml(short)}">${escapeHtml(short)}</td>
        <td><span class="pill ${INCIDENT_STATUS_PILL[item.status] || ""}"><i></i>${escapeHtml(incidentStatusLabel(item.status))}</span></td>
        <td>${formatStamp(item.created_at)}</td>
        <td class="actions">${incidentActions(item)}</td>
      </tr>`;
      })
      .join("");
    incidentPage = data.page || 1;
    setPager(incidentPager, incidentPage, data.pages || 1);
    restoreRowChecks(incidentTable, selected);
    syncIncidentSelection();
  };
  if (typeof runViewTransition === "function") runViewTransition(render);
  else render();
}

async function updateIncident(id, action, status) {
  const error = document.querySelector("#incident-error");
  error.hidden = true;
  if (action === "delete" && currentUser?.role !== "admin") return;
  if (action === "delete") {
    const ok = await confirmAction({
      title: t("incidents.confirm_delete"),
      body: t("common.confirm_delete_body"),
      danger: true,
      confirmLabel: t("dash.delete"),
    });
    if (!ok) return;
  }
  const payload = { action };
  if (status) payload.status = status;
  try {
    await api(`/api/incidents/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadIncidents();
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
    await loadIncidents();
  }
}

document.querySelector("#incident-status")?.addEventListener("change", () => {
  incidentPage = 1;
  loadIncidents();
});
document.querySelector("#incident-rows").addEventListener("click", (event) => {
  if (event.target.closest(".col-check")) return;
  const menuBtn = event.target.closest(".row-menu-btn");
  if (!menuBtn) return;
  event.stopPropagation();
  if (menuBtn.getAttribute("aria-expanded") === "true") closeIncidentMenu();
  else {
    closeIncidentMenu();
    openIncidentMenu(menuBtn);
  }
});
incidentMenu?.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button || !menuIncidentId) return;
  const id = menuIncidentId;
  const action = button.dataset.action;
  closeIncidentMenu();
  updateIncident(id, action);
});
document.addEventListener("click", (event) => {
  if (event.target.closest(".row-dropdown, .row-menu-btn")) return;
  closeIncidentMenu();
});
window.addEventListener("resize", closeIncidentMenu);
window.addEventListener("scroll", closeIncidentMenu, true);
bindPager(incidentPager, {
  prev: () => {
    incidentPage = Math.max(1, incidentPage - 1);
    loadIncidents();
  },
  next: () => {
    incidentPage += 1;
    loadIncidents();
  },
});

const incidentTable = document.querySelector(".incidents-table");
const incidentBulk = document.querySelector("#incident-bulk");

function incidentBulkActions(ids) {
  if (currentUser?.role !== "admin") return "";
  return bulkBarHtml(ids.length, [{ id: "delete", label: t("incidents.delete"), danger: true }]);
}

function syncIncidentSelection() {
  syncTableSelection(incidentTable, incidentBulk, incidentBulkActions);
}

async function bulkUpdateIncidents(action, ids) {
  const error = document.querySelector("#incident-error");
  if (error) error.hidden = true;
  if (action === "delete" && currentUser?.role !== "admin") return;
  if (action === "delete") {
    const ok = await confirmAction({
      title: t("incidents.confirm_delete_many", { count: ids.length }),
      body: t("common.confirm_delete_body"),
      danger: true,
      confirmLabel: t("dash.delete"),
    });
    if (!ok) return;
  }
  const errors = await runOnIds(ids, (id) =>
    api(`/api/incidents/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    })
  );
  if (errors.length && error) {
    error.textContent = errors[0];
    error.hidden = false;
  }
  await loadIncidents();
}

bindTableSelection(incidentTable, {
  bar: incidentBulk,
  renderActions: incidentBulkActions,
  onAction: bulkUpdateIncidents,
});

window.sessionReady.then(loadIncidents);
window.addEventListener("pingwatch:refresh", loadIncidents);
window.addEventListener("pingwatch:i18n", loadIncidents);
setInterval(loadIncidents, 15000);
