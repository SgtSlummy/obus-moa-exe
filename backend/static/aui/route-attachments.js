(() => {
  const MAX_ATTACHMENTS = 8;
  const MAX_ATTACHMENT_BYTES = 512 * 1024;
  const MAX_TOTAL_BYTES = 1024 * 1024;
  const MAX_IMAGE_ATTACHMENTS = 4;
  const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
  const MAX_IMAGE_TOTAL_BYTES = 8 * 1024 * 1024;
  const IMAGE_MIME_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
  const IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "webp"]);
  const TEXT_EXTENSIONS = new Set([
    "txt", "md", "mdx", "rst", "log", "csv", "tsv", "json", "yaml", "yml", "toml", "ini", "cfg",
    "py", "js", "mjs", "cjs", "ts", "tsx", "jsx", "html", "htm", "css", "scss", "less", "xml",
    "sql", "sh", "ps1", "bat", "cmd", "go", "rs", "java", "c", "h", "cpp", "hpp", "cs", "rb",
    "php", "swift", "kt", "kts", "lua", "r", "vue", "svelte", "dockerfile", "gitignore",
  ]);

  const extensionOf = (name) => String(name || "").split(".").pop().toLowerCase();
  const safeName = (name) => String(name || "attachment.txt")
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_").trim().slice(0, 160) || "attachment.txt";
  const formatBytes = (value) => {
    const bytes = Math.max(0, Number(value) || 0);
    return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : bytes >= 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${bytes} B`;
  };
  const attachmentBlock = (attachment) => `\n\n--- Selected local attachment: ${attachment.name} ---\n${attachment.content}\n--- End local attachment: ${attachment.name} ---`;
  const isText = (file) => String(file?.type || "").startsWith("text/") || TEXT_EXTENSIONS.has(extensionOf(file?.name));
  const isImage = (file) => IMAGE_MIME_TYPES.has(String(file?.type || "").toLowerCase()) || IMAGE_EXTENSIONS.has(extensionOf(file?.name));
  const imageMime = (file) => {
    const declared = String(file?.type || "").toLowerCase();
    if (IMAGE_MIME_TYPES.has(declared)) return declared;
    return {png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp"}[extensionOf(file?.name)] || "";
  };
  const base64FromFile = async (file) => {
    const view = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    const chunkSize = 0x8000;
    for (let offset = 0; offset < view.length; offset += chunkSize) binary += String.fromCharCode(...view.subarray(offset, offset + chunkSize));
    return btoa(binary);
  };

  window.OBusRouteAttachments = {
    create({input, picker, button, captureButton, list, dropTarget, toast = () => {}, onChange = () => {}, getPromptLimit = () => 262144} = {}) {
      const attachments = [];
      const images = [];
      const totalTextBytes = () => attachments.reduce((sum, item) => sum + item.bytes, 0);
      const totalImageBytes = () => images.reduce((sum, item) => sum + item.bytes, 0);
      const compose = (basePrompt = input?.value || "", items = attachments) => {
        const prompt = String(basePrompt || "").trim();
        const attachmentText = items.map(attachmentBlock).join("");
        if (!attachmentText) return prompt;
        const instruction = prompt || "Review the selected local attachments, identify concrete findings, and state the next useful action.";
        return `${instruction}${attachmentText}`;
      };
      const characterCount = (basePrompt) => compose(basePrompt).length;
      const summary = () => {
        const labels = [];
        if (attachments.length) labels.push(`${attachments.length} local text attachment${attachments.length === 1 ? "" : "s"} · ${formatBytes(totalTextBytes())}`);
        if (images.length) labels.push(`${images.length} local image${images.length === 1 ? "" : "s"} · ${formatBytes(totalImageBytes())} · never remote`);
        return labels.join(" · ");
      };
      const discardImage = (image) => { if (image?.previewUrl) URL.revokeObjectURL(image.previewUrl); };
      const render = () => {
        if (!list) return;
        list.replaceChildren();
        list.hidden = !(attachments.length || images.length);
        for (const attachment of [...attachments, ...images]) {
          const chip = document.createElement("div");
          chip.className = `route-attachment-chip${attachment.kind === "image" ? " route-image-chip" : ""}`;
          if (attachment.kind === "image") {
            const preview = document.createElement("img");
            preview.className = "route-attachment-preview";
            preview.src = attachment.previewUrl;
            preview.alt = "";
            chip.append(preview);
          }
          const label = document.createElement("span");
          label.textContent = `${attachment.kind === "image" ? "◉" : "▣"} ${attachment.name} · ${formatBytes(attachment.bytes)}${attachment.kind === "image" ? " · local only" : ""}`;
          const remove = document.createElement("button");
          remove.type = "button";
          remove.className = "route-attachment-remove";
          remove.textContent = "×";
          remove.title = `Remove ${attachment.name}`;
          remove.setAttribute("aria-label", `Remove ${attachment.name}`);
          remove.onclick = () => {
            const source = attachment.kind === "image" ? images : attachments;
            const index = source.findIndex((item) => item.id === attachment.id);
            if (index >= 0) {
              const [removed] = source.splice(index, 1);
              if (removed?.kind === "image") discardImage(removed);
            }
            render();
            onChange();
          };
          chip.append(label, remove);
          list.append(chip);
        }
      };
      const stageText = async (file) => {
        if (attachments.length >= MAX_ATTACHMENTS) return toast(`A route can include at most ${MAX_ATTACHMENTS} local text attachments`, true);
        if (file.size > MAX_ATTACHMENT_BYTES) return toast(`${safeName(file.name)} exceeds the ${formatBytes(MAX_ATTACHMENT_BYTES)} per-file limit`, true);
        if (totalTextBytes() + file.size > MAX_TOTAL_BYTES) return toast(`Selected text files exceed the ${formatBytes(MAX_TOTAL_BYTES)} local attachment limit`, true);
        let content;
        try { content = await file.text(); } catch { return toast(`OBus could not read ${safeName(file.name)}`, true); }
        if (!content || content.includes("\u0000")) return toast(`${safeName(file.name)} is empty or binary and was not attached`, true);
        const attachment = {id: crypto.randomUUID?.() || `attachment-${Date.now()}-${attachments.length}`, kind: "text", name: safeName(file.name), bytes: file.size, content};
        if (compose(input?.value || "", [...attachments, attachment]).length > Math.max(1, Number(getPromptLimit()) || 262144)) return toast(`${attachment.name} would exceed the active model's route input budget`, true);
        attachments.push(attachment);
      };
      const stageImage = async (file) => {
        if (images.length >= MAX_IMAGE_ATTACHMENTS) return toast(`A route can include at most ${MAX_IMAGE_ATTACHMENTS} local images`, true);
        if (file.size > MAX_IMAGE_BYTES) return toast(`${safeName(file.name)} exceeds the ${formatBytes(MAX_IMAGE_BYTES)} per-image limit`, true);
        if (totalImageBytes() + file.size > MAX_IMAGE_TOTAL_BYTES) return toast(`Selected images exceed the ${formatBytes(MAX_IMAGE_TOTAL_BYTES)} local image limit`, true);
        const mimeType = imageMime(file);
        if (!IMAGE_MIME_TYPES.has(mimeType)) return toast(`${safeName(file.name)} is not a supported PNG, JPEG, or WebP image`, true);
        let dataBase64;
        try { dataBase64 = await base64FromFile(file); } catch { return toast(`OBus could not read ${safeName(file.name)}`, true); }
        if (!dataBase64) return toast(`${safeName(file.name)} is empty and was not attached`, true);
        images.push({id: crypto.randomUUID?.() || `image-${Date.now()}-${images.length}`, kind: "image", name: safeName(file.name), bytes: file.size, mime_type: mimeType, data_base64: dataBase64, previewUrl: URL.createObjectURL(file)});
      };
      const stage = async (files) => {
        for (const file of Array.from(files || [])) {
          if (isImage(file)) await stageImage(file);
          else if (isText(file)) await stageText(file);
          else toast(`${safeName(file.name)} is not a supported text, code, or image file`, true);
        }
        render();
        onChange();
      };
      const captureScreen = async () => {
        if (!navigator.mediaDevices?.getDisplayMedia) return toast("Screen capture is unavailable in this desktop view", true);
        if (images.length >= MAX_IMAGE_ATTACHMENTS) return toast(`A route can include at most ${MAX_IMAGE_ATTACHMENTS} local images`, true);
        let stream;
        let video;
        try {
          // The operating system chooser is the consent boundary. No frame is
          // requested until the user selects a display, window, or tab.
          stream = await navigator.mediaDevices.getDisplayMedia({video: {frameRate: 1}, audio: false});
          video = document.createElement("video");
          video.muted = true;
          video.playsInline = true;
          video.srcObject = stream;
          await new Promise((resolve, reject) => {
            video.onloadedmetadata = resolve;
            video.onerror = () => reject(new Error("OBus could not read the selected display"));
          });
          await video.play();
          const sourceWidth = Math.max(1, video.videoWidth || 1);
          const sourceHeight = Math.max(1, video.videoHeight || 1);
          const scale = Math.min(1, 1280 / sourceWidth, 720 / sourceHeight);
          const canvas = document.createElement("canvas");
          canvas.width = Math.max(1, Math.round(sourceWidth * scale));
          canvas.height = Math.max(1, Math.round(sourceHeight * scale));
          canvas.getContext("2d", {alpha: false})?.drawImage(video, 0, 0, canvas.width, canvas.height);
          const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/webp", 0.78));
          if (!blob) throw new Error("OBus could not encode the selected display");
          const filename = `obus-screen-${new Date().toISOString().replace(/[:.]/g, "-")}.webp`;
          const before = images.length;
          await stageImage(new File([blob], filename, {type: "image/webp"}));
          render();
          onChange();
          if (images.length > before) toast("Screen capture staged locally. It will never use remote aggregation.");
        } catch (error) {
          if (error?.name !== "NotAllowedError") toast(error?.message || "Screen capture was unavailable", true);
        } finally {
          stream?.getTracks?.().forEach((track) => track.stop());
          if (video) video.srcObject = null;
        }
      };
      const stagePastedImages = async (event) => {
        // Only intercept a paste when the clipboard actually contains a
        // supported image. Plain-text paste retains the browser's normal
        // composer behavior, and no clipboard data is retained otherwise.
        const clipboard = event.clipboardData;
        const items = Array.from(clipboard?.items || []);
        const pastedImages = items
          .filter((item) => item.kind === "file" && IMAGE_MIME_TYPES.has(String(item.type || "").toLowerCase()))
          .map((item) => item.getAsFile())
          .filter(Boolean);
        if (!pastedImages.length) return;
        event.preventDefault();
        const before = images.length;
        await stage(pastedImages);
        if (images.length > before) toast("Pasted image staged locally. It will never use remote aggregation.");
      };
      picker?.addEventListener("change", async () => { await stage(picker.files); picker.value = ""; });
      button?.addEventListener("click", () => picker?.click());
      if (captureButton && !navigator.mediaDevices?.getDisplayMedia) captureButton.hidden = true;
      captureButton?.addEventListener("click", () => { captureScreen(); });
      dropTarget?.addEventListener("dragover", (event) => { event.preventDefault(); dropTarget.classList.add("route-attachment-drop-target"); });
      dropTarget?.addEventListener("dragleave", () => dropTarget.classList.remove("route-attachment-drop-target"));
      dropTarget?.addEventListener("drop", async (event) => { event.preventDefault(); dropTarget.classList.remove("route-attachment-drop-target"); await stage(event.dataTransfer?.files); });
      input?.addEventListener("paste", stagePastedImages);
      return {
        compose,
        characterCount,
        summary,
        imagePayload: () => images.map(({name, mime_type, data_base64}) => ({name, mime_type, data_base64})),
        count: () => attachments.length + images.length,
        captureScreen,
        stagePastedImages,
        clear: () => { images.forEach(discardImage); attachments.splice(0, attachments.length); images.splice(0, images.length); render(); onChange(); },
      };
    },
  };
})();
