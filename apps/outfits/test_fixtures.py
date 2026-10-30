from .providers import StylistReply

def _names(items):
    names = [item["name"] for item in items]
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return " dan ".join(names)
    return ", ".join(names[:-1]) + ", dan " + names[-1]


class DemoStylistProvider:
    def reply(self, *, prompt, history, wardrobe, recommendation=""):
        eligible = [item for item in wardrobe if item["photos"]]
        if not eligible:
            raise ValueError("No clothing available for the demo provider")
        offset = (len(history) // 2) % len(eligible)
        selected = (eligible[offset:] + eligible[:offset])[:3]
        names = _names(selected)
        if len(selected) == 1:
            text = f"Gunakan {names} sebagai dasar outfitmu. Ini pilihan simulasi dari pakaian aktif di lemarimu."
        else:
            prefix = "Untuk pilihan berikutnya, coba padukan" if history else "Coba padukan"
            text = f"{prefix} {names} dari lemarimu. Ini kombinasi simulasi."
        return StylistReply(text=text, title=prompt[:100], result={"mode": "demo", "item_ids": [item["id"] for item in selected]})



"""Public UI fixtures only; these are not a user's saved outfits or history."""

DEMO_IMAGE = {
    "source": "outfits/img/landing-reference.png",
    "viewbox": "82 801 283 268",
    "width": 1440,
    "height": 1611,
}

DEMO_RECOMMENDATIONS = (
    {"id": "demo-rec-1", "title": "Blouse cantik", "image": DEMO_IMAGE},
    {"id": "demo-rec-2", "title": "Blouse kasual", "image": DEMO_IMAGE},
    {"id": "demo-rec-3", "title": "Blouse pita", "image": DEMO_IMAGE},
    {"id": "demo-rec-4", "title": "Blouse pastel", "image": DEMO_IMAGE},
)
