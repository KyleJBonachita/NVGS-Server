(function () {
  "use strict";

  const form = document.getElementById("local-login-form");
  const button = document.getElementById("local-login-button");
  const errorBox = document.getElementById("login-error");

  function csrfToken() {
    const input = form.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function messageFrom(data) {
    if (!data) return "Sign-in failed. Please try again.";
    if (typeof data === "string") return data;
    if (Array.isArray(data.non_field_errors)) return data.non_field_errors.join(" ");
    if (Array.isArray(data.detail)) return data.detail.join(" ");
    return data.detail || data.error || "The email or password was not accepted.";
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    errorBox.hidden = true;
    button.disabled = true;
    button.textContent = "Signing in…";

    try {
      const response = await fetch("/api/auth/login/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify({
          email: document.getElementById("login-email").value,
          password: document.getElementById("login-password").value,
        }),
      });
      const data = await response.json().catch(function () { return null; });
      if (!response.ok) throw new Error(messageFrom(data));
      window.location.assign("/tickets/");
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
      button.disabled = false;
      button.textContent = "Sign in with NVGS password";
    }
  });
}());
