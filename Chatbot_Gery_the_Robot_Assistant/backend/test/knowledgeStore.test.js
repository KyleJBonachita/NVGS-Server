import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { KnowledgeStore } from "../src/services/knowledgeStore.js";
import { findStoredAnswer } from "../src/services/retrievalLite.js";

const projectKnowledgeDir = fileURLToPath(new URL("../../knowledge", import.meta.url));

test("bundled VIVE knowledge stays together as an eight-check guided SOP", async (context) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gery-bundled-vive-"));
  const dataDir = path.join(root, "data");
  context.after(() => fs.rm(root, { recursive: true, force: true }));

  const store = new KnowledgeStore({ bundledDir: projectKnowledgeDir, dataDir });
  const result = await store.initialize();
  const vive = store.getEntries().find((entry) => /VIVE trackers are detected as 0/i.test(entry.title));

  assert.ok(vive);
  assert.equal(vive.troubleshootingSteps.length, 8);
  assert.match(vive.canonicalAnswer, /conda activate dexcap/);
  assert.match(vive.canonicalAnswer, /ipconfig \/flushdns/);
  assert.doesNotMatch(vive.canonicalAnswer, /tracker ID/i);
  assert.ok(result.guidedTroubleshootingSections >= 2);

  const answer = findStoredAnswer("VIVE trackers not working", store.getEntries());
  assert.equal(answer?.entryId, vive.id);
});

test("indexes bundled and uploaded knowledge and persists reusable answers", async (context) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gery-store-"));
  const bundledDir = path.join(root, "bundled");
  const dataDir = path.join(root, "data");
  await fs.mkdir(bundledDir);
  await fs.writeFile(path.join(bundledDir, "setup.md"), "# Tracker setup\nStart the VIVE Server first.");
  context.after(() => fs.rm(root, { recursive: true, force: true }));

  const store = new KnowledgeStore({ bundledDir, dataDir });
  const initial = await store.initialize();
  assert.equal(initial.documents, 1);
  assert.equal(store.getEntries()[0].processingMode, "source-preserved");
  assert.ok(store.getEntries()[0].questions.some((question) => /not working/i.test(question)));

  await store.upload({
    name: "recovery.txt",
    contentBase64: Buffer.from("Restart the collector service after checking the cable.").toString("base64"),
  });
  assert.equal(store.listDocuments().length, 2);
  assert.equal(store.listDocuments().find((item) => item.name === "recovery.txt").origin, "uploaded");

  const reloaded = new KnowledgeStore({ bundledDir, dataDir });
  const result = await reloaded.initialize();
  assert.equal(result.processed, 0);
  assert.equal(reloaded.getEntries().length, 2);
});

test("rejects unsupported and duplicate knowledge uploads", async (context) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gery-store-"));
  const bundledDir = path.join(root, "bundled");
  const dataDir = path.join(root, "data");
  await fs.mkdir(bundledDir);
  context.after(() => fs.rm(root, { recursive: true, force: true }));

  const store = new KnowledgeStore({ bundledDir, dataDir });
  await store.initialize();
  await assert.rejects(
    store.upload({ name: "unsafe.exe", contentBase64: Buffer.from("x").toString("base64") }),
    /Only .md, .txt, and .pdf/,
  );
  await store.upload({ name: "guide.txt", contentBase64: Buffer.from("first").toString("base64") });
  await assert.rejects(
    store.upload({ name: "guide.txt", contentBase64: Buffer.from("second").toString("base64") }),
    /already exists/,
  );
});

test("approved troubleshooting routes VIVE and camera questions correctly", async (context) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gery-approved-"));
  const dataDir = path.join(root, "data");
  const bundledDir = path.join(root, "bundled");
  await fs.mkdir(bundledDir);
  await fs.writeFile(
    path.join(bundledDir, "troubleshooting.md"),
    [
      "# Troubleshooting",
      "## VIVE tracker still detected as 0",
      "1. Restart tracker service.",
      "2. Re-pair tracker in device manager.",
      "3. Re-run detection command.",
      "4. Validate tracker ID in telemetry output.",
      "## Teleop not working and camera is black",
      "1. Check camera device permissions.",
      "2. Restart camera stream process.",
      "3. Relaunch teleop stack.",
    ].join("\n"),
  );
  context.after(() => fs.rm(root, { recursive: true, force: true }));

  const store = new KnowledgeStore({ bundledDir, dataDir });
  await store.initialize();

  const vive = findStoredAnswer("VIVE is not working", store.getEntries());
  const camera = findStoredAnswer("My camera feed is black", store.getEntries());
  assert.match(vive?.reply, /restart tracker service/i);
  assert.match(vive?.reply, /re-pair tracker/i);
  assert.match(camera?.reply, /camera device permissions/i);
  assert.doesNotMatch(vive?.reply, /relaunch teleop stack/i);
});

test("AI enrichment can never replace or shorten the canonical SOP", async (context) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gery-ai-source-"));
  const bundledDir = path.join(root, "bundled");
  const dataDir = path.join(root, "data");
  await fs.mkdir(bundledDir);
  const canonicalSop = [
    "Prerequisite: Stop data collection before restarting the service.",
    "1. Record the current tracker ID.",
    "2. Restart the tracker service with `systemctl restart tracker`.",
    "3. Re-pair the tracker in Device Manager.",
    "4. Confirm telemetry reports the recorded tracker ID.",
    "Escalate with the service log if telemetry remains zero.",
  ].join("\n");
  await fs.writeFile(path.join(bundledDir, "vive-sop.md"), `# VIVE recovery\n${canonicalSop}`);
  context.after(() => fs.rm(root, { recursive: true, force: true }));

  const store = new KnowledgeStore({
    bundledDir,
    dataDir,
    preprocessSection: async () => JSON.stringify({
      answer: "Restart it and try again.",
      questions: ["How do I recover a VIVE tracker showing zero?"],
      keywords: ["vive", "tracker", "telemetry"],
    }),
  });
  const result = await store.initialize();
  const entry = store.getEntries()[0];

  assert.equal(entry.answer, canonicalSop);
  assert.doesNotMatch(entry.answer, /Restart it and try again/);
  assert.equal(entry.processingMode, "ai-search-enriched");
  assert.equal(result.aiEnrichedSections, 1);
  assert.equal(result.guidedTroubleshootingSections, 1);
  assert.equal(store.listDocuments()[0].processingMode, "ai-search-enriched");
  assert.equal(store.listDocuments()[0].guidedTroubleshootingSections, 1);
});

test("AI preprocessing failure is visible while the source SOP remains usable", async (context) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gery-ai-fallback-"));
  const bundledDir = path.join(root, "bundled");
  const dataDir = path.join(root, "data");
  await fs.mkdir(bundledDir);
  await fs.writeFile(path.join(bundledDir, "collector.md"), "# Collector recovery\n1. Stop collection.\n2. Restart the collector.");
  context.after(() => fs.rm(root, { recursive: true, force: true }));

  const store = new KnowledgeStore({
    bundledDir,
    dataDir,
    preprocessSection: async () => "not-json",
  });
  const result = await store.initialize();

  assert.match(store.getEntries()[0].answer, /1\. Stop collection/);
  assert.equal(store.getEntries()[0].processingMode, "ai-fallback-source-preserved");
  assert.equal(result.aiFallbackSections, 1);
  assert.equal(store.listDocuments()[0].processingMode, "ai-unavailable-source-preserved");
});

test("retrieval returns an entire long SOP instead of one indexed fragment", async (context) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "gery-long-sop-"));
  const bundledDir = path.join(root, "bundled");
  const dataDir = path.join(root, "data");
  await fs.mkdir(bundledDir);
  const longSop = Array.from(
    { length: 240 },
    (_value, index) => `${index + 1}. Validate collector checkpoint ${index + 1} before continuing.`,
  ).join("\n\n");
  await fs.writeFile(path.join(bundledDir, "collector-sop.md"), `# Extended collector recovery\n${longSop}`);
  context.after(() => fs.rm(root, { recursive: true, force: true }));

  const store = new KnowledgeStore({ bundledDir, dataDir });
  await store.initialize();
  assert.ok(store.getEntries().length > 1);

  const result = findStoredAnswer("extended collector recovery", store.getEntries());
  assert.equal(result?.reply, longSop);
  assert.match(result?.reply, /240\. Validate collector checkpoint 240/);
});
