from django.contrib import admin
from .models import Category, Transaction, UserProfile


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'type']
    list_filter = ['type']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['title', 'type', 'value', 'date', 'category', 'frequency']
    list_filter = ['type', 'frequency', 'category']
    date_hierarchy = 'date'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['name']
