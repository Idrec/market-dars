from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .cart import Cart
from .forms import RegisterForm, CheckoutForm
from .models import Category, Product, OrderItem, Profile


class StockError(Exception):
    """Omborda mahsulot yetarli bo'lmaganda ko'tariladi."""


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


# ---------------------------------------------------------------- Katalog

def home(request):
    products = (
        Product.objects.filter(is_active=True)
        .prefetch_related('images')
        .order_by('-created_at')
    )
    return render(request, 'shop/home.html', {
        'categories': Category.objects.filter(parent__isnull=True),
        'new_products': products[:8],
        # maydon nomini modelingizga moslang (masalan discount_price)
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
        products = products.filter(
            Q(name__icontains=q) | Q(description__icontains=q)
        )

    min_price, max_price = request.GET.get('min'), request.GET.get('max')
    if min_price and min_price.isdigit():
        products = products.filter(price__gte=min_price)
    if max_price and max_price.isdigit():
        products = products.filter(price__lte=max_price)

    sort_map = {'cheap': 'price', 'expensive': '-price', 'new': '-created_at'}
    products = products.order_by(sort_map.get(request.GET.get('sort'), '-created_at'))

    page = Paginator(products, 12).get_page(request.GET.get('page'))
    return render(request, 'shop/product_list.html', {
        'page_obj': page,
        'category': category,
        'categories': Category.objects.all(),
        'q': q,
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related('images'),
        slug=slug,
        is_active=True,
    )

    related = Product.objects.filter(
        category=product.category,
        is_active=True,
    ).exclude(id=product.id)[:4]

    return render(request, 'shop/product_detail.html', {
        'product': product,
        'related': related,
    })


# ----------------------------------------------------------------- Savat

def cart_detail(request):
    cart = Cart(request)
    return render(request, 'shop/cart.html', {
        'cart': cart,
        'total': cart.total_price(),
    })


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)

    if product.stock == 0:
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'error': 'Mahsulot tugagan'}, status=400)
        messages.error(request, 'Mahsulot tugagan')
        return redirect('cart_detail')

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1

    cart = Cart(request)
    cart.add(product, quantity, request.POST.get('override') == '1')

    if _is_ajax(request):
        return JsonResponse({
            'ok': True,
            'count': len(cart),
            'total': str(cart.total_price()),
        })

    messages.success(request, f"{product.name} savatga qo'shildi")
    return redirect('cart_detail')


@require_POST
def cart_remove(request, product_id):
    cart = Cart(request)
    cart.remove(product_id)

    if _is_ajax(request):
        return JsonResponse({
            'ok': True,
            'count': len(cart),
            'total': str(cart.total_price()),
        })

    return redirect('cart_detail')


# -------------------------------------------------------------- Buyurtma

def checkout(request):
    cart = Cart(request)

    if len(cart) == 0:
        messages.warning(request, "Savat bo'sh")
        return redirect('product_list')

    initial = {}

    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        initial = {
            'full_name': request.user.get_full_name(),
            'phone': profile.phone,
            'address': profile.address,
        }

    form = CheckoutForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                order = form.save(commit=False)
                order.user = request.user if request.user.is_authenticated else None
                order.save()

                total = Decimal('0')

                for item in cart:
                    product = Product.objects.select_for_update().get(
                        id=item['product'].id
                    )

                    if product.stock < item['quantity']:
                        raise StockError(f"{product.name} omborda yetarli emas")

                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_name=product.name,
                        price=item['price'],
                        quantity=item['quantity'],
                    )

                    Product.objects.filter(id=product.id).update(
                        stock=F('stock') - item['quantity']
                    )

                    total += item['total']

                order.total_price = total
                order.save(update_fields=['total_price'])

        except StockError as e:
            messages.error(request, str(e))
            return redirect('cart_detail')

        cart.clear()

        if order.payment_method in ('click', 'payme'):
            return redirect('payment', order_id=order.id)

        return redirect('order_success', order_id=order.id)

    return render(request, 'shop/checkout.html', {'form': form})


# ------------------------------------------------------- Ro'yxatdan o'tish

def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.get_or_create(user=user)
            login(request, user)  # ro'yxatdan o'tgach avtomatik kirish
            messages.success(request, "Muvaffaqiyatli ro'yxatdan o'tdingiz!")
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})