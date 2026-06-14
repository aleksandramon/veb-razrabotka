from __future__ import annotations

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404

from .models import Car, Service, ServiceOrder, Order, Review, Favorite
from .serializers import (
    CarSerializer, ServiceSerializer, ServiceOrderSerializer,
    OrderSerializer, ReviewSerializer,
)
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .filters import CarFilter, ServiceFilter


# ─────────────────────────────────────────────────────────
# Вспомогательный миксин — передача request в контекст
# ─────────────────────────────────────────────────────────
class RequestContextMixin:
    """
    Миксин для автоматической передачи request в контекст сериализатора.
    Нужен чтобы SerializerMethodField мог обращаться к текущему пользователю.
    """

    def get_serializer_context(self) -> dict:
        """Добавляет request в контекст сериализатора."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


# ─────────────────────────────────────────────────────────
# API автомобилей
# ─────────────────────────────────────────────────────────
class CarListAPIView(RequestContextMixin, generics.ListAPIView):
    """
    GET /api/cars/ — список всех доступных автомобилей.

    Возвращает автомобили с аннотациями:
        - avg_rating     — средний рейтинг из отзывов
        - favorite_count — количество добавлений в избранное
        - review_count   — количество отзывов

    Доступно всем пользователям (в т.ч. анонимным).
    """

    serializer_class = CarSerializer
    permission_classes = [permissions.AllowAny]

    filter_backends   = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class   = CarFilter
    search_fields     = ['brand', 'model']  

    def get_queryset(self):
        """
        Возвращает QuerySet автомобилей с аннотациями и оптимизированными запросами.
        Аннотированные поля avg_rating, favorite_count, review_count
        используются в CarSerializer напрямую.
        """
        return (
            Car.objects
            .exclude(status=Car.Status.ARCHIVE)
            .annotate(
                avg_rating=Avg('reviews__rating'),       # → CarSerializer.avg_rating
                favorite_count=Count('favorited_by'),    # → CarSerializer.favorite_count
                review_count=Count('reviews'),           # → CarSerializer.review_count
            )
            .prefetch_related('images', 'reviews__user')
            .order_by('-created_at')
        )


class CarDetailAPIView(RequestContextMixin, generics.RetrieveAPIView):
    """
    GET /api/cars/<id>/ — детальная карточка автомобиля.
    Доступно всем пользователям.
    """

    serializer_class = CarSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return (
            Car.objects
            .annotate(
                avg_rating=Avg('reviews__rating'),
                favorite_count=Count('favorited_by'),
                review_count=Count('reviews'),
            )
            .prefetch_related('images', 'reviews__user')
        )


# ─────────────────────────────────────────────────────────
# API услуг
# ─────────────────────────────────────────────────────────
class ServiceListAPIView(RequestContextMixin, generics.ListAPIView):
    """
    GET /api/services/ — список услуг тюнинга.

    Возвращает услуги с аннотацией order_count —
    количество записей на каждую услугу.
    Доступно всем пользователям.
    """

    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = ServiceFilter

    def get_queryset(self):
        """
        QuerySet услуг с аннотацией количества записей.
        order_count используется в ServiceSerializer.
        """
        return (
            Service.objects
            .annotate(order_count=Count('orders'))   # → ServiceSerializer.order_count
            .prefetch_related('orders')
            .order_by('price')
        )


class ServiceDetailAPIView(RequestContextMixin, generics.RetrieveAPIView):
    """
    GET /api/services/<id>/ — детальная информация об услуге.
    """

    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return (
            Service.objects
            .annotate(order_count=Count('orders'))
            .prefetch_related('orders')
        )


# ─────────────────────────────────────────────────────────
# API записей на услугу
# ─────────────────────────────────────────────────────────
class ServiceOrderListCreateAPIView(RequestContextMixin, generics.ListCreateAPIView):
    """
    GET  /api/bookings/ — мои записи на услуги
    POST /api/bookings/ — создать новую запись

    Только для авторизованных пользователей.
    Пользователь видит только свои записи.
    """

    serializer_class = ServiceOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Возвращает только записи текущего пользователя."""
        return (
            ServiceOrder.objects
            .filter(user=self.request.user)
            .select_related('user', 'service')
            .order_by('-date')
        )

    def perform_create(self, serializer: ServiceOrderSerializer) -> None:
        """
        Сохраняет запись, подставляя текущего пользователя.
        user берётся из контекста в ServiceOrderSerializer.create().

        Args:
            serializer: проверенный сериализатор
        """
        serializer.save()


# ─────────────────────────────────────────────────────────
# API заказов
# ─────────────────────────────────────────────────────────
class OrderListAPIView(RequestContextMixin, generics.ListAPIView):
    """
    GET /api/orders/ — список заказов.

    Администратор видит все заказы.
    Обычный пользователь — только свои.
    """

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Фильтрует заказы по роли:
        - staff → все заказы
        - обычный пользователь → только свои
        """
        qs = (
            Order.objects
            .select_related('user')
            .prefetch_related('items__car__images')
            .order_by('-created_at')
        )
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs


# ─────────────────────────────────────────────────────────
# API отзывов
# ─────────────────────────────────────────────────────────
class ReviewListCreateAPIView(RequestContextMixin, generics.ListCreateAPIView):
    """
    GET  /api/cars/<car_id>/reviews/ — отзывы на автомобиль
    POST /api/cars/<car_id>/reviews/ — оставить отзыв

    Читать могут все, писать — только авторизованные.
    """

    serializer_class = ReviewSerializer

    def get_permissions(self):
        """Читать — всем. Писать — только авторизованным."""
        if self.request.method == 'POST':
            return [permissions.IsAuthenticated()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        """Возвращает отзывы только для конкретного автомобиля."""
        car_id = self.kwargs['car_id']
        return (
            Review.objects
            .filter(car_id=car_id)
            .select_related('user')
            .order_by('-created_at')
        )

    def perform_create(self, serializer: ReviewSerializer) -> None:
        """
        Сохраняет отзыв, подставляя автомобиль и пользователя.

        Args:
            serializer: проверенный сериализатор
        """
        car_id = self.kwargs['car_id']
        car = get_object_or_404(Car, id=car_id)
        serializer.save(user=self.request.user, car=car)


# ─────────────────────────────────────────────────────────
# API статистики (пример сложного APIView с контекстом)
# ─────────────────────────────────────────────────────────
class StatsAPIView(APIView):
    """
    GET /api/stats/ — сводная статистика сайта.

    Демонстрирует передачу контекста вручную
    при вызове сериализатора внутри APIView.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request) -> Response:
        """
        Возвращает топ-5 автомобилей по рейтингу и топ-3 услуги.
        Передаёт request в контекст сериализаторов вручную.

        Args:
            request: HTTP-запрос
        """
        top_cars = (
            Car.objects
            .filter(status=Car.Status.SALE)
            .annotate(
                avg_rating=Avg('reviews__rating'),
                favorite_count=Count('favorited_by'),
                review_count=Count('reviews'),
            )
            .filter(review_count__gt=0)
            .prefetch_related('images')
            .order_by('-avg_rating')[:5]
        )

        top_services = (
            Service.objects
            .annotate(order_count=Count('orders'))
            .order_by('-order_count')[:3]
        )

        # ── Передача контекста вручную при вызове сериализатора ──
        # Это нужно когда сериализатор вызывается не через generic view,
        # а напрямую — без get_serializer_context()
        context = {'request': request}

        return Response({
            'top_cars': CarSerializer(
                top_cars, many=True, context=context       # ← context передаётся здесь
            ).data,
            'top_services': ServiceSerializer(
                top_services, many=True, context=context   # ← и здесь
            ).data,
        })