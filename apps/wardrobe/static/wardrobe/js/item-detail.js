(() => {
    const modal = document.getElementById("item-detail-modal");
    if (!modal) return;

    const close = document.getElementById("close-item-detail");
    const loading = document.getElementById("item-detail-loading");
    const errorPanel = document.getElementById("item-detail-error");
    const errorMessage = document.getElementById("item-detail-error-message");
    const retry = document.getElementById("retry-item-detail");
    const content = document.getElementById("item-detail-content");
    const name = document.getElementById("detail-item-name");
    const category = document.getElementById("detail-item-category");
    const photoLoading = document.getElementById("detail-photo-loading");
    const photoEmpty = document.getElementById("detail-photo-empty");
    const photoError = document.getElementById("detail-photo-error");
    const navigation = document.getElementById("detail-photo-navigation");
    const previous = document.getElementById("detail-previous-photo");
    const next = document.getElementById("detail-next-photo");
    const counter = document.getElementById("detail-photo-counter");
    const thumbnails = document.getElementById("detail-photo-thumbnails");
    const help = document.getElementById("detail-gallery-help");
    let mainPhoto = document.getElementById("detail-main-photo");
    let trigger = null;
    let detailURL = null;
    let controller = null;
    let requestVersion = 0;
    let photoVersion = 0;
    let item = null;
    let photoIndex = 0;

    function clearPhoto() {
        photoVersion += 1;
        mainPhoto.hidden = true;
        mainPhoto.removeAttribute("src");
        photoLoading.hidden = true;
        photoEmpty.hidden = true;
        photoError.hidden = true;
    }

    function showPhoto(index) {
        if (!item || !item.photos.length || index < 0 || index >= item.photos.length) return;
        clearPhoto();
        photoIndex = index;
        const version = photoVersion;
        previous.disabled = index === 0;
        next.disabled = index === item.photos.length - 1;
        counter.textContent = `Foto ${index + 1} dari ${item.photos.length}`;
        thumbnails.querySelectorAll("button").forEach((button, buttonIndex) => {
            button.setAttribute("aria-pressed", String(buttonIndex === index));
        });
        photoLoading.hidden = false;
        const image = document.createElement("img");
        image.id = "detail-main-photo";
        image.className = "detail-main-photo";
        image.alt = `${item.name}, foto ${index + 1} dari ${item.photos.length}`;
        image.decoding = "async";
        image.hidden = true;
        image.addEventListener("load", () => {
            if (version !== photoVersion || !modal.open) return;
            photoLoading.hidden = true;
            image.hidden = false;
        });
        image.addEventListener("error", () => {
            if (version !== photoVersion || !modal.open) return;
            photoLoading.hidden = true;
            photoError.hidden = false;
        });
        mainPhoto.replaceWith(image);
        mainPhoto = image;
        image.src = item.photos[index].url;
    }

    function renderItem(data) {
        item = data;
        name.textContent = item.name;
        category.textContent = item.category ? item.category.name : "Tanpa kategori";
        thumbnails.replaceChildren();
        navigation.hidden = item.photos.length === 0;
        previous.hidden = item.photos.length < 2;
        next.hidden = item.photos.length < 2;
        thumbnails.hidden = item.photos.length < 2;
        help.hidden = item.photos.length < 2;
        item.photos.forEach((photo, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "detail-photo-thumbnail";
            button.setAttribute("aria-label", `Tampilkan foto ${index + 1} dari ${item.photos.length}`);
            button.setAttribute("aria-pressed", "false");
            const image = document.createElement("img");
            image.src = photo.url;
            image.alt = "";
            image.addEventListener("error", () => { image.hidden = true; });
            const label = document.createElement("span");
            label.textContent = `Foto ${index + 1}`;
            button.append(image, label);
            button.addEventListener("click", () => showPhoto(index));
            thumbnails.append(button);
        });
        content.hidden = false;
        if (item.photos.length) showPhoto(0);
        else photoEmpty.hidden = false;
    }

    function validateItem(data) {
        if (!data || typeof data.name !== "string" || !Array.isArray(data.photos) || data.photos.length > 5) {
            throw new Error("INVALID_RESPONSE");
        }
        if (data.category !== null && (!data.category || typeof data.category.name !== "string")) {
            throw new Error("INVALID_RESPONSE");
        }
        for (const photo of data.photos) {
            if (typeof photo.url !== "string") throw new Error("INVALID_RESPONSE");
            const url = new URL(photo.url, window.location.origin);
            if (url.origin !== window.location.origin) throw new Error("INVALID_RESPONSE");
        }
        return data;
    }

    async function loadDetail() {
        controller?.abort();
        const requestController = new AbortController();
        controller = requestController;
        const signal = requestController.signal;
        const version = ++requestVersion;
        let timedOut = false;
        const timeout = window.setTimeout(() => {
            timedOut = true;
            requestController.abort();
        }, 15000);
        item = null;
        clearPhoto();
        thumbnails.replaceChildren();
        content.hidden = true;
        errorPanel.hidden = true;
        if (errorPanel.contains(document.activeElement)) close.focus();
        loading.hidden = false;
        modal.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(detailURL, {
                signal,
                credentials: "same-origin",
                cache: "no-store",
                headers: { Accept: "application/json" },
            });
            if (response.status === 404) throw new Error("NOT_FOUND");
            if (!response.ok) throw new Error("SERVER_ERROR");
            const result = await response.json();
            if (version !== requestVersion || !modal.open) return;
            renderItem(validateItem(result.item));
        } catch (error) {
            if (version !== requestVersion || !modal.open) return;
            if (error.name === "AbortError" && !timedOut) return;
            errorMessage.textContent = timedOut ? "Permintaan terlalu lama. Silakan coba lagi."
                : error.message === "NOT_FOUND" ? "Detail pakaian tidak tersedia. Pakaian mungkin telah dihapus atau sesi login berubah."
                : "Detail pakaian gagal dimuat. Periksa koneksi lalu coba lagi.";
            errorPanel.hidden = false;
            errorPanel.focus();
        } finally {
            window.clearTimeout(timeout);
            if (version === requestVersion) {
                loading.hidden = true;
                modal.setAttribute("aria-busy", "false");
            }
        }
    }

    document.addEventListener("click", (event) => {
        const card = event.target.closest("a[data-item-detail]");
        if (!card || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        trigger = card;
        detailURL = card.href;
        if (!modal.open) modal.showModal();
        document.documentElement.classList.add("wardrobe-modal-open");
        close.focus();
        loadDetail();
    });
    document.getElementById("open-item-edit").addEventListener("click", () => {
        if (!item || !trigger?.dataset.itemEditUrl) return;
        document.dispatchEvent(new CustomEvent("wardrobe:edit-item", {
            detail: { item, url: trigger.dataset.itemEditUrl },
        }));
    });
    close.addEventListener("click", () => modal.close());
    retry.addEventListener("click", loadDetail);
    previous.addEventListener("click", () => showPhoto(photoIndex - 1));
    next.addEventListener("click", () => showPhoto(photoIndex + 1));
    modal.addEventListener("keydown", (event) => {
        if (!item || item.photos.length < 2 || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        event.preventDefault();
        const step = event.key === "ArrowLeft" ? -1 : 1;
        showPhoto(photoIndex + step);
        if (thumbnails.contains(event.target)) thumbnails.children[photoIndex]?.focus();
    });
    modal.addEventListener("click", (event) => {
        if (event.target !== modal) return;
        const bounds = modal.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) modal.close();
    });
    modal.addEventListener("close", () => {
        requestVersion += 1;
        controller?.abort();
        clearPhoto();
        item = null;
        thumbnails.replaceChildren();
        content.hidden = true;
        loading.hidden = true;
        errorPanel.hidden = true;
        if (!document.querySelector("dialog[open]")) document.documentElement.classList.remove("wardrobe-modal-open");
        if (trigger?.isConnected) trigger.focus();
    });
})();
