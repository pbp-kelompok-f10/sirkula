from decimal import Decimal

from django.db import migrations


LOCATIONS = [
    ("jakarta-pusat", "Jakarta Pusat", "city", "Menteng, Jakarta Pusat", "-6.186486", "106.834091", 10),
    ("jakarta-selatan", "Jakarta Selatan", "city", "Kebayoran Baru, Jakarta Selatan", "-6.243221", "106.800842", 20),
    ("jakarta-timur", "Jakarta Timur", "city", "Jatinegara, Jakarta Timur", "-6.225014", "106.900447", 30),
    ("bogor-kota", "Kota Bogor", "city", "Bogor Tengah, Kota Bogor", "-6.595038", "106.816635", 40),
    ("kabupaten-bogor", "Kabupaten Bogor", "regency", "Cibinong, Kabupaten Bogor", "-6.485000", "106.842000", 50),
    ("depok", "Kota Depok", "city", "Pancoran Mas, Kota Depok", "-6.402484", "106.794243", 60),
    ("tangerang", "Kota Tangerang", "city", "Tangerang, Banten", "-6.178306", "106.631889", 70),
    ("tangerang-selatan", "Kota Tangerang Selatan", "city", "Serpong, Tangerang Selatan", "-6.288889", "106.718056", 80),
    ("bekasi", "Kota Bekasi", "city", "Bekasi Selatan, Kota Bekasi", "-6.238270", "106.975573", 90),
]

STORES = [
    ("thrift-lokal-menteng", "Thrift Lokal Menteng", "Koleksi pakaian preloved pilihan dari komunitas lokal.", "Jl. Cikini Raya, Menteng, Jakarta Pusat", "-6.190780", "106.839540"),
    ("barter-cikini", "Barter Cikini", "Tempat bertukar pakaian dan barang layak pakai.", "Jl. Raden Saleh Raya, Cikini, Jakarta Pusat", "-6.189120", "106.846210"),
    ("secondhand-gondangdia", "Secondhand Gondangdia", "Fashion secondhand berkualitas dengan harga terjangkau.", "Jl. RP. Soeroso, Gondangdia, Jakarta Pusat", "-6.184910", "106.836720"),
    ("lemari-kedua-depok", "Lemari Kedua Depok", "Thrift dan barter pakaian untuk komunitas Depok.", "Jl. Margonda Raya, Depok", "-6.386620", "106.830650"),
    ("putar-pakai-bekasi", "Putar Pakai Bekasi", "Barang preloved lokal Bekasi yang siap dipakai kembali.", "Jl. Ahmad Yani, Bekasi Selatan", "-6.242060", "106.992340"),
]

LISTINGS = [
    ("thrift-lokal-menteng", "thrift", "Jaket Denim Vintage", "jaket-denim-vintage", "Jaket denim preloved dalam kondisi sangat baik.", "185000.00", "-6.190780", "106.839540", "https://images.unsplash.com/photo-1551537482-f2075a1d41f2?auto=format&fit=crop&w=800&q=80"),
    ("thrift-lokal-menteng", "thrift", "Kemeja Linen Hijau", "kemeja-linen-hijau", "Kemeja linen ringan untuk aktivitas sehari-hari.", "95000.00", "-6.191120", "106.840030", "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=800&q=80"),
    ("barter-cikini", "barter", "Sweater Rajut Krem", "sweater-rajut-krem", "Ditukar dengan outer atau tote bag yang setara.", None, "-6.189120", "106.846210", "https://images.unsplash.com/photo-1576566588028-4147f3842f27?auto=format&fit=crop&w=800&q=80"),
    ("barter-cikini", "barter", "Tas Kanvas Lokal", "tas-kanvas-lokal", "Tas kanvas kokoh untuk barter dengan aksesori lain.", None, "-6.188940", "106.845880", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=800&q=80"),
    ("secondhand-gondangdia", "thrift", "Celana Chino Cokelat", "celana-chino-cokelat", "Celana chino uniseks, nyaman dan terawat.", "120000.00", "-6.184910", "106.836720", "https://images.unsplash.com/photo-1473966968600-fa801b869a1a?auto=format&fit=crop&w=800&q=80"),
    ("lemari-kedua-depok", "thrift", "Blazer Navy Klasik", "blazer-navy-klasik", "Blazer formal preloved dengan potongan klasik.", "210000.00", "-6.386620", "106.830650", "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80"),
    ("lemari-kedua-depok", "barter", "Rok Midi Motif", "rok-midi-motif", "Rok midi untuk ditukar dengan pakaian kasual.", None, "-6.387010", "106.831040", "https://images.unsplash.com/photo-1583496661160-fb5886a0aaaa?auto=format&fit=crop&w=800&q=80"),
    ("putar-pakai-bekasi", "thrift", "Sepatu Sneakers Putih", "sepatu-sneakers-putih", "Sneakers putih ukuran 41, bekas pemakaian ringan.", "175000.00", "-6.242060", "106.992340", "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=800&q=80"),
]


def seed_jabodetabek(apps, schema_editor):
    PredefinedLocation = apps.get_model("marketplace", "PredefinedLocation")
    Store = apps.get_model("marketplace", "Store")
    Listing = apps.get_model("marketplace", "Listing")

    for slug, name, region_type, address, latitude, longitude, sort_order in LOCATIONS:
        PredefinedLocation.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "region_type": region_type,
                "address_label": address,
                "latitude": Decimal(latitude),
                "longitude": Decimal(longitude),
                "sort_order": sort_order,
                "is_active": True,
            },
        )

    stores = {}
    for slug, name, description, address, latitude, longitude in STORES:
        store, _ = Store.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "description": description,
                "address": address,
                "latitude": Decimal(latitude),
                "longitude": Decimal(longitude),
                "is_active": True,
            },
        )
        stores[slug] = store

    for store_slug, listing_type, title, slug, description, price, latitude, longitude, image_url in LISTINGS:
        Listing.objects.update_or_create(
            slug=slug,
            defaults={
                "store": stores[store_slug],
                "listing_type": listing_type,
                "title": title,
                "description": description,
                "price": Decimal(price) if price is not None else None,
                "latitude": Decimal(latitude),
                "longitude": Decimal(longitude),
                "image_url": image_url,
                "is_available": True,
            },
        )


def remove_seed_data(apps, schema_editor):
    Listing = apps.get_model("marketplace", "Listing")
    Store = apps.get_model("marketplace", "Store")
    PredefinedLocation = apps.get_model("marketplace", "PredefinedLocation")
    Listing.objects.filter(slug__in=[item[3] for item in LISTINGS]).delete()
    Store.objects.filter(slug__in=[item[0] for item in STORES]).delete()
    PredefinedLocation.objects.filter(slug__in=[item[0] for item in LOCATIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [("marketplace", "0001_initial")]

    operations = [migrations.RunPython(seed_jabodetabek, remove_seed_data)]
