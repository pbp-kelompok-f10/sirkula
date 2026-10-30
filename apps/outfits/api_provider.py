import math
from uuid import UUID

from .api_client import WardrobeAPIClient, WardrobeAPIError, identifier
from .providers import StylistReply
from .sync import account_lease, sync_wardrobe
from .wardrobe_context import WardrobeUnavailable, build_result


def match_mode(prompt):
    return "random" if prompt.strip().casefold() in {"acak", "random", "acak outfit"} else "best"


class WardrobeAPIProvider:
    def reply_for_user(self, *, user, prompt, history, wardrobe, key, recommendation=""):
        client = WardrobeAPIClient()
        with account_lease(user, client) as (account, renew):
            synced = sync_wardrobe(user, wardrobe, account, client, renew)
            if {item["api_category"] for item in synced} != {"baju", "celana"}:
                raise WardrobeUnavailable("Pencocokan membutuhkan minimal satu Kaos/Kemeja/Outer dan satu Celana aktif yang memiliki foto. Sepatu tidak termasuk baju.")
            mode = match_mode(prompt)
            renew()
            data = client.match(account.api_owner, {"mode": mode, "seed": UUID(str(key)).int % 2147483648})
            rows = data.get("results")
            if data.get("mode") != mode or not isinstance(rows, list) or len(rows) != 1:
                raise WardrobeAPIError("Pasangan pakaian belum tersedia.", code="invalid_response")
            pair = rows[0]
            if not isinstance(pair, dict):
                raise WardrobeAPIError(code="invalid_response")
            lookup = {item["api_id"]: item for item in synced}
            top = lookup.get(identifier(pair.get("baju_id")))
            bottom = lookup.get(identifier(pair.get("celana_id")))
            score = pair.get("score")
            if (top is None or bottom is None or top["api_category"] != "baju" or bottom["api_category"] != "celana"
                    or type(score) not in (int, float) or not math.isfinite(score) or not -1 <= score <= 1):
                raise WardrobeAPIError(code="invalid_response")
            result = build_result({"mode": "ai", "item_ids": [top["id"], bottom["id"]]}, wardrobe)
            result["api"] = {
                "match_mode": mode, "score": score,
                "top": {"local_id": top["id"], "api_id": top["api_id"], "revision": top["api_revision"]},
                "bottom": {"local_id": bottom["id"], "api_id": bottom["api_id"], "revision": bottom["api_revision"]},
                "preview_status": "not_generated",
            }
            if pair.get("preview_id"):
                result["api"]["preview_id"] = identifier(pair["preview_id"], preview=True)
            label = "acak" if mode == "random" else "terbaik"
            text = f"Pencocokan {label} selesai: {top['name']} dan {bottom['name']}. Status preview ditampilkan di area gambar; foto pakaian tetap tersedia."
            return StylistReply(text=text, title=prompt[:100], result={"mode": "ai", "item_ids": [top["id"], bottom["id"]]}), result
