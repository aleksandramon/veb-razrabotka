from django.contrib import admin
from django.db import models as db_models
from .models import *
from django.shortcuts import redirect
from import_export import resources, fields 
from import_export.admin import ExportMixin 
from import_export.widgets import ForeignKeyWidget

'''test'''
class CarResource(resources.ModelResource):
    class Meta:
        model = Car
        fields = ('id', 'brand', 'model', 'year', 'price', 'status', 'created_at')
        export_order = ('id', 'brand', 'model', 'year', 'price', 'status', 'created_at')


class OrderResource(resources.ModelResource):
    username = fields.Field(
        column_name='Покупатель',
        attribute='user',
        widget=ForeignKeyWidget(model=User, field='username')
    )

    class Meta:
        model = Order
        fields = ('id', 'username', 'status', 'created_at')
        export_order = ('id', 'username', 'status', 'created_at')

@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'password_preview', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('name', 'phone', 'email')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)
    list_display_links = ('name', 'email')
    list_per_page = 25
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'email', 'phone', 'password')
        }),
        ('Права и даты', {
            'fields': ('role', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Пароль (зашифрован)', empty_value='Не задан')
    def password_preview(self, obj):
        return f"••••{obj.password[-4:]}" if obj.password else "Не задан"
    
    def short_name(self, obj):
        return obj.name[:15] + "..." if len(obj.name) > 15 else obj.name
    short_name.short_description = 'Имя (кратко)'
    short_name.admin_order_field = 'name'



class CarImageInline(admin.TabularInline):
    model = CarImage
    extra = 1

@admin.register(Car)
class CarAdmin(ExportMixin, admin.ModelAdmin):
    resource_classes = [CarResource]
    list_display = ('brand', 'model', 'year', 'formatted_price', 'status', 'get_equipment_packages', 'created_at')
    list_filter = ('brand', 'year', 'status', 'equipment_packages')
    search_fields = ('brand', 'model', 'year')
    inlines = [CarImageInline]
    date_hierarchy = 'created_at'
    list_display_links = ('brand', 'model')
    readonly_fields = ('created_at',)
    list_per_page = 20
    
    fieldsets = (
        ('Основная информация об автомобиле', {
            'fields': ('brand', 'model', 'year', 'price', 'status')
        }),
        ('Документы и медиа', {
        'fields': ('document', 'video_url'),
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_equipment_packages(self, obj):
        packages = obj.equipment_packages.filter(is_active=True)
        if not packages:
            return "—"
        package_icons = {
            'WINTER': '❄️', 'SPORT': '🏎️', 'PREMIUM': '👑', 
            'FAMILY': '👨‍👩‍👧‍👦', 'SAFETY': '🛡️', 'TECH': '📱'
        }
        package_list = []
        for pkg in packages[:3]:
            icon = package_icons.get(pkg.package_type, '📦')
            package_list.append(f"{icon} {pkg.name}")
        result = ", ".join(package_list)
        if packages.count() > 3:
            result += f" +{packages.count() - 3}"
        return result
    get_equipment_packages.short_description = 'Пакеты оборудования'
    
    @admin.display(description='Цена (с учетом пакетов)', ordering='price')
    def formatted_price(self, obj):
        base_price = obj.price
        if base_price >= 1000000:
            base_formatted = f"{base_price/1000000:.1f} млн ₽"
        else:
            base_formatted = f"{base_price:,.0f} ₽".replace(',', ' ')
        
        if obj.equipment_packages.exists():
            min_package_price = obj.equipment_packages.aggregate(
                min_price=db_models.Min('additional_price')
            )['min_price']
            if min_package_price and min_package_price > 0:
                total_price = base_price + min_package_price
                if total_price >= 1000000:
                    total_formatted = f"{total_price/1000000:.1f} млн ₽"
                else:
                    total_formatted = f"{total_price:,.0f} ₽".replace(',', ' ')
                return f"{base_formatted} → {total_formatted}"
        return base_formatted
    
    actions = ['archive_old_cars', 'delete_archived_cars']

    @admin.action(description='Архивировать авто до 1990 года (update)')
    def archive_old_cars(self, request, queryset):
        updated = Car.objects.filter(
            year__lt=1990,
            status=Car.Status.SALE
        ).update(status=Car.Status.ARCHIVE)
        self.message_user(request, f'Архивировано {updated} автомобилей.')

    @admin.action(description='Удалить выбранные архивные авто (delete)')
    def delete_archived_cars(self, request, queryset):
        deleted_count, _ = queryset.filter(status=Car.Status.ARCHIVE).delete()
        self.message_user(request, f'Удалено {deleted_count} автомобилей.')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    raw_id_fields = ('car',)
    readonly_fields = ('id',)


@admin.register(Order)
class OrderAdmin(ExportMixin, admin.ModelAdmin):
    resource_classes = [OrderResource]
    list_display = ("id", "user", "status", "created_at")
    list_filter = ("status",)
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
    raw_id_fields = ("user",)
    list_display_links = ('id', 'user')
    search_fields = ('user__username', 'user__email', 'id')
    readonly_fields = ('created_at', 'id')
    list_per_page = 30
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('user', 'status')
        }),
        ('Даты', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    actions = ['download_pdf'] 

    @admin.action(description='Скачать PDF квитанцию')
    def download_pdf(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Выберите ровно один заказ для скачивания PDF.", level='error')
            return
        order = queryset.first()
        return redirect('order_pdf', order_id=order.id)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "description_preview")
    list_display_links = ('name',)
    search_fields = ("name", "description")
    list_filter = ("price",)
    readonly_fields = ('id',)
    list_per_page = 25
    
    @admin.display(description='Описание (кратко)')
    def description_preview(self, obj):
        if len(obj.description) > 60:
            return obj.description[:60] + "..."
        return obj.description


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "service", "date", "status")
    list_filter = ("status", "date")
    date_hierarchy = "date"
    raw_id_fields = ("user", "service")
    list_display_links = ('id',)
    search_fields = ('user__username', 'user__email', 'service__name')
    readonly_fields = ('id',)
    list_per_page = 25
    
    fieldsets = (
        ('Запись на услугу', {
            'fields': ('user', 'service', 'date', 'status')
        }),
    )


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "car", "added_at")
    raw_id_fields = ("user", "car")
    list_display_links = ('user', 'car')
    list_filter = ("added_at",)
    search_fields = ('user__username', 'user__email', 'car__brand', 'car__model')
    readonly_fields = ('added_at',)
    list_per_page = 30


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user", "car", "rating", "comment_preview", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comment", "user__username", "car__brand", "car__model")
    raw_id_fields = ("user", "car")
    list_display_links = ('user', 'car')
    date_hierarchy = "created_at"
    readonly_fields = ('created_at',)
    list_per_page = 30

    @admin.display(description='Комментарий (кратко)')
    def comment_preview(self, obj):
        if len(obj.comment) > 60:
            return obj.comment[:60] + "..."
        return obj.comment


@admin.register(EquipmentPackage)
class EquipmentPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'package_type', 'additional_price', 'is_active', 'cars_count', 'created_at')
    list_filter = ('package_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    list_display_links = ('name',)
    list_editable = ('is_active', 'additional_price')
    readonly_fields = ('created_at',)
    list_per_page = 20
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'package_type', 'description', 'additional_price')
        }),
        ('Статус', {
            'fields': ('is_active', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def cars_count(self, obj):
        """Количество автомобилей с этим пакетом"""
        count = obj.package_cars.count()
        if count == 0:
            return "—"
        return f"{count} авто"
    cars_count.short_description = 'Автомобилей'
    cars_count.admin_order_field = 'package_cars__count'
    
    actions = ['activate_packages', 'deactivate_packages']
    
    @admin.action(description='Активировать выбранные пакеты')
    def activate_packages(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'✅ Активировано {updated} пакетов')
    
    @admin.action(description='Деактивировать выбранные пакеты')
    def deactivate_packages(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'❌ Деактивировано {updated} пакетов')


@admin.register(CarEquipmentPackage)
class CarEquipmentPackageAdmin(admin.ModelAdmin):
    list_display = ('car', 'package', 'status', 'installed_at')
    list_filter = ('status', 'package__package_type', 'installed_at')
    search_fields = ('car__brand', 'car__model', 'package__name')
    raw_id_fields = ('car', 'package')
    list_display_links = ('car', 'package')
    date_hierarchy = 'installed_at'
    list_per_page = 25
    
    fieldsets = (
        ('Связь автомобиля с пакетом', {
            'fields': ('car', 'package')
        }),
        ('Статус установки', {
            'fields': ('status', 'installed_at', 'notes')
        }),
    )

@admin.register(CarImage)
class CarImageAdmin(admin.ModelAdmin):
    list_display = ('car', 'image', 'uploaded_at')
    list_display_links = ('car',)
    raw_id_fields = ('car',)
    readonly_fields = ('uploaded_at',)
