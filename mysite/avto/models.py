from django.db import models
from django.utils import timezone                       
from django.contrib.auth.models import User
from django.urls import reverse   
from simple_history.models import HistoricalRecords                        

class CarManager(models.Manager):
    def for_sale(self):
        return self.filter(status='SL')
    def by_brand(self, brand_name):
        return self.filter(brand__icontains=brand_name)   
    def with_active_packages(self):
        return self.filter(equipment_packages__is_active=True).distinct()


class Users(models.Model):
    class Role(models.TextChoices):                       
        ADMIN = "ADMIN", 'Admin'
        USER = "USER", 'User'

    name = models.CharField(max_length=100, verbose_name="Имя")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    password = models.CharField(max_length=255, verbose_name="Пароль")
    role = models.CharField(
        max_length=5,
        choices=Role.choices,                            
        default=Role.USER,
        verbose_name="Роль",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")

    def __str__(self):                                     
        return f"{self.name} ({self.email})"

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ['-created_at']                        


class EquipmentPackage(models.Model):
    class PackageType(models.TextChoices):                
        WINTER  = 'WINTER',  '❄️ Зимний пакет'
        SPORT   = 'SPORT',   '🏎️ Спортивный пакет'
        PREMIUM = 'PREMIUM', '👑 Премиум пакет'
        FAMILY  = 'FAMILY',  '👨‍👩‍👧‍👦 Семейный пакет'
        SAFETY  = 'SAFETY',  '🛡️ Пакет безопасности'
        TECH    = 'TECH',    '📱 Технологический пакет'

    name             = models.CharField(max_length=100, verbose_name="Название пакета")
    package_type     = models.CharField(max_length=20, choices=PackageType.choices, verbose_name="Тип пакета")
    description      = models.TextField(verbose_name="Описание пакета", help_text="Что входит в пакет")
    additional_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Доплата за пакет (₽)")
    is_active        = models.BooleanField(default=True, verbose_name="Активен")
    created_at       = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    history = HistoricalRecords()

    def __str__(self):                                     
        return f"{self.get_package_type_display()} — {self.name} (+{self.additional_price:,.0f} ₽)"

    class Meta:
        verbose_name = "Пакет оборудования"
        verbose_name_plural = "Пакеты оборудования"
        ordering = ['package_type', 'additional_price']    


class Car(models.Model):
    class Status(models.TextChoices):                     
        SALE    = 'SL', 'Продаётся'
        BOOKING = 'BK', 'Забронирована'
        ARCHIVE = 'AR', 'В архиве'

    brand  = models.CharField(max_length=100, verbose_name="Марка")
    model  = models.CharField(max_length=100, verbose_name="Модель")
    year   = models.IntegerField(verbose_name="Год")
    price  = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    status = models.CharField(
        max_length=15,
        choices=Status.choices,                         
        default=Status.SALE,
        verbose_name="Статус",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    equipment_packages = models.ManyToManyField(
        EquipmentPackage,
        through='CarEquipmentPackage',
        through_fields=('car', 'package'),
        blank=True,
        verbose_name="Пакеты оборудования",
    )
    history = HistoricalRecords() 
    objects = CarManager()

    document = models.FileField(
        upload_to='car_documents/',
        null=True,
        blank=True,
        verbose_name="Документ на автомобиль",
        help_text="ПТС, сервисная книжка или другой документ"
    )

    video_url = models.URLField(
        null=True,
        blank=True,
        verbose_name="Ссылка на видеообзор",
        help_text="Ссылка на YouTube или другой видеохостинг"
    )

    def __str__(self):                                  
        return f"{self.brand} {self.model} ({self.year})"

    def get_absolute_url(self):
        return reverse('car_detail', kwargs={'car_id': self.id})
    
    def save(self, *args, **kwargs):
        if self.pk:
            old = Car.objects.get(pk=self.pk)
            if old.status != self.status:
                now = timezone.now().strftime("%d.%m.%Y %H:%M")
                print(f"[LOG] {now} | {self} — статус: {old.get_status_display()} → {self.get_status_display()}")
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Автомобиль"
        verbose_name_plural = "Автомобили"
        ordering = ['-created_at']                        



class CarImage(models.Model):
    car        = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='images',                          
        verbose_name="Автомобиль",
    )
    image      = models.ImageField(upload_to='cars/', verbose_name="Изображение")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")

    def __str__(self):                                     
        return f"Изображение {self.car}"

    class Meta:
        verbose_name = "Изображение"
        verbose_name_plural = "Изображения"


class Order(models.Model):
    class Status(models.TextChoices):                      
        CANCEL  = 'CN', 'Отказ'
        BOOKING = 'BK', 'Бронь'
        ARCHIVE = 'AR', 'В архиве'

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders', 
        verbose_name="Пользователь",
    )
    status = models.CharField(
        max_length=8,
        choices=Status.choices, 
        default=Status.BOOKING,
        verbose_name="Статус",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата")

    history = HistoricalRecords()

    def __str__(self):                                  
        return f"Заказ #{self.id}"

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']                      


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',                             
        verbose_name="Заказ",
    )
    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='order_items',                     
        verbose_name="Автомобиль",
    )

    def __str__(self):                                     
        return f"{self.order} — {self.car}"

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказов"



class Service(models.Model):
    name        = models.CharField(max_length=150, verbose_name="Название")
    description = models.TextField(verbose_name="Описание")
    price       = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    stock = models.PositiveIntegerField(default=10, verbose_name='Свободные места')

    def __str__(self):              
        return self.name

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ['name']                      


class ServiceOrder(models.Model):
    class Status(models.TextChoices):                  
        BOOKING = 'BK', 'Бронь'
        ARCHIVE = 'AR', 'В архиве'

    user    = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='service_orders',                  
        verbose_name="Пользователь",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='orders',                             
        verbose_name="Услуга",
    )

    date   = models.DateTimeField(verbose_name="Дата")
    status = models.CharField(
        max_length=8,
        choices=Status.choices,                          
        default=Status.BOOKING,
        verbose_name="Статус",
    )

    def __str__(self):                                     
        return f"{self.user} — {self.service}"

    class Meta:
        verbose_name = "Запись на услугу"
        verbose_name_plural = "Записи на услуги"


class Favorite(models.Model):
    user     = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorites',                          
        verbose_name="Пользователь",
    )
    car      = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='favorited_by',                      
        verbose_name="Автомобиль",
    )
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    def __str__(self):                                    
        return f"{self.user} ❤️ {self.car}"

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"

class Review(models.Model):
    user       = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews',                           
        verbose_name="Пользователь",
    )
    car        = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='reviews',                           
        verbose_name="Автомобиль",
    )
    rating     = models.IntegerField(verbose_name="Оценка")
    comment    = models.TextField(verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата")

    def __str__(self):                                     
        return f"Отзыв {self.user} — {self.car} ({self.rating}★)"

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ['-created_at']                       


class CarEquipmentPackage(models.Model):
    class InstallationStatus(models.TextChoices):          
        AVAILABLE   = 'AVAILABLE',   'Доступен для заказа'
        INSTALLED   = 'INSTALLED',   'Установлен'
        PLANNED     = 'PLANNED',     'Запланирован'
        UNAVAILABLE = 'UNAVAILABLE', 'Недоступен'

    car = models.ForeignKey(
        Car,
        on_delete=models.CASCADE,
        related_name='car_packages',                     
        verbose_name="Автомобиль",
    )
    package  = models.ForeignKey(
        EquipmentPackage,
        on_delete=models.CASCADE,
        related_name='package_cars',                      
        verbose_name="Пакет оборудования",
    )
    status = models.CharField(
        max_length=20,
        choices=InstallationStatus.choices,
        default=InstallationStatus.AVAILABLE,
        verbose_name="Статус установки",
    )
    
    installed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата установки")
    notes        = models.TextField(blank=True, verbose_name="Примечания")

    def __str__(self):                                   
        return f"{self.car} — {self.package} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Пакет на автомобиле"
        verbose_name_plural = "Пакеты на автомобилях"
        unique_together = ['car', 'package']
