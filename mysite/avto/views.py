from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Sum, Avg, Min, Max
from django.utils import timezone
from django.http import HttpResponse
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
from .forms import CarForm, ServiceForm, ReviewForm, CarEquipmentPackageForm, RegistrationForm, OrderForm


def home(request):

    q_brand = request.GET.get('q_brand', '').strip()
    q_model = request.GET.get('q_model', '').strip()
    q_max_price = request.GET.get('q_max_price', '').strip()
    q_sort = request.GET.get('q_sort', '-created_at')
    search_performed = any([q_brand, q_model, q_max_price])

    search_results = []
    if search_performed:
        qs = Car.objects.exclude(status='AR')
        if q_brand:
            qs = qs.filter(brand__icontains=q_brand)
        if q_model:
            qs = qs.filter(model__icontains=q_model)
        if q_max_price and q_max_price.isdigit():
            qs = qs.filter(price__lte=int(q_max_price))
        sort_map = {
            'price': 'price', '-price': '-price',
            'year': 'year', '-created_at': '-created_at',
        }
        qs = qs.order_by(sort_map.get(q_sort, '-created_at'))
        search_results = list(qs[:20])

    top_cars = (
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

    services = Service.objects.all().order_by('price')[:6]

    latest_reviews = (
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

    fav_cars = (
        Car.objects
        .filter(status='SL')
        .annotate(fav_count=Count('favorited_by'))
        .filter(fav_count__gt=0)
        .order_by('-fav_count')
        .prefetch_related('images')[:5]
    )

    newest_cars = (
        Car.objects
        .filter(status='SL')
        .order_by('-created_at')
        .prefetch_related('images')[:8]
    )

    stats = {
        'total_cars': Car.objects.filter(status='SL').count(),
        'total_services': Service.objects.count(),
        'total_reviews': Review.objects.count(),
        'avg_rating': Review.objects.aggregate(a=Avg('rating'))['a'] or 0,
        'avg_service_price': Service.objects.aggregate(a=Avg('price'))['a'] or 0,
    }

    all_brands = Car.objects.values_list('brand', flat=True).distinct().order_by('brand')

    return render(request, 'avto/home.html', {
        'q_brand': q_brand,
        'q_model': q_model,
        'q_max_price': q_max_price,
        'q_sort': q_sort,
        'search_performed': search_performed,
        'search_results': search_results,
        'top_cars': top_cars,
        'services': services,
        'latest_reviews': latest_reviews,
        'package_stats': package_stats,
        'newest_cars': newest_cars,
        'fav_cars': fav_cars,
        'stats': stats,
        'all_brands': all_brands,
    })


def car_list(request):
    cars = Car.objects.all()
    brand_filter = request.GET.get('brand', '')
    if brand_filter:
        cars = cars.filter(brand__icontains=brand_filter)
    model_filter = request.GET.get('model', '')
    if model_filter:
        cars = cars.filter(model__contains=model_filter)
    min_price = request.GET.get('min_price', '')
    if min_price and min_price.isdigit():
        cars = cars.filter(price__gte=int(min_price))
    max_price = request.GET.get('max_price', '')
    if max_price and max_price.isdigit():
        cars = cars.filter(price__lte=int(max_price))
    cars = cars.exclude(status='AR').exclude(status='BK')

    sort = request.GET.get('sort', '-created_at')
    sort_map = {
        'price': 'price', '-price': '-price',
        'brand': 'brand', 'year': '-year',
    }
    cars = cars.order_by(sort_map.get(sort, '-created_at'))

    cars = cars.prefetch_related('equipment_packages', 'car_packages__package', 'images')

    total_count = cars.count()

    has_results = cars.exists()

    all_brands = Car.objects.values_list('brand', flat=True).distinct().order_by('brand')

    price_data = cars.values('brand').annotate(
        avg_price=Avg('price'),
        count=Count('id')
    ).order_by('-count')[:5]

    stats = cars.aggregate(
        total=Count('id'),
        avg_price=Avg('price'),
        min_price=Min('price'),
        max_price=Max('price'),
    )
    cars_limited = Car.objects.order_by('-created_at')[:5]
    paginator = Paginator(cars, 6)
    page = request.GET.get('page', 1)
    try:
        cars_page = paginator.page(page)
    except PageNotAnInteger:
        cars_page = paginator.page(1)
    except EmptyPage:
        cars_page = paginator.page(paginator.num_pages)

    return render(request, 'avto/car_list.html', {
        'cars': cars_page,
        'stats': stats,
        'brand_filter': brand_filter,
        'model_filter': model_filter,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
        'total_count': total_count,
        'has_results': has_results,
        'all_brands': all_brands,
        'price_data': price_data,
        'cars_limited': cars_limited,
    })


def car_detail(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    history = request.session.get('viewed_cars', [])
    if car_id not in history:
        history.append(car_id)
    request.session['viewed_cars'] = history[-5:]

    reviews = car.reviews.select_related('user').order_by('-created_at')

    active_packages = car.car_packages.prefetch_related('package').filter(
        status='AVAILABLE'
    )

    viewed_cars = Car.objects.filter(
        id__in=request.session['viewed_cars']
    ).exclude(id=car_id)

    return render(request, 'avto/car_detail.html', {
        'car': car,
        'reviews': reviews,
        'active_packages': active_packages,
        'viewed_cars': viewed_cars,
    })

@login_required
def car_create(request):
    if request.method == 'POST':
        form = CarForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('car_list')
    else:
        form = CarForm()
    return render(request, 'avto/car_form.html', {
        'form': form, 'title': 'Добавить автомобиль', 'action': 'Создать'
    })


@login_required
def car_edit(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    if request.method == 'POST':
        form = CarForm(request.POST, request.FILES, instance=car)
        if form.is_valid():
            form.save()
            return redirect('car_detail', car_id=car.id)
    else:
        form = CarForm(instance=car)
    return render(request, 'avto/car_form.html', {
        'form': form, 'title': f'Редактировать: {car}', 'action': 'Сохранить', 'car': car
    })

@login_required
def car_delete(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    if request.method == 'POST':
        car.delete()
        return redirect('car_list')
    return render(request, 'avto/car_confirm_delete.html', {'car': car})


def service_list(request):
    services = Service.objects.order_by('price')
    return render(request, 'avto/service_list.html', {'services': services})


@login_required
def service_create(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('service_list')
    else:
        form = ServiceForm()
    return render(request, 'avto/service_form.html', {
        'form': form, 'title': 'Новая услуга', 'action': 'Создать'
    })


@login_required
def service_edit(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('service_list')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'avto/service_form.html', {
        'form': form, 'title': f'Редактировать: {service.name}', 'action': 'Сохранить'
    })


@login_required
def service_delete(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        service.delete()
        return redirect('service_list')
    return render(request, 'avto/service_confirm_delete.html', {'service': service})


@login_required
def book_service(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        ServiceOrder.objects.create(user=request.user, service=service, date=timezone.now())
        return redirect('service_list')
    return render(request, 'avto/book_service.html', {'service': service})


@login_required
def add_review(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.car  = car
            review.save()
            return redirect('car_detail', car_id=car_id)
    else:
        form = ReviewForm()
    return render(request, 'avto/add_review.html', {'car': car, 'form': form})


def package_list(request):
    packages = CarEquipmentPackage.objects.select_related('car', 'package').order_by('car__brand')
    return render(request, 'avto/package_list.html', {'packages': packages})


@login_required
def package_create(request):
    if request.method == 'POST':
        form = CarEquipmentPackageForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('package_list')
    else:
        form = CarEquipmentPackageForm()
    return render(request, 'avto/package_form.html', {
        'form': form, 'title': 'Добавить пакет к автомобилю', 'action': 'Создать'
    })


@login_required
def package_edit(request, pk):
    pkg = get_object_or_404(CarEquipmentPackage, pk=pk)
    if request.method == 'POST':
        form = CarEquipmentPackageForm(request.POST, instance=pkg)
        if form.is_valid():
            form.save()
            return redirect('package_list')
    else:
        form = CarEquipmentPackageForm(instance=pkg)
    return render(request, 'avto/package_form.html', {
        'form': form, 'title': 'Редактировать пакет', 'action': 'Сохранить'
    })


@login_required
def package_delete(request, pk):
    pkg = get_object_or_404(CarEquipmentPackage, pk=pk)
    if request.method == 'POST':
        pkg.delete()
        return redirect('package_list')
    return render(request, 'avto/package_confirm_delete.html', {'pkg': pkg})



@login_required
def order_list(request):
    orders = (Order.objects
              .filter(user=request.user)
              .select_related('user')
              .prefetch_related('items__car')
              .order_by('-created_at'))
    return render(request, 'avto/order_list.html', {'orders': orders})


@login_required
def create_order(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
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
def favorites(request):
    favs = Favorite.objects.filter(user=request.user).select_related('car')
    return render(request, 'avto/favorites.html', {'favorites': favs})


@login_required
def toggle_favorite(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    fav, created = Favorite.objects.get_or_create(user=request.user, car=car)
    if not created:
        fav.delete()
    return redirect('car_detail', car_id=car_id)



def register_view(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save() 
            login(request, user)
            return redirect('car_list')
    else:
        form = RegistrationForm()
    return render(request, 'avto/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('car_list')
    else:
        form = AuthenticationForm()
    return render(request, 'avto/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('car_list')


@login_required
def order_pdf(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'filename="order_{order.id}.pdf"'

    font_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'DejaVuSans.ttf')
    pdfmetrics.registerFont(TTFont('DejaVu', font_path))

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()

    style_normal = ParagraphStyle(
        'CustomNormal',
        fontName='DejaVu',
        fontSize=12,
        leading=20,
    )
    style_title = ParagraphStyle(
        'CustomTitle',
        fontName='DejaVu',
        fontSize=20,
        leading=30,
        spaceAfter=20,
    )
    style_small = ParagraphStyle(
        'CustomSmall',
        fontName='DejaVu',
        fontSize=10,
        leading=15,
        textColor=colors.grey,
    )

    elements = []

    elements.append(Paragraph("АвтоСалон — Квитанция о бронировании", style_title))
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph(f"Заказ № {order.id}", style_normal))
    elements.append(Paragraph(f"Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}", style_normal))
    elements.append(Paragraph(f"Логин: {order.user.username}", style_normal))
    full_name = f"{order.user.first_name} {order.user.last_name}".strip()
    if full_name:
        elements.append(Paragraph(f"ФИО: {full_name}", style_normal))
    elements.append(Paragraph(f"Статус: {order.get_status_display()}", style_normal))
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("Забронированные автомобили:", style_normal))
    elements.append(Spacer(1, 0.3 * cm))

    table_data = [['Автомобиль', 'Год', 'Цена']]
    total = 0
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
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVu'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('FONTNAME', (0, -1), (-1, -1), 'DejaVu'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (1, -1), (-1, -1), colors.HexColor('#2c3e50')),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph("Спасибо за выбор нашего автосалона!", style_normal))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(Paragraph("Данный документ является подтверждением бронирования.", style_small))

    doc.build(elements)
    return response