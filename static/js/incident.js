const PRIORITY_PILL = {
  P1: "p1",
  P2: "p2",
  P3: "p3",
};

const host = document.querySelector("#incident-detail");
const incidentId = host?.dataset.incidentId;
let current = null;
let currentTab = "notes";

function snField(label, value, extra = "") {
  return `<label class="sn-field"><span>${escapeHtml(label)}</span><input value="${escapeHtml(value ?? "—")}" readonly ${extra} /></label>`;
}

function fileSize(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function activityAuthor(item) {
  const role = item.role === "admin" ? "admin" : item.role === "user" ? "user" : "system";
  const name = (item.username || item.actor || "system").trim() || "system";
  const roleLabel = t(`incidents.actor_${role}`);
  if (role === "system") {
    return `<span class="inc-act-who"><strong>${escapeHtml(roleLabel)}</strong></span>`;
  }
  return `<span class="inc-act-who"><strong>${escapeHtml(name)}</strong><span class="inc-act-role">${escapeHtml(roleLabel)}</span></span>`;
}

function renderActivities(items) {
  if (!items || !items.length) {
    return `<p class="muted">${t("incidents.no_notes")}</p>`;
  }
  return `<ol class="inc-activity">${items
    .map((item) => {
      const kind = item.work_note === false ? t("incidents.comments") : t("incidents.work_notes");
      return `<li>
        <div class="inc-act-head">
          ${activityAuthor(item)}
          <span class="inc-act-meta">${escapeHtml(kind)} · ${formatStamp(item.created_at)}</span>
        </div>
        <p>${escapeHtml(item.body)}</p>
      </li>`;
    })
    .join("")}</ol>`;
}

function renderAttachments(items) {
  if (!items || !items.length) {
    return `<p class="muted">${t("incidents.no_attachments")}</p>`;
  }
  return `<div class="attach-grid">${items
    .map((item) => {
      const preview =
        item.kind === "image"
          ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener"><img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.filename)}" /></a>`
          : `<a class="attach-file-link" href="${escapeHtml(item.url)}">${escapeHtml(item.filename)}</a>`;
      return `<article class="attach-card">
        ${preview}
        <p class="attach-name" title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</p>
        <p class="muted">${fileSize(item.size_bytes)} · ${escapeHtml(item.actor || "system")}</p>
        <button type="button" class="ghost attach-remove" data-id="${item.id}">${t("incidents.remove_file")}</button>
      </article>`;
    })
    .join("")}</div>`;
}

function renderIncident(item, draft = "") {
  const priority = item.priority || "P3";
  const statusLabel = t("incidents." + item.status) || item.status;
  const archived = ARCHIVE_INCIDENT_STATUSES.includes(item.status);
  document.querySelector("#inc-heading").textContent = item.number || t("incidents.number");
  document.querySelector("#inc-crumb").textContent = item.number || "—";
  document.title = `${item.number || "Incident"} · Pingwatch`;
  const home = document.querySelector("#inc-crumb-home");
  if (home) {
    home.href = archived ? "/archives" : "/incidents";
    home.textContent = archived ? t("nav.archives") : t("nav.incidents");
    home.dataset.i18n = archived ? "nav.archives" : "nav.incidents";
  }
  host.innerHTML = `
    <header class="incident-form-head">
      <div>
        <h2 class="mono">${escapeHtml(item.number)}</h2>
        <p class="device-meta">
          <span class="pill ${INCIDENT_STATUS_PILL[item.status] || ""}"><i></i>${escapeHtml(statusLabel)}</span>
          <span class="pill ${PRIORITY_PILL[priority] || "p3"}"><i></i>${escapeHtml(priority)}</span>
          <span>${escapeHtml(item.device_name)}</span>
          <span class="meta-sep">·</span>
          <span class="mono">${escapeHtml(item.host)}</span>
        </p>
      </div>
    </header>
    <div class="sn-grid">
      ${snField(t("incidents.number"), item.number, `class="mono"`)}
      <label class="sn-field"><span>${t("dash.status")}</span>
        <select id="inc-status">${incidentStatusOptions(item.status)}</select>
      </label>
      ${snField(t("dash.item_id"), item.ci, `class="mono"`)}
      ${snField(t("incidents.priority"), priority)}
      ${snField(t("incidents.device"), item.device_name)}
      ${snField(t("admin.host_col"), item.host, `class="mono"`)}
      ${snField(t("incidents.channel"), item.channel || "Pingwatch")}
      ${snField(t("incidents.failures"), item.failure_count == null ? "—" : String(item.failure_count))}
      ${snField(t("incidents.created"), formatStamp(item.created_at))}
      ${snField(t("incidents.resolved_at"), item.resolved_at ? formatStamp(item.resolved_at) : "—")}
      ${snField(t("incidents.duration"), duration(item.duration_seconds))}
      ${snField(t("incidents.error"), item.last_error || "—")}
    </div>
    <label class="sn-wide">
      <span>${t("incidents.short_description")}</span>
      <input value="${escapeHtml(item.short_description || item.last_error || "—")}" readonly />
    </label>
    <label class="sn-wide">
      <span>${t("incidents.description")}</span>
      <textarea readonly rows="6">${escapeHtml(item.description || "")}</textarea>
    </label>
    <section class="inc-notes">
      <nav class="inc-tabs" aria-label="${t("incidents.notes")}">
        <button type="button" class="head-tab${currentTab === "notes" ? " active" : ""}" data-tab="notes">${t("incidents.notes")}</button>
        <button type="button" class="head-tab${currentTab === "attachments" ? " active" : ""}" data-tab="attachments">${t("incidents.attachments")}</button>
      </nav>
      <div class="inc-tab-panel" data-panel="notes"${currentTab === "notes" ? "" : " hidden"}>
        <p class="muted">${t("incidents.notes_hint")}</p>
        <label class="sn-wide">
          <span>${t("incidents.work_notes")}</span>
          <textarea id="inc-note-body" rows="4" maxlength="4000" placeholder="${t("incidents.note_placeholder")}">${escapeHtml(draft)}</textarea>
        </label>
        <div class="inc-note-actions">
          <label class="check"><input type="checkbox" id="inc-work-note" checked /> ${t("incidents.work_notes")}</label>
          <button type="button" class="primary" id="inc-post-note">${t("incidents.post")}</button>
        </div>
        <p class="form-error" id="inc-note-error" hidden></p>
        <p class="ok" id="inc-note-ok" hidden>${t("incidents.note_posted")}</p>
        <h3>${t("incidents.activities")}</h3>
        ${renderActivities(item.activities)}
      </div>
      <div class="inc-tab-panel" data-panel="attachments"${currentTab === "attachments" ? "" : " hidden"}>
        <p class="muted">${t("incidents.attach_help")}</p>
        <label class="file-btn ghost">
          <span>${t("incidents.add_files")}</span>
          <input id="inc-attach-input" type="file" multiple accept="image/*,.pdf,.txt,.csv,.log,.zip,.json,.xml,.doc,.docx,.xls,.xlsx,.pptx,.pcap,.cap" />
        </label>
        <p class="form-error" id="inc-attach-error" hidden></p>
        <p class="ok" id="inc-attach-ok" hidden>${t("incidents.attach_ok")}</p>
        ${renderAttachments(item.attachments)}
      </div>
    </section>`;
}

function draftValue() {
  return document.querySelector("#inc-note-body")?.value || "";
}

function showTab(name) {
  currentTab = name === "attachments" ? "attachments" : "notes";
  host.querySelectorAll(".inc-tabs .head-tab").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === currentTab);
  });
  host.querySelectorAll(".inc-tab-panel").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== currentTab;
  });
}

async function loadIncident() {
  if (!incidentId) return;
  if (!incidentsEnabled()) {
    document.querySelector(".crumb")?.setAttribute("hidden", "");
    if (host) host.innerHTML = incidentsDisabledState();
    return;
  }
  const error = document.querySelector("#incident-error");
  if (error) error.hidden = true;
  const draft = draftValue();
  try {
    const data = await api(`/api/incidents/${incidentId}`);
    current = data.incident;
    renderIncident(current, draft);
  } catch (err) {
    host.innerHTML = `<p class="form-error">${escapeHtml(err.message)}</p>`;
  }
}

async function postIncidentNote(silent = false) {
  const body = document.querySelector("#inc-note-body");
  const error = document.querySelector("#inc-note-error");
  const ok = document.querySelector("#inc-note-ok");
  const work = document.querySelector("#inc-work-note");
  if (error) error.hidden = true;
  if (ok) ok.hidden = true;
  const text = (body?.value || "").trim();
  if (!text) {
    if (!silent && error) {
      error.textContent = t("incidents.note_required");
      error.hidden = false;
    }
    return false;
  }
  try {
    await api(`/api/incidents/${incidentId}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: text, work_note: Boolean(work?.checked) }),
    });
    if (body) body.value = "";
    await loadIncident();
    const done = document.querySelector("#inc-note-ok");
    if (done) done.hidden = false;
    return true;
  } catch (err) {
    if (error) {
      error.textContent = err.message;
      error.hidden = false;
    }
    return false;
  }
}

async function uploadAttachments(fileList) {
  const error = document.querySelector("#inc-attach-error");
  const ok = document.querySelector("#inc-attach-ok");
  if (error) error.hidden = true;
  if (ok) ok.hidden = true;
  const files = [...(fileList || [])];
  if (!files.length) return;
  const data = new FormData();
  files.forEach((file) => data.append("files", file));
  try {
    await api(`/api/incidents/${incidentId}/attachments`, { method: "POST", body: data });
    currentTab = "attachments";
    await loadIncident();
    const done = document.querySelector("#inc-attach-ok");
    if (done) done.hidden = false;
  } catch (err) {
    if (error) {
      error.textContent = err.message;
      error.hidden = false;
    }
  }
}

async function removeAttachment(id) {
  const ok = await confirmAction({
    title: t("incidents.confirm_remove_file"),
    body: t("common.confirm_delete_body"),
    danger: true,
    confirmLabel: t("common.remove"),
  });
  if (!ok) return;
  const error = document.querySelector("#inc-attach-error");
  if (error) error.hidden = true;
  try {
    await api(`/api/incidents/${incidentId}/attachments/${id}`, { method: "DELETE" });
    currentTab = "attachments";
    await loadIncident();
  } catch (err) {
    if (error) {
      error.textContent = err.message;
      error.hidden = false;
    }
  }
}

async function updateIncident(action, status) {
  const error = document.querySelector("#incident-error");
  if (error) error.hidden = true;
  const payload = { action };
  if (status) payload.status = status;
  try {
    await api(`/api/incidents/${incidentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    await loadIncident();
  } catch (err) {
    if (error) {
      error.textContent = err.message;
      error.hidden = false;
    }
    await loadIncident();
  }
}

host?.addEventListener("click", (event) => {
  const tab = event.target.closest(".inc-tabs .head-tab");
  if (tab) {
    showTab(tab.dataset.tab);
    return;
  }
  if (event.target.closest("#inc-post-note")) {
    postIncidentNote();
    return;
  }
  const remove = event.target.closest(".attach-remove");
  if (remove) removeAttachment(remove.dataset.id);
});
host?.addEventListener("change", (event) => {
  if (event.target.id === "inc-status") {
    updateIncident("set_status", event.target.value);
    return;
  }
  const input = event.target.closest("#inc-attach-input");
  if (!input) return;
  uploadAttachments(input.files);
  input.value = "";
});
window.sessionReady.then(loadIncident);
window.addEventListener("pingwatch:refresh", loadIncident);
window.addEventListener("pingwatch:i18n", loadIncident);
