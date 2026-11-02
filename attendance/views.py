import io
import secrets
from datetime import date, timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.http import require_http_methods, require_POST

from .forms import CodeForm, LoginForm, ParticipantForm, PaymentForm, ChildForm, CommitteeForm, DutyForm
from .models import Attendance, Meeting, Participant, Payment, Child, CommitteeTerm


def allowed(user):
    return user.is_authenticated and user.is_active and user.username == getattr(settings, 'ATTENDANCE_ADMIN_USERNAME', '')


def private(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not allowed(request.user) or not request.session.get('attendance_2fa'):
            return redirect('attendance:login')
        return view(request, *args, **kwargs)
    return wrapped


def code_digest(code):
    return salted_hmac('attendance-mail-otp', code).hexdigest()


@require_http_methods(['GET', 'POST'])
def sign_in(request):
    if allowed(request.user) and request.session.get('attendance_2fa'):
        return redirect('attendance:index')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        throttle = 'attendance-login:' + username
        if cache.get(throttle, 0) >= 5:
            messages.error(request, '試行回数が多すぎるため、15分後に再試行してね。')
        else:
            user = authenticate(request, username=username, password=form.cleaned_data['password'])
            if not user or not allowed(user) or not user.email:
                cache.set(throttle, cache.get(throttle, 0) + 1, timeout=900)
                messages.error(request, 'ログイン情報を確認してね。')
            else:
                code = f'{secrets.randbelow(1000000):06d}'
                # メール送信が失敗した場合、2FA待ち状態にしない
                send_mail('出欠管理 認証コード', f'認証コード: {code}\n5分以内に入力してね。', settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
                request.session['attendance_pending_id'] = user.pk
                request.session['attendance_code_digest'] = code_digest(code)
                request.session['attendance_code_at'] = timezone.now().timestamp()
                request.session['attendance_code_tries'] = 0
                request.session.pop('attendance_2fa', None)
                return redirect('attendance:verify')
    return render(request, 'attendance/form.html', {'title': '管理者ログイン', 'form': form, 'submit': 'メール認証へ'})


@require_http_methods(['GET', 'POST'])
def verify(request):
    pending_id = request.session.get('attendance_pending_id')
    started = request.session.get('attendance_code_at', 0)
    if not pending_id or timezone.now().timestamp() - started > 300 or request.session.get('attendance_code_tries', 0) >= 5:
        request.session.pop('attendance_pending_id', None)
        messages.error(request, '認証コードの期限が切れたよ。ログインし直してね。')
        return redirect('attendance:login')
    form = CodeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.session['attendance_code_tries'] += 1
        if constant_time_compare(code_digest(form.cleaned_data['code']), request.session.get('attendance_code_digest', '')):
            from django.contrib.auth import get_user_model
            user = get_object_or_404(get_user_model(), pk=pending_id)
            if allowed(user):
                login(request, user, backend='portal.backends.EmailOrUsernameBackend')
                request.session['attendance_2fa'] = True
                for k in ('attendance_pending_id', 'attendance_code_digest', 'attendance_code_at', 'attendance_code_tries'):
                    request.session.pop(k, None)
                return redirect('attendance:index')
        messages.error(request, '認証コードが違うよ。')
    return render(request, 'attendance/form.html', {'title': 'メール認証', 'form': form, 'submit': '認証する'})


@require_POST
def sign_out(request):
    logout(request)
    return redirect('attendance:login')


def next_friday():
    today = timezone.localdate()
    return today + timedelta(days=(4 - today.weekday()) % 7)


def assigned_officers(day):
    return CommitteeTerm.objects.select_related('officer1', 'officer2').filter(start_date__lte=day, end_date__gte=day).first()


def selected_day(request):
    try:
        return date.fromisoformat(request.GET.get('date') or request.POST.get('date') or next_friday().isoformat())
    except ValueError:
        return timezone.localdate()


@private
@require_http_methods(['GET', 'POST'])
def index(request):
    day = selected_day(request)
    if request.method == 'POST':
        ids = set(request.POST.getlist('present'))
        # 既存の休止メンバーの記録は保持し、活動中の人だけ更新
        active_ids = list(Participant.objects.filter(active=True).values_list('id', flat=True))
        with transaction.atomic():
            meeting, _ = Meeting.objects.get_or_create(date=day)
            Attendance.objects.filter(meeting=meeting, participant_id__in=active_ids).exclude(participant_id__in=[i for i in active_ids if str(i) in ids]).delete()
            existing = set(Attendance.objects.filter(meeting=meeting).values_list('participant_id', flat=True))
            Attendance.objects.bulk_create([Attendance(meeting=meeting, participant_id=i) for i in active_ids if str(i) in ids and i not in existing])
        messages.success(request, '出欠を保存したよ。')
        return redirect('attendance:index' + ('?date=' + day.isoformat()))
    people = list(Participant.objects.filter(active=True).prefetch_related('children'))
    meeting = Meeting.objects.select_related('duty', 'key_holder').filter(date=day).first()
    present_ids = set(meeting.attendances.values_list('participant_id', flat=True)) if meeting else set()
    for p in people:
        p.present_today = p.pk in present_ids
    term = assigned_officers(day)
    upcoming = Meeting.objects.filter(date__gte=timezone.localdate()).select_related('duty', 'key_holder').order_by('date')[:8]
    return render(request, 'attendance/index.html', {'people': people, 'day': day, 'meeting': meeting, 'term': term, 'upcoming': upcoming, 'today_count': len(present_ids), 'low_count': sum(p.balance <= 2 for p in people), 'is_friday': day.weekday() == 4})


@private
def people(request):
    return render(request, 'attendance/people.html', {'people': Participant.objects.prefetch_related('children').all()})


@private
@require_http_methods(['GET', 'POST'])
def add_person(request):
    form = ParticipantForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('attendance:people')
    return render(request, 'attendance/form.html', {'title': '参加者を追加', 'form': form, 'submit': '追加'})


@private
@require_http_methods(['GET', 'POST'])
def add_payment(request, pk):
    person = get_object_or_404(Participant, pk=pk)
    form = PaymentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        payment = form.save(commit=False)
        payment.participant = person
        payment.paid_at = timezone.localdate()
        payment.amount = 32
        payment.credits = 10
        payment.save()
        messages.success(request, f'{person.name}さんに10回追加したよ。')
        return redirect('attendance:people')
    return render(request, 'attendance/form.html', {'title': f'{person.name}：32 CHF入金・10回追加', 'form': form, 'submit': '入金確定'})


@private
@require_POST
def toggle_person(request, pk):
    person = get_object_or_404(Participant, pk=pk)
    person.active = not person.active
    person.save(update_fields=['active'])
    return redirect('attendance:people')




@private
@require_http_methods(['GET', 'POST'])
def add_child(request, pk):
    person = get_object_or_404(Participant, pk=pk)
    form = ChildForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        child = form.save(commit=False)
        child.parent = person
        child.save()
        messages.success(request, f'{child.name}を登録したよ。')
        return redirect('attendance:people')
    return render(request, 'attendance/form.html', {'title': f'{person.name}のお子さんを追加', 'form': form, 'submit': '子どもを登録'})


@private
@require_http_methods(['GET', 'POST'])
def edit_child(request, pk):
    child = get_object_or_404(Child, pk=pk)
    form = ChildForm(request.POST or None, instance=child)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('attendance:people')
    return render(request, 'attendance/form.html', {'title': f'{child.name}の情報を編集', 'form': form, 'submit': '変更を保存'})


@private
@require_http_methods(['GET', 'POST'])
def schedule(request):
    day = selected_day(request)
    meeting = Meeting.objects.filter(date=day).first()
    form = DutyForm(request.POST or None, initial={'duty': meeting.duty_id if meeting else None, 'key_holder': meeting.key_holder_id if meeting else None})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            meeting, _ = Meeting.objects.get_or_create(date=day)
            meeting.duty = form.cleaned_data['duty']
            meeting.key_holder = form.cleaned_data['key_holder']
            meeting.save(update_fields=['duty', 'key_holder'])
        messages.success(request, '当番・鍵当番を保存したよ。')
        return redirect('attendance:schedule' + '?date=' + day.isoformat())
    start = timezone.localdate() - timedelta(days=28)
    fridays = [start + timedelta(days=(4-start.weekday()) % 7) + timedelta(weeks=i) for i in range(31)]
    meetings = {m.date: m for m in Meeting.objects.filter(date__in=fridays).select_related('duty', 'key_holder')}
    rows = [{'day': d, 'meeting': meetings.get(d), 'term': assigned_officers(d)} for d in fridays]
    return render(request, 'attendance/schedule.html', {'form': form, 'day': day, 'rows': rows, 'term': assigned_officers(day)})


@private
@require_http_methods(['GET', 'POST'])
def add_committee(request):
    form = CommitteeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        term = form.save(commit=False)
        overlap = CommitteeTerm.objects.filter(start_date__lte=term.end_date, end_date__gte=term.start_date)
        if overlap.exists():
            form.add_error(None, '既存の役員任期と期間が重なっているよ。')
        else:
            term.save()
            messages.success(request, '半期の役員を登録したよ。')
            return redirect('attendance:committees')
    return render(request, 'attendance/form.html', {'title': '半期の役員を登録', 'form': form, 'submit': '役員を保存'})


@private
def committees(request):
    return render(request, 'attendance/committees.html', {'terms': CommitteeTerm.objects.select_related('officer1', 'officer2').all()})

@private
def history(request):
    return render(request, 'attendance/history.html', {'meetings': Meeting.objects.prefetch_related('attendances__participant').all()[:100], 'payments': Payment.objects.select_related('participant').all()[:100]})


def report_data():
    people = list(Participant.objects.all())
    meets = list(Meeting.objects.all().order_by('date'))
    attendance = list(Attendance.objects.select_related('participant', 'meeting').order_by('meeting__date', 'participant__name'))
    payments = list(Payment.objects.select_related('participant').order_by('paid_at', 'id'))
    return people, meets, attendance, payments


@private
def export_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    people, meets, attendance, payments = report_data()
    wb = Workbook()
    ws = wb.active
    ws.title = '参加者一覧'
    ws.append(['名前', '状態', '出席回数', '購入回数', '残回数', '支払合計 CHF'])
    for p in people:
        bought = sum(x.credits for x in payments if x.participant_id == p.id)
        count = sum(x.participant_id == p.id for x in attendance)
        ws.append([p.name, '参加中' if p.active else '休止', count, bought, bought-count, float(p.paid_total)])
    ws2 = wb.create_sheet('出欠履歴')
    ws2.append(['活動日', '名前', '出欠'])
    present_pairs = {(a.meeting_id, a.participant_id) for a in attendance}
    for m in meets:
        for p in people:
            ws2.append([str(m.date), p.name, '出席' if (m.id, p.id) in present_pairs else '欠席'])
    ws3 = wb.create_sheet('支払履歴')
    ws3.append(['支払日', '名前', '金額 CHF', '追加回数', '支払方法'])
    for p in payments:
        ws3.append([str(p.paid_at), p.participant.name, float(p.amount), p.credits, p.get_method_display()])
    ws4 = wb.create_sheet('子ども一覧')
    ws4.append(['ママ', '子どもの名前', '生年月日', '現在の年齢', '4歳超'])
    for child in Child.objects.select_related('parent').all():
        ws4.append([child.parent.name, child.name, str(child.birth_date), child.age_label, 'はい' if child.older_child else 'いいえ'])
    ws5 = wb.create_sheet('当番・鍵当番')
    ws5.append(['活動日', '当番', '鍵当番'])
    for m in Meeting.objects.select_related('duty', 'key_holder').order_by('date'):
        ws5.append([str(m.date), m.duty.name if m.duty else '未定', m.key_holder.name if m.key_holder else '未定'])
    ws6 = wb.create_sheet('半期役員')
    ws6.append(['開始日', '終了日', '役員1', '役員2'])
    for t in CommitteeTerm.objects.select_related('officer1', 'officer2'):
        ws6.append([str(t.start_date), str(t.end_date), t.officer1.name, t.officer2.name])
    for sheet in wb:
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='2563EB')
        for col in sheet.columns:
            letter = col[0].column_letter
            sheet.column_dimensions[letter].width = min(28, max(13, max(len(str(c.value or '')) for c in col) * 2))
    buf = io.BytesIO()
    wb.save(buf)
    response = HttpResponse(buf.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="attendance.xlsx"'
    return response


@private
def export_pdf(request):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    people, meets, attendance, payments = report_data()
    out = io.BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
    c = canvas.Canvas(out, pagesize=(595, 842))
    c.setFont('HeiseiKakuGo-W5', 17)
    c.drawString(40, 790, '出欠・参加費 管理レポート')
    c.setFont('HeiseiKakuGo-W5', 10)
    c.drawString(40, 760, f'作成日: {timezone.localdate()}')
    c.drawString(40, 731, '名前                  出席数   購入回数   残回数   支払合計')
    y = 705
    for p in people:
        if y < 65:
            c.showPage()
            c.setFont('HeiseiKakuGo-W5', 10)
            y = 790
        count = p.attendances.count()
        bought = sum(x.credits for x in p.payments.all())
        c.drawString(40, y, p.name[:13])
        c.drawRightString(315, y, str(count))
        c.drawRightString(388, y, str(bought))
        c.drawRightString(451, y, str(bought - count))
        c.drawRightString(555, y, f'{p.paid_total} CHF')
        y -= 25
    # 詳細データも続くページにまとめる
    for title, rows in [
        ('出欠履歴（出席記録）', [(str(a.meeting.date), a.participant.name, '出席') for a in attendance]),
        ('入金履歴', [(str(p.paid_at), p.participant.name, f'{p.amount} CHF / {p.credits}回 / {p.get_method_display()}') for p in payments]),
    ]:
        c.showPage()
        c.setFont('HeiseiKakuGo-W5', 15)
        c.drawString(40, 795, title)
        c.setFont('HeiseiKakuGo-W5', 10)
        y = 770
        for dt, name, detail in rows:
            if y < 50:
                c.showPage()
                c.setFont('HeiseiKakuGo-W5', 10)
                y = 790
            c.drawString(40, y, dt)
            c.drawString(140, y, name[:18])
            c.drawString(335, y, detail)
            y -= 19
    c.showPage()
    c.setFont('HeiseiKakuGo-W5', 15)
    c.drawString(40, 795, '子ども一覧')
    c.setFont('HeiseiKakuGo-W5', 10)
    y = 770
    for child in Child.objects.select_related('parent'):
        if y < 60:
            c.showPage(); c.setFont('HeiseiKakuGo-W5', 10); y = 790
        c.drawString(40, y, f'{child.parent.name} / {child.name} / {child.birth_date} / {child.age_label}')
        y -= 20
    c.showPage()
    c.setFont('HeiseiKakuGo-W5', 15)
    c.drawString(40, 795, '当番・鍵当番・役員')
    c.setFont('HeiseiKakuGo-W5', 10)
    y = 766
    for m in Meeting.objects.select_related('duty', 'key_holder').order_by('-date'):
        if y < 60:
            c.showPage(); c.setFont('HeiseiKakuGo-W5', 10); y = 790
        c.drawString(40, y, f'{m.date}  当番: {m.duty.name if m.duty else "未定"}  鍵: {m.key_holder.name if m.key_holder else "未定"}')
        y -= 20
    for t in CommitteeTerm.objects.select_related('officer1', 'officer2'):
        if y < 60:
            c.showPage(); c.setFont('HeiseiKakuGo-W5', 10); y = 790
        c.drawString(40, y, f'{t.start_date}〜{t.end_date}  役員: {t.officer1.name} / {t.officer2.name}')
        y -= 20
    c.save()
    response = HttpResponse(out.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="attendance.pdf"'
    return response
