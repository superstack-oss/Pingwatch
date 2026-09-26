function showTab(id) {
  const apply = () => {
    document.querySelectorAll(".admin-tabs button").forEach((btn) => btn.classList.toggle("active", btn.dataset.tab === id));
    document.querySelectorAll(".admin-panel").forEach((panel) => {
      panel.hidden = panel.dataset.panel !== id;
    });
    const addBtn = document.querySelector("#admin-add");
    if (addBtn) addBtn.hidden = id !== "devices";
    const heading = document.querySelector(".workspace-heading h1");
    const lede = document.querySelector(".workspace-heading .lede");
    if (heading && lede) {
      const titles = {
        settings: ["page.settings", "page.settings_lede"],
        announcements: ["page.announcements", "page.announcements_lede"],
      };
      const titleKey = titles[id]?.[0] || "page.admin";
      const ledeKey = titles[id]?.[1] || "page.admin_lede";
      heading.setAttribute("data-i18n", titleKey);
      lede.setAttribute("data-i18n", ledeKey);
      heading.textContent = t(titleKey);
      lede.textContent = t(ledeKey);
      if (id === "settings" && typeof syncAppearance === "function") syncAppearance();
    }
    if (location.hash !== `#${id}`) history.replaceState(null, "", `#${id}`);
  };
  if (typeof runViewTransition === "function") runViewTransition(apply);
  else apply();
}

document.querySelector(".admin-tabs").addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-tab]");
  if (btn) showTab(btn.dataset.tab);
});

function fillTable(tbodyId, html, emptyId, emptyOpts) {
  const body = document.querySelector(tbodyId);
  const wrap = body.closest(".table-wrap");
  const empty = emptyId ? document.querySelector(emptyId) : null;
  const pager = wrap?.nextElementSibling?.classList.contains("pager") ? wrap.nextElementSibling : null;
  if (!html) {
    body.innerHTML = "";
    if (wrap) wrap.hidden = true;
    if (pager) pager.hidden = true;
    if (empty) {
      empty.hidden = false;
      empty.innerHTML = emptyState(emptyOpts || {});
    }
    return;
  }
  if (wrap) wrap.hidden = false;
  if (empty) empty.hidden = true;
  body.innerHTML = html;
}

function adminDeviceBulkActions(ids) {
  return bulkBarHtml(ids.length, [
    { id: "pause", label: t("dash.pause_selected") },
    { id: "resume", label: t("dash.resume_selected") },
    { id: "delete", label: t("dash.delete"), danger: true },
  ]);
}

function adminUserBulkActions(ids) {
  return bulkBarHtml(ids.length, [
    { id: "enable", label: t("admin.enable") },
    { id: "disable", label: t("admin.disable") },
  ]);
}

function adminAnnounceBulkActions(ids) {
  return bulkBarHtml(ids.length, [{ id: "delete", label: t("common.remove"), danger: true }]);
}

function adminRequestBulkActions(ids) {
  return bulkBarHtml(ids.length, [
    { id: "approved", label: t("admin.allow") },
    { id: "rejected", label: t("admin.reject") },
  ]);
}

const adminPages = { devices: 1, requests: 1, users: 1, audit: 1, announcements: 1 };

function loadDevices() {
  const table = document.querySelector("#admin-devices-table");
  const selected = new Set(selectedRowIds(table));
  return api(`/api/devices?page=${adminPages.devices}&page_size=${PAGE_SIZE}`).then((fleet) => {
    if (!fleet.devices.length) {
      fillTable("#admin-devices", "", "#admin-devices-empty", {
        title: t("dash.no_devices"),
        body: t("dash.no_devices_body"),
        actionLabel: t("dash.add_first"),
        actionId: "admin-empty-add",
      });
      document.querySelector("#admin-empty-add")?.addEventListener("click", () => {
        document.querySelector("#admin-add")?.click();
      });
      syncTableSelection(table, document.querySelector("#admin-devices-bulk"), adminDeviceBulkActions);
      return;
    }
    fillTable(
      "#admin-devices",
      fleet.devices
        .map(
          (device) => `<tr data-id="${device.id}">
        ${checkCell(device.id)}
        <td class="mono">${escapeHtml(device.ci || device.item_id || "")}</td>
        <td>${escapeHtml(device.name)}</td><td class="mono">${escapeHtml(device.host)}</td>
        <td>${escapeHtml(device.monitor_label || monitorLabel(device.monitor_type))}</td>
        <td>${kindLabel(device.kind)}</td>
        <td>${statusLabel(device.status)}</td>
        <td>
          <button class="ghost" data-edit="${encodeURIComponent(JSON.stringify(device))}">${t("common.edit")}</button>
          <button class="danger" data-del="${device.id}">${t("common.remove")}</button>
        </td></tr>`
        )
        .join(""),
      "#admin-devices-empty"
    );
    restoreRowChecks(table, selected);
    adminPages.devices = fleet.page || 1;
    setPager(document.querySelector("#admin-devices-pager"), adminPages.devices, fleet.pages || 1);
    syncTableSelection(table, document.querySelector("#admin-devices-bulk"), adminDeviceBulkActions);
  });
}

async function loadUsers() {
  const userTable = document.querySelector("#admin-users-table");
  const requestTable = document.querySelector("#admin-requests-table");
  const selectedUsers = new Set(selectedRowIds(userTable));
  const selectedRequests = new Set(selectedRowIds(requestTable));
  const users = await api(`/api/admin/users?page=${adminPages.users}&page_size=${PAGE_SIZE}`);
  fillTable(
    "#admin-users",
    (users.users || [])
      .map(
        (user) => `<tr data-id="${user.id}" data-role="${escapeHtml(user.role)}" data-status="${escapeHtml(user.status)}">
        ${user.role === "admin" ? `<td class="col-check"></td>` : checkCell(user.id)}
        <td>${escapeHtml(user.name)}</td><td>${escapeHtml(user.username)}</td><td>${escapeHtml(user.email)}</td>
        <td>${escapeHtml(user.role)}</td><td>${escapeHtml(user.status)}</td>
        <td>${user.role === "admin" ? "" : `<button class="ghost" data-user="${user.id}" data-status="${user.status === "active" ? "disabled" : "active"}">${user.status === "active" ? t("admin.disable") : t("admin.enable")}</button>`}</td>
      </tr>`
      )
      .join("")
  );
  restoreRowChecks(userTable, selectedUsers);
  adminPages.users = users.page || 1;
  setPager(document.querySelector("#admin-users-pager"), adminPages.users, users.pages || 1);
  syncTableSelection(userTable, document.querySelector("#admin-users-bulk"), adminUserBulkActions);
  const requests = await api(`/api/admin/access-requests?page=${adminPages.requests}&page_size=${PAGE_SIZE}`);
  fillTable(
    "#admin-requests",
    (requests.requests || [])
      .map(
        (row) => `<tr data-id="${row.id}">
        ${row.status === "pending" ? checkCell(row.id) : `<td class="col-check"></td>`}
        <td>${escapeHtml(row.name)}</td><td>${escapeHtml(row.email)}</td><td>${escapeHtml(row.phone || "")}</td><td>${escapeHtml(row.status)}</td>
        <td>${
          row.status === "pending"
            ? `<button class="primary" data-req="${row.id}" data-decision="approved">${t("admin.allow")}</button>
               <button class="ghost" data-req="${row.id}" data-decision="rejected">${t("admin.reject")}</button>`
            : ""
        }</td>
      </tr>`
      )
      .join(""),
    "#admin-requests-empty",
    {
      title: t("admin.no_requests"),
      body: t("admin.no_requests_body"),
    }
  );
  restoreRowChecks(requestTable, selectedRequests);
  syncTableSelection(requestTable, document.querySelector("#admin-requests-bulk"), adminRequestBulkActions);
  if (requests.requests && requests.requests.length) {
    adminPages.requests = requests.page || 1;
    setPager(document.querySelector("#admin-requests-pager"), adminPages.requests, requests.pages || 1);
  }
}

async function loadAudit() {
  const q = document.querySelector("#audit-q").value.trim();
  const data = await api(`/api/admin/audit?q=${encodeURIComponent(q)}&page=${adminPages.audit}&page_size=${PAGE_SIZE}`);
  fillTable(
    "#admin-audit",
    (data.logs || [])
      .map(
        (row) => `<tr><td>${formatStamp(row.created_at)}</td><td>${row.actor}</td><td>${row.action}</td><td>${row.detail || ""}</td><td class="mono">${row.ip_address || ""}</td></tr>`
      )
      .join(""),
    "#admin-audit-empty",
    {
      title: q ? t("admin.no_audit_match") : t("admin.no_audit"),
      body: q ? t("admin.no_audit_match_body") : t("admin.no_audit_body"),
    }
  );
  if (data.logs && data.logs.length) {
    adminPages.audit = data.page || 1;
    setPager(document.querySelector("#admin-audit-pager"), adminPages.audit, data.pages || 1);
  }
}

const TIMEZONES = [
  ["UTC", "🌐 UTC"],
  ["America/New_York", "🇺🇸 America/New_York"],
  ["America/Chicago", "🇺🇸 America/Chicago"],
  ["America/Denver", "🇺🇸 America/Denver"],
  ["America/Los_Angeles", "🇺🇸 America/Los_Angeles"],
  ["Europe/London", "🇬🇧 Europe/London"],
  ["Europe/Paris", "🇫🇷 Europe/Paris"],
  ["Europe/Berlin", "🇩🇪 Europe/Berlin"],
  ["Asia/Dubai", "🇦🇪 Asia/Dubai"],
  ["Asia/Kolkata", "🇮🇳 Asia/Kolkata"],
  ["Asia/Singapore", "🇸🇬 Asia/Singapore"],
  ["Asia/Shanghai", "🇨🇳 Asia/Shanghai"],
  ["Asia/Tokyo", "🇯🇵 Asia/Tokyo"],
  ["Australia/Sydney", "🇦🇺 Australia/Sydney"],
];

function tzOffset(tz) {
  try {
    const name = new Intl.DateTimeFormat("en-US", { timeZone: tz, timeZoneName: "shortOffset" })
      .formatToParts(new Date())
      .find((part) => part.type === "timeZoneName")?.value;
    return (name || "").replace("GMT", "UTC");
  } catch (err) {
    return "";
  }
}

function fillTimezones(current) {
  const select = document.querySelector("#timezone-select");
  if (!select) return;
  const known = new Set(TIMEZONES.map((item) => item[0]));
  const rows = TIMEZONES.slice();
  if (current && !known.has(current)) rows.unshift([current, current]);
  select.innerHTML = rows
    .map(([id, label]) => {
      const offset = tzOffset(id);
      const text = `${label}${offset ? `  ${offset}` : ""}`;
      return `<option value="${escapeHtml(id)}">${escapeHtml(text)}</option>`;
    })
    .join("");
}

function syncAppearance() {
  const theme = document.querySelector("#appearance-theme");
  const language = document.querySelector("#appearance-language");
  if (theme) theme.value = currentTheme();
  if (language) language.value = currentLanguage();
}

async function loadSettings() {
  const data = await api("/api/admin/settings");
  const form = document.querySelector("#settings-form");
  fillTimezones(data.settings.timezone || "UTC");
  Object.entries(data.settings).forEach(([key, value]) => {
    const field = form.elements[key];
    if (!field) return;
    if (field.type === "checkbox") field.checked = ["1", "true", "yes", "on"].includes(String(value).toLowerCase());
    else field.value = value;
  });
  const ping = form.elements.ping_interval;
  if (ping && ping.tagName === "SELECT") {
    const value = String(data.settings.ping_interval || "");
    if (value && ![...ping.options].some((opt) => opt.value === value)) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = `${value} sec`;
      ping.prepend(opt);
    }
    if (value) ping.value = value;
  }
  syncAppearance();
  paintChannelOptions();
  showNotifyChannel(firstEnabledChannel());
}

document.querySelector("#admin-devices").addEventListener("click", async (event) => {
  const edit = event.target.closest("[data-edit]");
  const del = event.target.closest("[data-del]");
  if (edit) {
    const device = JSON.parse(decodeURIComponent(edit.dataset.edit));
    const form = document.querySelector("#device-form");
    const idInput = form.querySelector("[name=id]");
    if (idInput) idInput.value = device.id;
    await fillMonitorForm(form, device);
    document.querySelector("#device-form-title").textContent = t("admin.update_device");
    document.querySelector("#device-form-title").setAttribute("data-i18n", "admin.update_device");
    document.querySelector("#device-modal").hidden = false;
  }
  if (del) {
    const ok = await confirmAction({
      title: t("admin.remove_confirm"),
      body: t("common.confirm_delete_body"),
      danger: true,
      confirmLabel: t("dash.delete"),
    });
    if (!ok) return;
    await api(`/api/devices/${del.dataset.del}`, { method: "DELETE" });
    loadDevices();
  }
});

document.querySelector("#admin-add").addEventListener("click", () => {
  const form = document.querySelector("#device-form");
  form.reset();
  const idInput = form.querySelector("[name=id]");
  if (idInput) idInput.value = "";
  form.querySelector("[name=kind][value=server]").checked = true;
  if (form.monitor_type) form.monitor_type.value = "ping";
  bindMonitorForm(form);
  syncMonitorFields(form);
  document.querySelector("#device-form-title").textContent = t("common.add_device");
  document.querySelector("#device-form-title").setAttribute("data-i18n", "common.add_device");
  document.querySelector("#device-modal").hidden = false;
});
document.querySelector("#close-device-modal").addEventListener("click", () => {
  document.querySelector("#device-modal").hidden = true;
});
document.querySelector("#device-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const payload = monitorFieldsPayload(form);
  const id = form.querySelector("[name=id]")?.value;
  const error = document.querySelector("#device-error");
  error.hidden = true;
  try {
    if (id) {
      await api(`/api/devices/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await api("/api/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }
    document.querySelector("#device-modal").hidden = true;
    loadDevices();
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});

document.querySelector("#admin-users").addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-user]");
  if (!btn) return;
  await api(`/api/admin/users/${btn.dataset.user}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: btn.dataset.status }),
  });
  loadUsers();
});

document.querySelector("#admin-requests").addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-req]");
  if (!btn) return;
  await api(`/api/admin/access-requests/${btn.dataset.req}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision: btn.dataset.decision }),
  });
  loadUsers();
});

document.querySelector("#audit-search").addEventListener("click", () => {
  adminPages.audit = 1;
  loadAudit();
});
document.querySelector("#settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const settings = {};
  Array.from(form.elements).forEach((field) => {
    if (!field.name) return;
    settings[field.name] = field.type === "checkbox" ? (field.checked ? "true" : "false") : field.value;
  });
  const error = document.querySelector("#settings-error");
  error.className = "form-error";
  error.hidden = true;
  try {
    await api("/api/admin/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings }),
    });
    error.className = "ok";
    error.textContent = t("admin.settings_saved");
    error.hidden = false;
    window.PINGWATCH_TZ = settings.timezone || window.PINGWATCH_TZ;
    window.PINGWATCH_INTERVAL = Number(settings.ping_interval || window.PINGWATCH_INTERVAL);
    window.PINGWATCH_INCIDENTS = settings.incidents_enabled !== "false";
    if (typeof paintCompanyName === "function") paintCompanyName(settings.company_name);
    if (typeof tickClock === "function") tickClock();
  } catch (err) {
    error.className = "form-error";
    error.textContent = err.message;
    error.hidden = false;
  }
});
document.querySelector("#snow-test").addEventListener("click", async () => {
  const result = await api("/api/admin/servicenow/test", { method: "POST" });
  document.querySelector("#snow-result").textContent = result.result;
});

const CHANNEL_ICONS = {
  teams: "/static/public/teams-svgrepo-com.svg",
  slack: "/static/public/slack-svgrepo-com.svg",
  webhook: "/static/public/webhook-svgrepo-com.svg",
  pagerduty: "/static/public/pager-duty-svgrepo-com.svg",
  discord: "/static/public/discord-communication-interaction-message-network-svgrepo-com.svg",
  telegram: "/static/public/telegram-svgrepo-com.svg",
  whatsapp: "/static/public/whatsapp-svgrepo-com.svg",
};

function selectedNotifyChannel() {
  return document.querySelector("#notify-channel")?.value || "teams";
}

function setChannelMenuOpen(open) {
  const menu = document.querySelector("#channel-menu");
  const button = document.querySelector("#channel-select-btn");
  if (!menu || !button) return;
  menu.hidden = !open;
  button.setAttribute("aria-expanded", open ? "true" : "false");
}

function showNotifyChannel(id) {
  const channel = id || "teams";
  document.querySelectorAll(".channel-block[data-channel]").forEach((block) => {
    block.hidden = block.dataset.channel !== channel;
  });
  const hidden = document.querySelector("#notify-channel");
  if (hidden) hidden.value = channel;
  const icon = document.querySelector("#channel-select-icon");
  if (icon && CHANNEL_ICONS[channel]) icon.src = CHANNEL_ICONS[channel];
  const label = document.querySelector("#channel-select-label");
  if (label) label.textContent = t(`admin.channel_${channel}`);
  document.querySelectorAll("#channel-menu [data-channel]").forEach((item) => {
    item.classList.toggle("is-selected", item.dataset.channel === channel);
  });
}

function firstEnabledChannel() {
  const form = document.querySelector("#settings-form");
  const items = document.querySelectorAll("#channel-menu [data-channel]");
  if (!form || !items.length) return "teams";
  const match = Array.from(items).find((item) => form.elements[`notify_${item.dataset.channel}_enabled`]?.checked);
  return match ? match.dataset.channel : selectedNotifyChannel();
}

function paintChannelOptions() {
  const form = document.querySelector("#settings-form");
  if (!form) return;
  document.querySelectorAll("#channel-menu [data-channel]").forEach((item) => {
    const channel = item.dataset.channel;
    const on = form.elements[`notify_${channel}_enabled`]?.checked;
    const label = item.querySelector("[data-channel-label]");
    if (label) label.textContent = t(`admin.channel_${channel}`);
    const badge = item.querySelector(".channel-on");
    if (badge) {
      badge.hidden = !on;
      badge.textContent = t("admin.channel_on");
    }
  });
  const current = selectedNotifyChannel();
  const label = document.querySelector("#channel-select-label");
  if (label) label.textContent = t(`admin.channel_${current}`);
}

function openChannelGuide() {
  const channel = selectedNotifyChannel();
  const modal = document.querySelector("#channel-guide-modal");
  const title = document.querySelector("#channel-guide-title");
  const body = document.querySelector("#channel-guide-body");
  if (!modal || !title || !body) return;
  title.textContent = t(`admin.guide.${channel}.title`);
  const introKey = `admin.guide.${channel}.intro`;
  const intro = t(introKey);
  const steps = [];
  for (let i = 1; i <= 8; i += 1) {
    const key = `admin.guide.${channel}.${i}`;
    const text = t(key);
    if (text === key) break;
    steps.push(text);
  }
  const introHtml = intro && intro !== introKey ? `<p>${escapeHtml(intro)}</p>` : "";
  body.innerHTML = `${introHtml}<ol>${steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>`;
  modal.hidden = false;
}

function closeChannelGuide() {
  const modal = document.querySelector("#channel-guide-modal");
  if (modal) modal.hidden = true;
}

document.querySelector("#channel-select-btn")?.addEventListener("click", (event) => {
  event.stopPropagation();
  const menu = document.querySelector("#channel-menu");
  setChannelMenuOpen(Boolean(menu?.hidden));
});

document.querySelector("#channel-menu")?.addEventListener("click", (event) => {
  const item = event.target.closest("[data-channel]");
  if (!item) return;
  showNotifyChannel(item.dataset.channel);
  setChannelMenuOpen(false);
});

document.addEventListener("click", (event) => {
  if (event.target.closest("#channel-select")) return;
  setChannelMenuOpen(false);
});

document.querySelector("#settings-form")?.addEventListener("change", (event) => {
  const name = event.target?.name || "";
  if (name.startsWith("notify_") && name.endsWith("_enabled")) paintChannelOptions();
});

document.querySelector("#channel-guide-btn")?.addEventListener("click", openChannelGuide);
document.querySelector("#channel-guide-close")?.addEventListener("click", closeChannelGuide);
document.querySelector("#channel-guide-modal")?.addEventListener("click", (event) => {
  if (event.target.id === "channel-guide-modal") closeChannelGuide();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeChannelGuide();
    setChannelMenuOpen(false);
  }
});
window.addEventListener("pingwatch:i18n", paintChannelOptions);

document.querySelector("#settings-form")?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-notify-test]");
  if (!button) return;
  const channel = button.dataset.notifyTest;
  const out = document.querySelector(`[data-notify-result="${channel}"]`);
  if (out) out.textContent = "…";
  try {
    const result = await api("/api/admin/notifications/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ channel }),
    });
    if (out) out.textContent = result.result === "ok" ? t("admin.channel_test_ok") : result.result;
  } catch (err) {
    if (out) out.textContent = err.message;
  }
});

document.querySelector("#appearance-theme")?.addEventListener("change", (event) => {
  applyTheme(event.target.value);
});

function wireAdminPager(id, key, reload) {
  bindPager(document.querySelector(id), {
    prev: () => {
      adminPages[key] = Math.max(1, adminPages[key] - 1);
      reload();
    },
    next: () => {
      adminPages[key] += 1;
      reload();
    },
  });
}

async function loadAnnouncements() {
  const table = document.querySelector("#admin-announcements-table");
  const selected = new Set(selectedRowIds(table));
  const data = await api(`/api/announcements?page=${adminPages.announcements}&page_size=${PAGE_SIZE}`);
  fillTable(
    "#admin-announcements",
    (data.announcements || [])
      .map(
        (item) => `<tr data-id="${item.id}">
        ${checkCell(item.id)}
        <td>${escapeHtml(item.title)}</td>
        <td>${escapeHtml(item.short_description || "—")}</td>
        <td>${formatStamp(item.created_at)}</td>
        <td><button class="danger" data-announcement="${item.id}">${t("common.remove")}</button></td>
      </tr>`
      )
      .join(""),
    "#admin-announcements-empty",
    {
      title: t("admin.announce_empty"),
      body: t("admin.announce_empty_body"),
    }
  );
  restoreRowChecks(table, selected);
  adminPages.announcements = data.page || 1;
  setPager(document.querySelector("#admin-announcements-pager"), adminPages.announcements, data.pages || 1);
  syncTableSelection(table, document.querySelector("#admin-announcements-bulk"), adminAnnounceBulkActions);
}

document.querySelector("#announce-form")?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.target;
  const error = document.querySelector("#announce-error");
  error.className = "form-error";
  error.hidden = true;
  const payload = Object.fromEntries(new FormData(form).entries());
  try {
    await api("/api/announcements", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    form.reset();
    error.className = "ok";
    error.textContent = t("admin.announce_posted");
    error.hidden = false;
    adminPages.announcements = 1;
    await loadAnnouncements();
    if (typeof refreshNotifications === "function") refreshNotifications();
  } catch (err) {
    error.className = "form-error";
    error.textContent = err.message;
    error.hidden = false;
  }
});

document.querySelector("#admin-announcements")?.addEventListener("click", async (event) => {
  const btn = event.target.closest("[data-announcement]");
  if (!btn) return;
  const ok = await confirmAction({
    title: t("admin.announce_remove"),
    body: t("common.confirm_delete_body"),
    danger: true,
    confirmLabel: t("dash.delete"),
  });
  if (!ok) return;
  await api(`/api/announcements/${btn.dataset.announcement}`, { method: "DELETE" });
  await loadAnnouncements();
  if (typeof refreshNotifications === "function") refreshNotifications();
});

bindTableSelection(document.querySelector("#admin-devices-table"), {
  bar: document.querySelector("#admin-devices-bulk"),
  renderActions: adminDeviceBulkActions,
  onAction: async (action, ids) => {
    if (action === "delete") {
      const ok = await confirmAction({
        title: t("dash.confirm_delete_many", { count: ids.length }),
        body: t("common.confirm_delete_body"),
        danger: true,
        confirmLabel: t("dash.delete"),
      });
      if (!ok) return;
    }
    await runOnIds(ids, async (id) => {
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
    await loadDevices();
  },
});
bindTableSelection(document.querySelector("#admin-users-table"), {
  bar: document.querySelector("#admin-users-bulk"),
  renderActions: adminUserBulkActions,
  onAction: async (action, ids) => {
    const ok = await confirmAction({
      title: t("admin.confirm_status_many", { count: ids.length }),
      body: t("common.confirm_body"),
      danger: true,
      confirmLabel: t("common.continue"),
    });
    if (!ok) return;
    const status = action === "enable" ? "active" : "disabled";
    const table = document.querySelector("#admin-users-table");
    const filtered = ids.filter((id) => {
      const row = table?.querySelector(`tr[data-id="${id}"]`);
      return row && row.dataset.role !== "admin";
    });
    await runOnIds(filtered, (id) =>
      api(`/api/admin/users/${id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      })
    );
    await loadUsers();
  },
});
bindTableSelection(document.querySelector("#admin-announcements-table"), {
  bar: document.querySelector("#admin-announcements-bulk"),
  renderActions: adminAnnounceBulkActions,
  onAction: async (action, ids) => {
    if (action !== "delete") return;
    const ok = await confirmAction({
      title: t("common.confirm_delete_many", { count: ids.length }),
      body: t("common.confirm_delete_body"),
      danger: true,
      confirmLabel: t("dash.delete"),
    });
    if (!ok) return;
    await runOnIds(ids, (id) => api(`/api/announcements/${id}`, { method: "DELETE" }));
    await loadAnnouncements();
    if (typeof refreshNotifications === "function") refreshNotifications();
  },
});
bindTableSelection(document.querySelector("#admin-requests-table"), {
  bar: document.querySelector("#admin-requests-bulk"),
  renderActions: adminRequestBulkActions,
  onAction: async (action, ids) => {
    if (action !== "approved" && action !== "rejected") return;
    const ok = await confirmAction({
      title: t("admin.confirm_review_many", { count: ids.length }),
      body: t("common.confirm_body"),
      danger: true,
      confirmLabel: t("common.continue"),
    });
    if (!ok) return;
    await runOnIds(ids, (id) =>
      api(`/api/admin/access-requests/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: action }),
      })
    );
    await loadUsers();
  },
});

window.sessionReady.then(async (user) => {
  if (!user || user.role !== "admin") {
    window.location.href = "/";
    return;
  }
  wireAdminPager("#admin-devices-pager", "devices", loadDevices);
  wireAdminPager("#admin-users-pager", "users", loadUsers);
  wireAdminPager("#admin-requests-pager", "requests", loadUsers);
  wireAdminPager("#admin-audit-pager", "audit", loadAudit);
  wireAdminPager("#admin-announcements-pager", "announcements", loadAnnouncements);
  const tab = (location.hash || "#devices").replace("#", "");
  showTab(["devices", "users", "audit", "settings", "announcements"].includes(tab) ? tab : "devices");
  bindMonitorForm(document.querySelector("#device-form"));
  await Promise.all([loadDevices(), loadUsers(), loadAudit(), loadSettings(), loadAnnouncements()]);
});
window.addEventListener("pingwatch:refresh", () => {
  Promise.all([loadDevices(), loadUsers(), loadAudit(), loadSettings(), loadAnnouncements()]).catch(() => {});
});
window.addEventListener("pingwatch:i18n", () => {
  Promise.all([loadDevices(), loadUsers(), loadAudit(), loadAnnouncements()]).catch(() => {});
});
