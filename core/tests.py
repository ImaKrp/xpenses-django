import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse
from django.views.defaults import server_error

from . import repository
from . import supabase_client as sb
from .forms import SignUpForm, TransactionForm
from .storage import SupabaseStorage


def _response(json_data, status_code=200):
    response = MagicMock()
    response.ok = 200 <= status_code < 300
    response.status_code = status_code
    response.json.return_value = json_data
    response.content = b'1' if json_data is not None else b''
    response.text = str(json_data)
    response.headers = {'content-length': '0'}
    return response


class SupabaseClientTests(TestCase):
    @patch('core.supabase_client.requests.get')
    def test_select_sends_schema_headers(self, mock_get):
        mock_get.return_value = _response([{'id': 1}])
        result = sb.select('categories', [('type', 'eq.custom')], schema='user_1')
        self.assertEqual(result, [{'id': 1}])
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs['headers']['Accept-Profile'], 'user_1')
        self.assertEqual(kwargs['headers']['Content-Profile'], 'user_1')

    @patch('core.supabase_client.requests.get')
    def test_select_raises_on_error(self, mock_get):
        mock_get.return_value = _response('boom', status_code=500)
        with self.assertRaises(sb.SupabaseError):
            sb.select('categories')

    def test_user_schema_naming(self):
        self.assertEqual(sb.user_schema(7), 'user_7')


class RepositoryTests(TestCase):
    @patch('core.repository.sb.select')
    def test_list_default_categories_hydrates_pk(self, mock_select):
        mock_select.return_value = [{'id': 1, 'name': 'moradia', 'type': 'default'}]
        result = repository.list_default_categories()
        self.assertEqual(result[0]['pk'], 1)

    @patch('core.repository.sb.select')
    def test_hydrate_transaction_parses_decimal_and_date(self, mock_select):
        mock_select.side_effect = [
            [{'id': 10, 'title': 'mercado', 'value': 45.9, 'date': '2026-01-10',
              'type': 'despesa', 'category_id': None}],
            [],
            [],
        ]
        rows = repository.list_transactions('user_1')
        self.assertEqual(rows[0]['value'], Decimal('45.9'))
        self.assertEqual(rows[0]['date'], datetime.date(2026, 1, 10))
        self.assertIsNone(rows[0]['category'])

    @patch('core.repository.sb.insert')
    def test_create_transaction_serializes_decimal_and_date(self, mock_insert):
        mock_insert.return_value = [{
            'id': 1, 'title': 'luz', 'value': '80.00', 'date': '2026-01-01',
            'type': 'despesa', 'category_id': None,
        }]
        with patch('core.repository._category_lookup', return_value={}):
            repository.create_transaction('user_1', {
                'title': 'luz', 'category_id': None, 'value': Decimal('80.00'),
                'date': datetime.date(2026, 1, 1), 'frequency': 'unique', 'type': 'despesa',
            })
        payload = mock_insert.call_args[0][1]
        self.assertEqual(payload['value'], '80.00')
        self.assertEqual(payload['date'], '2026-01-01')


class StorageTests(TestCase):
    def setUp(self):
        self.storage = SupabaseStorage(
            base_url='https://proj.supabase.co', bucket='avatars', service_key='key123',
        )

    @patch('core.storage.requests.post')
    def test_save_uploads_to_object_url(self, mock_post):
        mock_post.return_value = _response(None, status_code=200)
        content = MagicMock()
        content.read.return_value = b'fake-bytes'
        content.content_type = 'image/png'
        name = self.storage._save('profile/1.png', content)
        self.assertEqual(name, 'profile/1.png')
        url = mock_post.call_args[0][0]
        self.assertEqual(url, 'https://proj.supabase.co/storage/v1/object/avatars/profile/1.png')

    def test_url_is_public_object_url(self):
        self.assertEqual(
            self.storage.url('profile/1.png'),
            'https://proj.supabase.co/storage/v1/object/public/avatars/profile/1.png',
        )


class FormTests(TestCase):
    def test_transaction_form_parses_brl_value(self):
        form = TransactionForm(data={
            'title': 'aluguel', 'value': '1.234,56', 'date': '2026-01-10',
            'frequency': 'unique', 'type': 'despesa',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['value'], Decimal('1234.56'))

    def test_transaction_form_rejects_invalid_value(self):
        form = TransactionForm(data={
            'title': 'aluguel', 'value': 'abc', 'date': '2026-01-10',
            'frequency': 'unique', 'type': 'despesa',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('value', form.errors)

    def test_signup_form_rejects_mismatched_passwords(self):
        form = SignUpForm(data={
            'name': 'Maria', 'username': 'maria', 'email': '',
            'password': 'abc12345', 'password_confirm': 'different',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password_confirm', form.errors)

    def test_signup_form_rejects_existing_username(self):
        User.objects.create_user(username='maria', password='x')
        form = SignUpForm(data={
            'name': 'Maria', 'username': 'maria', 'email': '',
            'password': 'abc12345', 'password_confirm': 'abc12345',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)


@patch('core.views.supabase_client.rpc')
@patch('core.views.repository.upsert_profile')
class AuthViewTests(TestCase):
    def test_signup_creates_django_user_and_provisions_profile(self, mock_upsert_profile, mock_rpc):
        mock_upsert_profile.return_value = {'user_id': 1, 'name': 'Maria'}
        response = self.client.post(reverse('signup'), {
            'name': 'Maria', 'username': 'maria', 'email': 'maria@example.com',
            'password': 'abc12345', 'password_confirm': 'abc12345',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        user = User.objects.get(username='maria')
        mock_rpc.assert_called_once_with('create_user_schema', {'p_user_id': user.id})
        mock_upsert_profile.assert_called_once()

    def test_login_with_valid_credentials(self, mock_upsert_profile, mock_rpc):
        User.objects.create_user(username='joao', password='senha123')
        response = self.client.post(reverse('login'), {'username': 'joao', 'password': 'senha123'})
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_login_with_invalid_credentials_shows_error(self, mock_upsert_profile, mock_rpc):
        User.objects.create_user(username='joao', password='senha123')
        response = self.client.post(reverse('login'), {'username': 'joao', 'password': 'errada'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuário ou senha inválidos.')

    def test_logout_redirects_to_login(self, mock_upsert_profile, mock_rpc):
        User.objects.create_user(username='joao', password='senha123')
        self.client.login(username='joao', password='senha123')
        response = self.client.get(reverse('logout'))
        self.assertRedirects(response, reverse('login'))

    def test_home_requires_login(self, mock_upsert_profile, mock_rpc):
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('home')}")


def _tx(id, title, value, date, type, category=None, category_id=None, frequency='unique'):
    return {
        'id': id, 'pk': id, 'title': title, 'value': Decimal(value),
        'date': date, 'type': type, 'category': category,
        'category_id': category_id, 'frequency': frequency,
    }


@patch('core.context_processors.repository.get_profile', return_value=None)
class TransactionViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='joao', password='senha123')
        self.client.login(username='joao', password='senha123')

    @patch('core.views.repository.list_transactions')
    def test_home_balance_is_receita_minus_despesa(self, mock_list, mock_profile):
        today = datetime.date.today()
        mock_list.return_value = [
            _tx(1, 'salário', '3000', today, 'receita'),
            _tx(2, 'mercado', '500', today, 'despesa'),
        ]
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['receita'], Decimal('3000'))
        self.assertEqual(response.context['despesa'], Decimal('500'))
        self.assertEqual(response.context['balance'], Decimal('2500'))

    @patch('core.views.repository.list_categories', return_value=[])
    @patch('core.views.repository.list_transactions')
    def test_list_filters_by_type(self, mock_list, mock_categories, mock_profile):
        today = datetime.date.today()
        mock_list.return_value = [_tx(1, 'salário', '100', today, 'receita')]
        response = self.client.get(reverse('list'), {'type': 'receita'})
        params = mock_list.call_args
        self.assertEqual(params.kwargs['type'], 'receita')
        titles = [tx['title'] for txs in response.context['grouped'].values() for tx in txs]
        self.assertEqual(titles, ['salário'])

    @patch('core.views.repository.list_categories', return_value=[])
    @patch('core.views.repository.create_transaction')
    def test_create_unique_transaction(self, mock_create, mock_categories, mock_profile):
        mock_create.return_value = _tx(1, 'farmácia', '45.90', datetime.date(2026, 6, 1), 'despesa', frequency='unique')
        response = self.client.post(reverse('transaction_new'), {
            'title': 'farmácia', 'value': '45,90', 'date': '2026-06-01',
            'category': '', 'frequency': 'unique', 'type': 'despesa',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        payload = mock_create.call_args[0][1]
        self.assertEqual(payload['value'], Decimal('45.90'))

    @patch('core.views.repository.list_categories', return_value=[])
    @patch('core.views.repository.create_transaction')
    def test_create_recurrent_transaction_generates_one_per_month(self, mock_create, mock_categories, mock_profile):
        mock_create.side_effect = lambda schema, data: {
            **data, 'id': 1, 'category_id': data.get('category_id'),
        }
        response = self.client.post(reverse('transaction_new'), {
            'title': 'assinatura', 'value': '20,00', 'date': '2026-01-15',
            'category': '', 'frequency': 'recurrent', 'type': 'despesa',
            'recurrent_to': '2026-03-20',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        dates = sorted(call.args[1]['date'] for call in mock_create.call_args_list)
        self.assertEqual(dates, [
            datetime.date(2026, 1, 15),
            datetime.date(2026, 2, 15),
            datetime.date(2026, 3, 15),
        ])

    @patch('core.views.repository.get_transaction', return_value=None)
    def test_edit_missing_transaction_404(self, mock_get, mock_profile):
        response = self.client.get(reverse('transaction_edit', args=[999]))
        self.assertEqual(response.status_code, 404)

    @patch('core.views.repository.delete_transaction')
    @patch('core.views.repository.get_transaction')
    def test_delete_transaction(self, mock_get, mock_delete, mock_profile):
        mock_get.return_value = _tx(1, 'apagar', '10', datetime.date(2026, 1, 1), 'despesa')
        response = self.client.post(reverse('transaction_delete', args=[1]))
        self.assertRedirects(response, reverse('list'), fetch_redirect_response=False)
        mock_delete.assert_called_once()

    def test_delete_transaction_requires_post(self, mock_profile):
        response = self.client.get(reverse('transaction_delete', args=[1]))
        self.assertEqual(response.status_code, 405)


@patch('core.context_processors.repository.get_profile', return_value=None)
class CategoryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='joao', password='senha123')
        self.client.login(username='joao', password='senha123')

    @patch('core.views.repository.list_custom_categories', return_value=[])
    @patch('core.views.repository.list_default_categories', return_value=[])
    @patch('core.views.repository.create_category')
    def test_create_custom_category(self, mock_create, mock_defaults, mock_customs, mock_profile):
        mock_create.return_value = {'id': 1, 'pk': 1, 'name': 'pets', 'type': 'custom'}
        response = self.client.post(reverse('categories'), {'name': 'pets', 'icon': 'dog', 'color': '#ff0000'})
        self.assertRedirects(response, reverse('categories'))
        payload = mock_create.call_args[0][1]
        self.assertEqual(payload['name'], 'pets')

    @patch('core.views.repository.delete_category')
    @patch('core.views.repository.get_custom_category')
    def test_delete_custom_category(self, mock_get, mock_delete, mock_profile):
        mock_get.return_value = {'id': 1, 'pk': 1, 'name': 'pets', 'type': 'custom'}
        response = self.client.post(reverse('category_delete', args=[1]))
        self.assertRedirects(response, reverse('categories'), fetch_redirect_response=False)
        mock_delete.assert_called_once()

    @patch('core.views.repository.get_custom_category', return_value=None)
    def test_cannot_delete_default_category(self, mock_get, mock_profile):
        response = self.client.post(reverse('category_delete', args=[1]))
        self.assertEqual(response.status_code, 404)


@patch('core.context_processors.repository.get_profile', return_value=None)
class AnalysisInsightsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='joao', password='senha123')
        self.client.login(username='joao', password='senha123')

    @patch('core.views.repository.list_transactions')
    def test_analysis_groups_by_category(self, mock_list, mock_profile):
        cat = {'id': 1, 'pk': 1, 'name': 'alimentação', 'color': '#73A942', 'icon': 'utensils'}
        today = datetime.date.today()
        mock_list.return_value = [
            _tx(1, 'mercado', '100', today, 'despesa', category=cat, category_id=1),
            _tx(2, 'padaria', '50', today, 'despesa', category=cat, category_id=1),
        ]
        response = self.client.get(reverse('analysis'), {'type': 'despesa'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_sum'], Decimal('150'))

    @patch('core.views.repository.upsert_insight_snapshot')
    @patch('core.views.repository.list_insight_snapshots', return_value=[])
    @patch('core.views.repository.list_transactions', return_value=[])
    def test_insights_renders_without_data(self, mock_list, mock_history, mock_upsert, mock_profile):
        response = self.client.get(reverse('insights'))
        self.assertEqual(response.status_code, 200)
        mock_upsert.assert_called_once()


class ErrorPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='joao', password='senha123')
        self.client.login(username='joao', password='senha123')

    @override_settings(DEBUG=False)
    @patch('core.context_processors.repository.get_profile', return_value=None)
    def test_unknown_url_renders_custom_404(self, mock_profile):
        response = self.client.get('/esta-pagina-nao-existe/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')

    @override_settings(DEBUG=False)
    @patch('core.context_processors.repository.get_profile', return_value=None)
    @patch('core.views.repository.get_transaction', return_value=None)
    def test_missing_object_renders_custom_404(self, mock_get, mock_profile):
        response = self.client.get(reverse('transaction_edit', args=[999999]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')

    def test_500_uses_custom_template(self):
        request = RequestFactory().get('/')
        response = server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Xpenses', response.content)
