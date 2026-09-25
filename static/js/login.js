document.querySelector("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const error = document.querySelector("#form-error");
  error.hidden = true;
  const data = Object.fromEntries(new FormData(event.target).entries());
  try {
    const result = await api("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    window.location.href = result.must_change_password ? "/password" : "/";
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
});
