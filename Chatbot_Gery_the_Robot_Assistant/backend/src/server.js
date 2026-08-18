import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import cors from "cors";
import dotenv from "dotenv";
import express from "express";
import { KnowledgeStore } from "./services/knowledgeStore.js";
import { askLmStudio } from "./services/lmStudioClient.js";
import {
  findRelevantSections,
  findStoredAnswer,
  normalizeText,
} from "./services/retrievalLite.js";
import {
  buildPreprocessingPrompts,
  buildSystemPrompt,
  buildUserPrompt,
} from "./utils/promptBuilder.js";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, "..", "..");
const frontendDir = path.join(rootDir, "frontend");
const bundledKnowledgeDir = path.join(rootDir, "knowledge");

function envBoolean(name, fallback = false) {
  const value = process.env[name];
  if (value === undefined) return fallback;
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

function envNumber(name, fallback) {
  const value = Number(process.env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function readSecret(fileName, directValue = "") {
  if (fileName) {
    try {
      return fs.readFileSync(fileName, "utf8").trim();
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
  return directValue.trim();
}

const config = {
  host: process.env.HOST || "0.0.0.0",
  port: envNumber("PORT", 3000),
  dataDir: path.resolve(process.env.GERY_DATA_DIR || path.join(rootDir, "data")),
  maxUploadBytes: envNumber("GERY_MAX_UPLOAD_BYTES", 25 * 1024 * 1024),
  allowedOrigins: String(process.env.GERY_ALLOWED_ORIGINS || "")
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean),
  ingestionAiEnabled: envBoolean("GERY_INGESTION_AI_ENABLED", false),
  allowLiveAi: envBoolean("GERY_ALLOW_LIVE_AI", false),
  aiBaseUrl:
    process.env.GERY_AI_BASE_URL ||
    process.env.LM_STUDIO_BASE_URL ||
    "http://127.0.0.1:1234",
  aiModel:
    process.env.GERY_AI_MODEL ||
    process.env.LM_STUDIO_MODEL ||
    "meta-llama-3.1-8b-instruct",
  aiApiKey: readSecret(
    process.env.GERY_AI_API_KEY_FILE,
    process.env.GERY_AI_API_KEY || ""
  ),
  adminToken: readSecret(
    process.env.GERY_ADMIN_TOKEN_FILE,
    process.env.GERY_ADMIN_TOKEN || ""
  ),
  allowInsecureAdmin: envBoolean("GERY_ALLOW_INSECURE_ADMIN", false),
  maxSections: envNumber("MAX_CONTEXT_SECTIONS", 5),
  maxChars: envNumber("MAX_CONTEXT_CHARS", 8000),
};

async function preprocessSection(section) {
  const prompts = buildPreprocessingPrompts(section);
  return askLmStudio({
    baseUrl: config.aiBaseUrl,
    model: config.aiModel,
    apiKey: config.aiApiKey,
    ...prompts,
    maxTokens: 700,
    temperature: 0.1,
  });
}

const knowledgeStore = new KnowledgeStore({
  bundledDir: bundledKnowledgeDir,
  dataDir: config.dataDir,
  preprocessSection: config.ingestionAiEnabled ? preprocessSection : null,
  maxUploadBytes: config.maxUploadBytes,
});

const app = express();
app.disable("x-powered-by");
app.use((request, response, next) => {
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("X-Frame-Options", "DENY");
  response.setHeader("Referrer-Policy", "same-origin");
  response.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  response.setHeader(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
  );
  next();
});
app.use(cors({
  origin(origin, callback) {
    if (!origin || config.allowedOrigins.includes("*") || config.allowedOrigins.includes(origin)) {
      callback(null, true);
    } else {
      callback(null, false);
    }
  },
}));
app.use(express.json({ limit: `${Math.ceil(config.maxUploadBytes / (1024 * 1024) * 1.4) + 1}mb` }));
app.use(express.static(frontendDir, { index: false, maxAge: "1h" }));

function constantTimeEqual(left, right) {
  const leftBuffer = Buffer.from(String(left || ""));
  const rightBuffer = Buffer.from(String(right || ""));
  return leftBuffer.length === rightBuffer.length && crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

function requireAdmin(request, response, next) {
  if (!config.adminToken) {
    return response.status(503).json({ error: "Knowledge administration is not configured." });
  }
  const authorization = String(request.headers.authorization || "");
  const supplied = authorization.startsWith("Bearer ") ? authorization.slice(7).trim() : "";
  if (!constantTimeEqual(supplied, config.adminToken)) {
    return response.status(401).json({ error: "The knowledge administrator token is invalid." });
  }
  const forwardedProto = String(request.headers["x-forwarded-proto"] || "").split(",", 1)[0].trim();
  const remoteAddress = String(request.socket.remoteAddress || "");
  const hostName = String(request.headers.host || "").split(":", 1)[0].toLowerCase();
  const localRequest =
    ["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(remoteAddress) ||
    ["localhost", "127.0.0.1", "[::1]"].includes(hostName);
  if (!config.allowInsecureAdmin && forwardedProto !== "https" && !localRequest) {
    return response.status(403).json({
      error: "Knowledge administration requires NVGS HTTPS or the Ubuntu server's local browser.",
    });
  }
  return next();
}

function builtInAnswer(message) {
  const normalized = normalizeText(message);
  if (/^(hi|hello|hey|good morning|good afternoon|good evening)$/.test(normalized)) {
    return "Hello! I’m Gery. Ask me about setup, troubleshooting, onboarding, or an internal workflow.";
  }
  if (["help", "what can you do", "how can you help"].includes(normalized)) {
    return "I search the approved internal knowledge library and return a saved answer without calling AI. Try asking about a setup step, error, tool, or workflow.";
  }
  if (["thanks", "thank you", "thankyou"].includes(normalized)) {
    return "You’re welcome. If the issue is still unresolved, ask a follow-up question or file an NVGS ticket.";
  }
  return null;
}

app.get("/health", (_request, response) => {
  response.json({
    ok: true,
    service: "gery-chatbot",
    knowledgeDocuments: knowledgeStore.listDocuments().length,
    knowledgeEntries: knowledgeStore.getEntries().length,
    ingestionAiEnabled: config.ingestionAiEnabled,
    liveAiEnabled: config.allowLiveAi,
  });
});

app.post("/chat", async (request, response) => {
  const message = String(request.body?.message || "").trim();
  if (!message || message.length > 1200) {
    return response.status(400).json({ reply: "Please enter a question between 1 and 1,200 characters." });
  }

  const builtIn = builtInAnswer(message);
  if (builtIn) {
    return response.json({ reply: builtIn, sources: [], answerMode: "built-in", usedAI: false });
  }

  const contextEntryId = String(request.body?.contextEntryId || "").trim().slice(0, 100) || null;
  const stored = findStoredAnswer(message, knowledgeStore.getEntries(), { contextEntryId });
  if (stored) {
    return response.json({
      reply: stored.reply,
      sources: stored.sources,
      answerMode: stored.answerMode,
      usedAI: false,
      contextEntryId: stored.entryId,
    });
  }

  if (config.allowLiveAi) {
    const matches = findRelevantSections(
      message,
      knowledgeStore.getEntries(),
      config.maxSections,
      config.maxChars
    );
    try {
      const reply = await askLmStudio({
        baseUrl: config.aiBaseUrl,
        model: config.aiModel,
        apiKey: config.aiApiKey,
        systemPrompt: buildSystemPrompt(),
        userPrompt: buildUserPrompt(message, matches),
      });
      return response.json({
        reply: reply || "I am not sure based on current internal documentation. Please file an NVGS ticket or contact the Tech Team or your Team Lead.",
        sources: [...new Set(matches.map((item) => item.source))],
        answerMode: "live-ai-fallback",
        usedAI: true,
      });
    } catch (error) {
      console.error(`Live AI fallback failed: ${error.message}`);
    }
  }

  return response.json({
    reply: "I am not sure based on current internal documentation. Please file an NVGS ticket or contact the Tech Team or your Team Lead.",
    sources: [],
    answerMode: "no-match",
    usedAI: false,
    contextEntryId: null,
  });
});

app.get("/admin/knowledge", requireAdmin, (_request, response) => {
  response.json({
    documents: knowledgeStore.listDocuments(),
    entryCount: knowledgeStore.getEntries().length,
    ingestionAiEnabled: config.ingestionAiEnabled,
    supportedTypes: ["md", "txt", "pdf"],
    maxUploadBytes: config.maxUploadBytes,
  });
});

app.post("/admin/knowledge/upload", requireAdmin, async (request, response) => {
  try {
    const result = await knowledgeStore.upload({
      name: request.body?.name,
      contentBase64: request.body?.contentBase64,
      replace: request.body?.replace === true,
    });
    response.status(201).json({ ok: true, ...result });
  } catch (error) {
    response.status(error.statusCode || 500).json({ error: error.message || "Knowledge upload failed." });
  }
});

app.post("/admin/knowledge/reprocess", requireAdmin, async (_request, response) => {
  try {
    response.json({ ok: true, ...(await knowledgeStore.reprocessAll()) });
  } catch (error) {
    response.status(500).json({ error: error.message || "Knowledge processing failed." });
  }
});

app.delete("/admin/knowledge/:filename", requireAdmin, async (request, response) => {
  try {
    response.json({ ok: true, ...(await knowledgeStore.remove(request.params.filename)) });
  } catch (error) {
    response.status(error.statusCode || 500).json({ error: error.message || "Knowledge removal failed." });
  }
});

app.get(["/admin", "/admin/"], (_request, response) => {
  response.sendFile(path.join(frontendDir, "admin.html"));
});

app.get(["/", "/index.html"], (_request, response) => {
  response.sendFile(path.join(frontendDir, "index.html"));
});

app.get("/favicon.ico", (_request, response) => {
  response.status(204).end();
});

app.use((_request, response) => {
  response.status(404).json({ error: "Page not found." });
});

async function start() {
  const result = await knowledgeStore.initialize();
  app.listen(config.port, config.host, () => {
    console.log(`Gery Chatbot Server running at http://${config.host}:${config.port}`);
    console.log(`Knowledge: ${result.documents} documents / ${result.entries} stored answers`);
    console.log(`Upload-time AI preprocessing: ${config.ingestionAiEnabled ? "enabled" : "disabled"}`);
    console.log(`Live chat AI fallback: ${config.allowLiveAi ? "enabled" : "disabled"}`);
  });
}

start().catch((error) => {
  console.error("Failed to start Gery:", error);
  process.exit(1);
});
