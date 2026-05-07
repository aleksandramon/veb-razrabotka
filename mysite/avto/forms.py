from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Car, Service, Review, CarEquipmentPackage, Order

class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = ['brand', 'model', 'year', 'price', 'status', 'document', 'video_url']
        widgets = {
            'brand': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Toyota',
            }),
            'model': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: Camry',
            }),
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1900,
                'max': 2025,
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'video_url': forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://youtube.com/...',
            }),
            'document': forms.ClearableFileInput(attrs={
            'class': 'form-control',
            }),
        }
        labels = {
            'brand': 'Марка автомобиля',
            'model': 'Модель',
            'year':  'Год выпуска',
            'price': 'Цена (руб.)',
            'status': 'Статус',
        }

        help_texts = {
            'year': 'Укажите год выпуска от 1900 до 2025',
            'video_url': 'Ссылка на YouTube или другой видеохостинг',
        }
        error_messages = {
            'brand': {'required': 'Пожалуйста, укажите марку автомобиля.'},
            'price': {'required': 'Укажите цену автомобиля.'},
        }

    def clean_year(self):
        year = self.cleaned_data.get('year')
        if year is None:
            raise forms.ValidationError("Укажите год выпуска.")
        if year < 1900 or year > 2025:
            raise forms.ValidationError("Год должен быть в диапазоне от 1900 до 2025.")
        return year

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price <= 0:
            raise forms.ValidationError("Цена должна быть больше нуля.")
        return price
    
    class Media:
        css = {
            'all': ('https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',)
        }
        js = ('https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',)


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['name', 'description', 'price']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название услуги',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание услуги',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
            }),
        }
    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise forms.ValidationError("Цена услуги не может быть отрицательной.")
        return price

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if len(name) < 3:
            raise forms.ValidationError("Название услуги должно быть не короче 3 символов.")
        return name


class ReviewForm(forms.ModelForm):

    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(
                choices=[(i, f"{i} звезд{'а' if i == 1 else 'ы' if 2 <= i <= 4 else ''}") for i in range(1, 6)],
                attrs={'class': 'form-select'},
            ),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Ваш отзыв...',
            }),
        }

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is not None and not (1 <= rating <= 5):
            raise forms.ValidationError("Оценка должна быть от 1 до 5.")
        return rating

    def clean_comment(self):
        comment = self.cleaned_data.get('comment', '').strip()
        if len(comment) < 10:
            raise forms.ValidationError("Комментарий должен содержать не менее 10 символов.")
        return comment


class CarEquipmentPackageForm(forms.ModelForm):

    class Meta:
        model = CarEquipmentPackage
        fields = ['car', 'package', 'status', 'installed_at', 'notes']
        widgets = {
            'car':     forms.Select(attrs={'class': 'form-select'}),
            'package': forms.Select(attrs={'class': 'form-select'}),
            'status':  forms.Select(attrs={'class': 'form-select'}),
            'installed_at': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label='Email',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()  
        return user
    
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
        }