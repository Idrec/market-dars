from decimal import Decimal

from .models import Product

CART_KEY = 'cart'


class Cart:
    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.setdefault(CART_KEY, {})
        # {"5": 2} -> product_id: quantity

    def add(self, product, quantity=1, override=False):
        if product.stock < 1:
            return

        pid = str(product.id)
        new_qty = quantity if override else self.cart.get(pid, 0) + quantity

        self.cart[pid] = max(1, min(new_qty, product.stock))
        self.save()

    def remove(self, product_id):
        self.cart.pop(str(product_id), None)
        self.save()

    def clear(self):
        self.session[CART_KEY] = {}
        self.cart = self.session[CART_KEY]
        self.save()

    def save(self):
        self.session.modified = True

    def __iter__(self):
        products = Product.objects.filter(
            id__in=self.cart.keys(),
            is_active=True,
        ).order_by('id')

        found = set()
        for p in products:
            pid = str(p.id)
            found.add(pid)
            qty = self.cart[pid]

            yield {
                'product': p,
                'quantity': qty,
                'price': p.final_price,
                'total': p.final_price * qty,
            }

        # o'chirilgan yoki nofaol mahsulotlarni savatdan tozalash
        stale = set(self.cart.keys()) - found
        if stale:
            for pid in stale:
                self.cart.pop(pid, None)
            self.save()

    def __len__(self):
        return sum(self.cart.values())

    def total_price(self):
        return sum((item['total'] for item in self), Decimal('0'))