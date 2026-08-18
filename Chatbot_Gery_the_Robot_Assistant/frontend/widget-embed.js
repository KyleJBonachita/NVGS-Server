(function () {
  if (document.querySelector("[data-gery-widget]")) return;

  const scriptUrl = document.currentScript?.src
    ? new URL(document.currentScript.src)
    : new URL(window.location.href);
  const inferredBase = scriptUrl.href.replace(/\/widget-embed\.js(?:\?.*)?$/, "").replace(/\/$/, "");
  const defaults = {
    apiBase: inferredBase,
    title: "Gery Robot Assistant",
    welcome: "Hi, I’m Gery. Ask me about setup, troubleshooting, onboarding, or an internal workflow.",
  };
  const cfg = Object.assign({}, defaults, window.GeryWidgetConfig || {});
  const apiBase = String(cfg.apiBase || "").replace(/\/$/, "");

  const stylesheetId = "gery-widget-styles";
  if (!document.getElementById(stylesheetId)) {
    const stylesheet = document.createElement("link");
    stylesheet.id = stylesheetId;
    stylesheet.rel = "stylesheet";
    stylesheet.href = `${apiBase}/widget.css?v=2`;
    document.head.appendChild(stylesheet);
  }

  const root = document.createElement("div");
  root.className = "gery-launcher";
  root.dataset.geryWidget = "";
  root.innerHTML = `
    <button class="gery-button" type="button" aria-label="Open Gery Robot Assistant" aria-expanded="false">
      <img alt="" src="${apiBase}/assets/gerry-logo.jpg">
      <span class="gery-online" aria-hidden="true"></span>
    </button>
    <section class="gery-panel" role="dialog" aria-label="Gery Robot Assistant">
      <header class="gery-header">
        <img alt="" src="${apiBase}/assets/gerry-logo.jpg">
        <span class="gery-heading"><span class="gery-title"></span><span class="gery-subtitle">Saved knowledge • token-free answers</span></span>
        <button class="gery-close" type="button" aria-label="Close Gery">Close</button>
      </header>
      <div class="gery-log" aria-live="polite"></div>
      <form class="gery-form" autocomplete="off">
        <input class="gery-input" maxlength="1200" placeholder="Ask Gery a question…" required>
        <button class="gery-send" type="submit">Send</button>
      </form>
    </section>
  `;
  document.body.appendChild(root);

  const button = root.querySelector(".gery-button");
  const panel = root.querySelector(".gery-panel");
  const closeButton = root.querySelector(".gery-close");
  const log = root.querySelector(".gery-log");
  const form = root.querySelector(".gery-form");
  const input = root.querySelector(".gery-input");
  const sendButton = root.querySelector(".gery-send");
  let contextEntryId = null;
  root.querySelector(".gery-title").textContent = cfg.title;

  function addMessage(text, role, meta = "") {
    const element = document.createElement("div");
    element.className = `gery-message ${role}`;
    element.textContent = text;
    log.appendChild(element);
    if (meta) {
      const metaElement = document.createElement("div");
      metaElement.className = "gery-meta";
      metaElement.textContent = meta;
      log.appendChild(metaElement);
    }
    log.scrollTop = log.scrollHeight;
    return element;
  }

  async function ask(message) {
    addMessage(message, "user");
    const pending = addMessage("Searching saved knowledge…", "bot");
    sendButton.disabled = true;
    try {
      const response = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, contextEntryId }),
      });
      if (!response.ok) throw new Error("Chat request failed");
      const data = await response.json();
      if (Object.hasOwn(data, "contextEntryId")) contextEntryId = data.contextEntryId;
      pending.textContent = data.reply || "No response received.";
      const sources = Array.isArray(data.sources) ? data.sources.filter(Boolean) : [];
      const label = data.usedAI ? "AI fallback used" : "No AI tokens used";
      const meta = sources.length ? `${label} • Source: ${sources.join(", ")}` : label;
      const metaElement = document.createElement("div");
      metaElement.className = "gery-meta";
      metaElement.textContent = meta;
      pending.after(metaElement);
    } catch (_error) {
      pending.textContent = "Gery became unavailable. Please try again after the Chatbot Server is restarted.";
    } finally {
      sendButton.disabled = false;
      input.focus();
    }
  }

  function setOpen(open) {
    panel.classList.toggle("is-open", open);
    button.setAttribute("aria-expanded", String(open));
    if (open && !log.children.length) addMessage(cfg.welcome, "bot");
    if (open) input.focus();
  }

  button.addEventListener("click", () => setOpen(!panel.classList.contains("is-open")));
  closeButton.addEventListener("click", () => setOpen(false));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panel.classList.contains("is-open")) setOpen(false);
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    await ask(message);
  });
})();
