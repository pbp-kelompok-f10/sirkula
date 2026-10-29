(() => {
    if (!window.fetch || !window.FormData) return;
    document.addEventListener("submit", async (event) => {
        const form = event.target.closest("form[data-review-like]");
        if (!form) return;
        event.preventDefault();
        const button = form.querySelector("button[name=action]");
        if (button.disabled) return;
        const status = document.getElementById("review-action-status");
        const payload = new FormData(form);
        payload.set("action", button.value);
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        if (status) status.textContent = "Menyimpan…";
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(form.getAttribute("action"), {
                method: "POST",
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" },
                body: payload,
                signal: controller.signal,
            });
            const isJson = response.headers.get("content-type")?.includes("application/json");
            const data = isJson ? await response.json() : null;
            if (!response.ok || !data) {
                throw new Error(data?.error || "Perubahan belum dapat disimpan. Muat ulang halaman dan coba lagi.");
            }
            if (data.html) {
                // HTML is rendered by our own escaped Django template, never user-supplied markup.
                const section = document.getElementById("reviews");
                const template = document.createElement("template");
                template.innerHTML = data.html.trim();
                section.replaceWith(template.content);
                document.querySelector('[aria-label="Filter ulasan"] [aria-current="page"]')?.focus({ preventScroll: true });
            } else {
                button.value = data.liked ? "unlike" : "like";
                button.setAttribute("aria-pressed", String(data.liked));
                button.setAttribute("aria-label", `${data.liked ? "Batalkan suka" : "Sukai ulasan"} ${button.dataset.author}`);
                button.querySelector("[data-like-icon]").textContent = data.liked ? "♥" : "♡";
                button.querySelector("[data-like-count]").textContent = data.like_count;
            }
            document.getElementById("review-action-status").textContent = data.liked ? "Ulasan disukai." : "Suka dibatalkan.";
        } catch (error) {
            if (status) status.textContent = error.name === "AbortError"
                ? "Koneksi terlalu lama. Status belum dapat dipastikan; muat ulang sebelum mencoba lagi."
                : error.message;
        } finally {
            clearTimeout(timeout);
            button.disabled = false;
            button.removeAttribute("aria-busy");
        }
    });
})();
