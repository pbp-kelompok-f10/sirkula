"""Pure provider boundary; Wardrobe queries and photo access stay in services."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StylistReply:
    text: str
    title: str
    result: dict


def get_stylist_provider():
    from django.conf import settings
    if settings.OUTFITS_PROVIDER != "api":
        from .api_client import WardrobeAPIError
        raise WardrobeAPIError("Provider Outfits tidak dikenal.", code="configuration")
    from .api_provider import WardrobeAPIProvider
    return WardrobeAPIProvider()
