"""
Data migration: seed default categories, matching the mobile app's utils/categories.js
"""
from django.db import migrations


DEFAULTS = [
    {"name": "alimentação", "icon": "utensils",        "color": "#73A942"},
    {"name": "moradia",     "icon": "home",            "color": "#DF5555"},
    {"name": "saúde",       "icon": "heart-pulse",     "color": "#CA3EAB"},
    {"name": "compras",     "icon": "shopping-bag",    "color": "#B5A137"},
    {"name": "educação",    "icon": "graduation-cap",  "color": "#9437B5"},
    {"name": "transporte",  "icon": "car",             "color": "#37B5AD"},
    {"name": "saldo",       "icon": "piggy-bank",      "color": "#5837B5"},
    {"name": "outros",      "icon": "more-horizontal", "color": "#6F6F6F"},
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('core', 'Category')
    for cat in DEFAULTS:
        Category.objects.update_or_create(
            name=cat['name'],
            defaults={'icon': cat['icon'], 'color': cat['color'], 'type': 'default'}
        )


def unseed_categories(apps, schema_editor):
    Category = apps.get_model('core', 'Category')
    Category.objects.filter(type='default').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
