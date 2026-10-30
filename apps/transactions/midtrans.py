import base64

import httpx
from django.conf import settings


def _authorization_header():
    credentials = f"{settings.MIDTRANS_SERVER_KEY}:".encode()
    encoded_credentials = base64.b64encode(credentials).decode()
    return {"Authorization": f"Basic {encoded_credentials}"}


def _api_url(path):
    base_url = (
        "https://api.midtrans.com"
        if settings.MIDTRANS_IS_PRODUCTION
        else "https://api.sandbox.midtrans.com"
    )
    return f"{base_url}{path}"


def create_qris_payment(order, items):
    item_details = [
        {
            "id": str(item.product_id),
            "price": int(item.price),
            "quantity": 1,
            "name": item.product.name[:50],
        }
        for item in items
    ]
    item_details.append({
        "id": "admin-fee",
        "price": int(order.admin_fee),
        "quantity": 1,
        "name": "Biaya admin",
    })
    if order.shipping_cost:
        item_details.append({
            "id": "shipping-cost",
            "price": int(order.shipping_cost),
            "quantity": 1,
            "name": "Biaya pengiriman",
        })
    payload = {
        "payment_type": "qris",
        "transaction_details": {
            "order_id": order.order_number,
            "gross_amount": int(order.total),
        },
        "item_details": item_details,
        "customer_details": {
            "first_name": order.buyer.get_short_name() or order.buyer.username,
            "email": order.buyer.email or "customer@sirkula.local",
            "phone": order.phone_number,
        },
        "qris": {
            "acquirer": settings.MIDTRANS_QRIS_ACQUIRER,
        },
    }
    response = httpx.post(
        _api_url("/v2/charge"),
        headers={**_authorization_header(), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_qr_code_url(payment_response):
    actions = payment_response.get("actions", [])
    preferred_names = ("generate-qr-code-v2", "generate-qr-code")
    for name in preferred_names:
        for action in actions:
            if action.get("name") == name:
                return action.get("url", "")
    return ""


def get_payment_status(order_number):
    response = httpx.get(
        _api_url(f"/v2/{order_number}/status"),
        headers=_authorization_header(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
