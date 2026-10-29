(() => {
    const byId = (id) => document.getElementById(id);
    const form = byId("item-form");
    if (!form) return;
    const modal = byId("item-modal");
    const confirmModal = byId("draft-discard-modal");
    const name = byId("item-name");
    const category = byId("item-category");
    const input = byId("item-photos");
    const save = byId("save-item");
    const saveDraft = byId("save-item-draft");
    const discard = byId("discard-item-draft");
    const reload = byId("item-draft-reload");
    const operationError = byId("item-operation-error");
    const state = byId("item-draft-state");
    const savedList = byId("item-saved-photos");
    const newList = byId("item-photo-previews");
    const zone = byId("item-upload-zone");
    let draft = null;
    let selected = [];
    let removed = new Set();
    let loading = false;
    let checking = false;
    let submitting = false;
    let blocked = true;
    let pageReloadRequired = false;
    let generation = 0;
    let readController;
    form.noValidate = true;

    function message(element, text) {
        element.textContent = text;
        element.hidden = !text;
    }
    function fieldError(field, text) {
        message(byId(`${field.id}-client-error`), text);
        if (text) field.setAttribute("aria-invalid", "true");
        else field.removeAttribute("aria-invalid");
    }
    function clearErrors() {
        [name, category, input].forEach((field) => {
            fieldError(field, "");
            const serverError = byId(`${field.id}-errors`);
            if (serverError) serverError.hidden = true;
        });
        const serverError = byId("item-form-errors");
        if (serverError) serverError.hidden = true;
        message(operationError, "");
    }
    function count() {
        return (draft?.photos.filter((photo) => !removed.has(photo.id)).length || 0) + selected.length;
    }
    function updateControls() {
        const busy = loading || checking || submitting;
        [name, category, input].forEach((field) => { field.disabled = busy || blocked; });
        save.disabled = busy || blocked || category.options.length < 2;
        saveDraft.disabled = busy || blocked;
        discard.disabled = busy || blocked;
        reload.disabled = busy;
        byId("close-item-modal").disabled = submitting;
        save.textContent = submitting ? "Menyimpan…" : "Simpan";
        form.setAttribute("aria-busy", String(busy));
        [...savedList.querySelectorAll("button"), ...newList.querySelectorAll("button")].forEach((button) => {
            button.disabled = busy || blocked;
        });
        confirmModal.querySelectorAll("button").forEach((button) => { button.disabled = submitting; });
        byId("confirm-draft-discard").disabled = submitting || blocked;
        zone.setAttribute("aria-disabled", String(busy || blocked));
    }
    function releaseSelected() {
        selected.forEach(({ url }) => URL.revokeObjectURL(url));
        selected = [];
        input.value = "";
    }
    function preview(url, label, action, handler, pending = false) {
        const card = document.createElement("li");
        card.className = `item-photo-preview${pending ? " is-pending-delete" : ""}`;
        const image = document.createElement("img");
        image.src = url;
        image.alt = label;
        image.addEventListener("error", () => { image.alt = `${label} — foto tidak dapat dimuat`; });
        const caption = document.createElement("p");
        caption.className = "item-photo-filename";
        caption.textContent = pending ? `${label} (akan dihapus)` : label;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "item-photo-remove";
        button.textContent = action;
        button.setAttribute("aria-label", `${action} ${label}`);
        button.addEventListener("click", handler);
        card.append(image, caption, button);
        return card;
    }
    function renderPhotos() {
        savedList.replaceChildren();
        (draft?.photos || []).forEach((photo, index) => {
            const pending = removed.has(photo.id);
            savedList.append(preview(photo.url, `Foto tersimpan ${index + 1}`, pending ? "Batalkan hapus" : "Hapus", () => {
                if (pending && count() >= 5) {
                    fieldError(input, "Maksimal 5 foto. Hapus pilihan foto lain sebelum mengembalikan foto ini.");
                    return;
                }
                if (pending) removed.delete(photo.id);
                else removed.add(photo.id);
                fieldError(input, "");
                renderPhotos();
                savedList.querySelectorAll("button")[index]?.focus();
            }, pending));
        });
        savedList.hidden = !draft?.photos.length;
        newList.replaceChildren();
        selected.forEach(({ file, url }, index) => {
            newList.append(preview(url, `Foto baru ${index + 1}: ${file.name}`, "Hapus", () => {
                URL.revokeObjectURL(selected[index].url);
                selected.splice(index, 1);
                fieldError(input, "");
                renderPhotos();
                (newList.querySelectorAll("button")[index] || input).focus();
            }));
        });
        newList.hidden = !selected.length;
        byId("item-photos-status").textContent = draft
            ? `${count()} dari 5 foto. Foto yang ditandai dihapus baru dihapus setelah Draft atau Simpan berhasil.`
            : `${count()} dari 5 foto dipilih. Foto pertama menjadi gambar kartu.`;
        updateControls();
    }
    function applyDraft(value) {
        releaseSelected();
        removed.clear();
        draft = value;
        name.value = value?.name || "";
        if (value?.category && ![...category.options].some((option) => option.value === String(value.category.id))) {
            category.add(new Option(value.category.name, value.category.id));
        }
        category.value = value?.category ? String(value.category.id) : "";
        byId("item-draft-id").value = value?.id || "";
        byId("item-draft-version").value = value?.version || "";
        discard.hidden = !value;
        input.required = !value;
        message(state, value ? "Draft tersimpan dimuat. Lengkapi isian lalu Simpan, atau simpan kembali sebagai Draft." : "");
        renderPhotos();
    }
    function requireReload(text, wholePage = false) {
        blocked = true;
        pageReloadRequired = wholePage;
        reload.textContent = wholePage ? "Muat ulang halaman" : "Muat ulang draft";
        reload.hidden = false;
        message(operationError, text);
        updateControls();
    }
    async function loadDraft() {
        readController?.abort();
        const controller = new AbortController();
        readController = controller;
        const version = ++generation;
        loading = true;
        blocked = true;
        pageReloadRequired = false;
        reload.hidden = true;
        message(operationError, "");
        message(state, "Memeriksa draft tersimpan…");
        updateControls();
        const timeout = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(form.dataset.currentDraftUrl, {
                headers: { Accept: "application/json" }, credentials: "same-origin", cache: "no-store", signal: controller.signal,
            });
            if (!response.ok) throw new Error("read_failed");
            const result = await response.json();
            if (version !== generation || !modal.open) return;
            if (!result.ok || !(result.draft === null || (result.draft.version && Array.isArray(result.draft.photos)))) throw new Error("invalid_response");
            if (result.draft || draft) applyDraft(result.draft);
            else message(state, "");
            blocked = false;
            clearErrors();
            reload.hidden = true;
        } catch (error) {
            if (version !== generation || !modal.open) return;
            message(state, "");
            requireReload("Draft belum dapat dimuat. Muat ulang draft sebelum menyimpan agar draft tersimpan tetap aman.");
            operationError.focus();
        } finally {
            clearTimeout(timeout);
            if (version === generation) {
                loading = false;
                updateControls();
                if (!blocked) name.focus();
            }
        }
    }
    async function addFiles(files) {
        if (!files.length || loading || checking || submitting || blocked) return;
        fieldError(input, "");
        if (count() + files.length > 5) { fieldError(input, "Maksimal 5 foto, termasuk foto draft yang dipertahankan."); return; }
        const version = ++generation;
        const pending = [];
        const allowedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
        checking = true;
        updateControls();
        try {
            for (const file of files) {
                if (file.size > 5_000_000) throw new Error("Ukuran setiap foto maksimal 5 MB.");
                if (!allowedTypes.has(file.type) || !/\.(jpe?g|png|webp)$/i.test(file.name)) {
                    throw new Error("Gunakan foto JPG, PNG, atau WebP yang valid.");
                }
                const url = URL.createObjectURL(file);
                pending.push({ file, url });
                const image = new Image();
                image.src = url;
                try {
                    await image.decode();
                } catch {
                    throw new Error("Foto rusak atau tidak dapat dibaca. Pilih foto lain.");
                }
            }
            if (version !== generation || !modal.open) return;
            selected.push(...pending.splice(0));
            renderPhotos();
        } catch (error) {
            if (version === generation && modal.open) fieldError(input, error.message);
        } finally {
            pending.forEach(({ url }) => URL.revokeObjectURL(url));
            if (version === generation) { checking = false; updateControls(); }
        }
    }
    input.addEventListener("change", () => { const files = [...input.files]; input.value = ""; addFiles(files); });
    zone.addEventListener("dragover", (event) => { event.preventDefault(); });
    zone.addEventListener("drop", (event) => { event.preventDefault(); addFiles([...event.dataTransfer.files]); });
    [name, category].forEach((field) => field.addEventListener("input", () => fieldError(field, "")));
    function validate(partial) {
        clearErrors();
        if (name.value.trim().length > 100) fieldError(name, "Nama pakaian maksimal 100 karakter.");
        if (!partial) {
            if (!name.value.trim()) fieldError(name, "Isi nama pakaian.");
            if (!category.value) fieldError(category, "Pilih kategori pakaian.");
            if (!count()) fieldError(input, "Tambahkan minimal 1 foto pakaian.");
        } else if (!name.value.trim() && !category.value && !count()) {
            message(operationError, "Isi setidaknya nama, kategori, atau satu foto untuk menyimpan Draft.");
        }
        if (count() > 5) fieldError(input, "Maksimal 5 foto pakaian.");
        const invalid = form.querySelector('[aria-invalid="true"]');
        if (invalid || !operationError.hidden) { (invalid || operationError).focus(); return false; }
        return true;
    }
    function requestData() {
        const data = new FormData(form);
        data.delete("photos");
        data.delete("delete_photos");
        selected.forEach(({ file }) => data.append("photos", file));
        removed.forEach((id) => data.append("delete_photos", id));
        return data;
    }
    function serverErrors(result) {
        const fields = { name, category, photos: input, delete_photos: input };
        const general = [];
        Object.entries(result.errors || {}).forEach(([key, errors]) => {
            const text = errors.map((error) => error.message).join(" ");
            if (fields[key]) fieldError(fields[key], text);
            else general.push(text);
        });
        message(operationError, general.join(" "));
        if (!form.querySelector('[aria-invalid="true"]') && operationError.hidden) message(operationError, "Penyimpanan gagal. Periksa isian dan coba lagi.");
    }
    async function submit(partial) {
        if (blocked || loading || checking || submitting || !validate(partial)) return;
        const data = requestData();
        const wasDraft = Boolean(draft);
        const url = partial ? form.dataset.saveDraftUrl : wasDraft ? form.dataset.completeDraftUrl : form.action;
        submitting = true;
        updateControls();
        try {
            const response = await fetch(url, { method: "POST", body: data, headers: { Accept: "application/json" }, credentials: "same-origin", cache: "no-store" });
            const result = await response.json();
            if (response.ok && result.ok) {
                if (partial) {
                    applyDraft(result.draft);
                    modal.close();
                    message(byId("wardrobe-feedback"), "Draft tersimpan. Buka Tambah Baju untuk melanjutkan.");
                } else { window.location.reload(); return; }
            } else if (response.status === 409) {
                requireReload("Draft sudah berubah di tab lain. Muat ulang draft sebelum melanjutkan.");
            } else if (response.status === 400) {
                serverErrors(result);
            } else {
                requireReload("Penyimpanan belum dapat dipastikan. Muat ulang untuk memeriksa hasil sebelum mencoba lagi.", !wasDraft && !partial);
            }
        } catch (error) {
            requireReload("Koneksi terputus atau respons tidak dapat dibaca. Muat ulang untuk memeriksa hasil penyimpanan.", !wasDraft && !partial);
        } finally {
            submitting = false;
            updateControls();
            if (modal.open) (form.querySelector('[aria-invalid="true"]') || (!operationError.hidden ? operationError : name)).focus();
        }
    }
    form.addEventListener("submit", (event) => { event.preventDefault(); submit(false); });
    saveDraft.addEventListener("click", () => submit(true));
    reload.addEventListener("click", () => { if (pageReloadRequired) window.location.reload(); else loadDraft(); });
    function open() {
        if (modal.open) return;
        modal.showModal();
        document.documentElement.classList.add("wardrobe-modal-open");
        if (pageReloadRequired) {
            requireReload("Muat ulang halaman untuk memeriksa hasil penyimpanan sebelumnya.", true);
        } else loadDraft();
    }
    byId("open-item-modal").addEventListener("click", open);
    byId("close-item-modal").addEventListener("click", () => { if (!submitting) modal.close(); });
    function backdrop(dialog, event) {
        if (submitting || event.target !== dialog) return;
        const bounds = dialog.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    }
    [modal, confirmModal].forEach((dialog) => {
        dialog.addEventListener("cancel", (event) => { if (submitting) event.preventDefault(); });
        dialog.addEventListener("click", (event) => backdrop(dialog, event));
    });
    modal.addEventListener("close", () => {
        ++generation;
        readController?.abort();
        loading = false;
        checking = false;
        if (draft) applyDraft(draft);
        if (!document.querySelector("dialog[open]")) document.documentElement.classList.remove("wardrobe-modal-open");
        byId("open-item-modal").focus();
    });
    discard.addEventListener("click", () => {
        if (!draft || submitting || blocked) return;
        message(byId("draft-discard-error"), "");
        confirmModal.showModal();
        byId("cancel-draft-discard").focus();
    });
    ["close-draft-discard", "cancel-draft-discard"].forEach((id) => byId(id).addEventListener("click", () => { if (!submitting) confirmModal.close(); }));
    confirmModal.addEventListener("close", () => { (discard.hidden ? name : discard).focus(); });
    byId("confirm-draft-discard").addEventListener("click", async () => {
        if (!draft || submitting || blocked) return;
        const data = new FormData();
        data.set("csrfmiddlewaretoken", form.elements.csrfmiddlewaretoken.value);
        data.set("draft_id", draft.id);
        data.set("version", draft.version);
        submitting = true;
        updateControls();
        try {
            const response = await fetch(form.dataset.discardDraftUrl, { method: "POST", body: data, headers: { Accept: "application/json" }, credentials: "same-origin", cache: "no-store" });
            const result = await response.json();
            if (response.ok && result.ok) {
                applyDraft(null);
                clearErrors();
                confirmModal.close();
                message(state, "Draft dibuang. Kamu bisa mulai pakaian baru.");
            } else {
                requireReload(response.status === 409 ? "Draft sudah berubah. Muat ulang draft sebelum membuangnya." : "Draft belum dapat dibuang. Muat ulang untuk memeriksa kondisinya.");
                message(byId("draft-discard-error"), "Draft belum dibuang atau hasilnya belum pasti. Tutup konfirmasi lalu muat ulang draft.");
            }
        } catch (error) {
            requireReload("Koneksi terputus. Muat ulang untuk memeriksa apakah draft sudah dibuang.");
            message(byId("draft-discard-error"), "Koneksi terputus. Tutup konfirmasi lalu muat ulang draft.");
        } finally {
            submitting = false;
            updateControls();
            if (confirmModal.open) byId("draft-discard-error").focus();
            else name.focus();
        }
    });
    updateControls();
    if (modal.dataset.openOnLoad === "true") open();
})();
