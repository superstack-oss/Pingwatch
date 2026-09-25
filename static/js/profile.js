function formatUserCode(id) {
  return `PW-${String(id ?? 0).padStart(5, "0")}`;
}

function accountStatus(user) {
  if (!user) return "—";
  if (user.status && user.status !== "active") return user.status;
  return user.approved_by ? t("profile.approved") : t("profile.active");
}

function fillProfile(user) {
  if (!user) return;
  const role = user.role === "admin" ? t("nav.admin_role") : t("nav.user_role");
  const status = accountStatus(user);
  const code = formatUserCode(user.id);
  paintAvatar(document.querySelector("#profile-avatar"), user);
  document.querySelector("#profile-name").textContent = user.name || user.username;
  document.querySelector("#profile-role").textContent = role;
  const pill = document.querySelector("#profile-status-pill");
  pill.textContent = status;
  pill.classList.toggle("ok", user.status === "active");
  document.querySelector("#profile-userid").textContent = code;
  document.querySelector("#hero-email-text").textContent = user.email || "—";
  document.querySelector("#hero-phone-text").textContent = user.phone || "—";
  document.querySelector("#hero-since-text").textContent = formatTenureCompact(user.created_at);
  document.querySelector("#hero-status").textContent = status;
  document.querySelector("#hero-login").textContent = user.last_login_at ? relTime(user.last_login_at) : "—";
  const version = document.querySelector("#app-version")?.textContent || "1.1.0";
  document.querySelector("#hero-version").textContent = version.startsWith("v") ? version : `v${version}`;

  document.querySelector("#fact-username").textContent = user.username || "—";
  document.querySelector("#fact-name").textContent = user.name || "—";
  document.querySelector("#fact-email").textContent = user.email || "—";
  document.querySelector("#fact-role").textContent = role;
  document.querySelector("#fact-phone").textContent = user.phone || "—";
  document.querySelector("#fact-id").textContent = code;
  document.querySelector("#nest-phone").textContent = user.phone || "—";
  document.querySelector("#nest-since").textContent = formatTenure(user.created_at);
  document.querySelector("#approver-name").textContent = user.approved_by?.name || "—";
  document.querySelector("#approver-email").textContent = user.approved_by?.email || "—";

  document.querySelector("#ov-status").textContent = status;
  document.querySelector("#ov-reviewer").textContent = user.approved_by?.name || "—";
  document.querySelector("#ov-phone").textContent = user.phone || "—";
  document.querySelector("#fact-created").textContent = formatStamp(user.created_at);
  document.querySelector("#fact-updated").textContent = formatStamp(user.updated_at || user.created_at);
  document.querySelector("#fact-password-updated").textContent = formatStamp(user.password_updated_at || user.created_at);

  const form = document.querySelector("#profile-form");
  form.name.value = user.name || "";
  form.email.value = user.email || "";
  form.phone.value = user.phone || "";
  document.querySelector("#edit-username").value = user.username || "";
  document.querySelector("#edit-role").value = role;
  document.querySelector("#edit-id").value = code;
}

function setEditing(on) {
  document.querySelector("#profile-view").hidden = on;
  document.querySelector("#profile-form").hidden = !on;
  document.querySelector("#profile-edit-label").textContent = on ? t("common.close") : t("profile.edit");
  if (on) {
    document.querySelector("#profile-error").hidden = true;
    document.querySelector("#profile-ok").hidden = true;
  }
}

function showPanel(id) {
  document.querySelectorAll(".head-tab").forEach((btn) => btn.classList.toggle("active", btn.dataset.panel === id));
  document.querySelector("#panel-profile").hidden = id !== "profile";
  document.querySelector("#panel-password").hidden = id !== "password";
  if (location.hash !== `#${id}`) history.replaceState(null, "", `#${id}`);
}

window.sessionReady.then((user) => {
  fillProfile(user);
  const tab = location.hash === "#password" ? "password" : "profile";
  showPanel(tab);
});
window.addEventListener("pingwatch:i18n", () => {
  if (currentUser) fillProfile(currentUser);
});

document.querySelector(".profile-head-tabs").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-panel]");
  if (btn) showPanel(btn.dataset.panel);
});

document.querySelector("#profile-edit").addEventListener("click", () => {
  const form = document.querySelector("#profile-form");
  setEditing(form.hidden);
});

document.querySelector("#profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#profile-error");
  const ok = document.querySelector("#profile-ok");
  error.hidden = true;
  ok.hidden = true;
  const form = event.target;
  try {
    const result = await api("/api/auth/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: form.name.value,
        email: form.email.value,
        phone: form.phone.value,
      }),
    });
    currentUser = result.user;
    fillProfile(result.user);
    paintAvatar(document.querySelector("#nav-initials"), result.user);
    document.querySelector("#nav-user").textContent = result.user.name || result.user.username;
    setEditing(false);
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});

document.querySelector("#password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#password-error");
  const ok = document.querySelector("#password-ok");
  error.hidden = true;
  ok.hidden = true;
  const form = event.target;
  if (form.new_password.value !== form.confirm_password.value) {
    error.textContent = t("profile.password_mismatch");
    error.hidden = false;
    return;
  }
  try {
    const result = await api("/api/auth/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: form.current_password.value,
        new_password: form.new_password.value,
      }),
    });
    form.reset();
    if (result?.user) {
      currentUser = result.user;
      fillProfile(result.user);
    }
    ok.hidden = false;
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});
