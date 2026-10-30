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
})();
