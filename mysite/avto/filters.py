from __future__ import annotations

import django_filters
from django_filters import FilterSet, CharFilter, NumberFilter, ChoiceFilter, OrderingFilter

from .models import Car, Service


# ─────────────────────────────────────────────────────────
# FilterSet для автомобилей
# ─────────────────────────────────────────────────────────
class CarFilter(FilterSet):
    """
    Фильтрация автомобилей по различным критериям.

    Доступные фильтры:
        brand       — марка (частичное совпадение, без учёта регистра)
        model       — модель (частичное совпадение)
        year_min    — год выпуска от
        year_max    — год выпуска до
        price_min   — цена от
        price_max   — цена до
        status      — статус (продаётся / забронирована / в архиве)
        ordering    — сортировка

    Пример запроса:
        /api/cars/?brand=toyota&price_min=500000&price_max=2000000&ordering=-price
    """

    # Фильтр по марке — icontains (без учёта регистра, частичное совпадение)
    brand = CharFilter(
        field_name='brand',
        lookup_expr='icontains',
        label='Марка',
    )

    # Фильтр по модели
    model = CharFilter(
        field_name='model',
        lookup_expr='icontains',
        label='Модель',
    )

    # Диапазон года выпуска
    year_min = NumberFilter(
        field_name='year',
        lookup_expr='gte',
        label='Год выпуска от',
    )
    year_max = NumberFilter(
        field_name='year',
        lookup_expr='lte',
        label='Год выпуска до',
    )

    # Диапазон цены
    price_min = NumberFilter(
        field_name='price',
        lookup_expr='gte',
        label='Цена от (₽)',
    )
    price_max = NumberFilter(
        field_name='price',
        lookup_expr='lte',
        label='Цена до (₽)',
    )

    # Фильтр по статусу — строгое совпадение
    status = ChoiceFilter(
        field_name='status',
        choices=Car.Status.choices,
        label='Статус',
        empty_label='Все статусы',
    )

    # Сортировка
    ordering = OrderingFilter(
        fields=(
            ('price',      'price'),       # /api/cars/?ordering=price
            ('year',       'year'),        # /api/cars/?ordering=-year
            ('created_at', 'created_at'),  # /api/cars/?ordering=-created_at
            ('brand',      'brand'),       # /api/cars/?ordering=brand
        ),
        label='Сортировка',
    )

    class Meta:
        model = Car
        fields = [
            'brand', 'model',
            'year_min', 'year_max',
            'price_min', 'price_max',
            'status',
        ]


# ─────────────────────────────────────────────────────────
# FilterSet для услуг
# ─────────────────────────────────────────────────────────
class ServiceFilter(FilterSet):
    """
    Фильтрация услуг тюнинга.

    Доступные фильтры:
        name        — название (частичное совпадение)
        price_min   — цена от
        price_max   — цена до
        has_stock   — только с доступными местами (true/false)
        ordering    — сортировка

    Пример запроса:
        /api/services/?price_max=10000&has_stock=true&ordering=price
    """

    # Фильтр по названию
    name = CharFilter(
        field_name='name',
        lookup_expr='icontains',
        label='Название услуги',
    )

    # Диапазон цены
    price_min = NumberFilter(
        field_name='price',
        lookup_expr='gte',
        label='Цена от (₽)',
    )
    price_max = NumberFilter(
        field_name='price',
        lookup_expr='lte',
        label='Цена до (₽)',
    )

    # Фильтр по наличию мест — кастомный метод
    has_stock = django_filters.BooleanFilter(
        method='filter_has_stock',
        label='Только с доступными местами',
    )

    # Сортировка
    ordering = OrderingFilter(
        fields=(
            ('price', 'price'),   # /api/services/?ordering=price
            ('name',  'name'),    # /api/services/?ordering=name
            ('stock', 'stock'),   # /api/services/?ordering=-stock
        ),
        label='Сортировка',
    )

    class Meta:
        model = Service
        fields = ['name', 'price_min', 'price_max', 'has_stock']

    def filter_has_stock(self, queryset, name: str, value: bool):
        """
        Фильтрует услуги по наличию свободных мест.

        Args:
            queryset: исходный QuerySet услуг
            name: имя поля (не используется — метод кастомный)
            value: True — только с местами, False — только без мест
        """
        if value:
            return queryset.filter(stock__gt=0)
        return queryset.filter(stock=0)