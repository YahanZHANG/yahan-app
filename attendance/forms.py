from django import forms
from .models import Participant, Payment, Child, CommitteeTerm, Meeting

class LoginForm(forms.Form):
    username = forms.CharField(label='ID', max_length=150)
    password = forms.CharField(label='パスワード', widget=forms.PasswordInput)

class CodeForm(forms.Form):
    code = forms.CharField(label='メールで届いた6桁コード', min_length=6, max_length=6, widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}))

class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['name']

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['method']


class ChildForm(forms.ModelForm):
    class Meta:
        model = Child
        fields = ['name', 'birth_date']
        widgets = {'birth_date': forms.DateInput(attrs={'type': 'date'})}


class CommitteeForm(forms.ModelForm):
    class Meta:
        model = CommitteeTerm
        fields = ['start_date', 'end_date', 'officer1', 'officer2']
        widgets = {'start_date': forms.DateInput(attrs={'type': 'date'}), 'end_date': forms.DateInput(attrs={'type': 'date'})}

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('start_date') and cleaned.get('end_date') and cleaned['end_date'] < cleaned['start_date']:
            raise forms.ValidationError('終了日は開始日以降にしてね。')
        if cleaned.get('officer1') and cleaned.get('officer1') == cleaned.get('officer2'):
            raise forms.ValidationError('役員は異なる2人を選んでね。')
        return cleaned


class DutyForm(forms.Form):
    duty = forms.ModelChoiceField(queryset=Participant.objects.none(), label='今週の当番', required=False, empty_label='未定')
    key_holder = forms.ModelChoiceField(queryset=Participant.objects.none(), label='鍵当番', required=False, empty_label='未定')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Participant.objects.filter(active=True)
        self.fields['duty'].queryset = qs
        self.fields['key_holder'].queryset = qs
