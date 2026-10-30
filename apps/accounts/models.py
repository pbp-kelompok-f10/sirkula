from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    display_name = models.CharField("Nama tampilan", max_length=60, blank=True)   # "Prabowo Subianto" (header)
    full_name = models.CharField("Nama lengkap", max_length=120, blank=True)      # judul besar italic
    bio = models.TextField("Bio", max_length=300, blank=True)
    location = models.CharField("Lokasi", max_length=80, blank=True,
                                help_text="Contoh: Depok, Jawa Barat")            # dipakai juga Discovery Map
    avatar = models.ImageField("Foto profil", upload_to="avatars/", blank=True, null=True)

    # Metrik kartu profil. Nanti dihitung dari modul Transaksi (Ilman),
    # sementara disimpan sebagai angka agar halaman bisa tampil.
    reputation_score = models.PositiveSmallIntegerField(default=100)    # %
    item_quality_score = models.PositiveSmallIntegerField(default=100)  # %
    successful_transactions = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profil {self.user.username}"

    @property
    def name(self):
        return self.display_name or self.full_name or self.user.get_full_name() or self.user.username

    @property
    def title_name(self):
        return self.full_name or self.display_name or self.user.get_full_name() or self.name

    @property
    def initial(self):
        return self.name[:1].upper()
