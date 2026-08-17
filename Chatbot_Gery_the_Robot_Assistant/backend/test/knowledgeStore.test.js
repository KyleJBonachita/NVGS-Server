import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { KnowledgeStore } from "../src/services/knowledgeStore.js";

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
  assert.equal(store.getEntries()[0].processingMode, "deterministic");

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
