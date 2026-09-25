let notificationPage = 1;
let notificationIndex = {};
const notificationPager = document.querySelector("#notification-pager");
const notifModal = document.querySelector("#notif-modal");

function notificationLine(item) {
  return (item.short_description || item.title || "—").replace(/\s+/g, " ").trim();
}

function closeNotification() {
  if (!notifModal || notifModal.hidden) return;
  notifModal.hidden = true;
  document.querySelectorAll("#notification-rows tr.is-open").forEach((row) => row.classList.remove("is-open"));
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
}

function openNotification(item) {
  if (!item || !notifModal) return;
  const title = document.querySelector("#notif-modal-title");
  const meta = document.querySelector("#notif-modal-meta");
  const short = document.querySelector("#notif-modal-short");
  const body = document.querySelector("#notif-modal-body");
  if (title) title.textContent = item.title || t("notif.item");
  if (meta) {
    meta.textContent = t("notif.posted", {
      actor: item.actor || t("incidents.actor_system"),
      time: formatStamp(item.created_at),
    });
  }
  const summary = (item.short_description || "").trim();
  const full = (item.body || "").trim();
  if (short) {
    short.textContent = summary;
    short.hidden = !summary || summary === full;
  }
  if (body) body.textContent = full || summary || "—";
  notifModal.hidden = false;
  const hash = `#${item.id}`;
  if (location.hash !== hash) history.replaceState(null, "", `${location.pathname}${location.search}${hash}`);
  document.querySelectorAll("#notification-rows tr[data-id]").forEach((row) => {
    row.classList.toggle("is-open", row.dataset.id === String(item.id));
  });
}

async function openFromHash() {
  const raw = (location.hash || "").replace(/^#/, "");
  const id = raw.replace(/^announcement-/, "");
  if (!id) {
    closeNotification();
    return;
  }
  let item = notificationIndex[id];
  if (!item) {
    try {
      const data = await api(`/api/announcements/${id}`);
      item = data.announcement;
      if (item) notificationIndex[String(item.id)] = item;
    } catch (err) {
      return;
    }
  }
  if (item) openNotification(item);
}

async function loadNotifications() {
  try {
    await api("/api/announcements/read-all", { method: "POST" });
  } catch (err) {
    /* still render the list */
  }
  if (typeof refreshNotifications === "function") refreshNotifications();
  const data = await api(`/api/announcements?page=${notificationPage}&page_size=${PAGE_SIZE}`);
  const empty = document.querySelector("#notification-empty");
  const wrap = document.querySelector(".table-wrap");
  const rows = document.querySelector("#notification-rows");
  notificationIndex = {};
  if (!data.announcements.length) {
    rows.innerHTML = "";
    if (wrap) wrap.hidden = true;
    setPager(notificationPager, 1, 1);
    empty.hidden = false;
    empty.innerHTML = emptyState({
      title: t("notif.none"),
      body: t("notif.none_body"),
    });
    if (location.hash) await openFromHash();
    return;
  }
  empty.hidden = true;
  if (wrap) wrap.hidden = false;
  rows.innerHTML = data.announcements
    .map((item) => {
      notificationIndex[String(item.id)] = item;
      const line = notificationLine(item);
      return `<tr data-id="${item.id}" tabindex="0">
        <td class="notif-line" title="${escapeHtml(line)}">${escapeHtml(line)}</td>
        <td class="col-time">${formatStamp(item.created_at)}</td>
      </tr>`;
    })
    .join("");
  notificationPage = data.page || 1;
  setPager(notificationPager, notificationPage, data.pages || 1);
  if (location.hash) await openFromHash();
}

document.querySelector("#notification-rows")?.addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-id]");
  if (!row) return;
  const item = notificationIndex[row.dataset.id];
  if (item) openNotification(item);
});
document.querySelector("#notification-rows")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" && event.key !== " ") return;
  const row = event.target.closest("tr[data-id]");
  if (!row) return;
  event.preventDefault();
  const item = notificationIndex[row.dataset.id];
  if (item) openNotification(item);
});
document.querySelector("#notif-modal-close")?.addEventListener("click", closeNotification);
notifModal?.addEventListener("click", (event) => {
  if (event.target === notifModal) closeNotification();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeNotification();
});
window.addEventListener("hashchange", () => {
  if (location.hash) openFromHash();
  else closeNotification();
});

bindPager(notificationPager, {
  prev: () => {
    notificationPage = Math.max(1, notificationPage - 1);
    loadNotifications();
  },
  next: () => {
    notificationPage += 1;
    loadNotifications();
  },
});

window.sessionReady.then(loadNotifications);
window.addEventListener("pingwatch:refresh", loadNotifications);
window.addEventListener("pingwatch:i18n", loadNotifications);
