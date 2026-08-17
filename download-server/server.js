"use strict";

const http = require("node:http");
const https = require("node:https");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");

const ROOT_DIR = __dirname;
const DEFAULT_PUBLIC_DIR = path.join(ROOT_DIR, "public");
const DEFAULT_DOWNLOADS_DIR = path.join(ROOT_DIR, "downloads");
const DEFAULT_CONFIG = {
  siteName: "DownloadServer",
  eyebrow: "LOCAL FILE LIBRARY",
  headline: "Ready when you are.",
  description:
    "Browse the collection and download what you need—directly over the local network.",
};

const MIME_TYPES = {
  ".avif": "image/avif",
  ".bmp": "image/bmp",
  ".css": "text/css; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".doc": "application/msword",
  ".docx":
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".epub": "application/epub+zip",
  ".gif": "image/gif",
  ".gz": "application/gzip",
  ".htm": "text/html; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".m4a": "audio/mp4",
  ".mkv": "video/x-matroska",
  ".mov": "video/quicktime",
  ".mp3": "audio/mpeg",
  ".mp4": "video/mp4",
  ".msi": "application/x-msi",
  ".ogg": "audio/ogg",
  ".pdf": "application/pdf",
  ".png": "image/png",
  ".ppt": "application/vnd.ms-powerpoint",
  ".pptx":
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".rar": "application/vnd.rar",
  ".svg": "image/svg+xml",
  ".tar": "application/x-tar",
  ".txt": "text/plain; charset=utf-8",
  ".wav": "audio/wav",
  ".webm": "video/webm",
  ".webp": "image/webp",
  ".xls": "application/vnd.ms-excel",
  ".xlsx":
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".xml": "application/xml; charset=utf-8",
  ".zip": "application/zip",
};

const CATEGORY_EXTENSIONS = {
  image: new Set([
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
  ]),
  video: new Set([".avi", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"]),
  audio: new Set([".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav", ".wma"]),
  document: new Set([
    ".csv",
    ".doc",
    ".docx",
    ".epub",
    ".md",
    ".odp",
    ".ods",
    ".odt",
    ".pdf",
    ".ppt",
    ".pptx",
    ".rtf",
    ".txt",
    ".xls",
    ".xlsx",
  ]),
  archive: new Set([".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".zip"]),
  software: new Set([".apk", ".appx", ".dmg", ".exe", ".iso", ".msi", ".pkg"]),
};

const COVER_SUFFIX = /\.cover\.(avif|gif|jpe?g|png|webp)$/i;
const COVER_EXTENSIONS = [".cover.jpg", ".cover.jpeg", ".cover.png", ".cover.webp", ".cover.gif", ".cover.avif"];
const MAX_FILES = 5000;
const MAX_DEPTH = 10;

function classifyFile(filename) {
  const extension = path.extname(filename).toLowerCase();

  for (const [category, extensions] of Object.entries(CATEGORY_EXTENSIONS)) {
    if (extensions.has(extension)) return category;
  }

  return "other";
}

function contentTypeFor(filename) {
  return MIME_TYPES[path.extname(filename).toLowerCase()] || "application/octet-stream";
}

function normalizeRelativePath(value) {
  if (typeof value !== "string" || !value.trim() || value.includes("\0")) {
    return null;
  }

  const normalized = value.replaceAll("\\", "/");
  const segments = normalized.split("/");

  if (
    segments.some(
      (segment) =>
        !segment ||
        segment === "." ||
        segment === ".." ||
        segment.startsWith("."),
    )
  ) {
    return null;
  }

  return segments.join("/");
}

function resolveDownloadPath(downloadsDir, relativePath) {
  const normalized = normalizeRelativePath(relativePath);
  if (!normalized) return null;

  const root = path.resolve(downloadsDir);
  const target = path.resolve(root, ...normalized.split("/"));
  const relation = path.relative(root, target);

  if (!relation || relation.startsWith("..") || path.isAbsolute(relation)) {
    return null;
  }

  return target;
}

async function readConfig(configPath) {
  try {
    const contents = await fsp.readFile(configPath, "utf8");
    const parsed = JSON.parse(contents);
    return { ...DEFAULT_CONFIG, ...parsed };
  } catch (error) {
    if (error.code !== "ENOENT") {
      console.warn(`Could not read config.json: ${error.message}`);
    }
    return { ...DEFAULT_CONFIG };
  }
}

async function collectFiles(downloadsDir, directory = downloadsDir, prefix = "", depth = 0, output = []) {
  if (depth > MAX_DEPTH || output.length >= MAX_FILES) return output;

  let entries;
  try {
    entries = await fsp.readdir(directory, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") {
      await fsp.mkdir(downloadsDir, { recursive: true });
      return output;
    }
    throw error;
  }

  entries.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));

  for (const entry of entries) {
    if (output.length >= MAX_FILES) break;
    if (entry.name.startsWith(".")) continue;
    if (entry.isSymbolicLink()) continue;

    const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
    const absolutePath = path.join(directory, entry.name);

    if (entry.isDirectory()) {
      await collectFiles(
        downloadsDir,
        absolutePath,
        relativePath,
        depth + 1,
        output,
      );
      continue;
    }

    if (!entry.isFile()) continue;

    const stat = await fsp.stat(absolutePath);
    output.push({
      relativePath,
      absolutePath,
      size: stat.size,
      modified: stat.mtime.toISOString(),
    });
  }

  return output;
}

async function listDownloadFiles(downloadsDir) {
  const rawFiles = await collectFiles(downloadsDir);
  const byLowercasePath = new Map(
    rawFiles.map((file) => [file.relativePath.toLowerCase(), file]),
  );

  return rawFiles
    .filter((file) => !COVER_SUFFIX.test(file.relativePath))
    .map((file) => {
      const extension = path.extname(file.relativePath).toLowerCase();
      const category = classifyFile(file.relativePath);
      let previewPath = category === "image" ? file.relativePath : null;

      if (!previewPath) {
        const coverStems = [file.relativePath];
        if (extension) {
          coverStems.push(file.relativePath.slice(0, -extension.length));
        }

        for (const stem of coverStems) {
          for (const suffix of COVER_EXTENSIONS) {
            const cover = byLowercasePath.get(`${stem}${suffix}`.toLowerCase());
            if (cover) {
              previewPath = cover.relativePath;
              break;
            }
          }
          if (previewPath) break;
        }
      }

      return {
        path: file.relativePath,
        name: path.basename(file.relativePath),
        folder: path.dirname(file.relativePath).replaceAll("\\", "/"),
        extension: extension ? extension.slice(1).toUpperCase() : "FILE",
        size: file.size,
        modified: file.modified,
        category,
        previewPath,
      };
    })
    .sort(
      (a, b) =>
        new Date(b.modified).getTime() - new Date(a.modified).getTime() ||
        a.name.localeCompare(b.name, undefined, { numeric: true }),
    );
}

function setSecurityHeaders(response) {
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("X-Frame-Options", "DENY");
  response.setHeader("Referrer-Policy", "no-referrer");
  response.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
}

function sendJson(response, statusCode, value) {
  const payload = Buffer.from(JSON.stringify(value));
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
  });
  response.end(payload);
}

function sendText(response, statusCode, message) {
  const payload = Buffer.from(message);
  response.writeHead(statusCode, {
    "Content-Type": "text/plain; charset=utf-8",
    "Content-Length": payload.length,
    "Cache-Control": "no-store",
  });
  response.end(payload);
}

function proxyGerryRequest(request, response, upstreamValue) {
  let upstream;
  try {
    upstream = new URL(upstreamValue);
  } catch (_error) {
    sendJson(response, 502, { error: "Gery Chatbot Server is unavailable." });
    return;
  }

  const incoming = new URL(request.url, "http://localhost");
  const strippedPath = incoming.pathname.replace(/^\/gerry(?=\/|$)/, "") || "/";
  const client = upstream.protocol === "https:" ? https : http;
  const headers = { ...request.headers };
  delete headers.host;
  headers["x-forwarded-host"] = request.headers.host || "";
  headers["x-forwarded-proto"] = "http";

  const proxyRequest = client.request(
    {
      protocol: upstream.protocol,
      hostname: upstream.hostname,
      port: upstream.port,
      method: request.method,
      path: `${strippedPath}${incoming.search}`,
      headers,
    },
    (proxyResponse) => {
      response.writeHead(proxyResponse.statusCode || 502, proxyResponse.headers);
      proxyResponse.pipe(response);
    },
  );

  proxyRequest.on("error", () => {
    if (!response.headersSent) {
      sendJson(response, 502, { error: "Gery Chatbot Server is unavailable." });
    } else {
      response.destroy();
    }
  });
  request.pipe(proxyRequest);
}

function safeContentDisposition(filename) {
  const fallback = filename
    .normalize("NFKD")
    .replace(/[^\x20-\x7E]/g, "_")
    .replace(/["\\]/g, "_");
  return `attachment; filename="${fallback}"; filename*=UTF-8''${encodeURIComponent(filename)}`;
}

function parseByteRange(rangeHeader, size) {
  if (!rangeHeader || !rangeHeader.startsWith("bytes=")) return null;

  const [startValue, endValue] = rangeHeader.slice(6).split("-", 2);
  let start;
  let end;

  if (!startValue) {
    const suffixLength = Number(endValue);
    if (!Number.isInteger(suffixLength) || suffixLength <= 0) return false;
    start = Math.max(size - suffixLength, 0);
    end = size - 1;
  } else {
    start = Number(startValue);
    end = endValue ? Number(endValue) : size - 1;
  }

  if (
    !Number.isInteger(start) ||
    !Number.isInteger(end) ||
    start < 0 ||
    end < start ||
    start >= size
  ) {
    return false;
  }

  return { start, end: Math.min(end, size - 1) };
}

async function serveFile(request, response, options) {
  const {
    absolutePath,
    displayName,
    attachment = false,
    cacheControl = "private, max-age=300",
  } = options;

  let stat;
  try {
    stat = await fsp.stat(absolutePath);
    if (!stat.isFile()) throw Object.assign(new Error("Not a file"), { code: "ENOENT" });
  } catch (error) {
    if (error.code === "ENOENT") {
      sendText(response, 404, "File not found.");
      return;
    }
    throw error;
  }

  const range = parseByteRange(request.headers.range, stat.size);
  if (range === false) {
    response.writeHead(416, {
      "Content-Range": `bytes */${stat.size}`,
      "Content-Length": 0,
    });
    response.end();
    return;
  }

  const headers = {
    "Content-Type": contentTypeFor(displayName),
    "Accept-Ranges": "bytes",
    "Cache-Control": cacheControl,
    "Last-Modified": stat.mtime.toUTCString(),
  };

  if (attachment) {
    headers["Content-Disposition"] = safeContentDisposition(path.basename(displayName));
  }

  let streamOptions;
  let statusCode = 200;

  if (range) {
    statusCode = 206;
    streamOptions = { start: range.start, end: range.end };
    headers["Content-Range"] = `bytes ${range.start}-${range.end}/${stat.size}`;
    headers["Content-Length"] = range.end - range.start + 1;
  } else {
    headers["Content-Length"] = stat.size;
  }

  response.writeHead(statusCode, headers);
  if (request.method === "HEAD") {
    response.end();
    return;
  }

  const stream = fs.createReadStream(absolutePath, streamOptions);
  stream.on("error", () => {
    if (!response.headersSent) sendText(response, 500, "Could not read the file.");
    else response.destroy();
  });
  stream.pipe(response);
}

function createAppServer(options = {}) {
  const downloadsDir = path.resolve(options.downloadsDir || DEFAULT_DOWNLOADS_DIR);
  const publicDir = path.resolve(options.publicDir || DEFAULT_PUBLIC_DIR);
  const configPath = path.resolve(options.configPath || path.join(ROOT_DIR, "config.json"));
  const gerryUpstreamUrl = options.gerryUpstreamUrl || process.env.GERRY_UPSTREAM_URL || "http://127.0.0.1:3000";
  const staticRoutes = new Map([
    ["/", "index.html"],
    ["/index.html", "index.html"],
    ["/styles.css", "styles.css"],
    ["/app.js", "app.js"],
    ["/gerry-loader.js", "gerry-loader.js"],
  ]);

  return http.createServer(async (request, response) => {
    setSecurityHeaders(response);

    try {
      const url = new URL(request.url, "http://localhost");

      if (url.pathname === "/gerry" || url.pathname.startsWith("/gerry/")) {
        const allowedMethods = new Set(["GET", "HEAD", "POST", "DELETE"]);
        if (!allowedMethods.has(request.method)) {
          response.setHeader("Allow", [...allowedMethods].join(", "));
          sendText(response, 405, "Method not allowed.");
          return;
        }
        proxyGerryRequest(request, response, gerryUpstreamUrl);
        return;
      }

      const methodAllowed = request.method === "GET" || request.method === "HEAD";

      if (!methodAllowed) {
        response.setHeader("Allow", "GET, HEAD");
        sendText(response, 405, "Method not allowed.");
        return;
      }

      if (url.pathname === "/api/files") {
        const [files, config] = await Promise.all([
          listDownloadFiles(downloadsDir),
          readConfig(configPath),
        ]);
        sendJson(response, 200, {
          ...config,
          files,
          generatedAt: new Date().toISOString(),
        });
        return;
      }

      if (url.pathname === "/health") {
        const files = await listDownloadFiles(downloadsDir);
        sendJson(response, 200, {
          status: "ok",
          fileCount: files.length,
          uptimeSeconds: Math.round(process.uptime()),
        });
        return;
      }

      if (url.pathname === "/download" || url.pathname === "/preview") {
        const relativePath = url.searchParams.get("file");
        const absolutePath = resolveDownloadPath(downloadsDir, relativePath);

        if (!absolutePath) {
          sendText(response, 400, "Invalid file path.");
          return;
        }

        if (
          url.pathname === "/preview" &&
          classifyFile(relativePath) !== "image"
        ) {
          sendText(response, 415, "Preview not available.");
          return;
        }

        await serveFile(request, response, {
          absolutePath,
          displayName: relativePath,
          attachment: url.pathname === "/download",
          cacheControl:
            url.pathname === "/preview"
              ? "private, max-age=300"
              : "no-store",
        });
        return;
      }

      if (url.pathname === "/favicon.ico") {
        response.writeHead(204, { "Cache-Control": "public, max-age=86400" });
        response.end();
        return;
      }

      const staticFilename = staticRoutes.get(url.pathname);
      if (staticFilename) {
        if (staticFilename === "index.html") {
          response.setHeader(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
          );
        }
        await serveFile(request, response, {
          absolutePath: path.join(publicDir, staticFilename),
          displayName: staticFilename,
          cacheControl:
            staticFilename === "index.html"
              ? "no-cache"
              : "public, max-age=3600",
        });
        return;
      }

      sendText(response, 404, "Page not found.");
    } catch (error) {
      console.error(`[${new Date().toISOString()}] ${error.stack || error.message}`);
      if (!response.headersSent) sendText(response, 500, "Internal server error.");
      else response.destroy();
    }
  });
}

function localNetworkAddresses(port) {
  const addresses = [];
  const interfaces = os.networkInterfaces();

  for (const entries of Object.values(interfaces)) {
    for (const entry of entries || []) {
      if (entry.family === "IPv4" && !entry.internal) {
        addresses.push(`http://${entry.address}:${port}`);
      }
    }
  }

  return [...new Set(addresses)];
}

async function startServer() {
  const parsedPort = Number.parseInt(process.env.PORT || "8080", 10);
  const port =
    Number.isInteger(parsedPort) && parsedPort > 0 && parsedPort <= 65535
      ? parsedPort
      : 8080;
  const host = process.env.HOST || "0.0.0.0";

  await fsp.mkdir(DEFAULT_DOWNLOADS_DIR, { recursive: true });
  const server = createAppServer();

  server.on("error", (error) => {
    if (error.code === "EADDRINUSE") {
      console.error(`\nPort ${port} is already in use. Close the other server or set a different PORT.`);
    } else {
      console.error(`\nServer error: ${error.message}`);
    }
    process.exitCode = 1;
  });

  server.listen(port, host, () => {
    console.log("\n  DownloadServer is ready\n");
    console.log(`  This computer:  http://localhost:${port}`);
    for (const address of localNetworkAddresses(port)) {
      console.log(`  Wi-Fi / LAN:    ${address}`);
    }
    console.log("\n  Add or remove files in the downloads folder at any time.");
    console.log("  Keep this window open. Press Ctrl+C to stop.\n");
  });

  const stop = () => {
    console.log("\nStopping DownloadServer...");
    server.close(() => process.exit(0));
  };
  process.once("SIGINT", stop);
  process.once("SIGTERM", stop);

  return server;
}

if (require.main === module) {
  startServer();
}

module.exports = {
  classifyFile,
  createAppServer,
  listDownloadFiles,
  normalizeRelativePath,
  parseByteRange,
  resolveDownloadPath,
};
