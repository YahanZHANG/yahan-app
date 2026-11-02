from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('attendance', '0001_initial')]

    operations = [
        migrations.AddField(
            model_name='meeting', name='duty',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='duty_meetings', to='attendance.participant', verbose_name='当番'),
        ),
        migrations.AddField(
            model_name='meeting', name='key_holder',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='key_meetings', to='attendance.participant', verbose_name='鍵当番'),
        ),
        migrations.CreateModel(
            name='Child',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='子どもの名前')),
                ('birth_date', models.DateField(verbose_name='生年月日')),
                ('parent', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='children', to='attendance.participant', verbose_name='ママ')),
            ],
            options={'ordering': ['birth_date', 'id']},
        ),
        migrations.CreateModel(
            name='CommitteeTerm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField(verbose_name='任期開始')),
                ('end_date', models.DateField(verbose_name='任期終了')),
                ('officer1', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='committee_terms_1', to='attendance.participant', verbose_name='役員1')),
                ('officer2', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='committee_terms_2', to='attendance.participant', verbose_name='役員2')),
            ],
            options={'ordering': ['-start_date']},
        ),
    ]
