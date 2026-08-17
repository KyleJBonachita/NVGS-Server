import fs from "node:fs/promises";
import path from "node:path";
import pdf from "pdf-parse";

export const SUPPORTED_KNOWLEDGE_EXTENSIONS = new Set([".md", ".txt", ".pdf"]);

function cleanText(value) {
  return String(value || "")
    .replace(/\r/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function splitLongSection(title, text, maxChars = 2600) {
  if (text.length <= maxChars) {
    return [{ title, text }];
  }

  const paragraphs = text.split(/\n\s*\n/).filter(Boolean);
  const chunks = [];
  let current = "";

  for (const paragraph of paragraphs) {
    if (current && current.length + paragraph.length + 2 > maxChars) {
      chunks.push(current);
      current = "";
    }

    if (paragraph.length > maxChars) {
      if (current) {
        chunks.push(current);
        current = "";
      }
      for (let offset = 0; offset < paragraph.length; offset += maxChars) {
        chunks.push(paragraph.slice(offset, offset + maxChars));
      }
      continue;
    }

    current = current ? `${current}\n\n${paragraph}` : paragraph;
  }

  if (current) {
    chunks.push(current);
  }

  return chunks.map((chunk, index) => ({
    title: chunks.length > 1 ? `${title} (${index + 1})` : title,
    text: chunk,
  }));
}

export function splitIntoSections(fileName, input) {
  const cleaned = cleanText(input);
  if (!cleaned) {
    return [];
  }

  const defaultTitle = path.basename(fileName, path.extname(fileName)).replaceAll(/[_-]+/g, " ");
  const lines = cleaned.split("\n");
  const rawSections = [];
  let currentTitle = defaultTitle;
  let currentLines = [];

  const flush = () => {
    const text = cleanText(currentLines.join("\n"));
    if (text) {
      rawSections.push({ title: currentTitle, text });
    }
    currentLines = [];
  };

  for (const line of lines) {
    const heading = line.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      flush();
      currentTitle = cleanText(heading[1]) || defaultTitle;
    } else {
      currentLines.push(line);
    }
  }
  flush();

  const sections = rawSections.length ? rawSections : [{ title: defaultTitle, text: cleaned }];
  return sections.flatMap((section) => splitLongSection(section.title, section.text));
}

async function readPdf(filePath) {
  const dataBuffer = await fs.readFile(filePath);
  const result = await pdf(dataBuffer);
  return result.text || "";
}

export async function loadKnowledgeDocument(filePath, displayName = path.basename(filePath)) {
  const extension = path.extname(displayName).toLowerCase();
  if (!SUPPORTED_KNOWLEDGE_EXTENSIONS.has(extension)) {
    throw new Error(`Unsupported knowledge file type: ${extension || "unknown"}`);
  }

  const text = extension === ".pdf"
    ? await readPdf(filePath)
    : await fs.readFile(filePath, "utf8");

  return splitIntoSections(displayName, text);
}
