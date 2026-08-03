"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fsp = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");

const {
  classifyFile,
  createAppServer,
  listDownloadFiles,
  normalizeRelativePath,
  parseByteRange,
  resolveDownloadPath,
} = require("../server");

test("classifies common file types", () => {
  assert.equal(classifyFile("photo.JPG"), "image");
  assert.equal(classifyFile("manual.pdf"), "document");
  assert.equal(classifyFile("release.zip"), "archive");
  assert.equal(classifyFile("installer.exe"), "software");
  assert.equal(classifyFile("unknown.bin"), "other");
});

test("normalizes safe paths and rejects traversal", () => {
  assert.equal(normalizeRelativePath("folder/file.txt"), "folder/file.txt");
  assert.equal(normalizeRelativePath("folder\\file.txt"), "folder/file.txt");
  assert.equal(normalizeRelativePath("../server.js"), null);
  assert.equal(normalizeRelativePath(".hidden"), null);
  assert.equal(normalizeRelativePath("folder/../secret.txt"), null);
  assert.equal(normalizeRelativePath(""), null);
});

test("resolves paths only inside the downloads directory", () => {
  const root = path.resolve("downloads");
  assert.equal(
    resolveDownloadPath(root, "folder/file.txt"),
    path.resolve(root, "folder", "file.txt"),
  );
  assert.equal(resolveDownloadPath(root, "../server.js"), null);
});

test("parses valid byte ranges and rejects invalid ones", () => {
  assert.deepEqual(parseByteRange("bytes=0-3", 10), { start: 0, end: 3 });
  assert.deepEqual(parseByteRange("bytes=5-", 10), { start: 5, end: 9 });
  assert.deepEqual(parseByteRange("bytes=-4", 10), { start: 6, end: 9 });
  assert.equal(parseByteRange("bytes=12-20", 10), false);
  assert.equal(parseByteRange(undefined, 10), null);
});

test("lists files, attaches custom covers, and serves downloads", async (context) => {
  const temporaryRoot = await fsp.mkdtemp(path.join(os.tmpdir(), "download-server-"));
  const downloadsDir = path.join(temporaryRoot, "downloads");
  const publicDir = path.join(__dirname, "..", "public");
  const configPath = path.join(temporaryRoot, "config.json");

  await fsp.mkdir(path.join(downloadsDir, "Guides"), { recursive: true });
  await Promise.all([
    fsp.writeFile(path.join(downloadsDir, ".gitkeep"), ""),
    fsp.writeFile(path.join(downloadsDir, "Guides", "hello.txt"), "hello world"),
    fsp.writeFile(path.join(downloadsDir, "Guides", "hello.cover.jpg"), "image"),
    fsp.writeFile(
      configPath,
      JSON.stringify({ siteName: "Test Library" }),
    ),
  ]);

  const files = await listDownloadFiles(downloadsDir);
  assert.equal(files.length, 1);
  assert.equal(files[0].path, "Guides/hello.txt");
  assert.equal(files[0].previewPath, "Guides/hello.cover.jpg");

  const server = createAppServer({ downloadsDir, publicDir, configPath });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  context.after(
    () =>
      new Promise((resolve) => {
        server.close(resolve);
      }),
  );
  context.after(() => fsp.rm(temporaryRoot, { recursive: true, force: true }));

  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;

  const apiResponse = await fetch(`${baseUrl}/api/files`);
  assert.equal(apiResponse.status, 200);
  const apiPayload = await apiResponse.json();
  assert.equal(apiPayload.siteName, "Test Library");
  assert.equal(apiPayload.files.length, 1);

  const downloadResponse = await fetch(
    `${baseUrl}/download?file=${encodeURIComponent("Guides/hello.txt")}`,
  );
  assert.equal(downloadResponse.status, 200);
  assert.match(
    downloadResponse.headers.get("content-disposition"),
    /attachment; filename="hello\.txt"/,
  );
  assert.equal(await downloadResponse.text(), "hello world");

  const rangeResponse = await fetch(
    `${baseUrl}/download?file=${encodeURIComponent("Guides/hello.txt")}`,
    { headers: { Range: "bytes=0-4" } },
  );
  assert.equal(rangeResponse.status, 206);
  assert.equal(await rangeResponse.text(), "hello");

  const traversalResponse = await fetch(
    `${baseUrl}/download?file=${encodeURIComponent("../server.js")}`,
  );
  assert.equal(traversalResponse.status, 400);
});
