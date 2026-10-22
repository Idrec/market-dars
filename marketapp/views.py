from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Category, Product, Order, OrderItem, Profile


CART_KEY = 'cart'
class Cart:
    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.setdefault(CART_KEY, {})   # {"5": 2} -> product_id: quantity

    def add(self, product, quantity=1, override=False):
        pid = str(product.id)
        new_qty = quantity if override else self.cart.get(pid, 0) + quantity
        self.cart[pid] = max(1, min(new_qty, product.stock))
        self.save()

    def remove(self, product_id):
        self.cart.pop(str(product_id), None)
        self.save()

    def clear(self):
        self.session[CART_KEY] = {}
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        products = Product.objects.filter(id__in=self.cart.keys(), is_active=True)
        for p in products:
            qty = self.cart[str(p.id)]
            yield {'product': p, 'quantity': qty, 'price': p.final_price, 'total': p.final_price * qty}

    def __len__(self):
        return sum(self.cart.values())

    def total_price(self):
        return sum((item['total'] for item in self), Decimal('0'))

def cart_count(request):
       return {'cart_count': len(Cart(request))}

PHONE_ATTRS = {'placeholder': '+998901234567', 'pattern': r'\+998\d{9}'}
class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label='Ism', max_length=50)
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'email', 'password1', 'password2')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('phone', 'address')
        widgets = {'phone': forms.TextInput(attrs=PHONE_ATTRS)}


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('full_name', 'phone', 'address', 'comment', 'payment_method')
        widgets = {
            'phone': forms.TextInput(attrs=PHONE_ATTRS),
            'address': forms.Textarea(attrs={'rows': 2}),
            'comment': forms.Textarea(attrs={'rows': 2}),
        }


# ==================== KATALOG =================


def home(request):
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    return render(request, 'shop/home.html', {
        'categories': Category.objects.filter(parent__isnull=True),
        'new_products': products[:8],
        'sale_products': products.filter(discount_price__isnull=False)[:8],
    })


def product_list(request, category_slug=None):
    products = Product.objects.filter(is_active=True).prefetch_related('images')
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(Q(category=category) | Q(category__parent=category))
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))

    min_price, max_price = request.GET.get('min'), request.GET.get('max')
    if min_price and min_price.isdigit():
        products = products.filter(price__gte=min_price)
    if max_price and max_price.isdigit():
        products = products.filter(price__lte=max_price)

    sort_map = {'cheap': 'price', 'expensive': '-price', 'new': '-created_at'}
    products = products.order_by(sort_map.get(request.GET.get('sort'), '-created_at'))

    page = Paginator(products, 12).get_page(request.GET.get('page'))
    return render(request, 'shop/product_list.html', {
        'page_obj': page, 'category': category,
        'categories': Category.objects.all(), 'q': q,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.prefetch_related('images'), slug=slug, is_active=True)
    related = Product.objects.filter(category=product.category, is_active=True).exclude(id=product.id)[:4]
    return render(request, 'shop/product_detail.html', {'product': product, 'related': related})


# ==================== SAVAT ====================
def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'

def cart_detail(request):
    cart = Cart(request)
    return render(request, 'shop/cart.html', {'cart': cart, 'total': cart.total_price()})

@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    if product.stock == 0:
        return JsonResponse({'ok': False, 'error': 'Mahsulot tugagan'}, status=400)
    cart = Cart(request)
    cart.add(product, int(request.POST.get('quantity', 1)), request.POST.get('override') == '1')
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'count': len(cart), 'total': str(cart.total_price())})
    messages.success(request, f"{product.name} savatga qo'shildi")
    return redirect('cart_detail')
@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    cart.remove(product_id)
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'count': len(cart), 'total': str(cart.total_price())})
    return redirect('cart_detail')


# ==================== BUYURTMA ====================

def checkout(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, "Savat bo'sh")
        return redirect('product_list')

    initial = {}
    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        initial = {'full_name': request.user.get_full_name(), 'phone': profile.phone, 'address': profile.address}

    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                order = form.save(commit=False)
                order.user = request.user if request.user.is_authenticated else None
                order.save()

                total = Decimal('0')
                for item in cart:
                    product = Product.objects.select_for_update().get(id=item['product'].id)
                    if product.stock < item['quantity']:
                        raise ValueError(f"{product.name} omborda yetarli emas")
                    OrderItem.objects.create(
                        order=order, product=product, product_name=product.name,
                        price=item['price'], quantity=item['quantity'],
                    )
                    Product.objects.filter(id=product.id).update(stock=F('stock') - item['quantity'])
                    total += item['total']

                order.total_price = total
                order.save(update_fields=['total_price'])
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('cart_detail')

        cart.clear()
        if order.payment_method in ('click', 'payme'):
            return redirect('payment', order_id=order.id)
        return redirect('order_success', order_id=order.id)

    return render(request, 'shop/checkout.html', {'form': form, 'cart': cart, 'total': cart.total_price()})


def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, 'shop/order_success.html', {'order': order})


# ==================== AUTH / PROFIL ====================

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        Profile.objects.create(user=user)
        login(request, user)
        messages.success(request, "Ro'yxatdan o'tdingiz!")
        return redirect('home')
    return render(request, 'shop/register.html', {'form': form})


@login_required
def profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Ma'lumotlar saqlandi")
        return redirect('profile')
    orders = request.user.orders.prefetch_related('items')
    return render(request, 'shop/profile.html', {'form': form, 'orders': orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order_detail.html', {'order': order})


# ==================== TO'LOV ====================

def payment(request, order_id):
    order = get_object_or_404(Order, id=order_id, is_paid=False)
    # TODO: Click / Payme havolasini shu yerda yasash
    return render(request, 'shop/payment.html', {'order': order})



from django.contrib.auth.decorators import user_passes_test
from django.db.models import Sum, Count
from django.utils import timezone
from django.utils.text import slugify
from .models import ProductImage


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('category', 'name', 'description', 'price', 'discount_price', 'stock', 'is_active')
        widgets = {'description': forms.Textarea(attrs={'rows': 5})}

    def clean(self):
        data = super().clean()
        price, disc = data.get('price'), data.get('discount_price')
        if price and disc and disc >= price:
            self.add_error('discount_price', "Chegirma narxi asosiy narxdan kichik bo'lishi kerak")
        return data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'parent', 'image')


# ==================== PANEL (ADMIN) ====================

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='login')


def unique_slug(model, text, instance=None):
    base = slugify(text) or 'item'
    slug, i = base, 1
    qs = model.objects.exclude(pk=instance.pk) if instance and instance.pk else model.objects.all()
    while qs.filter(slug=slug).exists():
        i += 1
        slug = f'{base}-{i}'
    return slug


@staff_required
def panel_dashboard(request):
    today = timezone.localdate()
    revenue = Order.objects.filter(Q(is_paid=True) | Q(status='delivered')) \
                           .aggregate(s=Sum('total_price'))['s'] or 0
    return render(request, 'shop/panel/dashboard.html', {
        'today_orders': Order.objects.filter(created_at__date=today).count(),
        'new_orders': Order.objects.filter(status='new').count(),
        'revenue': revenue,
        'product_count': Product.objects.count(),
        'low_stock': Product.objects.filter(is_active=True, stock__lte=5).order_by('stock')[:5],
        'recent_orders': Order.objects.all()[:10],
    })


# --- Mahsulotlar ---

@staff_required
def panel_products(request):
    products = Product.objects.select_related('category').prefetch_related('images').order_by('-created_at')
    q = request.GET.get('q', '').strip()
    if q:
        products = products.filter(name__icontains=q)
    page = Paginator(products, 20).get_page(request.GET.get('page'))
    return render(request, 'shop/panel/products.html', {'page_obj': page, 'q': q})


@staff_required
def panel_product_form(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        obj = form.save(commit=False)
        if not obj.slug:
            obj.slug = unique_slug(Product, obj.name, obj)
        obj.save()

        has_main = obj.images.filter(is_main=True).exists()
        for i, f in enumerate(request.FILES.getlist('images')):
            ProductImage.objects.create(product=obj, image=f, is_main=(not has_main and i == 0))

        messages.success(request, "Mahsulot saqlandi")
        return redirect('panel_products')
    return render(request, 'shop/panel/product_form.html', {'form': form, 'product': product})


@staff_required
@require_POST
def panel_product_delete(request, pk):
    get_object_or_404(Product, pk=pk).delete()
    messages.success(request, "Mahsulot o'chirildi")
    return redirect('panel_products')


@staff_required
@require_POST
def panel_image_delete(request, pk):
    img = get_object_or_404(ProductImage, pk=pk)
    product_id = img.product_id
    img.image.delete(save=False)   # faylni diskdan ham o'chirish
    img.delete()
    return redirect('panel_product_edit', pk=product_id)


# --- Kategoriyalar ---

@staff_required
def panel_categories(request):
    form = CategoryForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        cat = form.save(commit=False)
        cat.slug = unique_slug(Category, cat.name)
        cat.save()
        messages.success(request, "Kategoriya qo'shildi")
        return redirect('panel_categories')
    categories = Category.objects.select_related('parent').annotate(n=Count('products'))
    return render(request, 'shop/panel/categories.html', {'form': form, 'categories': categories})


@staff_required
@require_POST
def panel_category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk)
    if Product.objects.filter(Q(category=cat) | Q(category__parent=cat)).exists():
        messages.error(request, "Bu kategoriyada mahsulotlar bor — avval ularni boshqa kategoriyaga o'tkazing")
    else:
        cat.delete()
        messages.success(request, "Kategoriya o'chirildi")
    return redirect('panel_categories')


# --- Buyurtmalar ---

@staff_required
def panel_orders(request):
    orders = Order.objects.all()
    status = request.GET.get('status', '')
    if status:
        orders = orders.filter(status=status)
    q = request.GET.get('q', '').strip()
    if q:
        cond = Q(full_name__icontains=q) | Q(phone__icontains=q)
        if q.isdigit():
            cond |= Q(id=q)
        orders = orders.filter(cond)
    page = Paginator(orders, 20).get_page(request.GET.get('page'))
    return render(request, 'shop/panel/orders.html', {
        'page_obj': page, 'status': status, 'q': q, 'statuses': Order.STATUS_CHOICES,
    })


@staff_required
def panel_order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related('items'), pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if order.status == 'canceled':
            messages.error(request, "Bekor qilingan buyurtmani o'zgartirib bo'lmaydi")
        elif new_status in dict(Order.STATUS_CHOICES) and new_status != order.status:
            with transaction.atomic():
                if new_status == 'canceled':          # mahsulotlarni omborga qaytarish
                    for item in order.items.all():
                        if item.product_id:
                            Product.objects.filter(id=item.product_id).update(stock=F('stock') + item.quantity)
                if new_status == 'delivered':
                    order.is_paid = True              # naqd to'lov yetkazilganda olinadi
                order.status = new_status
                order.save(update_fields=['status', 'is_paid'])
            messages.success(request, "Holat yangilandi")
        return redirect('panel_order_detail', pk=pk)

    return render(request, 'shop/panel/order_detail.html', {'order': order, 'statuses': Order.STATUS_CHOICES})