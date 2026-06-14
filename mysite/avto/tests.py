from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from avto.models import Car, Service, Review, Favorite, Order
from avto.forms import RegistrationForm, ReviewForm


class KaidoSpiritTests(TestCase):

    def setUp(self):
        """Создаём тестовые данные перед каждым тестом"""
        self.client = Client()

        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Тест',
            last_name='Пользователь'
        )

        self.car = Car.objects.create(
            brand='Toyota',
            model='Supra MK4',
            year=1998,
            price=4500000,
            status='SL'
        )

        self.service = Service.objects.create(
            name='Полная реставрация',
            description='Полная восстановление кузова и двигателя',
            price=250000,
            stock=5,
        )

    # ====================== 1-4. Тесты моделей ======================

    def test_car_creation(self):
        """Тест создания автомобиля"""
        self.assertEqual(self.car.brand, 'Toyota')
        self.assertEqual(self.car.get_status_display(), 'Продаётся')  # исправлено: ё
        self.assertTrue(self.car.created_at is not None)

    def test_service_str(self):
        """Тест строкового представления услуги"""
        self.assertEqual(str(self.service), 'Полная реставрация')

    def test_review_creation(self):
        """Тест создания отзыва"""
        review = Review.objects.create(
            user=self.user,
            car=self.car,
            rating=5,
            comment='Отличный автомобиль!'
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.car, self.car)

    # ====================== 5-8. Тесты URL и Views ======================

    def test_home_page_status(self):
        """Главная страница доступна"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_car_list_page(self):
        """Страница каталога доступна"""
        response = self.client.get(reverse('car_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Каталог автомобилей')

    def test_login_page(self):
        """Страница логина доступна"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

    def test_register_page(self):
        """Страница регистрации доступна"""
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    # ====================== 9-12. Тесты аутентификации и форм ======================

    def test_user_registration(self):
        """Тест успешной регистрации"""
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'newuser@example.com',  # исправлено: добавлен email
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_login_valid_user(self):
        """Успешный логин"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)

    def test_favorite_toggle(self):
        """Добавление/удаление из избранного (требует логина)"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('toggle_favorite', args=[self.car.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Favorite.objects.filter(user=self.user, car=self.car).exists())

    def test_review_form_validation(self):
        """Валидация формы отзыва — короткий комментарий должен не пройти"""
        form = ReviewForm(data={
            'rating': 5,
            'comment': 'Ок'   # исправлено: 2 символа — меньше минимума в 10
        })
        self.assertFalse(form.is_valid())
        self.assertIn('comment', form.errors)