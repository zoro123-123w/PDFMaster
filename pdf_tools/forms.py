from django import forms


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single_file_clean = super().clean

        if isinstance(data, (list, tuple)):
            result = [single_file_clean(file, initial) for file in data]
        else:
            result = [single_file_clean(data, initial)]

        return result


class PDFUploadForm(forms.Form):
    files = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'file-input',
            'accept': 'application/pdf'
        }),
        required=False
    )


class SinglePDFUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'file-input',
            'accept': 'application/pdf'
        }),
        required=True
    )


class ImageUploadForm(forms.Form):
    files = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'file-input',
            'accept': 'image/*'
        }),
        required=True
    )


class PageRangeForm(forms.Form):
    pages = forms.CharField(
        max_length=500,
        help_text="e.g., 1-3, 5, 7-10",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '1-3, 5, 7-10'
        })
    )


class RotationForm(forms.Form):
    angle = forms.ChoiceField(
        choices=[
            (90, '90°'),
            (180, '180°'),
            (270, '270°')
        ],
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )