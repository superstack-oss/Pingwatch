const rows = document.querySelector("#ssl-rows");
const state = document.querySelector("#ssl-empty");
const hint = document.querySelector("#ssl-hint");
const pager = document.querySelector("#ssl-pager");
const modal = document.querySelector("#ssl-modal");
const form = document.querySelector("#ssl-form");
const formError = document.querySelector("#ssl-form-error");
const sslTable = document.querySelector(".ssl-table");
const sslBulk = document.querySelector("#ssl-bulk");
const sslMenu = document.querySelector("#ssl-menu");

const query = {
  q: "",
  status: "",
  sort: "name",
  order: "asc",
  page: 1,
  page_size: 25,
};

let sslIndex = {};
let menuSslId = null;

function params() {
  const search = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== "" && value != null) search.set(key, value);
  });
  return search.toString();
}

function showState(title, body, retry) {
  rows.innerHTML = "";
  document.querySelector(".table-wrap").hidden = true;
  state.hidden = false;
  closeSslMenu();
  if (retry) {
    state.innerHTML = emptyState({
      title,
      body,
      actionLabel: t("common.retry"),
      actionId: "ssl-retry",
    });
    document.querySelector("#ssl-retry")?.addEventListener("click", () => load());
    return;
  }
  const canAdd = currentUser && currentUser.role === "admin";
  state.innerHTML = emptyState({
    title,
    body,
    actionLabel: canAdd ? t("ssl.add_first") : "",
    actionId: canAdd ? "empty-add-ssl" : "",
  });
  document.querySelector("#empty-add-ssl")?.addEventListener("click", () => openModal());
}

function rowHtml(item) {
  const admin = currentUser?.role === "admin";
  const sameName = String(item.name || "").toLowerCase() === String(item.host || "").toLowerCase();
  const domain = item.domain_expires
    ? `${escapeHtml(formatSslDate(item.domain_expires))}${
        item.domain_days != null ? `<small>${escapeHtml(sslDaysLabel(item.domain_days))}</small>` : ""
      }`
    : "—";
  return `<tr data-id="${item.id}">
    ${admin ? checkCell(item.id) : ""}
    <td>
      <a class="entity" href="/ssl/${item.id}">${escapeHtml(item.name)}${sameName ? "" : `<small>${escapeHtml(item.host)}</small>`}</a>
    </td>
    <td>${sslProviderHtml(item)}</td>
    <td>${sslPillHtml(item.status)}</td>
    <td>${escapeHtml(sslDaysLabel(item.days_left))}</td>
    <td>${item.not_after ? escapeHtml(formatSslDate(item.not_after)) : "—"}</td>
    <td>${domain}</td>
    <td class="actions">${rowMenuGearHtml(item.id)}</td>
  </tr>`;
}

function sslBulkActions(ids) {
  const admin = currentUser?.role === "admin";
  return bulkBarHtml(ids.length, [
    { id: "refresh", label: t("dash.refresh") },
    ...(admin ? [{ id: "delete", label: t("dash.delete"), danger: true }] : []),
  ]);
}

function syncSslSelection() {
  syncTableSelection(sslTable, sslBulk, sslBulkActions);
}

function render(payload) {
  closeSslMenu();
  document.querySelector('[data-kpi="valid"]').textContent = payload.valid;
  document.querySelector('[data-kpi="expiring"]').textContent = payload.expiring;
  document.querySelector('[data-kpi="expired"]').textContent = payload.expired;
  document.querySelector('[data-kpi="invalid"]').textContent = payload.invalid;
  document.querySelector(".table-wrap").hidden = false;
  state.hidden = true;
  if (!payload.hosts.length) {
    showState(t("ssl.empty_title"), t("ssl.empty_body"));
    document.querySelector("#ssl-count").textContent = t("dash.items", { count: 0 });
    pager.hidden = true;
    sslIndex = {};
    syncSslSelection();
    return;
  }
  const selected = new Set(selectedRowIds(sslTable));
  sslIndex = {};
  rows.innerHTML = payload.hosts
    .map((item) => {
      sslIndex[String(item.id)] = item;
      return rowHtml(item);
    })
    .join("");
  restoreRowChecks(sslTable, selected);
  document.querySelector("#ssl-count").textContent = t("dash.showing", {
    start: (payload.page - 1) * payload.page_size + 1,
    end: (payload.page - 1) * payload.page_size + payload.hosts.length,
    total: payload.filtered_total,
  });
  pager.hidden = payload.pages <= 1;
  document.querySelector("#ssl-page-label").textContent = t("dash.page", { page: payload.page, pages: payload.pages });
  document.querySelector("#ssl-prev").disabled = payload.page <= 1;
  document.querySelector("#ssl-next").disabled = payload.page >= payload.pages;
  document.querySelectorAll(".ssl-table th[data-sort]").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.sort === query.sort);
  });
  syncSslSelection();
}

async function load() {
  hint.textContent = t("ssl.refreshing");
  try {
    const payload = await api(`/api/ssl?${params()}`);
    hint.textContent = payload.last_checked_at
      ? t("ssl.last_check", { time: relTime(payload.last_checked_at) })
      : t("ssl.waiting_check");
    render(payload);
  } catch (error) {
    showState(t("dash.load_error"), error.message, true);
    hint.textContent = t("dash.connection_error");
  }
}

function modalMode(editing) {
  const title = document.querySelector("#ssl-modal-title");
  const submit = document.querySelector("#ssl-form-submit");
  if (title) {
    title.textContent = t(editing ? "ssl.edit_title" : "ssl.add_title");
    title.setAttribute("data-i18n", editing ? "ssl.edit_title" : "ssl.add_title");
  }
  if (submit) {
    submit.textContent = t(editing ? "ssl.save_and_check" : "ssl.add_and_check");
    submit.setAttribute("data-i18n", editing ? "ssl.save_and_check" : "ssl.add_and_check");
  }
}

function openModal(item) {
  modal.hidden = false;
  formError.hidden = true;
  form.reset();
  form.querySelector("[name=id]").value = item?.id || "";
  if (item) {
    const sameName = String(item.name || "").toLowerCase() === String(item.host || "").toLowerCase();
    form.name.value = sameName ? "" : item.name || "";
    form.host.value = item.host || "";
  }
  modalMode(Boolean(item?.id));
  form.querySelector("[name=host]").focus();
}

function closeModal() {
  modal.hidden = true;
  formError.hidden = true;
  modalMode(false);
}

function closeSslMenu() {
  if (!sslMenu) return;
  sslMenu.hidden = true;
  document.querySelectorAll(".ssl-table .row-menu-btn[aria-expanded='true']").forEach((btn) => {
    btn.setAttribute("aria-expanded", "false");
  });
  menuSslId = null;
}

function openSslMenu(button) {
  const id = button.dataset.id;
  const item = sslIndex[String(id)] || { id, host: "", name: "" };
  const admin = currentUser?.role === "admin";
  menuSslId = id;
  sslMenu.innerHTML = `
    <a href="${escapeHtml(httpsSiteUrl(item.host))}" target="_blank" rel="noopener" role="menuitem">${rowMenuIcon("open")} ${t("dash.open_site")}</a>
    <a href="/ssl/${id}" role="menuitem">${rowMenuIcon("details")} ${t("dash.details")}</a>
    <button type="button" role="menuitem" data-action="refresh">${rowMenuIcon("refresh")} ${t("dash.refresh")}</button>
    ${admin ? `<button type="button" role="menuitem" data-action="edit">${rowMenuIcon("edit")} ${t("common.edit")}</button>` : ""}
    ${
      admin
        ? `<div class="menu-sep"></div>
    <button type="button" role="menuitem" class="danger-text" data-action="delete">${rowMenuIcon("trash")} ${t("dash.delete")}</button>`
        : ""
    }
  `;
  sslMenu.hidden = false;
  positionRowMenu(sslMenu, button);
  button.setAttribute("aria-expanded", "true");
}

async function deleteSslHost(id) {
  const item = sslIndex[String(id)];
  const ok = await confirmAction({
    title: t("ssl.confirm_delete_title"),
    body: t("ssl.confirm_delete_body", { name: item?.name || item?.host || t("ssl.hostname") }),
    danger: true,
    confirmLabel: t("dash.delete"),
  });
  if (!ok) return;
  try {
    await api(`/api/ssl/${id}`, { method: "DELETE" });
    await load();
  } catch (error) {
    hint.textContent = error.message;
  }
}

document.querySelector("#open-ssl-modal")?.addEventListener("click", () => openModal());
document.querySelector("#close-ssl-modal")?.addEventListener("click", closeModal);
modal?.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  formError.hidden = true;
  const id = form.querySelector("[name=id]")?.value;
  const body = {
    name: form.name.value.trim() || form.host.value.trim() || null,
    host: form.host.value.trim(),
  };
  try {
    if (id) {
      await api(`/api/ssl/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } else {
      await api("/api/ssl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    }
    closeModal();
    if (!id) query.page = 1;
    await load();
  } catch (error) {
    formError.hidden = false;
    formError.textContent = error.message;
  }
});

document.querySelector("#ssl-search")?.addEventListener("input", () => {
  query.q = document.querySelector("#ssl-search").value.trim();
  query.page = 1;
  load();
});
document.querySelector("#ssl-status-filter")?.addEventListener("change", (event) => {
  query.status = event.target.value;
  query.page = 1;
  load();
});
document.querySelector("#ssl-prev")?.addEventListener("click", () => {
  query.page = Math.max(1, query.page - 1);
  load();
});
document.querySelector("#ssl-next")?.addEventListener("click", () => {
  query.page += 1;
  load();
});
document.querySelector(".ssl-table thead")?.addEventListener("click", (event) => {
  const th = event.target.closest("th[data-sort]");
  if (!th) return;
  if (query.sort === th.dataset.sort) query.order = query.order === "asc" ? "desc" : "asc";
  else {
    query.sort = th.dataset.sort;
    query.order = "asc";
  }
  load();
});

rows?.addEventListener("click", (event) => {
  if (event.target.closest(".col-check")) return;
  const menuBtn = event.target.closest(".row-menu-btn");
  if (!menuBtn) return;
  event.preventDefault();
  event.stopPropagation();
  if (menuSslId === menuBtn.dataset.id && sslMenu && !sslMenu.hidden) {
    closeSslMenu();
    return;
  }
  closeSslMenu();
  openSslMenu(menuBtn);
});

sslMenu?.addEventListener("click", async (event) => {
  const actionBtn = event.target.closest("[data-action]");
  if (!actionBtn || !menuSslId) return;
  const id = menuSslId;
  const action = actionBtn.dataset.action;
  closeSslMenu();
  if (action === "refresh") {
    try {
      await api(`/api/ssl/${id}/refresh`, { method: "POST" });
      await load();
    } catch (error) {
      hint.textContent = error.message;
    }
    return;
  }
  if (action === "edit") {
    const item = sslIndex[String(id)];
    if (item) openModal(item);
    return;
  }
  if (action === "delete") await deleteSslHost(id);
});

document.addEventListener("click", (event) => {
  if (!event.target.closest("#ssl-menu") && !event.target.closest(".ssl-table .row-menu-btn")) {
    closeSslMenu();
  }
});
document.querySelector(".workspace")?.addEventListener("scroll", closeSslMenu, { passive: true });
window.addEventListener("resize", closeSslMenu);

bindTableSelection(sslTable, {
  bar: sslBulk,
  renderActions: sslBulkActions,
  onAction: async (action, ids) => {
    if (action === "delete") {
      if (currentUser?.role !== "admin") return;
      const ok = await confirmAction({
        title: t("ssl.confirm_delete_many_title", { count: ids.length }),
        body: t("ssl.confirm_delete_many", { count: ids.length }),
        danger: true,
        confirmLabel: t("dash.delete"),
      });
      if (!ok) return;
      await runOnIds(ids, (id) => api(`/api/ssl/${id}`, { method: "DELETE" }));
      await load();
      return;
    }
    if (action === "refresh") {
      await runOnIds(ids, (id) => api(`/api/ssl/${id}/refresh`, { method: "POST" }));
      await load();
    }
  },
});

window.sessionReady.then(() => {
  load().catch(() => {});
  setInterval(() => load().catch(() => {}), 30000);
});
window.addEventListener("pingwatch:refresh", () => load().catch(() => {}));
