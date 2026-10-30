(() => {
    document.querySelectorAll("[data-start-chat]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (form.dataset.submitting === "true") { event.preventDefault(); return; }
            form.dataset.submitting = "true";
            form.setAttribute("aria-busy", "true");
            form.querySelectorAll('button[type="submit"]').forEach((button) => { button.disabled = true; });
        });
    });
    window.addEventListener("pageshow", () => {
        document.querySelectorAll("[data-start-chat]").forEach((form) => {
            delete form.dataset.submitting;
            form.removeAttribute("aria-busy");
            form.querySelectorAll('button[type="submit"]').forEach((button) => { button.disabled = false; });
        });
    });
    const toggle = document.getElementById("chat-history-toggle");
    if (!toggle) return;
    const panel = document.getElementById("chat-history-panel");
    function closeHistory(restoreFocus = false) {
        panel.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        if (restoreFocus) toggle.focus();
    }
    toggle.addEventListener("click", () => {
        if (!panel.hidden) { closeHistory(true); return; }
        panel.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        panel.querySelector("a")?.focus();
    });
    document.addEventListener("pointerdown", (event) => {
        if (!panel.hidden && !panel.contains(event.target) && !toggle.contains(event.target)) closeHistory();
    });
    document.addEventListener("focusin", (event) => {
        if (!panel.hidden && !panel.contains(event.target) && !toggle.contains(event.target)) closeHistory();
    });
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) { event.preventDefault(); closeHistory(true); }
    });
    const log = document.getElementById("chat-messages");
    log.scrollTop = log.scrollHeight;
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-prompt");
    const errors = document.getElementById("chat-errors");
    const status = document.getElementById("chat-status");
    const button = form.querySelector('button[type="submit"]');
    const workspace = document.querySelector("[data-preview-status-url]");
    let previewStopped = false;
    let previewPolls = 0;
    window.addEventListener("pagehide", () => { previewStopped = true; });
    async function checkPreview() {
        if (!workspace || previewStopped || ++previewPolls > 40 || busy) return;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(workspace.dataset.previewStatusUrl, {
                credentials: "same-origin", cache: "no-store", signal: controller.signal,
                headers: { Accept: "application/json" },
            });
            if (previewStopped || !response.ok) return;
            const data = await response.json();
            if (previewStopped || busy) return;
            if (data.preview_status === "ready" && data.preview_url) {
                const url = new URL(data.preview_url, window.location.href);
                if (url.origin !== window.location.origin) return;
                const image = workspace.querySelector(".result-preview img");
                if (image) { image.src = url.href; image.alt = data.preview_label; }
                status.textContent = data.preview_label;
                status.hidden = false;
            } else if (["queued", "running"].includes(data.preview_status)) {
                status.textContent = "Preview sedang diproses.";
                status.hidden = false;
                setTimeout(checkPreview, 3000);
            }
        } catch { /* Keep the private wardrobe photos when preview is unavailable. */ }
        finally { clearTimeout(timer); }
    }
    setTimeout(checkPreview, 0);
    let busy = false;
    function error(text) {
        errors.textContent = text;
        errors.hidden = !text;
    }
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (busy) return;
        if (!input.value.trim()) { error("Tulis pesan terlebih dahulu."); input.focus(); return; }
        error("");
        previewStopped = true;
        const data = new FormData(form);
        busy = true;
        form.setAttribute("aria-busy", "true");
        input.disabled = true;
        button.disabled = true;
        status.textContent = "Menyiapkan rekomendasi…";
        status.hidden = false;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 30000);
        try {
            const response = await fetch(form.action, {
                method: "POST", body: data, credentials: "same-origin", cache: "no-store",
                headers: { Accept: "application/json" }, signal: controller.signal,
            });
            const result = await response.json();
            if (response.ok && result.ok) {
                const url = new URL(result.url, window.location.href);
                if (url.origin !== window.location.origin) throw new Error("invalid_response");
                window.location.assign(url.href);
                return;
            }
            const messages = Object.values(result.errors || {}).flat().map((entry) => entry.message);
            error(messages.join(" ") || "Pesan belum dapat dikirim. Buka ulang percakapan dari menu riwayat.");
        } catch {
            // Keep the same key: retrying an uncertain request must not duplicate a turn.
            error("Hasil pengiriman belum dapat dipastikan. Kirim kembali pesan yang sama atau buka ulang dari menu riwayat.");
        } finally {
            clearTimeout(timeout);
            busy = false;
            input.disabled = false;
            button.disabled = false;
            form.removeAttribute("aria-busy");
            status.hidden = true;
            if (!errors.hidden) errors.focus();
        }
    });
})();
