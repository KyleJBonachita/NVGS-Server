const apiBase = window.location.pathname.includes("/gerry/") ? "/gerry" : "";
let adminToken = "";

const authForm = document.getElementById("admin-auth");
const tokenInput = document.getElementById("admin-token");
const uploadForm = document.getElementById("upload-form");
const fileInput = document.getElementById("knowledge-files");
const replaceInput = document.getElementById("replace-existing");
const uploadButton = document.getElementById("upload-button");
const reprocessButton = document.getElementById("reprocess-button");
const statusElement = document.getElementById("knowledge-status");
const lockedStatusElement = document.getElementById("locked-knowledge-status");
const listElement = document.getElementById("knowledge-list");
const protectedSections = document.querySelectorAll("[data-admin-protected]");

function setAdminUnlocked(unlocked) {
  for (const section of protectedSections) {
    section.classList.toggle("is-locked", !unlocked);
    const content = section.querySelector(".protected-content");
    if (content) content.inert = !unlocked;
  }
  uploadButton.disabled = !unlocked;
  reprocessButton.disabled = !unlocked;
}

async function adminFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${adminToken}`);
  const response = await fetch(`${apiBase}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function formatProcessedAt(value) {
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.getTime()) ? "unknown time" : timestamp.toLocaleString();
}

function processingLabel(document) {
  const enriched = Number(document.aiEnrichedSections || 0);
  const fallback = Number(document.aiFallbackSections || 0);
  if (document.processingMode === "ai-search-enriched") {
    return `AI search-enriched (${enriched}/${document.sectionCount}); source SOP preserved`;
  }
  if (document.processingMode === "partial-ai-search-enrichment") {
    return `Partial AI search enrichment (${enriched}/${document.sectionCount}); ${fallback} AI failures; source SOP preserved`;
  }
  if (document.processingMode === "ai-unavailable-source-preserved") {
    return `AI unavailable for ${fallback} sections; source SOP preserved`;
  }
  return "Source SOP preserved; AI not used";
}

function renderDocuments(data) {
  listElement.replaceChildren();
  for (const knowledgeDocument of data.documents) {
    const item = document.createElement("article");
    item.className = "knowledge-item";
    const copy = document.createElement("div");
    const heading = document.createElement("h3");
    heading.textContent = knowledgeDocument.name;
    const meta = document.createElement("p");
    meta.textContent = [
      knowledgeDocument.origin,
      `${knowledgeDocument.sectionCount} preserved SOP sections`,
      `${Number(knowledgeDocument.guidedTroubleshootingSections || 0)} guided troubleshooting flows`,
      formatBytes(knowledgeDocument.size),
      processingLabel(knowledgeDocument),
      `processed ${formatProcessedAt(knowledgeDocument.processedAt)}`,
    ].join(" | ");
    copy.append(heading, meta);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "Remove";
    remove.hidden = knowledgeDocument.origin !== "uploaded";
    remove.addEventListener("click", () => removeDocument(knowledgeDocument.name));
    item.append(copy, remove);
    listElement.appendChild(item);
  }
  const guidedFlows = data.documents.reduce(
    (total, document) => total + Number(document.guidedTroubleshootingSections || 0),
    0,
  );
  statusElement.textContent = `${data.documents.length} documents | ${data.entryCount} preserved SOP sections | ${guidedFlows} guided troubleshooting flows | Upload-time AI ${data.ingestionAiEnabled ? "enabled" : "disabled"}`;
}

async function loadLibrary() {
  const data = await adminFetch("/admin/knowledge");
  renderDocuments(data);
  uploadButton.disabled = false;
  reprocessButton.disabled = false;
}

async function loadPublicStatus() {
  try {
    const response = await fetch(`${apiBase}/health`, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Health check failed");
    const health = await response.json();
    lockedStatusElement.textContent = `Gery has ${health.knowledgeDocuments} documents, ${health.knowledgeEntries} preserved SOP sections, and ${health.guidedTroubleshootingSections || 0} guided troubleshooting flows. Enter the administrator token above to display and manage them.`;
  } catch (_error) {
    lockedStatusElement.textContent = "Gery is not reachable. Start the Chatbot Server, then reload this page.";
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(reader.error || new Error("Could not read file."));
    reader.readAsDataURL(file);
  });
}

async function removeDocument(name) {
  if (!window.confirm(`Remove ${name} from Gery's uploaded knowledge?`)) return;
  statusElement.textContent = `Removing ${name}…`;
  try {
    await adminFetch(`/admin/knowledge/${encodeURIComponent(name)}`, { method: "DELETE" });
    await loadLibrary();
  } catch (error) {
    statusElement.textContent = error.message;
  }
}

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  adminToken = tokenInput.value;
  statusElement.textContent = "Checking administrator access…";
  try {
    await loadLibrary();
    setAdminUnlocked(true);
    tokenInput.value = "";
  } catch (error) {
    adminToken = "";
    setAdminUnlocked(false);
    lockedStatusElement.textContent = error.message;
  }
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = [...fileInput.files];
  if (!files.length || !adminToken) return;
  uploadButton.disabled = true;
  try {
    for (let index = 0; index < files.length; index += 1) {
      const file = files[index];
      statusElement.textContent = `Processing ${file.name} (${index + 1} of ${files.length})…`;
      await adminFetch("/admin/knowledge/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: file.name,
          contentBase64: await fileToBase64(file),
          replace: replaceInput.checked,
        }),
      });
    }
    fileInput.value = "";
    await loadLibrary();
  } catch (error) {
    statusElement.textContent = error.message;
  } finally {
    uploadButton.disabled = !adminToken;
  }
});

reprocessButton.addEventListener("click", async () => {
  reprocessButton.disabled = true;
  statusElement.textContent = "Reprocessing all knowledge. Source procedures will be preserved exactly...";
  try {
    const result = await adminFetch("/admin/knowledge/reprocess", { method: "POST" });
    await loadLibrary();
    const aiResult = result.aiFallbackSections
      ? `${result.aiEnrichedSections} AI-enriched and ${result.aiFallbackSections} AI failures`
      : `${result.aiEnrichedSections} AI-enriched`;
    statusElement.textContent = `Reprocessing completed ${formatProcessedAt(result.generatedAt)}: ${result.documents} documents, ${result.entries} preserved SOP sections, ${result.guidedTroubleshootingSections || 0} guided troubleshooting flows, ${aiResult}.`;
  } catch (error) {
    statusElement.textContent = `Reprocessing failed: ${error.message}`;
  } finally {
    reprocessButton.disabled = !adminToken;
  }
});

loadPublicStatus();
