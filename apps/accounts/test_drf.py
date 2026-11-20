from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Profile

User = get_user_model()


@override_settings(ROOT_URLCONF='apps.accounts.api_urls_drf')
class AccountsAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='alice', email='alice@example.com', password='A-strong-passphrase-412'
        )
        self.other = User.objects.create_user(
            username='bob', email='bob@example.com', password='Another-passphrase-512'
        )

    def test_registration_creates_normalized_account_and_profile(self):
        response = self.client.post('/register/', {
            'full_name': 'Jane Doe',
            'email': 'JANE@example.com',
            'password': 'A-strong-passphrase-412',
            'location': 'Depok',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='jane@example.com')
        self.assertTrue(user.check_password('A-strong-passphrase-412'))
        self.assertEqual(user.profile.full_name, 'Jane Doe')
        self.assertEqual(user.profile.location, 'Depok')
        self.assertNotIn('password', response.data)
        self.assertNotIn('token', response.data)

    def test_registration_rejects_duplicate_email_and_weak_password(self):
        duplicate = self.client.post('/register/', {
            'full_name': 'Alice Example', 'email': 'ALICE@example.com',
            'password': 'A-strong-passphrase-412',
        }, format='json')
        self.assertEqual(duplicate.status_code, 400)
        weak = self.client.post('/register/', {
            'full_name': 'Jane Doe', 'email': 'jane@example.com', 'password': '123',
        }, format='json')
        self.assertEqual(weak.status_code, 400)
        self.assertIn('password', weak.data)
        self.assertFalse(User.objects.filter(email='jane@example.com').exists())

    def test_login_authenticates_and_logout_revokes_token(self):
        invalid = self.client.post('/login/', {
            'email': 'alice@example.com', 'password': 'wrong',
        }, format='json')
        self.assertEqual(invalid.status_code, 400)
        response = self.client.post('/login/', {
            'email': 'ALICE@example.com', 'password': 'A-strong-passphrase-412',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        token = response.data['token']
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        self.assertEqual(self.client.get('/profile/').status_code, 200)
        self.assertEqual(self.client.post('/logout/').status_code, 204)
        self.assertFalse(Token.objects.filter(key=token).exists())
        self.assertIn(self.client.get('/profile/').status_code, (401, 403))

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post('/login/', {
            'email': 'alice@example.com', 'password': 'A-strong-passphrase-412',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_profile_update_is_confined_to_owner_and_safe_fields(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.patch('/profile/', {
            'display_name': 'New name', 'user': self.other.pk,
            'username': 'hijacked', 'email': 'hijacked@example.com',
            'reputation_score': 0, 'successful_transactions': 999,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.display_name, 'New name')
        self.assertEqual(profile.reputation_score, 100)
        self.assertEqual(profile.successful_transactions, 0)
        self.assertEqual(self.user.username, 'alice')
        self.assertEqual(self.user.email, 'alice@example.com')
        self.assertNotEqual(self.other.profile.display_name, 'New name')
        self.assertNotIn('password', response.data)
        self.assertNotIn('is_staff', response.data)

    def test_anonymous_cannot_access_profile_or_logout(self):
        self.assertIn(self.client.get('/profile/').status_code, (401, 403))
        self.assertIn(self.client.patch('/profile/', {}, format='json').status_code, (401, 403))
        self.assertIn(self.client.post('/logout/').status_code, (401, 403))

    def test_session_logout_ends_session(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/logout/').status_code, 204)
        self.assertIn(self.client.get('/profile/').status_code, (401, 403))
