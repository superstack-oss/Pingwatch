const root = document.querySelector(".detail");
const id = root.dataset.sslId;
let current = null;
let sslLookupInFlight = false;

function statusDot(status) {
  if (status === "Valid") return "online";
  if (status === "Expiring") return "warning";
  if (status === "Expired" || status === "Invalid") return "offline";
  return "unknown";
}

function renderHost(item) {
  current = item;
  document.querySelector("#ssl-host-name").textContent = item.name;
  document.querySelector("#ssl-host-target").textContent = item.host;
  document.querySelector("#ssl-host-provider").textContent = item.provider || item.issuer || t("ssl.cert");
  document.querySelector("#ssl-host-dot").className = `live-dot ${statusDot(item.status)}`;
  document.title = `${item.name} · Pingwatch`;
  const open = document.querySelector("#ssl-host-open");
  if (open) open.href = httpsSiteUrl(item.host);
  const report = document.querySelector("#ssl-host-report");
  if (report) report.href = `/api/ssl/${item.id}/report.pdf`;
  renderSslCards(item.ssl, item.host);
}

async function lookupSsl() {
  if (sslLookupInFlight) return;
  sslLookupInFlight = true;
  const buttons = [document.querySelector("#ssl-refresh"), document.querySelector("#ssl-host-refresh")];
  buttons.forEach((button) => {
    if (button) button.disabled = true;
  });
  try {
    const item = await api(`/api/ssl/${id}/refresh`, { method: "POST" });
    renderHost(item);
  } catch (error) {
    const box = document.querySelector("#ssl-host-error");
    box.hidden = false;
    box.textContent = error.message;
  } finally {
    sslLookupInFlight = false;
    buttons.forEach((button) => {
      if (button) button.disabled = false;
    });
  }
}

async function load() {
  const item = await api(`/api/ssl/${id}`);
  renderHost(item);
  if (sslNeedsLookup(item.ssl)) await lookupSsl();
}

document.querySelector("#ssl-refresh")?.addEventListener("click", () => lookupSsl());
document.querySelector("#ssl-host-refresh")?.addEventListener("click", () => lookupSsl());
document.querySelector("#ssl-host-remove")?.addEventListener("click", async () => {
  const name = current?.name || current?.host || t("ssl.hostname");
  const ok = await confirmAction({
    title: t("ssl.confirm_delete_title"),
    body: t("ssl.confirm_delete_body", { name }),
    danger: true,
    confirmLabel: t("dash.delete"),
  });
  if (!ok) return;
  await api(`/api/ssl/${id}`, { method: "DELETE" });
  window.location.href = "/ssl";
});

window.sessionReady.then(() => {
  load().catch((error) => {
    document.querySelector("#ssl-host-name").textContent = "Unable to load certificate";
    const box = document.querySelector("#ssl-host-error");
    box.hidden = false;
    box.textContent = error.message;
  });
});
window.addEventListener("pingwatch:refresh", () => load().catch(() => {}));
