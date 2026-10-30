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

DEMO_HISTORY = (
    {"id": "demo-history-1", "title": "Blouse untuk kuliah", "image": DEMO_IMAGE},
    {"id": "demo-history-2", "title": "Blouse untuk hangout", "image": DEMO_IMAGE},
    {"id": "demo-history-3", "title": "Blouse kasual", "image": DEMO_IMAGE},
    {"id": "demo-history-4", "title": "Blouse pastel", "image": DEMO_IMAGE},
)
