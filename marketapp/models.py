from django.db import models
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    image = models.ImageField(upload_to='categories/', blank=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    name = models.CharField("Nomi", max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField("Tavsif", blank=True)
    price = models.DecimalField("Narx", max_digits=12, decimal_places=2)
    discount_price = models.DecimalField("Chegirma narxi", max_digits=12, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField("Omborda", default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def final_price(self):
        return self.discount_price or self.price
    @property
    def main_image(self):
        imgs = list(self.images.all())
        return next((i for i in imgs if i.is_main), imgs[0] if imgs else None)
    
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    is_main = models.BooleanField(default=False)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField("Telefon", max_length=13, blank=True)  
    address = models.TextField("Manzil", blank=True)

    def __str__(self):
        return self.user.username

class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Yangi'),
        ('paid', "To'langan"),
        ('shipping', 'Yetkazilmoqda'),
        ('delivered', 'Yetkazildi'),
        ('canceled', 'Bekor qilindi'),
    ]
    PAYMENT_CHOICES = [
        ('cash', 'Naqd'),
        ('click', 'Click'),
        ('payme', 'Payme'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    full_name = models.CharField("F.I.Sh", max_length=150)
    phone = models.CharField("Telefon", max_length=13)
    address = models.TextField("Manzil")
    comment = models.TextField("Izoh", blank=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cash')
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Buyurtma #{self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)                  # mahsulot o'chirilsa ham nomi saqlanadi
    price = models.DecimalField(max_digits=12, decimal_places=2)     # sotilgan paytdagi narx
    quantity = models.PositiveIntegerField(default=1)

    @property
    def total(self):
        return self.price * self.quantity