const apiBase = window.location.pathname.includes("/gerry/") ? "/gerry" : "";
const config = { endpoint: `${apiBase}/chat`, health: `${apiBase}/health` };

const messageList = document.getElementById("messageList");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const connectionPill = document.getElementById("connectionPill");
const chips = document.querySelectorAll(".chip");
let contextEntryId = null;
let troubleshootingState = null;

function renderMessage(text, role, meta = "") {
  const item = document.createElement("article");
  item.className = `msg ${role}`;
  item.textContent = text;
  messageList.appendChild(item);
  if (meta) {
    const detail = document.createElement("p");
    detail.className = "message-meta";
    detail.textContent = meta;
    messageList.appendChild(detail);
  }
  messageList.scrollTop = messageList.scrollHeight;
  return item;
}

function clearQuickReplies() {
  messageList.querySelectorAll(".quick-replies").forEach((element) => element.remove());
}

function renderQuickReplies(replies) {
  if (!Array.isArray(replies) || !replies.length) return;
  const container = document.createElement("div");
  container.className = "quick-replies";
  for (const reply of replies) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = reply;
    button.addEventListener("click", () => {
      clearQuickReplies();
      sendMessage(reply);
    });
    container.appendChild(button);
  }
  messageList.appendChild(container);
  messageList.scrollTop = messageList.scrollHeight;
}

async function checkBackendConnection() {
  try {
    const response = await fetch(config.health, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("health check failed");
    const health = await response.json();
    connectionPill.textContent = `Online • ${health.knowledgeDocuments} docs`;
    connectionPill.className = "pill is-online";
  } catch (_error) {
    connectionPill.textContent = "Offline";
    connectionPill.className = "pill is-offline";
  }
}

async function sendMessage(message) {
  sendBtn.disabled = true;
  clearQuickReplies();
  renderMessage(message, "user");
  const pending = renderMessage("Searching saved knowledge…", "bot");
  try {
    const response = await fetch(config.endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, contextEntryId, troubleshootingState }),
    });
    if (!response.ok) throw new Error("chat failed");
    const data = await response.json();
    if (Object.hasOwn(data, "contextEntryId")) contextEntryId = data.contextEntryId;
    if (Object.hasOwn(data, "troubleshootingState")) troubleshootingState = data.troubleshootingState;
    pending.textContent = data.reply || "No response received.";
    const detail = document.createElement("p");
    detail.className = "message-meta";
    const sourceText = data.sources?.length ? ` • ${data.sources.join(", ")}` : "";
    detail.textContent = `${data.usedAI ? "AI fallback used" : "No AI tokens used"}${sourceText}`;
    pending.after(detail);
    renderQuickReplies(data.quickReplies);
  } catch (_error) {
    pending.textContent = "I could not reach the local Chatbot Server.";
  } finally {
    sendBtn.disabled = false;
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  messageInput.value = "";
  await sendMessage(message);
  messageInput.focus();
});

chips.forEach((chip) => chip.addEventListener("click", () => sendMessage(chip.dataset.prompt)));
renderMessage("Hello. I’m Gery. Ask me about setup, troubleshooting, onboarding, or internal workflows.", "bot");
checkBackendConnection();
