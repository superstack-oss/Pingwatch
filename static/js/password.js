document.querySelector("#password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#form-error");
  error.hidden = true;
  const data = Object.fromEntries(new FormData(event.target).entries());
  try {
    await api("/api/auth/password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    window.location.href = "/";
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});
