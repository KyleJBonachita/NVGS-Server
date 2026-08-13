(function () {
  "use strict";

  const form = document.getElementById("upload-form");
  const input = document.getElementById("file-input");
  const chooseButton = document.getElementById("choose-files");
  const dropZone = document.getElementById("drop-zone");
  const summary = document.getElementById("selection-summary");
  const message = document.getElementById("upload-message");
  const progress = document.getElementById("upload-progress");
  const progressBar = document.getElementById("upload-progress-bar");
  const progressLabel = document.getElementById("upload-progress-label");
  const duplicateDialog = document.getElementById("duplicate-dialog");
  const duplicateNames = document.getElementById("duplicate-names");
  const existingNames = new Set(
    JSON.parse(document.getElementById("existing-download-names").textContent)
  );
  let uploading = false;

  function conflictsFor(files) {
    const occupied = new Set(existingNames);
    const conflicts = [];
    files.forEach(function (file) {
      if (occupied.has(file.name) && !conflicts.includes(file.name)) {
        conflicts.push(file.name);
      }
      occupied.add(file.name);
    });
    return conflicts;
  }

  function chooseConflictPolicy(conflicts) {
    if (!conflicts.length) return Promise.resolve("rename");
    duplicateNames.textContent = conflicts.slice(0, 12).map(function (name) {
      return "• " + name;
    }).join("\n");
    duplicateDialog.showModal();
    return new Promise(function (resolve) {
      duplicateDialog.addEventListener("close", function closed() {
        duplicateDialog.removeEventListener("close", closed);
        resolve(duplicateDialog.returnValue || "cancel");
      });
    });
  }

  function setBusy(value) {
    uploading = value;
    chooseButton.disabled = value;
    dropZone.disabled = value;
  }

  function showError(text) {
    message.textContent = text;
    message.hidden = !text;
  }

  function upload(files, policy) {
    const data = new FormData();
    data.append("csrfmiddlewaretoken", form.elements.csrfmiddlewaretoken.value);
    data.append("conflict_policy", policy);
    files.forEach(function (file) { data.append("files", file, file.name); });

    setBusy(true);
    showError("");
    progress.hidden = false;
    progressBar.value = 0;
    progressLabel.textContent = "Uploading…";

    const request = new XMLHttpRequest();
    request.open("POST", window.location.href);
    request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    request.upload.addEventListener("progress", function (event) {
      if (!event.lengthComputable) return;
      const percent = Math.round((event.loaded / event.total) * 100);
      progressBar.value = percent;
      progressLabel.textContent = "Uploading… " + percent + "%";
    });
    request.addEventListener("load", function () {
      let result = {};
      try { result = JSON.parse(request.responseText); } catch (_error) {}
      if (request.status >= 200 && request.status < 300 && result.ok) {
        progressBar.value = 100;
        progressLabel.textContent = "Upload complete. Refreshing the library…";
        window.setTimeout(function () { window.location.reload(); }, 450);
        return;
      }
      setBusy(false);
      progress.hidden = true;
      showError(result.error || "The upload failed. Check the server and try again.");
    });
    request.addEventListener("error", function () {
      setBusy(false);
      progress.hidden = true;
      showError("The connection was interrupted before the upload completed.");
    });
    request.send(data);
  }

  async function prepareUpload(fileList) {
    if (uploading) return;
    const files = Array.from(fileList || []);
    if (!files.length) return;
    summary.textContent = files.length + (files.length === 1 ? " file" : " files") + " selected.";
    const policy = await chooseConflictPolicy(conflictsFor(files));
    if (policy === "cancel") {
      summary.textContent = "Upload cancelled; nothing was changed.";
      input.value = "";
      return;
    }
    upload(files, policy);
  }

  chooseButton.addEventListener("click", function () { input.click(); });
  dropZone.addEventListener("click", function () { input.click(); });
  input.addEventListener("change", function () { prepareUpload(input.files); });
  document.getElementById("refresh-library").addEventListener("click", function () {
    window.location.reload();
  });

  ["dragenter", "dragover"].forEach(function (eventName) {
    dropZone.addEventListener(eventName, function (event) {
      event.preventDefault();
      if (!uploading) dropZone.classList.add("drag-active");
    });
  });
  ["dragleave", "drop"].forEach(function (eventName) {
    dropZone.addEventListener(eventName, function (event) {
      event.preventDefault();
      dropZone.classList.remove("drag-active");
    });
  });
  dropZone.addEventListener("drop", function (event) {
    if (!uploading) prepareUpload(event.dataTransfer.files);
  });
})();
