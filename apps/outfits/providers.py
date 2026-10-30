"""Provider boundary: an AI adapter must return the same normalized reply."""
from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class StylistReply:
    text: str
    title: str
    result: dict


_REFERENCE = "outfits/img/workspace-reference.png"


def _image(viewbox):
    return {"kind": "reference", "source": _REFERENCE, "viewbox": viewbox, "width": 1440, "height": 1066}


class DemoStylistProvider:
    def reply(self, *, prompt, history, recommendation=""):
        # No network, ORM access, or inference: only public reference fixtures.
        text = "Coba padukan kaos putih, kemeja biru, dan celana krem untuk tampilan santai."
        if history:
            text = "Untuk pilihan berikutnya, gunakan kemeja biru sebagai outer dengan kaos putih dan celana krem."
        return StylistReply(
            text=text,
            title=prompt[:100],
            result=deepcopy({
                "mode": "demo",
                "preview": _image("67 379 417 642"),
                "pieces": [
                    {"name": "Kaos putih", "image": _image("506 379 205 204")},
                    {"name": "Kemeja biru", "image": _image("506 598 205 203")},
                    {"name": "Celana krem", "image": _image("506 817 205 203")},
                ],
            }),
        )


def get_stylist_provider():
    return DemoStylistProvider()
