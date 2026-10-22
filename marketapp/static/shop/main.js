// =========================================================
// main.js — do'kon sahifalari uchun
// =========================================================
document.documentElement.classList.add('js');

(function () {
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];

  // 1250000 -> "1 250 000"
  const fmt = (n) => Math.round(Number(n)).toLocaleString('ru-RU');

  // ---------- Toast xabar ----------
  function toast(text, type = 'success') {
    let box = $('#toasts');
    if (!box) {
      box = document.createElement('div');
      box.id = 'toasts';
      document.body.appendChild(box);
    }
    const t = document.createElement('div');
    t.className = `toast toast--${type}`;
    t.textContent = text;
    box.appendChild(t);
    setTimeout(() => t.classList.add('hide'), 2500);
    setTimeout(() => t.remove(), 3000);
  }

  // ---------- AJAX forma yuborish ----------
  async function send(form) {
    const res = await fetch(form.action, {
      method: 'POST',
      body: new FormData(form),          // csrf token ham shu ichida
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const data = await res.json().catch(() => ({ ok: false }));
    if (!res.ok || !data.ok) throw new Error(data.error || 'Xatolik yuz berdi');
    return data;
  }

  function updateCart(data) {
    const count = $('#cart-count');
    if (count) count.textContent = data.count;
    const total = $('#cart-total');
    if (total) total.textContent = fmt(data.total);
  }

  // ---------- Mobil menyu ----------
  const burger = $('#burger');
  const nav = $('#nav');
  if (burger && nav) burger.addEventListener('click', () => nav.classList.toggle('open'));

  // ---------- Savatga qo'shish ----------
  $$('.add-to-cart').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = $('button', form);
      btn.disabled = true;
      try {
        const data = await send(form);
        updateCart(data);
        toast("Savatga qo'shildi ✓");
      } catch (err) {
        toast(err.message, 'error');
      } finally {
        btn.disabled = false;
      }
    });
  });

  // ---------- Savatda miqdorni o'zgartirish ----------
  $$('.qty-form').forEach((form) => {
    const input = $('.qty-input', form);
    const row = form.closest('tr');
    let timer;

    const submit = async () => {
      let qty = parseInt(input.value, 10) || 1;
      const max = parseInt(input.max, 10) || qty;
      qty = Math.min(Math.max(qty, 1), max);
      input.value = qty;
      try {
        const data = await send(form);
        updateCart(data);
        const cell = $('.item-total', row);
        if (cell && row.dataset.price) cell.textContent = fmt(row.dataset.price * qty);
      } catch (err) {
        toast(err.message, 'error');
      }
    };

    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(submit, 400);
    });
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      submit();
    });
  });

  // ---------- Savatdan o'chirish ----------
  $$('.remove-form').forEach((form) => {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        const data = await send(form);
        updateCart(data);
        form.closest('tr').remove();
        if (data.count === 0) location.reload();
      } catch (err) {
        toast(err.message, 'error');
      }
    });
  });

  // ---------- Rasm galereyasi ----------
  const mainImg = $('#main-img');
  $$('.gallery__thumb').forEach((thumb) => {
    thumb.addEventListener('click', () => {
      if (mainImg) mainImg.src = thumb.dataset.full;
      $$('.gallery__thumb').forEach((t) => t.classList.remove('active'));
      thumb.classList.add('active');
    });
  });

  // ---------- Django xabarlarini 4 soniyadan keyin yashirish ----------
  $$('.messages .alert').forEach((a) => {
    setTimeout(() => {
      a.style.opacity = '0';
      setTimeout(() => a.remove(), 400);
    }, 4000);
  });

  // ---------- Telefon maydoni: +998 bilan boshlansin ----------
  $$('input[name="phone"]').forEach((inp) => {
    inp.addEventListener('focus', () => {
      if (!inp.value) inp.value = '+998';
    });
    inp.addEventListener('input', () => {
      inp.value = '+' + inp.value.replace(/\D/g, '').slice(0, 12);
    });
  });
})();
