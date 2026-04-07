from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from django.utils.dateparse import parse_date
import datetime
import json
from decimal import Decimal

from .models import Transaction, Category, UserProfile
from .forms import TransactionForm, CategoryForm, UserProfileForm


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def get_month_range(year, month):
    """Return (first_day, last_day) for given year/month."""
    first = datetime.date(year, month, 1)
    if month == 12:
        last = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return first, last


def parse_month_params(request):
    today = datetime.date.today()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if month < 1: month = 1
        if month > 12: month = 12
    except (ValueError, TypeError):
        year, month = today.year, today.month
    return year, month


def month_nav_context(year, month):
    """Build prev/next month context for navigation."""
    prev_month = month - 1 or 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    return {
        'year': year, 'month': month,
        'prev_year': prev_year, 'prev_month': prev_month,
        'next_year': next_year, 'next_month': next_month,
        'month_name': datetime.date(year, month, 1).strftime('%B'),
    }


MONTH_NAMES = [
    '', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
    'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'
]


# ────────────────────────────────────────────────────────────────
# Home
# ────────────────────────────────────────────────────────────────

def home(request):
    year, month = parse_month_params(request)
    first, last = get_month_range(year, month)
    today = datetime.date.today()

    # All transactions for this month
    qs = Transaction.objects.filter(date__gte=first, date__lte=last).select_related('category')

    # Split realised vs future (only relevant for current month)
    is_current_month = (year == today.year and month == today.month)

    if is_current_month:
        realised = qs.filter(date__lte=today)
        future = qs.filter(date__gt=today)
    else:
        realised = qs
        future = Transaction.objects.none()

    receita = sum(t.value for t in realised if t.type == 'receita')
    despesa = sum(t.value for t in realised if t.type == 'despesa')
    balance = receita - despesa

    a_receber = sum(t.value for t in future if t.type == 'receita')
    a_pagar = sum(t.value for t in future if t.type == 'despesa')
    projected = balance + a_receber - a_pagar

    # Last 3 distinct dates of transactions
    recent_dates = sorted(set(t.date for t in realised), reverse=True)[:3]
    recent = {}
    for d in recent_dates:
        recent[d] = [t for t in realised if t.date == d]

    ctx = {
        'receita': receita,
        'despesa': despesa,
        'balance': balance,
        'a_receber': a_receber,
        'a_pagar': a_pagar,
        'projected': projected,
        'recent': recent,
        'month_name': MONTH_NAMES[month],
        **month_nav_context(year, month),
    }
    return render(request, 'core/home.html', ctx)


# ────────────────────────────────────────────────────────────────
# List
# ────────────────────────────────────────────────────────────────

def transaction_list(request):
    year, month = parse_month_params(request)
    first, last = get_month_range(year, month)

    qs = Transaction.objects.filter(date__gte=first, date__lte=last).select_related('category')

    # Filters
    title_q = request.GET.get('title', '').strip()
    category_id = request.GET.get('category_id', '').strip()
    type_q = request.GET.get('type', '').strip()

    if title_q:
        qs = qs.filter(title__icontains=title_q)
    if category_id:
        qs = qs.filter(category_id=category_id)
    if type_q:
        qs = qs.filter(type=type_q)

    # Group by date
    grouped = {}
    for t in qs:
        grouped.setdefault(t.date, []).append(t)

    receita = sum(t.value for t in qs if t.type == 'receita')
    despesa = sum(t.value for t in qs if t.type == 'despesa')

    categories = Category.objects.all()

    ctx = {
        'grouped': grouped,
        'receita': receita,
        'despesa': despesa,
        'categories': categories,
        'filters': {'title': title_q, 'category_id': category_id, 'type': type_q},
        'month_name': MONTH_NAMES[month],
        **month_nav_context(year, month),
    }
    return render(request, 'core/list.html', ctx)


# ────────────────────────────────────────────────────────────────
# Transaction Form (Create / Edit / Delete)
# ────────────────────────────────────────────────────────────────

def transaction_new(request):
    today = datetime.date.today()
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.value = form.cleaned_data['value']

            # Recurrent — create one entry per month until recurrent_to
            recurrent_to_str = request.POST.get('recurrent_to')
            frequency = form.cleaned_data.get('frequency')

            transaction.save()

            if frequency == 'recurrent' and recurrent_to_str:
                recurrent_to = parse_date(recurrent_to_str)
                if recurrent_to:
                    current = datetime.date(transaction.date.year, transaction.date.month, 1)
                    current = current.replace(month=current.month % 12 + 1) if current.month < 12 else datetime.date(current.year + 1, 1, 1)
                    end = datetime.date(recurrent_to.year, recurrent_to.month, 1)
                    while current <= end:
                        day = min(transaction.date.day, [31,28+int(current.year%4==0 and (current.year%100!=0 or current.year%400==0)),31,30,31,30,31,31,30,31,30,31][current.month-1])
                        Transaction.objects.create(
                            title=transaction.title,
                            category=transaction.category,
                            value=transaction.value,
                            date=current.replace(day=day),
                            frequency=transaction.frequency,
                            type=transaction.type,
                        )
                        if current.month == 12:
                            current = datetime.date(current.year + 1, 1, 1)
                        else:
                            current = current.replace(month=current.month + 1)

            messages.success(request, 'Transação criada com sucesso!')
            return redirect('home')
    else:
        initial_type = request.GET.get('type', 'despesa')
        form = TransactionForm(initial={'date': today, 'type': initial_type})

    categories = Category.objects.all()
    ctx = {'form': form, 'categories': categories, 'is_edit': False}
    return render(request, 'core/form.html', ctx)


def transaction_edit(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            t = form.save(commit=False)
            t.value = form.cleaned_data['value']
            t.save()
            messages.success(request, 'Transação atualizada!')
            return redirect('list')
    else:
        form = TransactionForm(instance=transaction, initial={
            'value': str(transaction.value).replace('.', ',')
        })

    categories = Category.objects.all()
    ctx = {'form': form, 'transaction': transaction, 'categories': categories, 'is_edit': True}
    return render(request, 'core/form.html', ctx)


@require_POST
def transaction_delete(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    transaction.delete()
    messages.success(request, 'Transação deletada.')
    return redirect('list')


# ────────────────────────────────────────────────────────────────
# Analysis
# ────────────────────────────────────────────────────────────────

def analysis(request):
    year, month = parse_month_params(request)
    first, last = get_month_range(year, month)
    type_q = request.GET.get('type', 'despesa')

    qs = Transaction.objects.filter(
        date__gte=first, date__lte=last, type=type_q
    ).select_related('category')

    total_sum = sum(t.value for t in qs)

    by_category = {}
    for t in qs:
        cat_name = t.category.name if t.category else 'outros'
        cat_color = t.category.color if t.category else '#6F6F6F'
        cat_icon = t.category.icon if t.category else '⋯'
        if cat_name not in by_category:
            by_category[cat_name] = {'name': cat_name, 'value': Decimal('0'), 'color': cat_color, 'icon': cat_icon}
        by_category[cat_name]['value'] += t.value

    mapped = sorted(by_category.values(), key=lambda x: x['value'], reverse=True)

    # Calculate percentages
    for item in mapped:
        item['percent'] = float(item['value'] * 100 / total_sum) if total_sum > 0 else 0
        item['value_float'] = float(item['value'])

    # Top 4 + outros (same logic as mobile)
    if len(mapped) > 5:
        top4 = [m for m in mapped if m['name'] != 'outros'][:4]
        rest = [m for m in mapped if m['name'] != 'outros'][4:]
        outros_existing = next((m for m in mapped if m['name'] == 'outros'), None)
        if outros_existing:
            rest.append(outros_existing)
        outros_val = sum(m['value'] for m in rest)
        outros_pct = float(outros_val * 100 / total_sum) if total_sum > 0 else 0
        top4.append({'name': 'outros', 'value': outros_val, 'value_float': float(outros_val), 'color': '#6F6F6F', 'icon': '⋯', 'percent': outros_pct})
        chart_data = top4
    else:
        chart_data = mapped

    ctx = {
        'mapped': mapped,
        'chart_data': json.dumps([{
            'label': d['name'],
            'value': d['value_float'],
            'percent': round(d['percent'], 2),
            'color': d['color'],
        } for d in chart_data]),
        'total_sum': total_sum,
        'type_q': type_q,
        'month_name': MONTH_NAMES[month],
        **month_nav_context(year, month),
    }
    return render(request, 'core/analysis.html', ctx)


# ────────────────────────────────────────────────────────────────
# Categories
# ────────────────────────────────────────────────────────────────

def categories(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoria criada!')
            return redirect('categories')
    else:
        form = CategoryForm()

    default_cats = Category.objects.filter(type='default').order_by('name')
    custom_cats = Category.objects.filter(type='custom').order_by('-id')
    ctx = {'form': form, 'default_cats': default_cats, 'custom_cats': custom_cats}
    return render(request, 'core/categories.html', ctx)


@require_POST
def category_delete(request, pk):
    cat = get_object_or_404(Category, pk=pk, type='custom')
    cat.delete()
    messages.success(request, 'Categoria deletada.')
    return redirect('categories')


# ────────────────────────────────────────────────────────────────
# Insights
# ────────────────────────────────────────────────────────────────

def insights(request):
    year, month = parse_month_params(request)
    first, last = get_month_range(year, month)
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    prev_first, prev_last = get_month_range(prev_year, prev_month)

    qs_current = Transaction.objects.filter(date__gte=first, date__lte=last).select_related('category')
    qs_prev = Transaction.objects.filter(date__gte=prev_first, date__lte=prev_last).select_related('category')

    receita_current = sum(t.value for t in qs_current if t.type == 'receita')
    despesa_current = sum(t.value for t in qs_current if t.type == 'despesa')
    
    despesa_prev = sum(t.value for t in qs_prev if t.type == 'despesa')

    # Mapping essentials vs non-essentials based on keywords
    essential_keywords = ['alimentação', 'moradia', 'saúde', 'educação', 'transporte', 'água', 'luz', 'internet', 'supermercado', 'farmácia']
    
    necessities = sum(t.value for t in qs_current if t.type == 'despesa' and t.category and any(k in t.category.name.lower() for k in essential_keywords))
    wants = despesa_current - necessities
    savings = receita_current - despesa_current

    # Percentages against Receita (or total despesa if receita is 0? Generally 50/30/20 is % of net income)
    base_calc = receita_current if receita_current > 0 else despesa_current
    
    if base_calc > 0:
        pct_necessities = float((necessities * 100) / base_calc)
        pct_wants = float((wants * 100) / base_calc)
        if receita_current > 0:
            pct_savings = float((savings * 100) / base_calc)
            # Cap visual bars out of 100 for proper display safely
        else:
            pct_savings = 0
    else:
        pct_necessities = pct_wants = pct_savings = 0

    # Diffs current vs prev by category
    from collections import defaultdict
    cat_current = defaultdict(Decimal)
    cat_prev = defaultdict(Decimal)

    for t in qs_current:
        if t.type == 'despesa':
            cat_name = t.category.name if t.category else 'outros'
            cat_current[cat_name] += t.value

    for t in qs_prev:
        if t.type == 'despesa':
            cat_name = t.category.name if t.category else 'outros'
            cat_prev[cat_name] += t.value

    tips = []
    
    # Needs
    if pct_necessities > 50:
        tips.append({
            'type': 'alert', 'title': 'Custos Essenciais Altos', 
            'icon': 'alert-triangle', 'color': 'var(--yellow)', 
            'text': f'Gastos fixos representam {pct_necessities:.1f}% do seu fluxo. O recomendado da regra 50/30/20 é tentar prender os fixos em 50%.'})
    elif pct_necessities > 0:
        tips.append({
            'type': 'success', 'title': 'Custos em Ordem', 
            'icon': 'check-circle', 'color': 'var(--receita)', 
            'text': f'Seus custos primários estão bem controlados ({pct_necessities:.1f}% do total).'})

    # Wants
    if pct_wants > 30:
        tips.append({
            'type': 'alert', 'title': 'Atenção aos Gastos Livres', 
            'icon': 'trending-down', 'color': 'var(--despesa)', 
            'text': f'As despesas não-essenciais chegaram a {pct_wants:.1f}%. Cuidado para o estilo de vida não consumir sua poupança.'})

    # Savings
    if receita_current > 0:
        if pct_savings < 20 and pct_savings > 0:
            tips.append({
                'type': 'warning', 'title': 'Aporte Pode Melhorar', 
                'icon': 'piggy-bank', 'color': 'var(--yellow)', 
                'text': f'Este mês você gerou um excedente de {pct_savings:.1f}%. A recomendação ideal é investir 20% das suas receitas mensais.'})
        elif pct_savings <= 0:
            tips.append({
                'type': 'alert', 'title': 'Alerta Crítico: Sem Sobras', 
                'icon': 'alert-circle', 'color': 'var(--despesa)', 
                'text': 'Atualmente você está fechando no negativo ou no zero-a-zero. Realize um diagnóstico nos seus gastos livres o quanto antes!'})
        else:
            tips.append({
                'type': 'success', 'title': 'Metas de Aporte Atingidas!', 
                'icon': 'trending-up', 'color': 'var(--accent)', 
                'text': f'Parabéns! Você tem {pct_savings:.1f}% disponível para investir em ativos ou formar reserva.'})

    # Find biggest increase vs last month
    biggest_increase = None
    max_increase_val = Decimal(0)
    for cat, val in cat_current.items():
        prev_val = cat_prev.get(cat, Decimal(0))
        if val > prev_val and prev_val > 0:
            increase = val - prev_val
            if increase > max_increase_val:
                max_increase_val = increase
                biggest_increase = cat
    
    if biggest_increase:
        tips.append({
            'type': 'warning', 'title': f'Leak de Orçamento: {biggest_increase.title()}', 
            'icon': 'scissors', 'color': 'var(--yellow)', 
            'text': f'A aba "{biggest_increase}" teve um salto de R$ {max_increase_val:.2f} comparado ao último mês. Corte os exageros nesta categoria!'})

    ctx = {
        'receita': receita_current,
        'despesa': despesa_current,
        'necessities': necessities,
        'wants': wants,
        'savings': savings,
        'pct_necessities': pct_necessities,
        'pct_wants': pct_wants,
        'pct_savings': pct_savings,
        'despesa_prev': despesa_prev,
        'tips': tips,
        'month_name': MONTH_NAMES[month],
        **month_nav_context(year, month),
    }

    return render(request, 'core/insights.html', ctx)


# ────────────────────────────────────────────────────────────────
# Profile
# ────────────────────────────────────────────────────────────────

def profile(request):
    user = UserProfile.objects.first()
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil salvo!')
            return redirect('home')
    else:
        form = UserProfileForm(instance=user)

    ctx = {'form': form, 'user': user}
    return render(request, 'core/profile.html', ctx)
