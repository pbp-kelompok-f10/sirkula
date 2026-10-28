(() => {
    const modal = document.getElementById("category-modal");
    const trigger = document.getElementById("open-category-modal");
    if (!modal || !trigger) return;

    const nameInput = document.getElementById("category-name");
    const openModal = () => {
        if (modal.open) return;
        modal.showModal();
        document.documentElement.classList.add("category-modal-open");
        nameInput.focus();
    };

    trigger.addEventListener("click", openModal);
    document.getElementById("close-category-modal").addEventListener("click", () => modal.close());
    modal.addEventListener("close", () => {
        document.documentElement.classList.remove("category-modal-open");
        trigger.focus();
    });
    modal.addEventListener("click", (event) => {
        if (event.target !== modal) return;
        const bounds = modal.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right ||
            event.clientY < bounds.top || event.clientY > bounds.bottom) {
            modal.close();
        }
    });

    if (modal.dataset.openOnLoad === "true") openModal();
})();
