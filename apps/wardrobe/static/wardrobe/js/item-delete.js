(() => {
    const modal = document.getElementById("item-delete-modal");
    if (!modal) return;
    const form = document.getElementById("item-delete-form");
    const name = document.getElementById("delete-item-name");
    const close = document.getElementById("close-item-delete");
    const cancel = document.getElementById("cancel-item-delete");
    const confirm = document.getElementById("confirm-item-delete");
    const error = document.getElementById("item-delete-error");
    const status = document.getElementById("item-delete-status");
    const reload = document.getElementById("reload-item-delete");
    const uncertainURLs = new Set();
    let deleting = false;
    let uncertain = false;

    function busy() {
        modal.setAttribute("aria-busy", String(deleting));
        close.disabled = deleting;
        cancel.disabled = deleting;
        confirm.disabled = deleting || uncertain;
        reload.disabled = deleting;
        confirm.textContent = deleting ? "Menghapus…" : "Ya, Hapus Permanen";
        status.hidden = !deleting;
        status.textContent = deleting ? "Menghapus pakaian…" : "";
    }

    function showError(message, needsReload = false) {
        error.textContent = message;
        error.hidden = !message;
        reload.hidden = !needsReload;
        if (needsReload) {
            uncertain = true;
            uncertainURLs.add(form.action);
        }
    }

    document.addEventListener("wardrobe:delete-item", (event) => {
        if (modal.open) return;
        const { item, url } = event.detail;
        const action = new URL(url, window.location.origin);
        if (action.origin !== window.location.origin) return;
        form.action = action.href;
        name.textContent = item.name;
        deleting = false;
        uncertain = uncertainURLs.has(action.href);
        showError(uncertain ? "Status penghapusan sebelumnya belum dapat dipastikan. Muat ulang halaman untuk memeriksa hasilnya." : "", uncertain);
        busy();
        modal.showModal();
        document.documentElement.classList.add("wardrobe-modal-open");
        cancel.focus();
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (deleting || uncertain) return;
        const data = new FormData(form);
        showError("");
        deleting = true;
        busy();
        try {
            const response = await fetch(form.action, {
                method: "POST", body: data, credentials: "same-origin", cache: "no-store",
                headers: { Accept: "application/json" },
            });
            if (response.status === 403 || response.status === 404) {
                showError("Pakaian sudah tidak tersedia atau sesi login berubah. Muat ulang halaman sebelum melanjutkan.", true);
            } else {
                const result = await response.json();
                if (response.ok && result.ok === true) {
                    // Pertahankan URL beserta filter kategori yang sedang aktif.
                    window.location.reload();
                    return;
                }
                if (response.status !== 500 || !result.errors) throw new Error("UNKNOWN_RESULT");
                const messages = Object.values(result.errors).flat().map((entry) => entry.message);
                showError(messages.join(" ") || "Pakaian gagal dihapus. Silakan coba lagi.");
            }
        } catch {
            showError("Status penghapusan belum dapat dipastikan. Muat ulang halaman untuk memeriksa hasil sebelum mencoba lagi.", true);
        }
        deleting = false;
        busy();
        error.focus();
    });

    function dismiss() { if (!deleting) modal.close(); }
    close.addEventListener("click", dismiss);
    cancel.addEventListener("click", dismiss);
    reload.addEventListener("click", () => window.location.reload());
    modal.addEventListener("cancel", (event) => { if (deleting) event.preventDefault(); });
    modal.addEventListener("click", (event) => {
        if (event.target !== modal) return;
        const bounds = modal.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dismiss();
    });
    modal.addEventListener("close", () => {
        form.reset();
        name.textContent = "";
        showError("");
        if (!document.querySelector("dialog[open]")) document.documentElement.classList.remove("wardrobe-modal-open");
    });
})();
