from django.shortcuts import render, redirect
from django.http import Http404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.utils.dateparse import parse_date
import datetime
import json
from decimal import Decimal
from collections import defaultdict

from . import repository
from . import supabase_client
from .supabase_client import user_schema
from .forms import TransactionForm, CategoryForm, UserProfileForm, SignUpForm, LoginForm
from .storage import SupabaseStorage


def get_month_range(year, month):
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


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data.get('email', ''),
                password=form.cleaned_data['password'],
            )
            supabase_client.rpc('create_user_schema', {'p_user_id': user.id})
            repository.upsert_profile(user_schema(user.id), {
                'user_id': user.id,
                'name': form.cleaned_data['name'],
            })
            login(request, user)
            messages.success(request, f'Bem-vindo(a), {form.cleaned_data["name"]}!')
            return redirect('home')
    else:
        form = SignUpForm()

    return render(request, 'core/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is not None:
                login(request, user)
                next_url = request.GET.get('next', 'home')
                messages.success(request, 'Login realizado com sucesso!')
                return redirect(next_url)
            else:
                form.add_error(None, 'Usuário ou senha inválidos.')
    else:
        form = LoginForm()

    return render(request, 'core/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'Você saiu da sua conta.')
    return redirect('login')


@login_required
def home(request):
    year, month = parse_month_params(request)
    first, last = get_month_range(year, month)
    today = datetime.date.today()
    schema = user_schema(request.user.id)

    qs = repository.list_transactions(schema, date_from=first, date_to=last)

    is_current_month = (year == today.year and month == today.month)

    if is_current_month:
        realised = [t for t in qs if t['date'] <= today]
        future = [t for t in qs if t['date'] > today]
    else:
        realised = qs
        future = []

    receita = sum(t['value'] for t in realised if t['type'] == 'receita')
    despesa = sum(t['value'] for t in realised if t['type'] == 'despesa')
    balance = receita - despesa

    a_receber = sum(t['value'] for t in future if t['type'] == 'receita')
    a_pagar = sum(t['value'] for t in future if t['type'] == 'despesa')
    projected = balance + a_receber - a_pagar

    recent_dates = sorted({t['date'] for t in realised}, reverse=True)[:3]
    recent = {}
    for d in recent_dates:
        recent[d] = [t for t in realised if t['date'] == d]

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


@login_required
def transaction_list(request):
    year, month = parse_month_params(request)
    first, last = get_month_range(year, month)
    schema = user_schema(request.user.id)

    title_q = request.GET.get('title', '').strip()
    category_id = request.GET.get('category_id', '').strip()
    type_q = request.GET.get('type', '').strip()

    qs = repository.list_transactions(
        schema, date_from=first, date_to=last,
        title=title_q or None, category_id=category_id or None, type=type_q or None,
    )

    grouped = {}
    for t in qs:
        grouped.setdefault(t['date'], []).append(t)

    receita = sum(t['value'] for t in qs if t['type'] == 'receita')
    despesa = sum(t['value'] for t in qs if t['type'] == 'despesa')
    balance = receita - despesa

    categories = repository.list_categories(schema)

    ctx = {
        'grouped': grouped,
        'receita': receita,
        'despesa': despesa,
        'balance': balance,
        'categories': categories,
        'filters': {'title': title_q, 'category_id': category_id, 'type': type_q},
        'month_name': MONTH_NAMES[month],
        **month_nav_context(year, month),
    }
    return render(request, 'core/list.html', ctx)


def _days_in_month(year, month):
    is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    return [31, 28 + int(is_leap), 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]


@login_required
def transaction_new(request):
    today = datetime.date.today()
    schema = user_schema(request.user.id)
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            recurrent_to_str = request.POST.get('recurrent_to')

            tx = repository.create_transaction(schema, {
                'title': form.cleaned_data['title'],
                'category_id': form.cleaned_data['category'],
                'value': form.cleaned_data['value'],
                'date': form.cleaned_data['date'],
                'frequency': form.cleaned_data['frequency'],
                'type': form.cleaned_data['type'],
            })

            if tx['frequency'] == 'recurrent' and recurrent_to_str:
                recurrent_to = parse_date(recurrent_to_str)
                if recurrent_to:
                    current = datetime.date(tx['date'].year, tx['date'].month, 1)
                    current = current.replace(month=current.month % 12 + 1) if current.month < 12 else datetime.date(current.year + 1, 1, 1)
                    end = datetime.date(recurrent_to.year, recurrent_to.month, 1)
                    while current <= end:
                        day = min(tx['date'].day, _days_in_month(current.year, current.month))
                        repository.create_transaction(schema, {
                            'title': tx['title'],
                            'category_id': tx['category_id'],
                            'value': tx['value'],
                            'date': current.replace(day=day),
                            'frequency': tx['frequency'],
                            'type': tx['type'],
                        })
                        if current.month == 12:
                            current = datetime.date(current.year + 1, 1, 1)
                        else:
                            current = current.replace(month=current.month + 1)

            messages.success(request, 'Transação criada com sucesso!')
            return redirect('home')
    else:
        initial_type = request.GET.get('type', 'despesa')
        form = TransactionForm(initial={'date': today, 'type': initial_type})

    categories = repository.list_categories(schema)
    ctx = {'form': form, 'categories': categories, 'is_edit': False}
    return render(request, 'core/form.html', ctx)


@login_required
def transaction_edit(request, pk):
    schema = user_schema(request.user.id)
    transaction = repository.get_transaction(schema, pk)
    if transaction is None:
        raise Http404

    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            repository.update_transaction(schema, pk, {
                'title': form.cleaned_data['title'],
                'category_id': form.cleaned_data['category'],
                'value': form.cleaned_data['value'],
                'date': form.cleaned_data['date'],
                'frequency': form.cleaned_data['frequency'],
                'type': form.cleaned_data['type'],
            })
            messages.success(request, 'Transação atualizada!')
            return redirect('list')
    else:
        form = TransactionForm(initial={
            'title': transaction['title'],
            'category': transaction['category_id'],
            'value': str(transaction['value']).replace('.', ','),
            'date': transaction['date'],
            'frequency': transaction['frequency'],
            'type': transaction['type'],
        })

    categories = repository.list_categories(schema)
    ctx = {'form': form, 'transaction': transaction, 'categories': categories, 'is_edit': True}
    return render(request, 'core/form.html', ctx)


@login_required
@require_POST
def transaction_delete(request, pk):
    schema = user_schema(request.user.id)
    transaction = repository.get_transaction(schema, pk)
    if transaction is None:
        raise Http404
    repository.delete_transaction(schema, pk)
    messages.success(request, 'Transação deletada.')
    return redirect('list')


@login_required
def analysis(request):
    year, month = parse_month_params(request)
    first, last = get_month_range(year, month)
    type_q = request.GET.get('type', 'despesa')
    schema = user_schema(request.user.id)

    qs = repository.list_transactions(schema, date_from=first, date_to=last, type=type_q)

    total_sum = sum(t['value'] for t in qs)

    by_category = {}
    for t in qs:
        cat = t['category']
        cat_name = cat['name'] if cat else 'outros'
        cat_color = cat['color'] if cat else '#6F6F6F'
        cat_icon = cat['icon'] if cat else '⋯'
        if cat_name not in by_category:
            by_category[cat_name] = {'name': cat_name, 'value': Decimal('0'), 'color': cat_color, 'icon': cat_icon}
        by_category[cat_name]['value'] += t['value']

    mapped = sorted(by_category.values(), key=lambda x: x['value'], reverse=True)

    for item in mapped:
        item['percent'] = float(item['value'] * 100 / total_sum) if total_sum > 0 else 0
        item['value_float'] = float(item['value'])

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


@login_required
def categories(request):
    schema = user_schema(request.user.id)
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            repository.create_category(schema, {
                'name': form.cleaned_data['name'],
                'icon': form.cleaned_data['icon'] or 'circle',
                'color': form.cleaned_data['color'] or '#6F6F6F',
            })
            messages.success(request, 'Categoria criada!')
            return redirect('categories')
    else:
        form = CategoryForm()

    default_cats = repository.list_default_categories()
    custom_cats = repository.list_custom_categories(schema)
    ctx = {'form': form, 'default_cats': default_cats, 'custom_cats': custom_cats}
    return render(request, 'core/categories.html', ctx)


@login_required
@require_POST
def category_delete(request, pk):
    schema = user_schema(request.user.id)
    cat = repository.get_custom_category(schema, pk)
    if cat is None:
        raise Http404
    repository.delete_category(schema, pk)
    messages.success(request, 'Categoria deletada.')
    return redirect('categories')


@login_required
def insights(request):
    year, month = parse_month_params(request)
    first, last = get_month_range(year, month)
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    prev_first, prev_last = get_month_range(prev_year, prev_month)
    schema = user_schema(request.user.id)

    qs_current = repository.list_transactions(schema, date_from=first, date_to=last)
    qs_prev = repository.list_transactions(schema, date_from=prev_first, date_to=prev_last)

    receita_current = sum(t['value'] for t in qs_current if t['type'] == 'receita')
    despesa_current = sum(t['value'] for t in qs_current if t['type'] == 'despesa')

    despesa_prev = sum(t['value'] for t in qs_prev if t['type'] == 'despesa')

    essential_keywords = ['alimentação', 'moradia', 'saúde', 'educação', 'transporte', 'água', 'luz', 'internet', 'supermercado', 'farmácia']

    necessities = sum(
        t['value'] for t in qs_current
        if t['type'] == 'despesa' and t['category'] and any(k in t['category']['name'].lower() for k in essential_keywords)
    )
    wants = despesa_current - necessities
    savings = receita_current - despesa_current

    base_calc = receita_current if receita_current > 0 else despesa_current

    if base_calc > 0:
        pct_necessities = float((necessities * 100) / base_calc)
        pct_wants = float((wants * 100) / base_calc)
        if receita_current > 0:
            pct_savings = float((savings * 100) / base_calc)
        else:
            pct_savings = 0
    else:
        pct_necessities = pct_wants = pct_savings = 0

    cat_current = defaultdict(Decimal)
    cat_prev = defaultdict(Decimal)

    for t in qs_current:
        if t['type'] == 'despesa':
            cat_name = t['category']['name'] if t['category'] else 'outros'
            cat_current[cat_name] += t['value']

    for t in qs_prev:
        if t['type'] == 'despesa':
            cat_name = t['category']['name'] if t['category'] else 'outros'
            cat_prev[cat_name] += t['value']

    tips = []

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

    if pct_wants > 30:
        tips.append({
            'type': 'alert', 'title': 'Atenção aos Gastos Livres',
            'icon': 'trending-down', 'color': 'var(--despesa)',
            'text': f'As despesas não-essenciais chegaram a {pct_wants:.1f}%. Cuidado para o estilo de vida não consumir sua poupança.'})

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

    repository.upsert_insight_snapshot(schema, {
        'year': year,
        'month': month,
        'receita': str(receita_current),
        'despesa': str(despesa_current),
        'necessities': str(necessities),
        'wants': str(wants),
        'savings': str(savings),
        'pct_necessities': pct_necessities,
        'pct_wants': pct_wants,
        'pct_savings': pct_savings,
    })
    history = repository.list_insight_snapshots(schema, exclude_year=year, exclude_month=month)
    for snapshot in history:
        snapshot['month_name'] = MONTH_NAMES[snapshot['month']]

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
        'history': history,
        'month_name': MONTH_NAMES[month],
        **month_nav_context(year, month),
    }

    return render(request, 'core/insights.html', ctx)


@login_required
def profile(request):
    schema = user_schema(request.user.id)
    profile_obj = repository.get_profile(schema)
    if profile_obj is None:
        profile_obj = repository.upsert_profile(schema, {
            'user_id': request.user.id,
            'name': request.user.get_full_name() or request.user.username,
        })

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES)
        if form.is_valid():
            data = {'user_id': request.user.id, 'name': form.cleaned_data['name']}
            image = form.cleaned_data.get('image')
            if image:
                storage = SupabaseStorage()
                name = storage.save(f'profile/{request.user.id}_{image.name}', image)
                data['image_url'] = storage.url(name)
            profile_obj = repository.upsert_profile(schema, data)
            messages.success(request, 'Perfil salvo!')
            return redirect('home')
    else:
        form = UserProfileForm(initial={'name': profile_obj.get('name', '')})

    ctx = {'form': form, 'profile_obj': profile_obj}
    return render(request, 'core/profile.html', ctx)
