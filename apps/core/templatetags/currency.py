from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()


@register.filter
def rupiah(value):
    """Format nominal dengan pemisah ribuan Indonesia tanpa simbol mata uang."""
    if value in (None, ""):
        return "0"

    try:
        amount = Decimal(str(value)).quantize(Decimal("1"))
    except (InvalidOperation, ValueError, TypeError):
        return value

    return f"{amount:,.0f}".replace(",", ".")
