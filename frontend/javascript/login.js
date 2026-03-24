const loginForm = document.getElementById("login-form");
const errorBox = document.createElement("div");
errorBox.className = "error";

function showError(msg) {
  errorBox.textContent = msg;
  if (!loginForm.contains(errorBox)) {
    loginForm.appendChild(errorBox);
  }
}

function wirePasswordToggles(formRoot) {
  const toggles = formRoot.querySelectorAll(".toggle-password");
  toggles.forEach((btn) => {
    const targetId = btn.getAttribute("data-target");
    if (!targetId) return;
    const input = formRoot.querySelector(`#${targetId}`);
    if (!input) return;

    btn.addEventListener("click", () => {
      const isHidden = input.type === "password";
      input.type = isHidden ? "text" : "password";
      btn.textContent = isHidden ? "Hide" : "Show";
    });
  });
}

if (loginForm) {
  wirePasswordToggles(loginForm);

  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.remove?.();

    const email = loginForm.email.value.trim();
    const password = loginForm.password.value.trim();

    if (!email || !password) {
      showError("Email and password are required.");
      return;
    }

    const formData = new FormData();
    formData.append("email", email);
    formData.append("password", password);

    try {
      const res = await fetch("/login", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Login failed");
      }

      window.location.href = data.redirect || "/index.html";
    } catch (err) {
      showError(err.message || "Login failed");
    }
  });
}
