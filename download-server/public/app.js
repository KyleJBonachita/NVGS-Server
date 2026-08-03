"use strict";

const state = {
  files: [],
  filter: "all",
  query: "",
  sort: "newest",
  generatedAt: null,
};

const elements = {
  fileGrid: document.querySelector("[data-file-grid]"),
  empty: document.querySelector("[data-empty]"),
  emptyTitle: document.querySelector("[data-empty-title]"),
  emptyCopy: document.querySelector("[data-empty-copy]"),
  filters: document.querySelector("[data-filters]"),
  search: document.querySelector("[data-search]"),
  sort: document.querySelector("[data-sort]"),
  refresh: document.querySelector("[data-refresh]"),
  fileCount: document.querySelector("[data-file-count]"),
  totalSize: document.querySelector("[data-total-size]"),
  resultCount: document.querySelector("[data-result-count]"),
  lastUpdated: document.querySelector("[data-last-updated]"),
  template: document.querySelector("#file-card-template"),
};

const categoryOrder = [
  "image",
  "document",
  "video",
  "audio",
  "archive",
  "software",
  "other",
];

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return "Unknown size";
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB", "TB"];
  const unitIndex = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / 1024 ** unitIndex;
  const digits = unitIndex === 0 || value >= 10 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[unitIndex]}`;
}

function formatDate(value) {
  const date = new Date(value);
  const now = new Date();
  const sameYear = date.getFullYear() === now.getFullYear();

  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    ...(sameYear ? {} : { year: "numeric" }),
  }).format(date);
}

function setText(selector, text) {
  const element = document.querySelector(selector);
  if (element) element.textContent = text;
}

function applyBranding(payload) {
  document.title = payload.siteName;
  setText("[data-site-name]", payload.siteName);
  setText("[data-footer-brand]", payload.siteName);
  setText("[data-eyebrow]", payload.eyebrow);
  setText("[data-headline]", payload.headline);
  setText("[data-description]", payload.description);
}

function buildFilters() {
  const counts = state.files.reduce(
    (result, file) => {
      result[file.category] = (result[file.category] || 0) + 1;
      return result;
    },
    { all: state.files.length },
  );

  const categories = [
    "all",
    ...categoryOrder.filter((category) => counts[category]),
  ];
  elements.filters.replaceChildren();

  for (const category of categories) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "filter-chip";
    button.classList.toggle("is-active", state.filter === category);
    button.dataset.category = category;
    button.setAttribute(
      "aria-pressed",
      state.filter === category ? "true" : "false",
    );
    button.textContent = `${category === "all" ? "All" : category} · ${counts[category]}`;
    elements.filters.append(button);
  }
}

function filteredFiles() {
  const query = state.query.trim().toLocaleLowerCase();
  const result = state.files.filter((file) => {
    const categoryMatches =
      state.filter === "all" || file.category === state.filter;
    const queryMatches =
      !query ||
      file.name.toLocaleLowerCase().includes(query) ||
      file.folder.toLocaleLowerCase().includes(query) ||
      file.extension.toLocaleLowerCase().includes(query);
    return categoryMatches && queryMatches;
  });

  return result.sort((a, b) => {
    if (state.sort === "name") {
      return a.name.localeCompare(b.name, undefined, {
        numeric: true,
        sensitivity: "base",
      });
    }
    if (state.sort === "size") return b.size - a.size;
    return new Date(b.modified).getTime() - new Date(a.modified).getTime();
  });
}

function createFileCard(file) {
  const card = elements.template.content.firstElementChild.cloneNode(true);
  const preview = card.querySelector(".file-preview");
  const image = preview.querySelector("img");
  const fallback = preview.querySelector(".file-fallback");
  const extension = preview.querySelector(".file-extension");
  const category = preview.querySelector(".category-badge");
  const name = card.querySelector("h3");
  const meta = card.querySelector(".file-meta");
  const folder = card.querySelector(".file-folder");
  const download = card.querySelector(".download-button");

  name.textContent = file.name;
  name.title = file.name;
  extension.textContent = file.extension.slice(0, 7);
  category.textContent = file.category;
  meta.textContent = `${formatBytes(file.size)} · ${formatDate(file.modified)}`;

  if (file.folder && file.folder !== ".") {
    folder.hidden = false;
    folder.textContent = file.folder;
    folder.title = file.folder;
  }

  if (file.previewPath) {
    image.src = `/preview?file=${encodeURIComponent(file.previewPath)}&v=${encodeURIComponent(file.modified)}`;
    image.alt =
      file.previewPath === file.path
        ? `Preview of ${file.name}`
        : `Cover image for ${file.name}`;
    image.hidden = false;
    fallback.hidden = true;
    image.addEventListener(
      "error",
      () => {
        image.hidden = true;
        fallback.hidden = false;
      },
      { once: true },
    );
  }

  download.href = `/download?file=${encodeURIComponent(file.path)}`;
  download.setAttribute("aria-label", `Download ${file.name}`);
  download.addEventListener("click", () => {
    const label = download.querySelector("span");
    label.textContent = "Starting…";
    window.setTimeout(() => {
      label.textContent = "Download";
    }, 1400);
  });

  return card;
}

function renderFiles() {
  const files = filteredFiles();
  elements.fileGrid.replaceChildren(...files.map(createFileCard));
  elements.fileGrid.setAttribute("aria-busy", "false");
  elements.resultCount.textContent = `${files.length} ${
    files.length === 1 ? "result" : "results"
  }`;

  const noLibraryFiles = state.files.length === 0;
  const noSearchResults = !noLibraryFiles && files.length === 0;
  elements.empty.hidden = !(noLibraryFiles || noSearchResults);
  elements.fileGrid.hidden = files.length === 0;

  if (noSearchResults) {
    elements.emptyTitle.textContent = "Nothing matched";
    elements.emptyCopy.textContent =
      "Try a different search term or choose another file type.";
  } else {
    elements.emptyTitle.textContent = "No files yet";
    elements.emptyCopy.innerHTML =
      "Add files to the <strong>downloads</strong> folder, then refresh this page.";
  }
}

function updateSummary() {
  const totalBytes = state.files.reduce((sum, file) => sum + file.size, 0);
  elements.fileCount.textContent = state.files.length.toLocaleString();
  elements.totalSize.textContent = `${formatBytes(totalBytes)} total`;

  if (state.generatedAt) {
    elements.lastUpdated.textContent = `Updated ${new Intl.DateTimeFormat(
      undefined,
      {
        hour: "numeric",
        minute: "2-digit",
      },
    ).format(new Date(state.generatedAt))}`;
  }
}

async function loadFiles({ announce = false } = {}) {
  elements.refresh.classList.add("is-loading");
  elements.refresh.disabled = true;

  try {
    const response = await fetch("/api/files", { cache: "no-store" });
    if (!response.ok) throw new Error(`Server returned ${response.status}`);

    const payload = await response.json();
    state.files = payload.files;
    state.generatedAt = payload.generatedAt;
    applyBranding(payload);
    buildFilters();
    renderFiles();
    updateSummary();

    if (announce) {
      elements.resultCount.textContent = `${state.files.length} files refreshed`;
      window.setTimeout(renderFiles, 1200);
    }
  } catch (error) {
    elements.fileGrid.hidden = true;
    elements.empty.hidden = false;
    elements.emptyTitle.textContent = "Library unavailable";
    elements.emptyCopy.textContent =
      "The server could not read the downloads folder. Try refreshing in a moment.";
    elements.resultCount.textContent = "Could not load files";
    console.error(error);
  } finally {
    elements.refresh.classList.remove("is-loading");
    elements.refresh.disabled = false;
  }
}

elements.filters.addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;

  state.filter = button.dataset.category;
  for (const chip of elements.filters.querySelectorAll(".filter-chip")) {
    const active = chip === button;
    chip.classList.toggle("is-active", active);
    chip.setAttribute("aria-pressed", active ? "true" : "false");
  }
  renderFiles();
});

elements.search.addEventListener("input", (event) => {
  state.query = event.target.value;
  renderFiles();
});

elements.sort.addEventListener("change", (event) => {
  state.sort = event.target.value;
  renderFiles();
});

elements.refresh.addEventListener("click", () => loadFiles({ announce: true }));

document.addEventListener("keydown", (event) => {
  if (
    event.key === "/" &&
    document.activeElement !== elements.search &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey
  ) {
    event.preventDefault();
    elements.search.focus();
  }
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) loadFiles();
});

loadFiles();
