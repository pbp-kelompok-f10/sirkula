"""Pure provider boundary; Wardrobe queries and photo access stay in services."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StylistReply:
    text: str
    title: str
    result: dict


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


def get_stylist_provider():
    from django.conf import settings
    if settings.OUTFITS_PROVIDER == "demo":
        return DemoStylistProvider()
    if settings.OUTFITS_PROVIDER != "api":
        from .api_client import WardrobeAPIError
        raise WardrobeAPIError("Provider Outfits tidak dikenal.", code="configuration")
    from .api_provider import WardrobeAPIProvider
    return WardrobeAPIProvider()
