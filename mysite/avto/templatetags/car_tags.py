from django import template
from django.utils import timezone

from ..models import Car, Review, EquipmentPackage

register = template.Library()


@register.simple_tag
def current_year():
    return timezone.now().year


@register.simple_tag(takes_context=True)
def greeting_tag(context):
    request = context.get('request')
    if request and request.user.is_authenticated:
        return f"Добро пожаловать, {request.user.username}! 👋"
    return "Добро пожаловать, гость! Войдите или зарегистрируйтесь."

@register.inclusion_tag('avto/tags/latest_cars.html')
def latest_cars(count=4):
    cars = Car.objects.for_sale().order_by('-created_at')[:count]
    return {'cars': cars}

@register.inclusion_tag('avto/tags/top_reviews.html')
def top_reviews(car, count=3):
    reviews = Review.objects.filter(car=car).order_by('-rating')[:count]
    return {'reviews': reviews, 'car': car}

@register.filter(name='rubles')
def rubles(value):
    try:
        value = float(value)
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f} млн ₽"
        return f"{value:,.0f} ₽".replace(',', ' ')
    except (TypeError, ValueError):
        return value


@register.filter(name='stars')
def stars(value):
    try:
        rating = int(value)
        return '★' * rating + '☆' * (5 - rating)
    except (TypeError, ValueError):
        return value
