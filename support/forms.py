from django import forms

from .models import Ticket


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["customer", "phone", "address", "description"]
        widgets = {
            "customer": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "e.g. Ali Khan"}),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel", "placeholder": "e.g. 0300 1234567"}),
            "address": forms.TextInput(attrs={"autocomplete": "street-address", "placeholder": "Building, street and area"}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell us what happened and when it started."}),
        }


class ModeForm(forms.Form):
    mode = forms.ChoiceField(choices=Ticket.Mode.choices, label="Service type")


class CompletionForm(forms.Form):
    resolution = forms.CharField(
        max_length=2000, label="Work performed", widget=forms.Textarea(attrs={"rows": 4})
    )


class HistoryFilter(forms.Form):
    employee = forms.CharField(max_length=150, required=False)
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
