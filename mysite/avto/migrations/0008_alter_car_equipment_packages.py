from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('avto', '0007_alter_car_options_alter_order_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='car',
            name='equipment_packages',
        ),
        migrations.AddField(
            model_name='car',
            name='equipment_packages',
            field=models.ManyToManyField(
                blank=True,
                through='avto.CarEquipmentPackage',
                through_fields=('car', 'package'),
                to='avto.equipmentpackage',
                verbose_name='Пакеты оборудования',
            ),
        ),
    ]