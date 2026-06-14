from __future__ import annotations

from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Avg, Count

from .models import (
    Car, CarImage, Service, ServiceOrder,
    Order, OrderItem, Review, Favorite,
    EquipmentPackage, CarEquipmentPackage,
)


# ─────────────────────────────────────────────────────────
# Вспомогательный сериализатор — изображения автомобиля
# ─────────────────────────────────────────────────────────
class CarImageSerializer(serializers.ModelSerializer):
    """Сериализатор изображения автомобиля."""

    class Meta:
        model = CarImage
        fields = ['id', 'image', 'uploaded_at']


# ─────────────────────────────────────────────────────────
# Вспомогательный сериализатор — пользователь (краткий)
# ─────────────────────────────────────────────────────────
class UserShortSerializer(serializers.ModelSerializer):
    """
    Краткое представление пользователя для вложенных сериализаторов.
    Не раскрывает пароль и лишние поля.
    """

    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name']

    def get_full_name(self, obj: User) -> str:
        """
        Возвращает полное имя пользователя.
        Если имя не заполнено — возвращает username.

        Args:
            obj: объект пользователя Django
        """
        full = f"{obj.first_name} {obj.last_name}".strip()
        return full if full else obj.username


# ─────────────────────────────────────────────────────────
# Сериализатор отзыва
# ─────────────────────────────────────────────────────────
class ReviewSerializer(serializers.ModelSerializer):
    """
    Сериализатор отзыва об автомобиле.

    SerializerMethodField: rating_display — текстовое представление оценки.
    Контекст: request — для определения, чужой ли это отзыв.
    """

    # ── SerializerMethodField #1 ──────────────────────────
    rating_display = serializers.SerializerMethodField()

    # ── SerializerMethodField #2 ──────────────────────────
    is_own = serializers.SerializerMethodField()

    user = UserShortSerializer(read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'user', 'rating', 'rating_display',
            'comment', 'created_at', 'is_own',
        ]
        read_only_fields = ['user', 'created_at']

    def get_rating_display(self, obj: Review) -> str:
        """
        Возвращает оценку в виде звёздочек.
        Пример: 4 → '★★★★☆'

        Args:
            obj: объект отзыва
        """
        filled = '★' * obj.rating
        empty  = '☆' * (5 - obj.rating)
        return filled + empty

    def get_is_own(self, obj: Review) -> bool:
        """
        Проверяет, принадлежит ли отзыв текущему пользователю.
        Использует request из контекста сериализатора.

        Args:
            obj: объект отзыва
        """
        # ── Передача данных через контекст #1 ──
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

    def validate_rating(self, value: int) -> int:
        """Проверяет, что оценка в диапазоне от 1 до 5."""
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Оценка должна быть от 1 до 5.")
        return value

    def validate_comment(self, value: str) -> str:
        """Проверяет минимальную длину комментария."""
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Комментарий должен содержать не менее 10 символов."
            )
        return value


# ─────────────────────────────────────────────────────────
# Сериализатор автомобиля
# ─────────────────────────────────────────────────────────
class CarSerializer(serializers.ModelSerializer):
    """
    Основной сериализатор автомобиля.

    SerializerMethodField:
        - formatted_price   — цена в формате «1 500 000 ₽»
        - is_favorite       — добавлен ли в избранное текущим пользователем
        - status_label      — читаемый статус на русском
        - main_image        — URL первого изображения

    Аннотированные поля (передаются через queryset):
        - avg_rating        — средний рейтинг из отзывов
        - favorite_count    — сколько раз добавили в избранное
        - review_count      — количество отзывов

    Контекст:
        - request           — для проверки избранного и формирования URL
    """

    images   = CarImageSerializer(many=True, read_only=True)
    reviews  = ReviewSerializer(many=True, read_only=True)

    # ── SerializerMethodField #3 ──────────────────────────
    formatted_price = serializers.SerializerMethodField()

    # ── SerializerMethodField #4 ──────────────────────────
    is_favorite = serializers.SerializerMethodField()

    # ── SerializerMethodField #5 ──────────────────────────
    status_label = serializers.SerializerMethodField()

    # ── SerializerMethodField #6 ──────────────────────────
    main_image = serializers.SerializerMethodField()

    # ── Аннотированные поля — приходят из .annotate() ────
    avg_rating     = serializers.FloatField(read_only=True, default=None)
    favorite_count = serializers.IntegerField(read_only=True, default=0)
    review_count   = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Car
        fields = [
            'id', 'brand', 'model', 'year', 'price', 'formatted_price',
            'status', 'status_label', 'video_url',
            'avg_rating', 'favorite_count', 'review_count',
            'is_favorite', 'main_image', 'images', 'reviews',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def get_formatted_price(self, obj: Car) -> str:
        """
        Форматирует цену с разделителями тысяч и символом рубля.
        Пример: Decimal('1500000.00') → '1 500 000 ₽'

        Args:
            obj: объект автомобиля
        """
        return f"{obj.price:,.0f} ₽".replace(',', ' ')

    def get_is_favorite(self, obj: Car) -> bool:
        """
        Проверяет, добавил ли текущий пользователь автомобиль в избранное.
        Использует request из контекста сериализатора.

        Args:
            obj: объект автомобиля
        """
        # ── Передача данных через контекст #2 ──
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user,
                car=obj,
            ).exists()
        return False

    def get_status_label(self, obj: Car) -> str:
        """
        Возвращает читаемое название статуса автомобиля.
        Пример: 'SL' → 'Продаётся'

        Args:
            obj: объект автомобиля
        """
        return obj.get_status_display()

    def get_main_image(self, obj: Car) -> str | None:
        """
        Возвращает URL первого изображения автомобиля.
        Если изображений нет — возвращает None.

        Args:
            obj: объект автомобиля
        """
        # ── Передача данных через контекст #3 ──
        request = self.context.get('request')
        first_image = obj.images.first()
        if first_image and request:
            return request.build_absolute_uri(first_image.image.url)
        return None


# ─────────────────────────────────────────────────────────
# Сериализатор услуги
# ─────────────────────────────────────────────────────────
class ServiceSerializer(serializers.ModelSerializer):
    """
    Сериализатор услуги тюнинга.

    SerializerMethodField:
        - formatted_price   — цена в формате «15 000 ₽»
        - availability      — текстовый статус доступности мест
        - booking_count     — количество активных записей

    Аннотированные поля:
        - avg_rating        — средний рейтинг (если добавишь отзывы к услугам)
        - order_count       — количество записей на услугу
    """

    # ── SerializerMethodField #7 ──────────────────────────
    formatted_price = serializers.SerializerMethodField()

    # ── SerializerMethodField #8 ──────────────────────────
    availability = serializers.SerializerMethodField()

    # ── SerializerMethodField #9 ──────────────────────────
    booking_count = serializers.SerializerMethodField()

    # Аннотированное поле
    order_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Service
        fields = [
            'id', 'name', 'description', 'price', 'formatted_price',
            'stock', 'availability', 'booking_count', 'order_count',
        ]

    def get_formatted_price(self, obj: Service) -> str:
        """
        Форматирует цену услуги с символом рубля.
        Пример: Decimal('15000.00') → '15 000 ₽'

        Args:
            obj: объект услуги
        """
        return f"{obj.price:,.0f} ₽".replace(',', ' ')

    def get_availability(self, obj: Service) -> str:
        """
        Возвращает текстовый статус доступности записи на услугу.

        Значения:
            'available'  — есть свободные места
            'limited'    — осталось мало мест (≤3)
            'booked'     — мест нет

        Args:
            obj: объект услуги
        """
        if not hasattr(obj, 'stock') or obj.stock is None:
            return 'available'
        if obj.stock <= 0:
            return 'booked'
        if obj.stock <= 3:
            return 'limited'
        return 'available'

    def get_booking_count(self, obj: Service) -> int:
        """
        Возвращает количество активных записей на услугу.
        Использует только брони со статусом BOOKING.

        Args:
            obj: объект услуги
        """
        return obj.orders.filter(status=ServiceOrder.Status.BOOKING).count()


# ─────────────────────────────────────────────────────────
# Сериализатор записи на услугу
# ─────────────────────────────────────────────────────────
class ServiceOrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор записи клиента на услугу.

    SerializerMethodField:
        - formatted_date    — дата в читаемом формате
        - status_label      — статус на русском языке

    Контекст:
        - request           — для отображения данных текущего пользователя
    """

    service = ServiceSerializer(read_only=True)
    user    = UserShortSerializer(read_only=True)

    # Для записи принимаем только ID услуги
    service_id = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(),
        source='service',
        write_only=True,
    )

    # ── SerializerMethodField #10 ─────────────────────────
    formatted_date = serializers.SerializerMethodField()

    # ── SerializerMethodField #11 ─────────────────────────
    status_label = serializers.SerializerMethodField()

    class Meta:
        model = ServiceOrder
        fields = [
            'id', 'user', 'service', 'service_id',
            'date', 'formatted_date', 'status', 'status_label',
        ]
        read_only_fields = ['user', 'status']

    def get_formatted_date(self, obj: ServiceOrder) -> str:
        """
        Форматирует дату записи в читаемый вид.
        Пример: datetime(2025, 6, 15, 14, 30) → '15 июня 2025, 14:30'

        Args:
            obj: объект записи на услугу
        """
        months = [
            '', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
            'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
        ]
        d = obj.date
        return f"{d.day} {months[d.month]} {d.year}, {d.strftime('%H:%M')}"

    def get_status_label(self, obj: ServiceOrder) -> str:
        """
        Возвращает читаемое название статуса записи.
        Пример: 'BK' → 'Бронь'

        Args:
            obj: объект записи на услугу
        """
        return obj.get_status_display()

    def create(self, validated_data: dict) -> ServiceOrder:
        """
        Создаёт запись на услугу, подставляя пользователя из контекста.

        Args:
            validated_data: проверенные данные формы
        """
        # ── Передача данных через контекст #4 ──
        request = self.context.get('request')
        validated_data['user'] = request.user
        return super().create(validated_data)


# ─────────────────────────────────────────────────────────
# Сериализатор позиции заказа
# ─────────────────────────────────────────────────────────
class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор позиции заказа — автомобиль внутри заказа."""

    car = CarSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'car']


# ─────────────────────────────────────────────────────────
# Сериализатор заказа
# ─────────────────────────────────────────────────────────
class OrderSerializer(serializers.ModelSerializer):
    """
    Сериализатор заказа.

    SerializerMethodField:
        - total_price       — итоговая сумма по всем позициям
        - status_label      — статус на русском языке
        - item_count        — количество автомобилей в заказе

    Контекст:
        - request           — для проверки прав доступа к заказу
    """

    items        = OrderItemSerializer(many=True, read_only=True)
    user         = UserShortSerializer(read_only=True)

    # ── SerializerMethodField #12 ─────────────────────────
    total_price = serializers.SerializerMethodField()

    # ── SerializerMethodField #13 ─────────────────────────
    status_label = serializers.SerializerMethodField()

    # ── SerializerMethodField #14 ─────────────────────────
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'status', 'status_label',
            'created_at', 'items', 'total_price', 'item_count',
        ]
        read_only_fields = ['user', 'created_at']

    def get_total_price(self, obj: Order) -> str:
        """
        Вычисляет и форматирует итоговую сумму заказа.
        Суммирует цены всех автомобилей в позициях заказа.

        Args:
            obj: объект заказа
        """
        total = sum(
            item.car.price
            for item in obj.items.select_related('car').all()
        )
        return f"{total:,.0f} ₽".replace(',', ' ')

    def get_status_label(self, obj: Order) -> str:
        """
        Возвращает читаемый статус заказа.

        Args:
            obj: объект заказа
        """
        return obj.get_status_display()

    def get_item_count(self, obj: Order) -> int:
        """
        Возвращает количество позиций (автомобилей) в заказе.

        Args:
            obj: объект заказа
        """
        return obj.items.count()

    def to_representation(self, instance: Order) -> dict:
        """
        Переопределяет вывод: скрывает поле user для
        не-администраторов (показывает только свои заказы).

        Args:
            instance: объект заказа
        """
        data = super().to_representation(instance)
        # ── Передача данных через контекст #5 ──
        request = self.context.get('request')
        if request and not request.user.is_staff:
            data.pop('user', None)
        return data