let currentUser = null;
window.PINGWATCH_TZ = "UTC";
window.PINGWATCH_INCIDENTS = true;
const PAGE_SIZE = 15;
window.PAGE_SIZE = PAGE_SIZE;

function bindPager(root, handlers) {
  if (!root || root.dataset.bound === "1") return;
  root.dataset.bound = "1";
  root.querySelector("[data-pager='prev']")?.addEventListener("click", () => handlers.prev());
  root.querySelector("[data-pager='next']")?.addEventListener("click", () => handlers.next());
}

function setPager(root, page, pages) {
  if (!root) return;
  const totalPages = Math.max(1, Number(pages) || 1);
  const current = Math.max(1, Number(page) || 1);
  root.hidden = totalPages <= 1;
  const label = root.querySelector("[data-pager='label']");
  if (label) label.textContent = t("dash.page", { page: current, pages: totalPages });
  const prev = root.querySelector("[data-pager='prev']");
  const next = root.querySelector("[data-pager='next']");
  if (prev) prev.disabled = current <= 1;
  if (next) next.disabled = current >= totalPages;
}

const INCIDENT_STATUSES = [
  "open",
  "active",
  "work_in_progress",
  "closed_successful",
  "closed_unsuccessful",
  "cancelled",
  "auto_resolved",
  "monitor",
  "pending",
];
const LIVE_INCIDENT_STATUSES = ["open", "active", "work_in_progress", "monitor", "pending"];
const ARCHIVE_INCIDENT_STATUSES = ["closed_successful", "closed_unsuccessful", "cancelled", "auto_resolved"];
const INCIDENT_STATUS_PILL = {
  open: "offline",
  active: "warning",
  work_in_progress: "warning",
  closed_successful: "online",
  closed_unsuccessful: "offline",
  cancelled: "unknown",
  auto_resolved: "online",
  monitor: "unknown",
  pending: "warning",
};

function incidentStatusLabel(status) {
  return t("incidents." + status) || status;
}

function incidentStatusOptions(selected) {
  return INCIDENT_STATUSES.map((status) => {
    const sel = status === selected ? " selected" : "";
    return `<option value="${status}"${sel}>${escapeHtml(incidentStatusLabel(status))}</option>`;
  }).join("");
}

function checkCell(id) {
  return `<td class="col-check"><input type="checkbox" class="row-check" value="${escapeHtml(String(id))}" aria-label="${t("common.select_row")}" /></td>`;
}

function selectedRowIds(table) {
  return [...(table?.querySelectorAll("tbody .row-check:checked:not(:disabled)") || [])].map((box) => box.value);
}

function restoreRowChecks(table, selected) {
  if (!table || !selected) return;
  table.querySelectorAll("tbody .row-check").forEach((box) => {
    box.checked = !box.disabled && selected.has(box.value);
  });
}

function bulkBarHtml(count, actions) {
  const buttons = (actions || [])
    .map(
      (item) =>
        `<button type="button" class="${item.danger ? "danger" : "ghost"}" data-bulk="${escapeHtml(item.id)}">${escapeHtml(item.label)}</button>`
    )
    .join("");
  return `<span>${escapeHtml(t("common.selected", { count }))}</span>${buttons}`;
}

function syncTableSelection(table, bar, renderActions) {
  if (!table) return [];
  const boxes = [...table.querySelectorAll("tbody .row-check:not(:disabled)")];
  const selected = boxes.filter((box) => box.checked);
  const master = table.querySelector("thead .select-all");
  if (master) {
    master.checked = boxes.length > 0 && selected.length === boxes.length;
    master.indeterminate = selected.length > 0 && selected.length < boxes.length;
  }
  table.querySelectorAll("tbody tr[data-id]").forEach((row) => {
    row.classList.toggle("is-selected", Boolean(row.querySelector(".row-check:checked")));
  });
  const ids = selected.map((box) => box.value);
  if (bar) {
    if (!ids.length) {
      bar.hidden = true;
      bar.innerHTML = "";
    } else {
      bar.hidden = false;
      bar.innerHTML = typeof renderActions === "function" ? renderActions(ids) : bulkBarHtml(ids.length, []);
    }
  }
  return ids;
}

function bindTableSelection(table, { bar, renderActions, onAction } = {}) {
  if (!table || table.dataset.selectBound === "1") return;
  table.dataset.selectBound = "1";
  table.addEventListener("change", (event) => {
    const target = event.target;
    if (target.classList.contains("select-all")) {
      table.querySelectorAll("tbody .row-check:not(:disabled)").forEach((box) => {
        box.checked = target.checked;
      });
    }
    if (target.classList.contains("select-all") || target.classList.contains("row-check")) {
      syncTableSelection(table, bar, renderActions);
    }
  });
  table.addEventListener("click", (event) => {
    if (event.target.closest(".col-check")) event.stopPropagation();
  });
  bar?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-bulk]");
    if (!button || typeof onAction !== "function") return;
    const ids = selectedRowIds(table);
    if (!ids.length) return;
    onAction(button.dataset.bulk, ids);
  });
}

async function runOnIds(ids, worker) {
  const errors = [];
  for (const id of ids) {
    try {
      await worker(id);
    } catch (err) {
      errors.push(err.message || String(err));
    }
  }
  return errors;
}

function currentTheme() {
  return document.documentElement.dataset.theme || "light";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("pingwatch-theme", theme);
}

function currentLanguage() {
  return localStorage.getItem("pingwatch-language") || "en";
}

function applyLanguage(lang) {
  const next = lang || "en";
  localStorage.setItem("pingwatch-language", next);
  if (typeof applyI18n === "function") applyI18n();
  else document.documentElement.lang = next;
  document.querySelectorAll("#lang-select, #appearance-language").forEach((select) => {
    if (select.value !== next) select.value = next;
  });
  window.dispatchEvent(new CustomEvent("pingwatch:i18n", { detail: { lang: next } }));
}

function initTheme() {
  const button = document.querySelector("#theme-toggle");
  if (!button) return;
  button.addEventListener("click", () => {
    applyTheme(currentTheme() === "light" ? "dark" : "light");
    const select = document.querySelector("#appearance-theme");
    if (select) select.value = currentTheme();
  });
}

function parseDate(value) {
  if (!value) return null;
  const parsed = value.endsWith("Z") || /[+-]\d\d:\d\d$/.test(value) ? new Date(value) : new Date(value + "Z");
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function relTime(value) {
  const parsed = parseDate(value);
  if (!parsed) return "—";
  const delta = (Date.now() - parsed.getTime()) / 1000;
  if (delta < 8) return "just now";
  if (delta < 60) return `${Math.floor(delta)}s ago`;
  if (delta < 3600) return `${Math.floor(delta / 60)}m ago`;
  if (delta < 86400) return `${Math.floor(delta / 3600)}h ago`;
  return `${Math.floor(delta / 86400)}d ago`;
}

function clock(value) {
  const parsed = parseDate(value);
  if (!parsed) return "—";
  try {
    return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: window.PINGWATCH_TZ });
  } catch (err) {
    return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
}

function formatStamp(value) {
  const parsed = parseDate(value);
  if (!parsed) return "—";
  try {
    return parsed.toLocaleString([], { timeZone: window.PINGWATCH_TZ });
  } catch (err) {
    return parsed.toLocaleString();
  }
}

function ms(value) {
  return value == null ? "—" : `${Number(value).toFixed(value < 10 ? 1 : 0)} ms`;
}

function pct(value) {
  return value == null ? "—" : `${Number(value).toFixed(2)}%`;
}

function statusLabel(status) {
  const key = {
    online: "status.up",
    offline: "status.down",
    warning: "status.warning",
    unknown: "status.unknown",
    paused: "status.paused",
    up: "status.up",
    down: "status.down",
  }[status];
  return key && typeof t === "function" ? t(key) : status;
}

function kindLabel(kind) {
  const key = {
    nas: "dash.nas",
    storage: "dash.storage",
    san: "dash.san",
    network: "dash.network",
    server: "dash.server",
    other: "dash.other",
  }[kind];
  return key && typeof t === "function" ? t(key) : kind;
}

function monitorLabel(type) {
  const key = {
    ping: "dash.monitor_ping",
    tcp: "dash.monitor_tcp",
    dns: "dash.monitor_dns",
    websocket: "dash.monitor_websocket",
    grpc: "dash.monitor_grpc",
    game: "dash.monitor_game",
  }[type];
  return key && typeof t === "function" ? t(key) : type || "Ping";
}

let MONITOR_CATALOG = { games: [], loaded: false };

async function loadMonitorCatalog() {
  if (MONITOR_CATALOG.loaded) return MONITOR_CATALOG;
  try {
    const data = await api("/api/monitors/catalog");
    MONITOR_CATALOG = { games: data.games || [], loaded: true };
  } catch (err) {
    MONITOR_CATALOG = { games: [], loaded: true };
  }
  return MONITOR_CATALOG;
}

function fillGameSelect(select, games, selected) {
  if (!select) return;
  const current = selected || select.value || "";
  const options = [`<option value="">${t("dash.game_type")}</option>`].concat(
    (games || []).map(
      (game) =>
        `<option value="${escapeHtml(game.id)}"${game.id === current ? " selected" : ""}>${escapeHtml(
          game.label
        )}</option>`
    )
  );
  select.innerHTML = options.join("");
  if (current) select.value = current;
}

function syncMonitorFields(form) {
  if (!form) return;
  const type = form.querySelector("[name=monitor_type]")?.value || "ping";
  form.querySelectorAll("[data-monitor-for]").forEach((el) => {
    const allow = (el.dataset.monitorFor || "").split(/\s+/).filter(Boolean);
    el.hidden = !allow.includes(type);
  });
  const host = form.querySelector("[name=host]");
  if (host) {
    host.placeholder =
      {
        ping: "192.168.1.10",
        tcp: "db.lab.local",
        dns: "internal.example.com",
        websocket: "chat.example.com",
        grpc: "api.lab.local",
        game: "game.lab.local",
      }[type] || "192.168.1.10";
  }
  const hostLabel = form.querySelector("[data-host-label]");
  if (hostLabel && typeof t === "function") {
    const key = type === "dns" ? "dash.host_dns" : type === "websocket" ? "dash.host_ws" : "admin.host";
    hostLabel.setAttribute("data-i18n", key);
    hostLabel.textContent = t(key);
  }
  const hint = form.querySelector("[data-monitor-hint]");
  if (hint && typeof t === "function") {
    const key = "dash.monitor_hint_" + type;
    hint.setAttribute("data-i18n", key);
    hint.textContent = t(key);
  }
}

function monitorFieldsPayload(form) {
  const data = Object.fromEntries(new FormData(form).entries());
  const type = data.monitor_type || "ping";
  const payload = {
    name: data.name,
    host: data.host,
    kind: data.kind || "server",
    notes: data.notes || null,
    monitor_type: type,
  };
  if (data.port) payload.port = Number(data.port);
  if (type === "dns") {
    payload.dns_qtype = data.dns_qtype || "A";
    if (data.dns_nameserver) payload.dns_nameserver = data.dns_nameserver;
  }
  if (type === "websocket") {
    payload.ws_path = data.ws_path || "/";
    payload.ws_secure = data.ws_secure === "true" || data.ws_secure === "wss";
    if (!data.port) payload.port = payload.ws_secure ? 443 : 80;
  }
  if (type === "grpc" && data.grpc_service) payload.grpc_service = data.grpc_service;
  if (type === "game" && data.game_type) payload.game_type = data.game_type;
  return payload;
}

async function bindMonitorForm(form) {
  if (!form || form.dataset.monitorBound === "1") return;
  form.dataset.monitorBound = "1";
  form.querySelectorAll("[name=monitor_type]").forEach((input) => {
    input.addEventListener("change", () => syncMonitorFields(form));
  });
  const catalog = await loadMonitorCatalog();
  fillGameSelect(form.querySelector("[name=game_type]"), catalog.games);
  syncMonitorFields(form);
}

async function fillMonitorForm(form, device) {
  const catalog = await loadMonitorCatalog();
  const spec = device.monitor_spec || {};
  fillGameSelect(form.querySelector("[name=game_type]"), catalog.games, spec.game_type || "");
  if (form.name) form.name.value = device.name || "";
  if (form.host) form.host.value = device.host || "";
  if (form.notes) form.notes.value = device.notes || "";
  if (form.kind && device.kind) form.kind.value = device.kind;
  const type = device.monitor_type || "ping";
  if (form.monitor_type) form.monitor_type.value = type;
  if (form.port) form.port.value = device.port || "";
  if (form.dns_qtype) form.dns_qtype.value = spec.qtype || "A";
  if (form.dns_nameserver) form.dns_nameserver.value = spec.nameserver || "";
  if (form.ws_path) form.ws_path.value = spec.path || "/";
  if (form.ws_secure) form.ws_secure.value = spec.secure ? "true" : "false";
  if (form.grpc_service) form.grpc_service.value = spec.service || "";
  if (form.game_type && spec.game_type) form.game_type.value = spec.game_type;
  syncMonitorFields(form);
}

function initialsFrom(user) {
  const source = (user && (user.name || user.username)) || "PW";
  return source
    .split(/\s+|@/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function paintAvatar(node, user) {
  if (!node) return;
  node.textContent = initialsFrom(user);
  const seed = String((user && (user.id || user.name || user.username)) || "pw");
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) hash = (hash * 33 + seed.charCodeAt(i)) >>> 0;
  const hue = [162, 198, 221, 258, 18, 332][hash % 6];
  node.style.background = `hsl(${hue} 38% 32%)`;
}

function formatTenure(value) {
  const parsed = parseDate(value);
  if (!parsed) return "—";
  const now = new Date();
  let years = now.getFullYear() - parsed.getFullYear();
  let months = now.getMonth() - parsed.getMonth();
  let days = now.getDate() - parsed.getDate();
  if (days < 0) {
    months -= 1;
    days += new Date(now.getFullYear(), now.getMonth(), 0).getDate();
  }
  if (months < 0) {
    years -= 1;
    months += 12;
  }
  const unit = (n, one, many) => t(n === 1 ? one : many, { n });
  const parts = [];
  if (years > 0) parts.push(unit(years, "profile.year", "profile.years"));
  if (months > 0) parts.push(unit(months, "profile.month", "profile.months"));
  if (days > 0 || !parts.length) parts.push(unit(days, "profile.day", "profile.days"));
  return parts.join(", ");
}

function formatTenureCompact(value) {
  const parsed = parseDate(value);
  if (!parsed) return "—";
  const now = new Date();
  let years = now.getFullYear() - parsed.getFullYear();
  let months = now.getMonth() - parsed.getMonth();
  let days = now.getDate() - parsed.getDate();
  if (days < 0) {
    months -= 1;
    days += new Date(now.getFullYear(), now.getMonth(), 0).getDate();
  }
  if (months < 0) {
    years -= 1;
    months += 12;
  }
  const bits = [];
  if (years > 0) bits.push(`${years}y`);
  if (months > 0) bits.push(`${months}m`);
  bits.push(`${days}d`);
  return bits.join(" ");
}

function duration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function emptyArt() {
  return `<svg class="empty-art-svg" viewBox="0 0 180 120" aria-hidden="true">
    <g fill="none" stroke="currentColor" stroke-opacity="0.18" stroke-width="1">
      <path d="M40 20h100M40 40h100M40 60h100M40 80h100M40 100h100"/>
      <path d="M60 8v104M90 8v104M120 8v104"/>
    </g>
    <rect x="58" y="18" width="86" height="54" rx="10" fill="#94a3b8" opacity="0.55"/>
    <rect x="70" y="30" width="44" height="7" rx="3" fill="#e2e8f0"/>
    <rect x="70" y="44" width="58" height="6" rx="3" fill="#e2e8f0"/>
    <rect x="32" y="40" width="92" height="58" rx="10" fill="#1a6758"/>
    <rect x="42" y="52" width="12" height="34" rx="3" fill="#3d8f7a"/>
    <rect x="62" y="54" width="46" height="8" rx="3" fill="#d5efe6"/>
    <rect x="62" y="70" width="50" height="6" rx="3" fill="#c8e6dc"/>
  </svg>`;
}

function emptyState({ title, body, actionLabel, actionId, compact }) {
  const button = actionLabel
    ? `<button type="button" class="empty-cta"${actionId ? ` id="${actionId}"` : ""}>${escapeHtml(actionLabel)}</button>`
    : "";
  return `<div class="empty-hero${compact ? " compact" : ""}">
    ${emptyArt()}
    <h3>${escapeHtml(title || "")}</h3>
    <p>${escapeHtml(body || "")}</p>
    ${button}
  </div>`;
}

function incidentsEnabled() {
  return window.PINGWATCH_INCIDENTS !== false;
}

function incidentsDisabledState() {
  return emptyState({
    title: t("incidents.disabled_title"),
    body: t("incidents.disabled_body"),
  });
}

function paintCompanyName(name) {
  const node = document.querySelector("#company-name");
  if (!node) return;
  const value = String(name || "").trim().slice(0, 15);
  node.textContent = value;
  node.hidden = !value;
}

async function api(path, options) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (response.status === 401 && !path.startsWith("/api/auth/login")) {
    window.location.href = "/login";
    throw new Error("Sign in required");
  }
  if (response.status === 403 && payload.detail === "password_change_required") {
    window.location.href = "/password";
    throw new Error("Password change required");
  }
  if (!response.ok) {
    const detail = payload.detail;
    const message = typeof detail === "string" ? detail : detail?.[0]?.msg || "Request failed";
    throw new Error(message);
  }
  return payload;
}

async function initSession() {
  const publicPage = ["/login", "/request-access"].includes(window.location.pathname);
  const versionNodes = document.querySelectorAll("#app-version, #about-version, #settings-version, #auth-version");
  if (publicPage || document.querySelector("#auth-version")) {
    fetch("/api/settings/public")
      .then((response) => (response.ok ? response.json() : null))
      .then((pub) => {
        if (!pub?.version) return;
        versionNodes.forEach((node) => {
          node.textContent = pub.version;
        });
      })
      .catch(() => {});
  }
  if (publicPage) return null;
  try {
    const me = await api("/api/auth/me");
    currentUser = me.user;
    window.PINGWATCH_TZ = me.settings?.timezone || "UTC";
    window.PINGWATCH_INTERVAL = me.settings?.ping_interval || 30;
    window.PINGWATCH_INCIDENTS = me.settings?.incidents_enabled !== false;
    paintCompanyName(me.settings?.company_name);
    if (currentUser.must_change_password && window.location.pathname !== "/password") {
      window.location.href = "/password";
      return currentUser;
    }
    document.querySelectorAll(".admin-only").forEach((node) => {
      node.hidden = currentUser.role !== "admin";
    });
    const navUser = document.querySelector("#nav-user");
    if (navUser) navUser.textContent = currentUser.name || currentUser.username;
    document.querySelector("#profile-link")?.classList.toggle("active", window.location.pathname === "/profile");
    const active = document.body.dataset.nav;
    document.querySelectorAll(".sidebar-nav a").forEach((link) => {
      link.classList.toggle("active", link.dataset.nav === active);
    });
    const role = document.querySelector("#nav-role");
    if (role) role.textContent = currentUser.role === "admin" ? t("nav.admin_role") : t("nav.user_role");
    const initials = document.querySelector("#nav-initials");
    if (initials) paintAvatar(initials, currentUser);
    document.querySelectorAll("#app-version, #about-version, #settings-version").forEach((node) => {
      if (me.settings?.version) node.textContent = me.settings.version;
    });
    tickClock();
    if (!window._tzTimer) window._tzTimer = setInterval(tickClock, 1000);
    document.querySelector("#logout-btn")?.addEventListener("click", async () => {
      await api("/api/auth/logout", { method: "POST" });
      window.location.href = "/login";
    });
    refreshNotifications();
    return currentUser;
  } catch (err) {
    return null;
  }
}

initTheme();
if (typeof fillLanguageSelects === "function") fillLanguageSelects();
document.querySelectorAll("#lang-select, #appearance-language").forEach((select) => {
  select.addEventListener("change", (event) => applyLanguage(event.target.value));
});
applyLanguage(currentLanguage());
initShell();
window.sessionReady = initSession();

function tickClock() {
  const el = document.querySelector("#tz-clock");
  if (!el) return;
  const now = new Date();
  try {
    const tz = window.PINGWATCH_TZ || "UTC";
    const time = now.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZone: tz,
    });
    el.textContent = `${tz}  ${time}`;
  } catch (err) {
    el.textContent = now.toLocaleTimeString();
  }
}

function initShell() {
  const toggle = document.querySelector("#sidebar-toggle");
  const scrim = document.querySelector("#sidebar-scrim");
  const closeNav = () => document.body.classList.remove("nav-open");
  toggle?.addEventListener("click", () => document.body.classList.toggle("nav-open"));
  scrim?.addEventListener("click", closeNav);
  document.querySelector("#refresh")?.addEventListener("click", () => {
    window.dispatchEvent(new Event("pingwatch:refresh"));
  });
  initUserMenu();
  initNotifications();
  initViewTransitions();
}

function runViewTransition(update) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    update();
    return null;
  }
  if (typeof document.startViewTransition === "function") {
    return document.startViewTransition(update);
  }
  update();
  return null;
}

function initUserMenu() {
  const menu = document.querySelector("#user-menu");
  const button = document.querySelector("#user-menu-btn");
  const dropdown = document.querySelector("#user-dropdown");
  const about = document.querySelector("#about-modal");
  const changelog = document.querySelector("#changelog-modal");
  if (!menu || !button || !dropdown) return;

  const closeMenu = () => {
    dropdown.hidden = true;
    button.setAttribute("aria-expanded", "false");
    menu.classList.remove("open");
  };
  const openMenu = () => {
    dropdown.hidden = false;
    button.setAttribute("aria-expanded", "true");
    menu.classList.add("open");
  };
  const openAbout = () => {
    closeMenu();
    if (about) about.hidden = false;
  };
  const renderChangelog = (releases) =>
    (releases || [])
      .map((release) => {
        const current = release.current ? `<span class="role-pill ok">${escapeHtml(t("changelog.current"))}</span>` : "";
        const notes = (release.notes || []).map((note) => `<li>${escapeHtml(note)}</li>`).join("");
        return `<article class="changelog-entry">
          <div class="changelog-head"><h3>${escapeHtml(release.version)}</h3>${current}</div>
          <p class="changelog-date">${escapeHtml(release.date || "")}</p>
          <ul>${notes}</ul>
        </article>`;
      })
      .join("");
  const openChangelog = async () => {
    closeMenu();
    if (!changelog) return;
    const body = document.querySelector("#changelog-body");
    if (body && !body.dataset.loaded) {
      try {
        const data = await fetch("/static/changelog.json").then((response) => response.json());
        body.innerHTML = renderChangelog(data);
        body.dataset.loaded = "1";
      } catch (err) {
        body.innerHTML = `<p class="muted">${escapeHtml(err.message || "Could not load changelog")}</p>`;
      }
    }
    changelog.hidden = false;
  };

  button.addEventListener("click", (event) => {
    event.stopPropagation();
    if (dropdown.hidden) openMenu();
    else closeMenu();
  });
  document.addEventListener("click", (event) => {
    if (!menu.contains(event.target)) closeMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
      if (about && !about.hidden) about.hidden = true;
      if (changelog && !changelog.hidden) changelog.hidden = true;
    }
  });
  document.querySelector("#about-btn")?.addEventListener("click", openAbout);
  document.querySelector("#version-btn")?.addEventListener("click", openChangelog);
  document.querySelector("#about-close")?.addEventListener("click", () => {
    if (about) about.hidden = true;
  });
  document.querySelector("#changelog-close")?.addEventListener("click", () => {
    if (changelog) changelog.hidden = true;
  });
  about?.addEventListener("click", (event) => {
    if (event.target === about) about.hidden = true;
  });
  changelog?.addEventListener("click", (event) => {
    if (event.target === changelog) changelog.hidden = true;
  });
}

async function refreshNotifications() {
  const badge = document.querySelector("#notif-badge");
  const button = document.querySelector("#notif-btn");
  const menu = document.querySelector("#notif-menu");
  if (!badge) return;
  try {
    const data = await api("/api/announcements?preview=6");
    window._notifPreview = data;
    const count = Number(data.unread || 0);
    badge.textContent = count > 99 ? "99+" : String(count);
    badge.hidden = count < 1;
    const latest = (data.announcements || [])[0];
    if (button && latest?.short_description) {
      button.title = latest.short_description;
      button.setAttribute("aria-label", latest.short_description);
    } else if (button) {
      button.title = t("nav.notifications");
      button.setAttribute("aria-label", t("nav.notifications"));
    }
    if (menu && !menu.hidden) renderNotifMenu(data);
  } catch (err) {
    badge.hidden = true;
  }
}

function renderNotifMenu(data) {
  const menu = document.querySelector("#notif-menu");
  if (!menu) return;
  const items = data?.announcements || [];
  if (!items.length) {
    menu.innerHTML = `<p class="notif-empty">${escapeHtml(t("notif.none"))}</p>
      <a class="notif-foot" href="/notifications">${escapeHtml(t("notif.view_all"))}</a>`;
    return;
  }
  menu.innerHTML =
    items
      .map(
        (item) => `<a class="notif-item${item.unread ? " unread" : ""}" href="/notifications#${item.id}" role="menuitem">
          <strong>${escapeHtml(item.title)}</strong>
          <small>${escapeHtml(item.short_description || "")}</small>
        </a>`
      )
      .join("") + `<a class="notif-foot" href="/notifications">${escapeHtml(t("notif.view_all"))}</a>`;
}

function initNotifications() {
  const wrap = document.querySelector("#notif-wrap");
  const button = document.querySelector("#notif-btn");
  const menu = document.querySelector("#notif-menu");
  if (!wrap || !button || !menu) return;
  const closeMenu = () => {
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
  };
  const openMenu = () => {
    renderNotifMenu(window._notifPreview);
    menu.hidden = false;
    button.setAttribute("aria-expanded", "true");
    refreshNotifications();
  };
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    if (menu.hidden) openMenu();
    else closeMenu();
  });
  document.addEventListener("click", (event) => {
    if (!wrap.contains(event.target)) closeMenu();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });
  window.addEventListener("pingwatch:refresh", refreshNotifications);
  setInterval(() => {
    if (document.hidden) return;
    refreshNotifications();
  }, 30000);
}

function isInternalNav(link, event) {
  if (!link || event.defaultPrevented) return null;
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return null;
  if (link.target && link.target !== "_self") return null;
  if (link.hasAttribute("download")) return null;
  let url;
  try {
    url = new URL(link.href, location.href);
  } catch (err) {
    return null;
  }
  if (url.origin !== location.origin) return null;
  if (url.pathname === location.pathname && url.search === location.search) return null;
  return url;
}

function initViewTransitions() {
  try {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync("@view-transition { navigation: auto; }");
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  } catch (err) {
    /* older browsers keep CSS fade on .page */
  }
  const hasMpaTransitions = "onpagereveal" in window;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link) return;
    document.body.classList.remove("nav-open");
    const url = isInternalNav(link, event);
    if (!url) return;
    sessionStorage.setItem("pw-nav", "1");
    if (hasMpaTransitions || reduceMotion) return;

    event.preventDefault();
    const page = document.querySelector(".page");
    let going = false;
    const go = () => {
      if (going) return;
      going = true;
      location.href = url.href;
    };
    if (!page) {
      go();
      return;
    }
    page.classList.add("is-leaving");
    const timer = setTimeout(go, 200);
    page.addEventListener("animationend", (animEvent) => {
      if (animEvent.target !== page) return;
      clearTimeout(timer);
      go();
    });
  });
}
