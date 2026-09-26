const state = {
  kind: location.hash === "#volumes" ? "volumes" : "shares",
  q: "",
  page: 1,
};

function catalogMeta() {
  if (state.kind === "volumes") {
    return {
      title: t("finder.volumes_title"),
      empty: t("finder.empty_volumes"),
      emptyHint: t("finder.empty_volumes_hint"),
      template: "/api/finder/volumes/template.csv",
      list: "/api/finder/volumes",
      upload: "/api/finder/volumes/upload",
      confirm: t("finder.confirm_volumes"),
    };
  }
  return {
    title: t("finder.shares_title"),
    empty: t("finder.empty_shares"),
    emptyHint: t("finder.empty_shares_hint"),
    template: "/api/finder/shares/template.csv",
    list: "/api/finder/shares",
    upload: "/api/finder/shares/upload",
    confirm: t("finder.confirm_shares"),
  };
}

function setKind(kind) {
  state.kind = kind === "volumes" ? "volumes" : "shares";
  state.page = 1;
  history.replaceState(null, "", state.kind === "volumes" ? "#volumes" : "#shares");
  document.querySelectorAll(".finder-tabs button").forEach((button) => {
    button.classList.toggle("active", button.dataset.kind === state.kind);
  });
  document.querySelectorAll(".table-wrap[data-table]").forEach((panel) => {
    panel.hidden = panel.dataset.table !== state.kind;
  });
  const meta = catalogMeta();
  document.querySelector("#finder-template").href = meta.template;
  document.querySelector("#finder-q").placeholder =
    state.kind === "shares" ? t("finder.search_shares") : t("finder.search_volumes");
  document.querySelector("#finder-q").setAttribute(
    "data-i18n-placeholder",
    state.kind === "shares" ? "finder.search_shares" : "finder.search_volumes"
  );
}

function showError(message) {
  const node = document.querySelector("#finder-error");
  if (!message) {
    node.hidden = true;
    node.textContent = "";
    return;
  }
  node.textContent = message;
  node.hidden = false;
}

function renderShares(items) {
  document.querySelector("#share-rows").innerHTML = items
    .map(
      (item, index) => `<tr>
        <td class="seq">${escapeHtml(item.seq_no || index + 1)}</td>
        <td>${escapeHtml(item.name)}</td>
        <td class="path-cell">${escapeHtml(item.path)}</td>
        <td class="issue-cell">${escapeHtml(item.description || "—")}</td>
        <td>${escapeHtml(item.storage || "—")}</td>
      </tr>`
    )
    .join("");
}

function renderVolumes(items) {
  document.querySelector("#volume-rows").innerHTML = items
    .map(
      (item, index) => `<tr>
        <td class="seq">${escapeHtml(item.seq_no || index + 1)}</td>
        <td>${escapeHtml(item.name)}</td>
        <td class="wwn-cell">${escapeHtml(item.wwn)}</td>
        <td class="mono">${escapeHtml(item.size || "—")}</td>
        <td>${escapeHtml(item.storage || "—")}</td>
      </tr>`
    )
    .join("");
}

async function loadCatalog() {
  const meta = catalogMeta();
  const hint = document.querySelector("#finder-hint");
  const empty = document.querySelector("#finder-empty");
  hint.textContent = t("finder.loading");
  showError("");
  try {
    const query = new URLSearchParams();
    if (state.q) query.set("q", state.q);
    query.set("page", String(state.page));
    query.set("page_size", String(PAGE_SIZE));
    const data = await api(`${meta.list}?${query.toString()}`);
    const items = data.items || [];
    if (state.kind === "shares") renderShares(items);
    else renderVolumes(items);
    const table = document.querySelector(`.table-wrap[data-table="${state.kind}"]`);
    if (!items.length) {
      table.hidden = true;
      empty.hidden = false;
      empty.innerHTML = emptyState({
        title: meta.empty,
        body: state.q ? t("finder.no_search") : meta.emptyHint,
      });
      hint.textContent = t("finder.zero");
      setPager(document.querySelector("#finder-pager"), 1, 1);
      return;
    }
    empty.hidden = true;
    table.hidden = false;
    state.page = data.page || 1;
    setPager(document.querySelector("#finder-pager"), state.page, data.pages || 1);
    hint.textContent =
      data.shown === data.total
        ? t("finder.shown_all", { total: data.total, title: meta.title })
        : t("finder.shown", { shown: data.shown, total: data.total, title: meta.title });
  } catch (error) {
    hint.textContent = t("finder.load_error");
    showError(error.message);
    setPager(document.querySelector("#finder-pager"), 1, 1);
  }
}

document.querySelectorAll(".finder-tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    setKind(button.dataset.kind);
    loadCatalog();
  });
});

let searchTimer = null;
document.querySelector("#finder-q").addEventListener("input", (event) => {
  state.q = event.target.value.trim();
  state.page = 1;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadCatalog, 220);
});

document.querySelector("#finder-file").addEventListener("change", async (event) => {
  const input = event.target;
  const file = input.files && input.files[0];
  input.value = "";
  if (!file) return;
  const meta = catalogMeta();
  const ok = await confirmAction({
    title: meta.confirm,
    body: t("common.confirm_delete_body"),
    danger: true,
    confirmLabel: t("common.continue"),
  });
  if (!ok) return;
  showError("");
  const body = new FormData();
  body.append("file", file);
  try {
    const result = await api(meta.upload, { method: "POST", body });
    const extra = result.warnings && result.warnings.length ? ` · ${result.warnings[0]}` : "";
    document.querySelector("#finder-hint").textContent = t("finder.imported", {
      count: result.imported,
      title: meta.title,
    }) + extra;
    await loadCatalog();
  } catch (error) {
    showError(error.message);
  }
});

window.sessionReady.then(() => {
  setKind(state.kind);
  bindPager(document.querySelector("#finder-pager"), {
    prev: () => {
      state.page = Math.max(1, state.page - 1);
      loadCatalog();
    },
    next: () => {
      state.page += 1;
      loadCatalog();
    },
  });
  loadCatalog();
});
window.addEventListener("pingwatch:refresh", loadCatalog);
window.addEventListener("pingwatch:i18n", loadCatalog);
window.addEventListener("hashchange", () => {
  const next = location.hash === "#volumes" ? "volumes" : "shares";
  if (next === state.kind) return;
  setKind(next);
  loadCatalog();
});
