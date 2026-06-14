from __future__ import annotations

from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, HttpResponse, HttpRequest
from django.urls import reverse
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Avg, Min, Max, QuerySet
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
import os

from .models import (
    Car, EquipmentPackage, CarEquipmentPackage,
    Order, OrderItem, Service, ServiceOrder, Review, Favorite,
)
from .forms import (
    CarForm, ServiceForm, ReviewForm,
    CarEquipmentPackageForm, RegistrationForm, OrderForm,
    ServiceOrderForm,
)


def home(request: HttpRequest) -> HttpResponse:
    """
    Главная страница сайта тюнинг-ателье.

    Отображает:
        - Форму поиска автомобилей по марке, модели и цене
        - Топ-5 автомобилей по среднему рейтингу
        - Последние 6 услуг
        - Последние 5 отзывов
        - Статистику сайта (количество машин, услуг, средний рейтинг)

    Args:
        request: HTTP-запрос

    Returns:
        HttpResponse с отрендеренным шаблоном avto/home.html
    """
    q_brand     = request.GET.get('q_brand', '').strip()
    q_model     = request.GET.get('q_model', '').strip()
    q_max_price = request.GET.get('q_max_price', '').strip()
    q_sort      = request.GET.get('q_sort', '-created_at')
    search_performed = any([q_brand, q_model, q_max_price])

    search_results: list[Car] = []
    if search_performed:
        qs: QuerySet[Car] = Car.objects.exclude(status='AR')
        if q_brand:
            qs = qs.filter(brand__icontains=q_brand)
        if q_model:
            qs = qs.filter(model__icontains=q_model)
        if q_max_price and q_max_price.isdigit():
            qs = qs.filter(price__lte=int(q_max_price))
        sort_map: dict[str, str] = {
            'price': 'price', '-price': '-price',
            'year': 'year',   '-created_at': '-created_at',
        }
        qs = qs.order_by(sort_map.get(q_sort, '-created_at'))
        search_results = list(qs[:20])

    top_cars: QuerySet[Car] = (
        Car.objects
        .filter(status='SL')
        .annotate(
            review_count=Count('reviews'),
            avg_rating=Avg('reviews__rating'),
        )
        .filter(review_count__gt=0)
        .order_by('-avg_rating', '-review_count')
        .prefetch_related('images')[:5]
    )

    services: QuerySet[Service] = Service.objects.all().order_by('price')[:6]

    latest_reviews: QuerySet[Review] = (
        Review.objects
        .exclude(rating__lt=1)
        .select_related('user', 'car')
        .order_by('-created_at')[:5]
    )

    package_stats = (
        CarEquipmentPackage.objects
        .filter(status='AVAILABLE')
        .values('package__name', 'package__package_type')
        .annotate(count=Count('id'))
        .order_by('-count')[:6]
    )

    fav_cars: QuerySet[Car] = (
        Car.objects
        .filter(status='SL')
        .annotate(fav_count=Count('favorited_by'))
        .filter(fav_count__gt=0)
        .order_by('-fav_count')
        .prefetch_related('images')[:5]
    )

    newest_cars: QuerySet[Car] = (
        Car.objects
        .filter(status='SL')
        .order_by('-created_at')
        .prefetch_related('images')[:8]
    )

    stats: dict[str, int | float] = {
        'total_cars':        Car.objects.filter(status='SL').count(),
        'total_services':    Service.objects.count(),
        'total_reviews':     Review.objects.count(),
        'avg_rating':        Review.objects.aggregate(a=Avg('rating'))['a'] or 0,
        'avg_service_price': Service.objects.aggregate(a=Avg('price'))['a'] or 0,
    }

    all_brands: QuerySet = Car.objects.values_list('brand', flat=True).distinct().order_by('brand')

    return render(request, 'avto/home.html', {
        'q_brand':          q_brand,
        'q_model':          q_model,
        'q_max_price':      q_max_price,
        'q_sort':           q_sort,
        'search_performed': search_performed,
        'search_results':   search_results,
        'top_cars':         top_cars,
        'services':         services,
        'latest_reviews':   latest_reviews,
        'package_stats':    package_stats,
        'newest_cars':      newest_cars,
        'fav_cars':         fav_cars,
        'stats':            stats,
        'all_brands':       all_brands,
    })


def car_list(request: HttpRequest) -> HttpResponse:
    """
    Каталог автомобилей с фильтрацией, сортировкой и пагинацией.

    Поддерживаемые GET-параметры:
        brand     — фильтр по марке (icontains)
        model     — фильтр по модели
        min_price — минимальная цена
        max_price — максимальная цена
        sort      — сортировка: price, -price, brand, year
        page      — номер страницы (6 автомобилей на страницу)

    Args:
        request: HTTP-запрос

    Returns:
        HttpResponse с отрендеренным шаблоном avto/car_list.html
    """
    cars: QuerySet[Car] = Car.objects.all()

    brand_filter: str = request.GET.get('brand', '')
    if brand_filter:
        cars = cars.filter(brand__icontains=brand_filter)

    model_filter: str = request.GET.get('model', '')
    if model_filter:
        cars = cars.filter(model__contains=model_filter)

    min_price: str = request.GET.get('min_price', '')
    if min_price and min_price.isdigit():
        cars = cars.filter(price__gte=int(min_price))

    max_price: str = request.GET.get('max_price', '')
    if max_price and max_price.isdigit():
        cars = cars.filter(price__lte=int(max_price))

    cars = cars.exclude(status='AR').exclude(status='BK')

    sort: str = request.GET.get('sort', '-created_at')
    sort_map: dict[str, str] = {
        'price': 'price', '-price': '-price',
        'brand': 'brand', 'year':   '-year',
    }
    cars = cars.order_by(sort_map.get(sort, '-created_at'))
    cars = cars.prefetch_related('equipment_packages', 'car_packages__package', 'images')

    total_count: int        = cars.count()
    has_results: bool       = cars.exists()
    all_brands: QuerySet    = Car.objects.values_list('brand', flat=True).distinct().order_by('brand')

    price_data = cars.values('brand').annotate(
        avg_price=Avg('price'),
        count=Count('id'),
    ).order_by('-count')[:5]

    stats: dict[str, int | float | None] = cars.aggregate(
        total=Count('id'),
        avg_price=Avg('price'),
        min_price=Min('price'),
        max_price=Max('price'),
    )

    cars_limited: QuerySet[Car] = Car.objects.order_by('-created_at')[:5]

    paginator = Paginator(cars, 6)
    page: str = request.GET.get('page', 1)
    try:
        cars_page = paginator.page(page)
    except PageNotAnInteger:
        cars_page = paginator.page(1)
    except EmptyPage:
        cars_page = paginator.page(paginator.num_pages)

    return render(request, 'avto/car_list.html', {
        'cars':         cars_page,
        'stats':        stats,
        'brand_filter': brand_filter,
        'model_filter': model_filter,
        'min_price':    min_price,
        'max_price':    max_price,
        'sort':         sort,
        'total_count':  total_count,
        'has_results':  has_results,
        'all_brands':   all_brands,
        'price_data':   price_data,
        'cars_limited': cars_limited,
    })


def car_detail(request: HttpRequest, car_id: int) -> HttpResponse:
    """
    Детальная страница автомобиля.

    Сохраняет ID просмотренного автомобиля в сессии (последние 5).
    Отображает отзывы, активные пакеты оборудования и недавно просмотренные машины.

    Args:
        request: HTTP-запрос
        car_id:  ID автомобиля

    Returns:
        HttpResponse с отрендеренным шаблоном avto/car_detail.html
    """
    car: Car = get_object_or_404(Car, id=car_id)

    history: list[int] = request.session.get('viewed_cars', [])
    if car_id not in history:
        history.append(car_id)
    request.session['viewed_cars'] = history[-5:]

    reviews: QuerySet[Review] = car.reviews.select_related('user').order_by('-created_at')

    active_packages = car.car_packages.prefetch_related('package').filter(status='AVAILABLE')

    viewed_cars: QuerySet[Car] = Car.objects.filter(
        id__in=request.session['viewed_cars']
    ).exclude(id=car_id)

    return render(request, 'avto/car_detail.html', {
        'car':             car,
        'reviews':         reviews,
        'active_packages': active_packages,
        'viewed_cars':     viewed_cars,
    })


@login_required
def car_create(request: HttpRequest) -> HttpResponse:
    """
    Создание нового автомобиля в каталоге. Только для авторизованных.

    Args:
        request: HTTP-запрос

    Returns:
        GET:  форма создания автомобиля
        POST: редирект на car_list при успехе, форма с ошибками при неудаче
    """
    if request.method == 'POST':
        form = CarForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('car_list')
    else:
        form = CarForm()
    return render(request, 'avto/car_form.html', {
        'form': form, 'title': 'Добавить автомобиль', 'action': 'Создать',
    })


@login_required
def car_edit(request: HttpRequest, car_id: int) -> HttpResponse:
    """
    Редактирование существующего автомобиля. Только для авторизованных.

    Args:
        request: HTTP-запрос
        car_id:  ID редактируемого автомобиля

    Returns:
        GET:  форма с текущими данными автомобиля
        POST: редирект на car_detail при успехе, форма с ошибками при неудаче
    """
    car: Car = get_object_or_404(Car, id=car_id)
    if request.method == 'POST':
        form = CarForm(request.POST, request.FILES, instance=car)
        if form.is_valid():
            form.save()
            return redirect('car_detail', car_id=car.id)
    else:
        form = CarForm(instance=car)
    return render(request, 'avto/car_form.html', {
        'form': form, 'title': f'Редактировать: {car}', 'action': 'Сохранить', 'car': car,
    })


@login_required
def car_delete(request: HttpRequest, car_id: int) -> HttpResponse:
    """
    Удаление автомобиля из каталога. Только для авторизованных.

    Args:
        request: HTTP-запрос
        car_id:  ID удаляемого автомобиля

    Returns:
        GET:  страница подтверждения удаления
        POST: редирект на car_list после удаления
    """
    car: Car = get_object_or_404(Car, id=car_id)
    if request.method == 'POST':
        car.delete()
        return redirect('car_list')
    return render(request, 'avto/car_confirm_delete.html', {'car': car})


def service_list(request: HttpRequest) -> HttpResponse:
    """
    Список всех услуг тюнинг-ателье, отсортированных по цене.

    Args:
        request: HTTP-запрос

    Returns:
        HttpResponse с отрендеренным шаблоном avto/service_list.html
    """
    services: QuerySet[Service] = Service.objects.order_by('price')
    return render(request, 'avto/service_list.html', {'services': services})


@login_required
def service_create(request: HttpRequest) -> HttpResponse:
    """
    Создание новой услуги. Только для авторизованных.

    Args:
        request: HTTP-запрос

    Returns:
        GET:  пустая форма создания услуги
        POST: редирект на service_list при успехе
    """
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('service_list')
    else:
        form = ServiceForm()
    return render(request, 'avto/service_form.html', {
        'form': form, 'title': 'Новая услуга', 'action': 'Создать',
    })


@login_required
def service_edit(request: HttpRequest, service_id: int) -> HttpResponse:
    """
    Редактирование существующей услуги. Только для авторизованных.

    Args:
        request:    HTTP-запрос
        service_id: ID редактируемой услуги

    Returns:
        GET:  форма с текущими данными услуги
        POST: редирект на service_list при успехе
    """
    service: Service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('service_list')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'avto/service_form.html', {
        'form': form, 'title': f'Редактировать: {service.name}', 'action': 'Сохранить',
    })


@login_required
def service_delete(request: HttpRequest, service_id: int) -> HttpResponse:
    """
    Удаление услуги. Только для авторизованных.

    Args:
        request:    HTTP-запрос
        service_id: ID удаляемой услуги

    Returns:
        GET:  страница подтверждения удаления
        POST: редирект на service_list после удаления
    """
    service: Service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        service.delete()
        return redirect('service_list')
    return render(request, 'avto/service_confirm_delete.html', {'service': service})


@login_required
def book_service(request: HttpRequest, service_id: int) -> HttpResponse:
    """
    Запись клиента на услугу тюнинга.

    Проверяет через ServiceOrderForm:
        - Доступность выбранного времени (±60 минут от других записей)
        - Наличие свободных мест (service.stock > 0)

    После успешной записи уменьшает service.stock на 1.

    Args:
        request:    HTTP-запрос
        service_id: ID услуги для записи

    Returns:
        GET:  форма записи с предзаполненной услугой
        POST: редирект на service_list при успехе, форма с ошибками при неудаче
    """
    service: Service = get_object_or_404(
        Service.objects.prefetch_related('orders__user'),
        id=service_id,
    )
    if request.method == 'POST':
        form = ServiceOrderForm(request.POST)
        if form.is_valid():
            service_order: ServiceOrder = form.save(commit=False)
            service_order.user    = request.user
            service_order.service = service
            service_order.save()
            service.stock = max(0, service.stock - 1)
            service.save(update_fields=['stock'])
            return redirect('service_list')
    else:
        form = ServiceOrderForm(initial={'service': service})
    return render(request, 'avto/book_service.html', {
        'service': service,
        'form':    form,
    })


@login_required
def add_review(request: HttpRequest, car_id: int) -> HttpResponse:
    """
    Добавление отзыва об автомобиле. Только для авторизованных.

    Args:
        request: HTTP-запрос
        car_id:  ID автомобиля, к которому добавляется отзыв

    Returns:
        GET:  форма написания отзыва
        POST: редирект на car_detail при успехе
    """
    car: Car = get_object_or_404(Car, id=car_id)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review: Review = form.save(commit=False)
            review.user = request.user
            review.car  = car
            review.save()
            return redirect('car_detail', car_id=car_id)
    else:
        form = ReviewForm()
    return render(request, 'avto/add_review.html', {'car': car, 'form': form})


def package_list(request: HttpRequest) -> HttpResponse:
    """
    Список всех пакетов оборудования, привязанных к автомобилям.

    Использует select_related для оптимизации запросов к Car и EquipmentPackage.

    Args:
        request: HTTP-запрос

    Returns:
        HttpResponse с отрендеренным шаблоном avto/package_list.html
    """
    packages: QuerySet[CarEquipmentPackage] = (
        CarEquipmentPackage.objects
        .select_related('car', 'package')
        .order_by('car__brand')
    )
    return render(request, 'avto/package_list.html', {'packages': packages})


@login_required
def package_create(request: HttpRequest) -> HttpResponse:
    """
    Привязка пакета оборудования к автомобилю. Только для авторизованных.

    Args:
        request: HTTP-запрос

    Returns:
        GET:  форма создания привязки пакета
        POST: редирект на package_list при успехе
    """
    if request.method == 'POST':
        form = CarEquipmentPackageForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('package_list')
    else:
        form = CarEquipmentPackageForm()
    return render(request, 'avto/package_form.html', {
        'form': form, 'title': 'Добавить пакет к автомобилю', 'action': 'Создать',
    })


@login_required
def package_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Редактирование привязанного пакета оборудования. Только для авторизованных.

    Args:
        request: HTTP-запрос
        pk:      первичный ключ записи CarEquipmentPackage

    Returns:
        GET:  форма с текущими данными пакета
        POST: редирект на package_list при успехе
    """
    pkg: CarEquipmentPackage = get_object_or_404(CarEquipmentPackage, pk=pk)
    if request.method == 'POST':
        form = CarEquipmentPackageForm(request.POST, instance=pkg)
        if form.is_valid():
            form.save()
            return redirect('package_list')
    else:
        form = CarEquipmentPackageForm(instance=pkg)
    return render(request, 'avto/package_form.html', {
        'form': form, 'title': 'Редактировать пакет', 'action': 'Сохранить',
    })


@login_required
def package_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Удаление привязки пакета оборудования. Только для авторизованных.

    Args:
        request: HTTP-запрос
        pk:      первичный ключ записи CarEquipmentPackage

    Returns:
        GET:  страница подтверждения удаления
        POST: редирект на package_list после удаления
    """
    pkg: CarEquipmentPackage = get_object_or_404(CarEquipmentPackage, pk=pk)
    if request.method == 'POST':
        pkg.delete()
        return redirect('package_list')
    return render(request, 'avto/package_confirm_delete.html', {'pkg': pkg})


@login_required
def order_list(request: HttpRequest) -> HttpResponse:
    """
    Список заказов текущего пользователя.

    Использует select_related и prefetch_related для оптимизации запросов.
    Пользователь видит только свои заказы.

    Args:
        request: HTTP-запрос

    Returns:
        HttpResponse с отрендеренным шаблоном avto/order_list.html
    """
    orders: QuerySet[Order] = (
        Order.objects
        .filter(user=request.user)
        .select_related('user')
        .prefetch_related('items__car')
        .order_by('-created_at')
    )
    return render(request, 'avto/order_list.html', {'orders': orders})


@login_required
def create_order(request: HttpRequest, car_id: int) -> HttpResponse:
    """
    Оформление заказа на автомобиль.

    После успешного создания заказа меняет статус автомобиля на BOOKING.

    Args:
        request: HTTP-запрос
        car_id:  ID автомобиля для заказа

    Returns:
        GET:  форма оформления заказа
        POST: редирект на order_list при успехе
    """
    car: Car = get_object_or_404(Car, id=car_id)
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order: Order = form.save(commit=False)
            order.user = request.user
            order.save()
            OrderItem.objects.create(order=order, car=car)
            car.status = Car.Status.BOOKING
            car.save()
            return HttpResponseRedirect(reverse('order_list'))
    else:
        form = OrderForm()
    return render(request, 'avto/create_order.html', {'car': car, 'form': form})


@login_required
def favorites(request: HttpRequest) -> HttpResponse:
    """
    Страница избранных автомобилей текущего пользователя.

    Args:
        request: HTTP-запрос

    Returns:
        HttpResponse с отрендеренным шаблоном avto/favorites.html
    """
    favs: QuerySet[Favorite] = (
        Favorite.objects
        .filter(user=request.user)
        .select_related('car')
    )
    return render(request, 'avto/favorites.html', {'favorites': favs})


@login_required
def toggle_favorite(request: HttpRequest, car_id: int) -> HttpResponse:
    """
    Переключение избранного: добавляет автомобиль в избранное или удаляет его оттуда.

    Использует get_or_create — если запись уже есть, удаляет её, если нет — создаёт.

    Args:
        request: HTTP-запрос
        car_id:  ID автомобиля

    Returns:
        Редирект на car_detail
    """
    car: Car = get_object_or_404(Car, id=car_id)
    fav, created = Favorite.objects.get_or_create(user=request.user, car=car)
    if not created:
        fav.delete()
    return redirect('car_detail', car_id=car_id)


def register_view(request: HttpRequest) -> HttpResponse:
    """
    Регистрация нового пользователя.

    После успешной регистрации автоматически выполняет вход и перенаправляет на car_list.

    Args:
        request: HTTP-запрос

    Returns:
        GET:  форма регистрации
        POST: редирект на car_list при успехе
    """
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('car_list')
    else:
        form = RegistrationForm()
    return render(request, 'avto/register.html', {'form': form})


def login_view(request: HttpRequest) -> HttpResponse:
    """
    Вход пользователя в систему.

    После успешного входа перенаправляет на car_list.

    Args:
        request: HTTP-запрос

    Returns:
        GET:  форма входа
        POST: редирект на car_list при успехе, форма с ошибкой при неудаче
    """
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('car_list')
    else:
        form = AuthenticationForm()
    return render(request, 'avto/login.html', {'form': form})


def logout_view(request: HttpRequest) -> HttpResponse:
    """
    Выход пользователя из системы.

    Args:
        request: HTTP-запрос

    Returns:
        Редирект на car_list
    """
    logout(request)
    return redirect('car_list')


@login_required
def order_pdf(request: HttpRequest, order_id: int) -> HttpResponse:
    """
    Генерация PDF-квитанции для заказа.

    Формирует PDF-документ с данными заказа, списком автомобилей и итоговой суммой.
    Использует библиотеку ReportLab и шрифт DejaVuSans для поддержки кириллицы.

    Args:
        request:  HTTP-запрос
        order_id: ID заказа для генерации PDF

    Returns:
        HttpResponse с PDF-файлом (Content-Type: application/pdf)
    """
    order: Order = get_object_or_404(Order, id=order_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'filename="order_{order.id}.pdf"'

    font_path: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'DejaVuSans.ttf'
    )
    pdfmetrics.registerFont(TTFont('DejaVu', font_path))

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()

    style_normal = ParagraphStyle('CustomNormal', fontName='DejaVu', fontSize=12, leading=20)
    style_title  = ParagraphStyle('CustomTitle',  fontName='DejaVu', fontSize=20, leading=30, spaceAfter=20)
    style_small  = ParagraphStyle('CustomSmall',  fontName='DejaVu', fontSize=10, leading=15, textColor=colors.grey)

    elements = []
    elements.append(Paragraph("АвтоСалон — Квитанция о бронировании", style_title))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph(f"Заказ № {order.id}", style_normal))
    elements.append(Paragraph(f"Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}", style_normal))
    elements.append(Paragraph(f"Логин: {order.user.username}", style_normal))

    full_name: str = f"{order.user.first_name} {order.user.last_name}".strip()
    if full_name:
        elements.append(Paragraph(f"ФИО: {full_name}", style_normal))

    elements.append(Paragraph(f"Статус: {order.get_status_display()}", style_normal))
    elements.append(Spacer(1, 0.5 * cm))
    elements.append(Paragraph("Забронированные автомобили:", style_normal))
    elements.append(Spacer(1, 0.3 * cm))

    table_data: list[list[str]] = [['Автомобиль', 'Год', 'Цена']]
    total: int = 0
    for item in order.items.select_related('car'):
        table_data.append([
            f"{item.car.brand} {item.car.model}",
            str(item.car.year),
            f"{item.car.price} руб.",
        ])
        total += item.car.price
    table_data.append(['', 'Итого:', f"{total} руб."])

    table = Table(table_data, colWidths=[10 * cm, 3 * cm, 5 * cm])
    table.setStyle(TableStyle([
        ('FONTNAME',    (0, 0),  (-1, -1), 'DejaVu'),
        ('FONTSIZE',    (0, 0),  (-1, -1), 11),
        ('BACKGROUND',  (0, 0),  (-1, 0),  colors.HexColor('#2c3e50')),
        ('TEXTCOLOR',   (0, 0),  (-1, 0),  colors.white),
        ('ALIGN',       (1, 0),  (-1, -1), 'CENTER'),
        ('GRID',        (0, 0),  (-1, -2), 0.5, colors.grey),
        ('FONTSIZE',    (0, -1), (-1, -1), 12),
        ('TEXTCOLOR',   (1, -1), (-1, -1), colors.HexColor('#2c3e50')),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph("Спасибо за выбор нашего автосалона!", style_normal))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph("Данный документ является подтверждением бронирования.", style_small))

    doc.build(elements)
    return response