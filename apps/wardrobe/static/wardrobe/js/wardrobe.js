(() => {
    function setupDialog(id, triggerId, closeId, defaultFocus) {
        const modal = document.getElementById(id);
        const trigger = document.getElementById(triggerId);
        if (!modal || !trigger) return;

        const openModal = () => {
            if (modal.open) return;
            modal.showModal();
            document.documentElement.classList.add("wardrobe-modal-open");
            const focusTarget = modal.querySelector('[tabindex="-1"], [aria-invalid="true"]')
                || document.getElementById(defaultFocus);
            focusTarget?.focus();
        };
        trigger.addEventListener("click", openModal);
        document.getElementById(closeId).addEventListener("click", () => modal.close());
        modal.addEventListener("close", () => {
            if (!document.querySelector("dialog[open]")) {
                document.documentElement.classList.remove("wardrobe-modal-open");
            }
            trigger.focus();
        });
        modal.addEventListener("click", (event) => {
            if (event.target !== modal) return;
            const bounds = modal.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right ||
                event.clientY < bounds.top || event.clientY > bounds.bottom) modal.close();
        });
        if (modal.dataset.openOnLoad === "true") openModal();
    }

    setupDialog("category-modal", "open-category-modal", "close-category-modal", "category-name");
    setupDialog("item-modal", "open-item-modal", "close-item-modal", "item-name");

    const form = document.getElementById("item-form");
    if (!form) return;

    const input = document.getElementById("item-photos");
    const zone = document.getElementById("item-upload-zone");
    const previews = document.getElementById("item-photo-previews");
    const status = document.getElementById("item-photos-status");
    const submit = document.getElementById("save-item");
    const nameInput = document.getElementById("item-name");
    const categoryInput = document.getElementById("item-category");
    const allowedTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
    const maxPhotos = 5;
    const maxBytes = 5_000_000;
    let selected = [];
    let checking = false;
    let submitting = false;
    form.noValidate = true;

    function showError(field, message) {
        const element = document.getElementById(`${field.id}-client-error`);
        element.textContent = message;
        element.hidden = !message;
        field.toggleAttribute("aria-invalid", Boolean(message));
        if (message) field.setAttribute("aria-invalid", "true");
    }

    function clearServerError(field) {
        const element = document.getElementById(`${field.id}-errors`);
        if (element) element.hidden = true;
    }

    function syncInput() {
        const transfer = new DataTransfer();
        selected.forEach(({ file }) => transfer.items.add(file));
        input.files = transfer.files;
    }

    function updateBusyState() {
        submit.disabled = checking || submitting || submit.dataset.noCategories === "true";
        submit.textContent = submitting ? "Menyimpan…" : "Simpan";
        form.setAttribute("aria-busy", String(checking || submitting));
        previews.querySelectorAll("button").forEach((button) => {
            button.disabled = checking || submitting;
        });
    }

    function renderPreviews() {
        previews.replaceChildren();
        previews.hidden = selected.length === 0;
        selected.forEach(({ file, url }, index) => {
            const card = document.createElement("li");
            card.className = "item-photo-preview";
            const image = document.createElement("img");
            image.src = url;
            image.alt = `Preview foto ${index + 1}: ${file.name}`;
            const filename = document.createElement("p");
            filename.textContent = file.name;
            filename.className = "item-photo-filename";
            filename.title = file.name;
            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "item-photo-remove";
            remove.textContent = "Hapus";
            remove.setAttribute("aria-label", `Hapus foto ${index + 1}: ${file.name}`);
            remove.addEventListener("click", () => {
                URL.revokeObjectURL(selected[index].url);
                selected.splice(index, 1);
                syncInput();
                renderPreviews();
                showError(input, "");
                const buttons = previews.querySelectorAll("button");
                (buttons[Math.min(index, buttons.length - 1)] || input).focus();
            });
            card.append(image, filename, remove);
            previews.append(card);
        });
        status.textContent = selected.length ? `${selected.length} dari 5 foto dipilih. Foto pertama menjadi gambar kartu.` : "Belum ada foto dipilih.";
        updateBusyState();
    }

    async function addFiles(files) {
        if (!files.length) return;
        if (checking || submitting) {
            syncInput();
            return;
        }
        clearServerError(input);
        if (selected.length + files.length > maxPhotos) {
            showError(input, "Maksimal lima foto. Hapus pilihan yang tidak diperlukan sebelum menambah foto.");
            syncInput();
            return;
        }
        checking = true;
        updateBusyState();
        status.textContent = "Memeriksa foto…";
        const additions = [];
        try {
            for (const file of files) {
                if (file.size > maxBytes) throw new Error(`Foto “${file.name}” melebihi batas 5 MB.`);
                if (!/\.(jpe?g|png|webp)$/i.test(file.name) || (file.type && !allowedTypes.has(file.type))) {
                    throw new Error(`Foto “${file.name}” harus berformat JPG, PNG, atau WebP.`);
                }
                const url = URL.createObjectURL(file);
                additions.push({ file, url });
                const image = new Image();
                image.src = url;
                try {
                    await image.decode();
                } catch {
                    throw new Error(`Foto “${file.name}” tidak dapat dibaca. Pilih gambar yang valid.`);
                }
            }
            selected.push(...additions);
            showError(input, "");
            const reselect = document.getElementById("item-photos-reselect");
            if (reselect) reselect.hidden = true;
        } catch (error) {
            additions.forEach(({ url }) => URL.revokeObjectURL(url));
            showError(input, error.message);
        } finally {
            checking = false;
            syncInput();
            renderPreviews();
        }
    }

    input.addEventListener("change", () => addFiles(Array.from(input.files)));
    zone.addEventListener("dragover", (event) => {
        event.preventDefault();
        zone.classList.add("is-dragging");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("is-dragging"));
    zone.addEventListener("drop", (event) => {
        event.preventDefault();
        zone.classList.remove("is-dragging");
        addFiles(Array.from(event.dataTransfer.files));
    });
    [nameInput, categoryInput].forEach((field) => {
        field.addEventListener("input", () => {
            clearServerError(field);
            showError(field, "");
        });
    });
    form.addEventListener("submit", (event) => {
        if (checking || submitting) {
            event.preventDefault();
            return;
        }
        showError(nameInput, !nameInput.value.trim() ? "Nama pakaian wajib diisi." : nameInput.value.length > 100 ? "Nama pakaian maksimal 100 karakter." : "");
        showError(categoryInput, !categoryInput.value ? "Kategori wajib dipilih." : "");
        showError(input, !selected.length ? "Tambahkan minimal satu foto pakaian." : "");
        const firstInvalid = form.querySelector('[aria-invalid="true"]');
        if (firstInvalid) {
            event.preventDefault();
            firstInvalid.focus();
            return;
        }
        syncInput();
        submitting = true;
        updateBusyState();
    });
    window.addEventListener("pageshow", () => {
        submitting = false;
        updateBusyState();
    });
})();
