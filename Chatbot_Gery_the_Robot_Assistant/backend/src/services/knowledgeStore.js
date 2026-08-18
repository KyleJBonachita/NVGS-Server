import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import {
  loadKnowledgeDocument,
  SUPPORTED_KNOWLEDGE_EXTENSIONS,
} from "./docsLoader.js";
import { tokenize } from "./retrievalLite.js";

// Version 3 guarantees that the displayed answer is copied verbatim from the
// approved source section. AI may enrich search metadata, but it may never
// replace or shorten the canonical procedure.
const INDEX_VERSION = 3;

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function safeFileName(value) {
  const raw = String(value || "").trim();
  const name = path.basename(raw);
  if (
    !name ||
    name.startsWith(".") ||
    raw.includes("/") ||
    raw.includes("\\") ||
    raw.includes("\0") ||
    name !== raw
  ) {
    return null;
  }
  return name;
}

function deterministicEntry(section, source, sourceId, index) {
  const title = section.title || path.basename(source, path.extname(source));
  const issue = String(section.text || "").match(/(?:^|\n)Issue:\s*(?:\n\s*[-*]\s*)?([^\n]+)/i)?.[1]?.trim();
  const keywords = unique([...tokenize(title), ...tokenize(issue), ...tokenize(section.text)]).slice(0, 50);
  return {
    id: crypto.createHash("sha256").update(`${sourceId}:${index}:${title}`).digest("hex").slice(0, 20),
    sourceId,
    source,
    title,
    sectionTitle: section.sectionTitle || title,
    partIndex: section.partIndex || 1,
    partCount: section.partCount || 1,
    answer: section.text,
    canonicalAnswer: section.sectionText || section.text,
    questions: [
      `What is ${title}?`,
      `How do I fix ${title}?`,
      `${title} is not working`,
      `Explain ${title}`,
      ...(issue ? [`How do I fix ${issue}?`, issue] : []),
    ],
    keywords,
    processingMode: "source-preserved",
  };
}

function parseAiJson(raw) {
  const start = raw.indexOf("{");
  const end = raw.lastIndexOf("}");
  if (start < 0 || end <= start) {
    throw new Error("The preprocessing model did not return JSON.");
  }
  return JSON.parse(raw.slice(start, end + 1));
}

async function aiEnhancedEntry(section, baseEntry, preprocessSection) {
  if (!preprocessSection) {
    return baseEntry;
  }

  try {
    const enhanced = parseAiJson(await preprocessSection(section));
    const questions = Array.isArray(enhanced.questions)
      ? enhanced.questions.map((value) => String(value).trim()).filter(Boolean).slice(0, 8)
      : [];
    const keywords = Array.isArray(enhanced.keywords)
      ? enhanced.keywords.map((value) => String(value).trim().toLowerCase()).filter(Boolean).slice(0, 40)
      : [];

    if (!questions.length) {
      throw new Error("The preprocessing model did not return representative questions.");
    }

    return {
      ...baseEntry,
      questions: unique([...questions, ...baseEntry.questions]),
      keywords: unique([...keywords, ...baseEntry.keywords]).slice(0, 50),
      processingMode: "ai-search-enriched",
    };
  } catch (error) {
    console.warn(`AI preprocessing skipped for ${baseEntry.source} / ${baseEntry.title}: ${error.message}`);
    return { ...baseEntry, processingMode: "ai-fallback-source-preserved" };
  }
}

function processingSummary(entries, aiConfigured) {
  const aiEnrichedSections = entries.filter(
    (entry) => entry.processingMode === "ai-search-enriched",
  ).length;
  const aiFallbackSections = entries.filter(
    (entry) => entry.processingMode === "ai-fallback-source-preserved",
  ).length;
  const sourceOnlySections = entries.length - aiEnrichedSections - aiFallbackSections;

  let processingMode = "source-preserved";
  if (aiConfigured && aiEnrichedSections === entries.length && entries.length) {
    processingMode = "ai-search-enriched";
  } else if (aiConfigured && aiEnrichedSections > 0) {
    processingMode = "partial-ai-search-enrichment";
  } else if (aiConfigured && entries.length) {
    processingMode = "ai-unavailable-source-preserved";
  }

  return {
    processingMode,
    aiEnrichedSections,
    aiFallbackSections,
    sourceOnlySections,
  };
}

async function hashFile(filePath) {
  const contents = await fs.readFile(filePath);
  return crypto.createHash("sha256").update(contents).digest("hex");
}

async function listFiles(directory, origin) {
  try {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile() && SUPPORTED_KNOWLEDGE_EXTENSIONS.has(path.extname(entry.name).toLowerCase()))
      .map((entry) => ({
        origin,
        name: entry.name,
        filePath: path.join(directory, entry.name),
        sourceId: `${origin}:${entry.name}`,
      }));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

export class KnowledgeStore {
  constructor({ bundledDir, dataDir, preprocessSection = null, maxUploadBytes = 25 * 1024 * 1024 }) {
    this.bundledDir = bundledDir;
    this.dataDir = dataDir;
    this.uploadsDir = path.join(dataDir, "uploads");
    this.indexPath = path.join(dataDir, "knowledge-index.json");
    this.preprocessSection = preprocessSection;
    this.maxUploadBytes = maxUploadBytes;
    this.index = { version: INDEX_VERSION, documents: [], entries: [], generatedAt: null };
    this.queue = Promise.resolve();
  }

  async initialize() {
    await fs.mkdir(this.uploadsDir, { recursive: true });
    try {
      const parsed = JSON.parse(await fs.readFile(this.indexPath, "utf8"));
      if (parsed.version === INDEX_VERSION && Array.isArray(parsed.documents) && Array.isArray(parsed.entries)) {
        this.index = parsed;
      }
    } catch (error) {
      if (error.code !== "ENOENT" && !(error instanceof SyntaxError)) throw error;
    }
    return this.refresh();
  }

  runExclusive(operation) {
    const result = this.queue.then(operation, operation);
    this.queue = result.catch(() => undefined);
    return result;
  }

  async refresh() {
    return this.runExclusive(async () => {
      const files = [
        ...(await listFiles(this.bundledDir, "bundled")),
        ...(await listFiles(this.uploadsDir, "uploaded")),
      ];
      const previousDocuments = new Map(this.index.documents.map((document) => [document.sourceId, document]));
      const previousEntries = new Map();
      for (const entry of this.index.entries) {
        if (!previousEntries.has(entry.sourceId)) previousEntries.set(entry.sourceId, []);
        previousEntries.get(entry.sourceId).push(entry);
      }

      const documents = [];
      const entries = [];
      let processed = 0;

      for (const file of files) {
        const [sha256, stat] = await Promise.all([hashFile(file.filePath), fs.stat(file.filePath)]);
        const previous = previousDocuments.get(file.sourceId);
        if (previous?.sha256 === sha256 && previousEntries.has(file.sourceId)) {
          documents.push(previous);
          entries.push(...previousEntries.get(file.sourceId));
          continue;
        }

        const sections = await loadKnowledgeDocument(file.filePath, file.name);
        const documentEntries = [];
        for (let index = 0; index < sections.length; index += 1) {
          const baseEntry = deterministicEntry(sections[index], file.name, file.sourceId, index);
          documentEntries.push(await aiEnhancedEntry(sections[index], baseEntry, this.preprocessSection));
        }

        const summary = processingSummary(documentEntries, Boolean(this.preprocessSection));
        documents.push({
          sourceId: file.sourceId,
          name: file.name,
          origin: file.origin,
          sha256,
          size: stat.size,
          modifiedAt: stat.mtime.toISOString(),
          processedAt: new Date().toISOString(),
          sectionCount: documentEntries.length,
          ...summary,
        });
        entries.push(...documentEntries);
        processed += 1;
      }

      this.index = {
        version: INDEX_VERSION,
        documents,
        entries,
        generatedAt: new Date().toISOString(),
      };
      await this.save();
      const summary = processingSummary(entries, Boolean(this.preprocessSection));
      return {
        processed,
        documents: documents.length,
        entries: entries.length,
        generatedAt: this.index.generatedAt,
        aiEnrichedSections: summary.aiEnrichedSections,
        aiFallbackSections: summary.aiFallbackSections,
        sourceOnlySections: summary.sourceOnlySections,
      };
    });
  }

  async save() {
    const temporaryPath = `${this.indexPath}.tmp`;
    await fs.writeFile(temporaryPath, `${JSON.stringify(this.index, null, 2)}\n`, "utf8");
    await fs.rm(this.indexPath, { force: true });
    await fs.rename(temporaryPath, this.indexPath);
  }

  getEntries() {
    return this.index.entries;
  }

  listDocuments() {
    return this.index.documents.map((document) => ({ ...document }));
  }

  async reprocessAll() {
    this.index = { version: INDEX_VERSION, documents: [], entries: [], generatedAt: null };
    return this.refresh();
  }

  async upload({ name, contentBase64, replace = false }) {
    const filename = safeFileName(name);
    const extension = path.extname(filename || "").toLowerCase();
    if (!filename || !SUPPORTED_KNOWLEDGE_EXTENSIONS.has(extension)) {
      const error = new Error("Only .md, .txt, and .pdf knowledge files are supported.");
      error.statusCode = 400;
      throw error;
    }

    const contents = Buffer.from(String(contentBase64 || ""), "base64");
    if (!contents.length || contents.length > this.maxUploadBytes) {
      const error = new Error(`Knowledge files must be between 1 byte and ${this.maxUploadBytes} bytes.`);
      error.statusCode = 400;
      throw error;
    }

    const destination = path.join(this.uploadsDir, filename);
    try {
      await fs.access(destination);
      if (!replace) {
        const error = new Error("A knowledge file with this name already exists.");
        error.statusCode = 409;
        throw error;
      }
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }

    const temporaryPath = path.join(this.uploadsDir, `.gery-upload-${crypto.randomUUID()}.part`);
    await fs.writeFile(temporaryPath, contents, { mode: 0o600 });
    if (replace) {
      await fs.rm(destination, { force: true });
    }
    await fs.rename(temporaryPath, destination);
    return this.refresh();
  }

  async remove(filename) {
    const safeName = safeFileName(filename);
    if (!safeName) {
      const error = new Error("Invalid knowledge filename.");
      error.statusCode = 400;
      throw error;
    }
    const destination = path.join(this.uploadsDir, safeName);
    try {
      await fs.rm(destination);
    } catch (error) {
      if (error.code === "ENOENT") error.statusCode = 404;
      throw error;
    }
    return this.refresh();
  }
}
