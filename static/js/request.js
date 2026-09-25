document.querySelector("#request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#form-error");
  const ok = document.querySelector("#form-ok");
  error.hidden = true;
  ok.hidden = true;
  const data = Object.fromEntries(new FormData(event.target).entries());
  try {
    await api("/api/auth/request-access", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    event.target.reset();
    ok.hidden = false;
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});
