function markTheme() {
  document.querySelectorAll(".theme-choice").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.theme === currentTheme());
  });
}

window.sessionReady.then((user) => {
  if (!user) return;
  const form = document.querySelector("#prefs-form");
  form.timezone.value = user.timezone || window.PINGWATCH_TZ || "UTC";
  markTheme();
});

document.querySelectorAll(".theme-choice").forEach((btn) => {
  btn.addEventListener("click", () => {
    applyTheme(btn.dataset.theme);
    markTheme();
  });
});

document.querySelector("#prefs-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#prefs-error");
  const ok = document.querySelector("#prefs-ok");
  error.hidden = true;
  ok.hidden = true;
  try {
    const result = await api("/api/auth/preferences", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ timezone: event.target.timezone.value.trim() }),
    });
    window.PINGWATCH_TZ = result.settings?.timezone || event.target.timezone.value.trim();
    tickClock();
    ok.hidden = false;
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});

window.addEventListener("pingwatch:refresh", () => {
  window.sessionReady.then((user) => {
    if (!user) return;
    document.querySelector("#prefs-form").timezone.value = user.timezone || window.PINGWATCH_TZ || "UTC";
    markTheme();
  });
});
