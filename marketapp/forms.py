from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Order, Profile

PHONE_ATTRS = {'placeholder': '+998901234567', 'pattern': r'\+998\d{9}'}


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(label='Ism', max_length=50)
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return email


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