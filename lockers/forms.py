from django import forms
from .models import Locker, Customer, LockerUser, AccessLog

_INPUT = 'vb-input'
_SELECT = 'vb-input'
_FILE = 'vb-input text-slate-400 file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer'
_CHECK = 'w-4 h-4 rounded accent-blue-500 cursor-pointer'


class LockerForm(forms.ModelForm):
    class Meta:
        model = Locker
        fields = ['locker_number', 'is_active']   # token is auto-generated
        widgets = {
            'locker_number': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'e.g. A-101'}),
            'is_active': forms.CheckboxInput(attrs={'class': _CHECK}),
        }


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'id_proof_type', 'id_proof_file']
        widgets = {
            'name': forms.TextInput(attrs={'class': _INPUT, 'placeholder': 'Full Name'}),
            'id_proof_type': forms.Select(attrs={'class': _SELECT}),
            'id_proof_file': forms.FileInput(attrs={'class': _FILE}),
        }


class LockerUserForm(forms.ModelForm):
    class Meta:
        model = LockerUser
        fields = ['customer']
        widgets = {
            'customer': forms.Select(attrs={'class': _SELECT}),
        }

    def __init__(self, locker=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if locker:
            # Exclude customers already linked to this locker
            existing_ids = LockerUser.objects.filter(locker=locker).values_list('customer_id', flat=True)
            self.fields['customer'].queryset = Customer.objects.exclude(id__in=existing_ids)
            self.locker = locker

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get('customer')
        locker = getattr(self, 'locker', None)
        if locker and customer:
            count = LockerUser.objects.filter(locker=locker).count()
            if count >= 3:
                raise forms.ValidationError(
                    f"Locker #{locker.locker_number} already has 3 customers (maximum allowed)."
                )
            if LockerUser.objects.filter(locker=locker, customer=customer).exists():
                raise forms.ValidationError(
                    f"{customer.name} is already assigned to this locker."
                )
        return cleaned_data


class ScanTokenForm(forms.Form):
    token = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': _INPUT,
            'placeholder': 'Scan or enter locker token...',
            'autofocus': True,
        })
    )


class CheckInForm(forms.Form):
    customer_id = forms.IntegerField(widget=forms.HiddenInput())
    locker_id = forms.IntegerField(widget=forms.HiddenInput())
