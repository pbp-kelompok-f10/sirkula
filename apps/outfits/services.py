"""Landing data boundary: templates do not depend on an AI provider."""
from copy import deepcopy

from .demo_data import DEMO_HISTORY, DEMO_RECOMMENDATIONS


def get_landing_content(prompt=""):
    recommendations = list(DEMO_RECOMMENDATIONS)
    if prompt:
        # Only vary the demo ordering; no inference or history is persisted.
        offset = sum(ord(character) for character in prompt.casefold()) % len(recommendations)
        recommendations = recommendations[offset:] + recommendations[:offset]
    return deepcopy({
        "mode": "demo",
        "recommendations": recommendations,
        "history": list(DEMO_HISTORY),
    })
