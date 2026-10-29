(() => {
    const modal = document.getElementById("item-edit-modal");
    if (!modal) return;
    const form = document.getElementById("item-edit-form");
    const name = document.getElementById("edit-item-name");
    const category = document.getElementById("edit-item-category");
    const input = document.getElementById("edit-item-photos");
    const zone = document.getElementById("edit-upload-zone");
    const oldList = document.getElementById("edit-old-photos");
    const newList = document.getElementById("edit-new-photos");
    const status = document.getElementById("edit-photos-status");
    const generalError = document.getElementById("item-edit-errors");
    const reload = document.getElementById("reload-item-edit");
    const save = document.getElementById("save-item-edit");
    const close = document.getElementById("close-item-edit");
    const cancel = document.getElementById("cancel-item-edit");
    const fields = {
        name: [name, document.getElementById("edit-name-error")],
        category: [category, document.getElementById("edit-category-error")],
        photos: [input, document.getElementById("edit-photos-error")],
    };
    let photos = [];
    let additions = [];
    let removed = new Set();
    let checking = false;
    let saving = false;
    let uncertain = false;
    let generation = 0;
    const uncertainURLs = new Set();

    function errorFor(key, message) {
        const [field, error] = fields[key];
        error.textContent = message;
        error.hidden = !message;
        if (message) field.setAttribute("aria-invalid", "true");
        else field.removeAttribute("aria-invalid");
    }

    function showGeneral(message) {
        generalError.textContent = message;
        generalError.hidden = !message;
    }

    function total() { return photos.length - removed.size + additions.length; }

    function busy() {
        form.setAttribute("aria-busy", String(saving || checking));
        form.querySelectorAll("input, select, button").forEach((element) => {
            element.disabled = saving;
        });
        input.disabled = checking || saving || uncertain;
        modal.querySelectorAll(".item-photo-remove").forEach((button) => {
            button.disabled = checking || saving || uncertain;
        });
        close.disabled = saving;
        save.disabled = saving || checking || uncertain;
        save.textContent = saving ? "Menyimpan…" : "Simpan";
    }

    function renderPhotos() {
        oldList.replaceChildren();
        newList.replaceChildren();
        const makeCard = (url, label, action, actionLabel, handler, marked = false) => {
            const card = document.createElement("li");
            card.className = `item-photo-preview${marked ? " is-pending-delete" : ""}`;
            const image = document.createElement("img");
            image.src = url;
            image.alt = label;
            const caption = document.createElement("p");
            caption.className = "item-photo-filename";
            caption.textContent = marked ? `${label} · Akan dihapus` : label;
            caption.title = caption.textContent;
            const fallback = document.createElement("p");
            fallback.className = "item-photo-filename";
            fallback.textContent = "Foto tidak dapat dimuat.";
            fallback.hidden = true;
            image.addEventListener("error", () => { image.hidden = true; fallback.hidden = false; });
            const button = document.createElement("button");
            button.type = "button";
            button.className = "item-photo-remove";
            button.textContent = action;
            button.setAttribute("aria-label", actionLabel);
            button.addEventListener("click", handler);
            card.append(image, fallback, caption, button);
            return card;
        };
        photos.forEach((photo, index) => {
            const marked = removed.has(photo.id);
            oldList.append(makeCard(photo.url, `Foto lama ${index + 1}`,
                marked ? "Batalkan hapus" : "Hapus", `${marked ? "Batalkan hapus" : "Hapus"} foto lama ${index + 1}`, () => {
                    if (marked && total() >= 5) {
                        errorFor("photos", "Maksimal lima foto. Kurangi foto baru sebelum membatalkan penghapusan.");
                        input.focus();
                        return;
                    }
                    if (marked) removed.delete(photo.id);
                    else removed.add(photo.id);
                    errorFor("photos", "");
                    renderPhotos();
                    oldList.children[index].querySelector("button").focus();
                }, marked));
        });
        additions.forEach((entry, index) => {
            newList.append(makeCard(entry.url, entry.file.name, "Hapus", `Hapus foto baru ${index + 1}: ${entry.file.name}`, () => {
                URL.revokeObjectURL(entry.url);
                additions.splice(index, 1);
                errorFor("photos", "");
                renderPhotos();
                (newList.children[Math.min(index, additions.length - 1)]?.querySelector("button") || input).focus();
            }));
        });
        newList.hidden = additions.length === 0;
        status.textContent = `${total()} dari 5 foto dipertahankan (${photos.length - removed.size} lama, ${additions.length} baru). Foto pertama menjadi gambar kartu.`;
        busy();
    }

    async function addFiles(files) {
        input.value = "";
        if (!files.length || checking || saving || uncertain) return;
        if (total() + files.length > 5) {
            errorFor("photos", "Total foto lama dan baru maksimal lima. Tandai foto lama untuk dihapus atau kurangi foto baru.");
            return;
        }
        const version = generation;
        const pending = [];
        checking = true;
        busy();
        status.textContent = "Memeriksa foto…";
        try {
            for (const file of files) {
                if (file.size > 5_000_000) throw new Error(`Foto “${file.name}” melebihi batas 5 MB.`);
                if (!/\.(jpe?g|png|webp)$/i.test(file.name) || (file.type && !["image/jpeg", "image/png", "image/webp"].includes(file.type))) {
                    throw new Error(`Foto “${file.name}” harus berformat JPG, PNG, atau WebP.`);
                }
                const entry = { file, url: URL.createObjectURL(file) };
                pending.push(entry);
                const image = new Image();
                image.src = entry.url;
                try { await image.decode(); }
                catch { throw new Error(`Foto “${file.name}” tidak dapat dibaca. Pilih gambar yang valid.`); }
                if (version !== generation || !modal.open) return;
            }
            additions.push(...pending);
            pending.length = 0;
            errorFor("photos", "");
        } catch (error) {
            if (version === generation && modal.open) errorFor("photos", error.message);
        } finally {
            pending.forEach(({ url }) => URL.revokeObjectURL(url));
            if (version === generation) {
                checking = false;
                renderPhotos();
            }
        }
    }

    document.addEventListener("wardrobe:edit-item", (event) => {
        if (modal.open) return;
        const { item, url } = event.detail;
        const action = new URL(url, window.location.origin);
        if (action.origin !== window.location.origin) return;
        generation += 1;
        form.reset();
        form.action = action.href;
        photos = item.photos.map((photo) => ({ ...photo }));
        additions = [];
        removed = new Set();
        checking = false;
        saving = false;
        uncertain = uncertainURLs.has(action.href);
        Object.keys(fields).forEach((key) => errorFor(key, ""));
        showGeneral(uncertain ? "Status penyimpanan sebelumnya belum dapat dipastikan. Muat ulang halaman sebelum mengirim perubahan lagi." : "");
        reload.hidden = !uncertain;
        name.value = item.name;
        category.value = item.category ? String(item.category.id) : "";
        document.getElementById("edit-category-help").hidden = Boolean(category.value);
        renderPhotos();
        modal.showModal();
        document.documentElement.classList.add("wardrobe-modal-open");
        name.focus();
    });

    input.addEventListener("change", () => addFiles(Array.from(input.files)));
    zone.addEventListener("dragover", (event) => {
        event.preventDefault();
        if (!saving && !checking && !uncertain) zone.classList.add("is-dragging");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("is-dragging"));
    zone.addEventListener("drop", (event) => {
        event.preventDefault();
        zone.classList.remove("is-dragging");
        addFiles(Array.from(event.dataTransfer.files));
    });
    name.addEventListener("input", () => errorFor("name", ""));
    category.addEventListener("change", () => {
        errorFor("category", "");
        document.getElementById("edit-category-help").hidden = Boolean(category.value);
    });
    name.addEventListener("blur", () => {
        errorFor("name", name.value.trim() ? "" : "Nama pakaian wajib diisi.");
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (checking || saving || uncertain) return;
        showGeneral("");
        errorFor("name", !name.value.trim() ? "Nama pakaian wajib diisi." : name.value.length > 100 ? "Nama pakaian maksimal 100 karakter." : "");
        errorFor("category", category.value ? "" : "Kategori wajib dipilih.");
        errorFor("photos", total() < 1 || total() > 5 ? "Jumlah akhir foto harus antara satu dan lima." : "");
        const invalid = form.querySelector('[aria-invalid="true"]');
        if (invalid) { invalid.focus(); return; }
        const data = new FormData(form);
        removed.forEach((id) => data.append("delete_photos", String(id)));
        additions.forEach(({ file }) => data.append("photos", file));
        saving = true;
        busy();
        status.textContent = "Menyimpan perubahan…";
        try {
            const response = await fetch(form.action, {
                method: "POST", body: data, credentials: "same-origin", cache: "no-store",
                headers: { Accept: "application/json" },
            });
            if (response.status === 403 || response.status === 404) {
                showGeneral("Pakaian tidak tersedia atau sesi login berubah. Muat ulang halaman sebelum melanjutkan.");
                uncertain = true;
                uncertainURLs.add(form.action);
                reload.hidden = false;
            } else {
                const result = await response.json();
                if (response.ok && result.ok === true) {
                    status.textContent = "Perubahan tersimpan. Memuat ulang koleksi…";
                    // Reload URL saat ini agar filter kategori tetap aktif.
                    window.location.reload();
                    return;
                }
                if (!result.errors || ![400, 500].includes(response.status)) throw new Error("UNKNOWN_RESULT");
                for (const [key, errors] of Object.entries(result.errors)) {
                    const message = errors.map((error) => error.message).join(" ");
                    if (fields[key]) errorFor(key, message);
                    else showGeneral([generalError.textContent, message].filter(Boolean).join(" "));
                }
            }
            saving = false;
            renderPhotos();
            (form.querySelector('[aria-invalid="true"]') || generalError).focus();
        } catch {
            saving = false;
            uncertain = true;
            uncertainURLs.add(form.action);
            reload.hidden = false;
            showGeneral("Status penyimpanan belum dapat dipastikan. Muat ulang halaman untuk memeriksa hasil sebelum mengirim perubahan lagi.");
            busy();
            generalError.focus();
        }
    });

    function dismiss() { if (!saving) modal.close(); }
    close.addEventListener("click", dismiss);
    cancel.addEventListener("click", dismiss);
    reload.addEventListener("click", () => window.location.reload());
    modal.addEventListener("cancel", (event) => { if (saving) event.preventDefault(); });
    modal.addEventListener("click", (event) => {
        if (event.target !== modal) return;
        const bounds = modal.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dismiss();
    });
    modal.addEventListener("close", () => {
        generation += 1;
        additions.forEach(({ url }) => URL.revokeObjectURL(url));
        additions = [];
        photos = [];
        removed.clear();
        checking = false;
        form.reset();
        oldList.replaceChildren();
        newList.replaceChildren();
        zone.classList.remove("is-dragging");
        if (!document.querySelector("dialog[open]")) document.documentElement.classList.remove("wardrobe-modal-open");
    });
})();
