"""Server-only client for the supplied Sirkula v2 HMAC contract."""
import hashlib
import hmac
import json
import re
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings


class WardrobeAPIError(Exception):
    def __init__(self, message="Layanan pencocokan belum tersedia. Silakan coba kembali.", *, code="unavailable"):
        super().__init__(message)
        self.code = code


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def identifier(value, *, preview=False):
    pattern = r"[a-f0-9]{64}" if preview else r"[A-Za-z0-9_-]{1,64}"
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise WardrobeAPIError("Respons layanan pencocokan tidak valid.", code="invalid_response")
    return value


def signed_headers(secret, method, path, owner, body=b"", *, timestamp=None, nonce=None):
    timestamp = str(int(time.time())) if timestamp is None else str(timestamp)
    nonce = uuid.uuid4().hex if nonce is None else nonce
    message = "\n".join([method.upper(), path, str(owner), timestamp, nonce, hashlib.sha256(body).hexdigest()])
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {"X-Wardrobe-Owner": str(owner), "X-Wardrobe-Time": timestamp,
            "X-Wardrobe-Nonce": nonce, "X-Wardrobe-Signature": signature}


class WardrobeAPIClient:
    def __init__(self):
        self.base_url = settings.WARDROBE_API_URL.rstrip("/")
        self.secret = settings.WARDROBE_SECRET
        parts = urlsplit(self.base_url)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.path or parts.query or parts.fragment or len(self.secret) < 32):
            raise WardrobeAPIError("Konfigurasi layanan pencocokan belum siap.", code="configuration")
        self.timeout = settings.OUTFITS_API_TIMEOUT_SECONDS

    def request(self, owner, method, path, *, payload=None, image=None, binary=False, missing_ok=False):
        body = image if image is not None else (json.dumps(payload, separators=(",", ":")).encode() if payload is not None else b"")
        headers = signed_headers(self.secret, method, path, owner, body)
        headers["Content-Type"] = "application/octet-stream" if image is not None else "application/json"
        request = Request(self.base_url + path, data=body if method not in ("GET", "HEAD") else None, headers=headers, method=method)
        try:
            with build_opener(NoRedirect).open(request, timeout=self.timeout) as response:
                maximum = 12 * 1024 * 1024 if binary else 1024 * 1024
                raw = response.read(maximum + 1)
                if len(raw) > maximum:
                    raise WardrobeAPIError("Respons layanan terlalu besar.", code="invalid_response")
                if binary:
                    expected = "image/png" if "/previews/" in path else "image/jpeg"
                    if response.headers.get_content_type() != expected:
                        raise WardrobeAPIError(code="invalid_response")
                    return raw
                if response.status == 204:
                    return None
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise WardrobeAPIError(code="invalid_response")
                return value
        except HTTPError as error:
            status = error.code
            error.close()
            if status == 404 and missing_ok:
                return None
            messages = {401: "Autentikasi layanan pencocokan gagal.", 413: "Foto terlalu besar untuk layanan pencocokan.",
                        422: "Data pakaian ditolak layanan pencocokan.", 429: "Batas layanan tercapai. Coba kembali nanti."}
            raise WardrobeAPIError(messages.get(status, "Layanan pencocokan belum tersedia. Silakan coba kembali."), code=str(status)) from None
        except (TimeoutError, URLError, OSError):
            raise WardrobeAPIError("Layanan pencocokan belum merespons. Periksa status lalu coba kembali.", code="timeout") from None
        except (ValueError, UnicodeError):
            raise WardrobeAPIError("Respons layanan pencocokan tidak valid.", code="invalid_response") from None

    def catalog(self, owner):
        data = self.request(owner, "GET", "/v2/items")
        rows = data.get("results")
        if not isinstance(rows, list):
            raise WardrobeAPIError(code="invalid_response")
        result = {}
        for row in rows:
            if not isinstance(row, dict) or row.get("category") not in ("baju", "celana") or row.get("status") != "ready":
                raise WardrobeAPIError(code="invalid_response")
            key = identifier(row.get("item_id"))
            identifier(row.get("revision"))
            if key in result:
                raise WardrobeAPIError(code="invalid_response")
            result[key] = row
        return result

    def put(self, owner, category, image, item_id=None):
        path = f"/v2/items/{identifier(item_id)}/{category}" if item_id else f"/v2/items/{category}"
        data = self.request(owner, "PUT" if item_id else "POST", path, image=image)
        key = identifier(data.get("item_id"))
        if data.get("status") != "ready" or (item_id and key != item_id):
            raise WardrobeAPIError(code="invalid_response")
        return key

    def delete(self, owner, item_id):
        return self.request(owner, "DELETE", f"/v2/items/{identifier(item_id)}", missing_ok=True)

    def item_image(self, owner, item_id):
        return self.request(owner, "GET", f"/v2/items/{identifier(item_id)}/image", binary=True)

    def match(self, owner, payload):
        return self.request(owner, "POST", "/v2/mix-match", payload=payload)

    def preview(self, owner, top, bottom):
        return self.request(owner, "POST", "/v2/previews", payload={"baju_id": identifier(top), "celana_id": identifier(bottom)})

    def preview_status(self, owner, key):
        return self.request(owner, "GET", f"/v2/previews/{identifier(key, preview=True)}", missing_ok=True)

    def preview_image(self, owner, key):
        return self.request(owner, "GET", f"/v2/previews/{identifier(key, preview=True)}/image", binary=True)
