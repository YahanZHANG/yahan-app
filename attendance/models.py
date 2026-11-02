from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Participant(models.Model):
    name = models.CharField('名前', max_length=100)
    active = models.BooleanField('参加中', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name

    @property
    def balance(self):
        credits = self.payments.aggregate(v=Sum('credits'))['v'] or 0
        used = self.attendances.count()
        return credits - used

    @property
    def paid_total(self):
        return self.payments.aggregate(v=Sum('amount'))['v'] or 0


class Meeting(models.Model):
    date = models.DateField('活動日', unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    duty = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name='duty_meetings', verbose_name='当番')
    key_holder = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, blank=True, related_name='key_meetings', verbose_name='鍵当番')

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return str(self.date)


class Attendance(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='attendances')
    participant = models.ForeignKey(Participant, on_delete=models.PROTECT, related_name='attendances')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['meeting', 'participant'], name='unique_meeting_participant')]


class Payment(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.PROTECT, related_name='payments')
    paid_at = models.DateField('支払日')
    amount = models.DecimalField('金額 CHF', max_digits=8, decimal_places=2, default=32)
    credits = models.PositiveSmallIntegerField('追加回数', default=10)
    method = models.CharField('支払方法', max_length=16, choices=[('cash', '現金'), ('twint', 'TWINT'), ('bank', '銀行振込'), ('other', 'その他')], default='cash')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_at', '-id']


class Child(models.Model):
    parent = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='children', verbose_name='ママ')
    name = models.CharField('子どもの名前', max_length=100)
    birth_date = models.DateField('生年月日')

    class Meta:
        ordering = ['birth_date', 'id']

    def __str__(self):
        return self.name

    @property
    def age(self):
        today = timezone.localdate()
        years = today.year - self.birth_date.year - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        return max(0, years)

    @property
    def age_label(self):
        today = timezone.localdate()
        if self.birth_date > today:
            return '生年月日を確認'
        years = self.age
        months = (today.year - self.birth_date.year) * 12 + today.month - self.birth_date.month - (today.day < self.birth_date.day)
        if years == 0:
            return f'{months}か月'
        return f'{years}歳{months % 12}か月'

    @property
    def older_child(self):
        return self.age > 4


class CommitteeTerm(models.Model):
    start_date = models.DateField('任期開始')
    end_date = models.DateField('任期終了')
    officer1 = models.ForeignKey(Participant, on_delete=models.PROTECT, related_name='committee_terms_1', verbose_name='役員1')
    officer2 = models.ForeignKey(Participant, on_delete=models.PROTECT, related_name='committee_terms_2', verbose_name='役員2')

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.start_date}〜{self.end_date}'
