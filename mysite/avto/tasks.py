from __future__ import annotations

from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta


@shared_task
def send_booking_reminder() -> str:
    """
    Периодическая задача: рассылка напоминаний о записи на услугу.

    Находит все активные записи на завтра и отправляет
    письмо-напоминание каждому клиенту.

    Returns:
        Строка с результатом — сколько писем отправлено.
    """
    from .models import ServiceOrder

    tomorrow_start = timezone.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    tomorrow_end   = tomorrow_start + timedelta(days=1)

    bookings = (
        ServiceOrder.objects
        .filter(
            date__range=(tomorrow_start, tomorrow_end),
            status=ServiceOrder.Status.BOOKING,
        )
        .select_related('user', 'service')
    )

    sent_count = 0
    for booking in bookings:
        send_mail(
            subject='Напоминание о записи — Салон винтажных автомобилей',
            message=(
                f'Здравствуйте, {booking.user.first_name or booking.user.username}!\n\n'
                f'Напоминаем, что завтра {booking.date.strftime("%d.%m.%Y в %H:%M")} '
                f'у вас запись на услугу «{booking.service.name}».\n\n'
                f'Ждём вас в нашем салоне!\n'
                f'С уважением, команда салона винтажных автомобилей'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.user.email],
            fail_silently=True,
        )
        sent_count += 1

    return f'Отправлено напоминаний: {sent_count}'


@shared_task
def archive_expired_bookings() -> str:
    """
    Периодическая задача: автоматический перевод просроченных записей в архив.

    Находит все активные брони, дата которых уже прошла,
    и меняет их статус на COMPLETED.

    Returns:
        Строка с результатом — сколько записей переведено в архив.
    """
    from .models import ServiceOrder

    expired = ServiceOrder.objects.filter(
        date__lt=timezone.now(),
        status=ServiceOrder.Status.BOOKING,
    )
    count = expired.count()
    expired.update(status=ServiceOrder.Status.COMPLETED)

    return f'Переведено в архив: {count} записей'


@shared_task
def send_daily_report() -> str:
    """
    Периодическая задача: ежедневный отчёт о заказах администратору.

    Собирает статистику за сегодня: новые заказы и записи на услуги.
    Отправляет письмо всем администраторам сайта.

    Returns:
        Строка с подтверждением отправки отчёта.
    """
    from .models import Order, ServiceOrder
    from django.contrib.auth.models import User

    today_start = timezone.now().replace(hour=0, minute=0, second=0)

    new_orders   = Order.objects.filter(created_at__gte=today_start).count()
    new_bookings = ServiceOrder.objects.filter(date__gte=today_start).count()

    admins = User.objects.filter(is_staff=True).values_list('email', flat=True)
    admin_emails = [e for e in admins if e]

    if admin_emails:
        send_mail(
            subject=f'Ежедневный отчёт — {timezone.now().strftime("%d.%m.%Y")}',
            message=(
                f'Отчёт за {timezone.now().strftime("%d.%m.%Y")}:\n\n'
                f'Новых заказов за сегодня: {new_orders}\n'
                f'Новых записей на услуги: {new_bookings}\n'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=True,
        )

    return f'Отчёт отправлен администраторам: {", ".join(admin_emails) or "нет email"}'