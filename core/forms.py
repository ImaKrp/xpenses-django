from django import forms
from .models import Transaction, Category, UserProfile
import datetime


class TransactionForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        input_formats=['%Y-%m-%d'],
    )
    value = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '0,00', 'id': 'value-input'}),
    )

    class Meta:
        model = Transaction
        fields = ['title', 'category', 'value', 'date', 'frequency', 'type']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'título'}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'frequency': forms.Select(attrs={'class': 'form-input'}),
            'type': forms.Select(attrs={'class': 'form-input'}),
        }

    def clean_value(self):
        raw = self.cleaned_data.get('value', '0')
        raw = raw.replace('.', '').replace(',', '.')
        try:
            return float(raw)
        except ValueError:
            raise forms.ValidationError('Valor inválido')


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'icon', 'color']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'nome da categoria'}),
            'icon': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ícone (emoji ou nome)'}),
            'color': forms.TextInput(attrs={'type': 'color', 'class': 'form-input color-input'}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['name', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'seu nome'}),
            'image': forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
        }
