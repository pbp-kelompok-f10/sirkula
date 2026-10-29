from decimal import Decimal

from apps.marketplace.models import Product

CART_SESSION_KEY = "cart"


class Cart:
    """Keranjang belanja berbasis session.

    Login belum tersedia, jadi keranjang disimpan di session browser, bukan
    di database. Session hanya menyimpan daftar id produk; data produk tetap
    diambil dari database supaya harga dan status selalu terbaru.
    """

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if cart is None:
            cart = []
        self.product_ids = [str(product_id) for product_id in cart]

    def _save(self):
        self.session[CART_SESSION_KEY] = self.product_ids
        self.session.modified = True

    def add(self, product):
        product_id = str(product.pk)
        if product_id not in self.product_ids:
            self.product_ids.append(product_id)
            self._save()

    def remove(self, product):
        product_id = str(product.pk)
        if product_id in self.product_ids:
            self.product_ids.remove(product_id)
            self._save()

    def clear(self):
        self.product_ids = []
        self._save()

    def __contains__(self, product):
        return str(product.pk) in self.product_ids

    def __len__(self):
        return len(self.product_ids)

    def get_items(self):
        """Ambil produk di keranjang sesuai urutan saat ditambahkan.

        Produk yang sudah dihapus atau tidak tersedia otomatis dibuang dari
        session supaya keranjang tidak menampilkan barang yang tidak bisa dibeli.
        """
        products = list(
            Product.objects.filter(
                pk__in=self.product_ids,
                is_available=True,
            ).select_related("seller")
        )

        available_ids = {str(product.pk) for product in products}
        if len(available_ids) != len(self.product_ids):
            self.product_ids = [
                product_id
                for product_id in self.product_ids
                if product_id in available_ids
            ]
            self._save()

        order = {
            product_id: index
            for index, product_id in enumerate(self.product_ids)
        }
        return sorted(products, key=lambda product: order[str(product.pk)])

    @property
    def total_price(self):
        return sum(
            (product.price for product in self.get_items()),
            Decimal("0"),
        )

    @property
    def count(self):
        return len(self.get_items())
