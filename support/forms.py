from io import BytesIO

from django import forms
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Ticket


class ComplaintForm(forms.ModelForm):
    photo = forms.FileField(
        required=False,
        label="Photo or screenshot (optional)",
        help_text="JPEG, PNG or WebP, up to 5 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )

    def clean_photo(self):
        upload = self.cleaned_data["photo"]
        if not upload:
            return None
        if upload.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Choose a photo that is 5 MB or smaller.")

        try:
            with Image.open(upload, formats=("JPEG", "PNG", "WEBP")) as source:
                if source.width * source.height > 25_000_000:
                    raise forms.ValidationError("Choose a photo with fewer than 25 megapixels.")
                source.load()
                photo = ImageOps.exif_transpose(source).convert("RGB")
                photo.thumbnail((2400, 2400))
                result = BytesIO()
                photo.save(result, format="JPEG", quality=88)
                return result.getvalue()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
            raise forms.ValidationError("Upload a valid JPEG, PNG or WebP image.") from None

    class Meta:
        model = Ticket
        fields = ["customer", "phone", "address", "description", "photo"]
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
