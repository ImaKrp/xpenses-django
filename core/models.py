from django.db import models


class Category(models.Model):
    TYPE_CHOICES = [('default', 'Padrão'), ('custom', 'Customizada')]

    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=100, default='circle')
    color = models.CharField(max_length=20, default='#6F6F6F')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='custom')

    class Meta:
        ordering = ['name']
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'

    def __str__(self):
        return self.name


class Transaction(models.Model):
    TYPE_CHOICES = [('receita', 'Receita'), ('despesa', 'Despesa')]
    FREQUENCY_CHOICES = [('unique', 'Único'), ('recurrent', 'Recorrente')]

    title = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='transactions'
    )
    value = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='unique')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='despesa')

    class Meta:
        ordering = ['-date', 'title']
        verbose_name = 'Transação'
        verbose_name_plural = 'Transações'

    def __str__(self):
        return f'{self.title} — R$ {self.value}'


class UserProfile(models.Model):
    name = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='profile/', null=True, blank=True)

    class Meta:
        verbose_name = 'Perfil'

    def __str__(self):
        return self.name or 'Usuário'
