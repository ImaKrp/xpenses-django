from django import forms
from django.contrib.auth.models import User
from decimal import Decimal, InvalidOperation

FREQUENCY_CHOICES = [('unique', 'Único'), ('recurrent', 'Recorrente')]
TYPE_CHOICES = [('receita', 'Receita'), ('despesa', 'Despesa')]


class TransactionForm(forms.Form):
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'título'}),
    )
    category = forms.IntegerField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    value = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '0,00', 'id': 'value-input'}),
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        input_formats=['%Y-%m-%d'],
    )
    frequency = forms.ChoiceField(
        choices=FREQUENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
    )

    def clean_value(self):
        raw = self.cleaned_data.get('value', '0')
        raw = raw.replace('.', '').replace(',', '.')
        try:
            return Decimal(raw)
        except InvalidOperation:
            raise forms.ValidationError('Valor inválido')


class CategoryForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'nome da categoria'}),
    )
    icon = forms.CharField(
        max_length=100, required=False, initial='circle',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ícone (emoji ou nome)'}),
    )
    color = forms.CharField(
        max_length=20, required=False, initial='#6F6F6F',
        widget=forms.TextInput(attrs={'type': 'color', 'class': 'form-input color-input'}),
    )


class UserProfileForm(forms.Form):
    name = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'seu nome'}),
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-input', 'accept': 'image/*'}),
    )


class SignUpForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'seu nome',
            'id': 'id_name',
            'autocomplete': 'name',
        }),
        label='nome',
    )
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'nome de usuário',
            'id': 'id_username',
            'autocomplete': 'username',
        }),
        label='usuário',
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'email@exemplo.com',
            'id': 'id_email',
            'autocomplete': 'email',
        }),
        label='e-mail',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'id_password',
            'autocomplete': 'new-password',
        }),
        label='senha',
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'id_password_confirm',
            'autocomplete': 'new-password',
        }),
        label='confirmar senha',
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nome de usuário já está em uso.')
        return username

    def clean(self):
        cleaned = super().clean()
        pw = cleaned.get('password')
        pw2 = cleaned.get('password_confirm')
        if pw and pw2 and pw != pw2:
            self.add_error('password_confirm', 'As senhas não coincidem.')
        return cleaned


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'nome de usuário',
            'id': 'id_username',
            'autocomplete': 'username',
        }),
        label='usuário',
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': '••••••••',
            'id': 'id_password',
            'autocomplete': 'current-password',
        }),
        label='senha',
    )
