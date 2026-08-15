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


# ---------------------------------------------------------------------------
# Extended tool forms (conversion / editing / security / OCR / e-signature)
# ---------------------------------------------------------------------------

class WordUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': '.docx'}),
        required=True,
        help_text='Word documents (.docx)'
    )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and not file.name.lower().endswith('.docx'):
            raise forms.ValidationError('Please upload a .docx file.')
        return file


class ExcelUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': '.xlsx'}),
        required=True
    )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and not file.name.lower().endswith('.xlsx'):
            raise forms.ValidationError('Please upload an .xlsx file.')
        return file


class PowerPointUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': '.pptx'}),
        required=True
    )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and not file.name.lower().endswith('.pptx'):
            raise forms.ValidationError('Please upload a .pptx file.')
        return file


class HTMLUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': '.html,.htm'}),
        required=True
    )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and not (file.name.lower().endswith('.html') or file.name.lower().endswith('.htm')):
            raise forms.ValidationError('Please upload an .html file.')
        return file


class TextFileUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': '.txt'}),
        required=True
    )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and not file.name.lower().endswith('.txt'):
            raise forms.ValidationError('Please upload a .txt file.')
        return file


class PasswordForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'PDF password'}),
        required=True,
        label='Password',
        help_text='The password used to protect the PDF.'
    )


class ProtectForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Choose a password'}),
        required=True,
        label='Password (minimum 4 characters)',
        help_text='Strong passwords are recommended. You will need it to unlock the PDF.'
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Repeat password'}),
        required=True,
        label='Confirm password'
    )

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('confirm_password')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm_password', 'Passwords do not match.')
        if p1 and len(p1) < 4:
            self.add_error('password', 'Password must be at least 4 characters.')
        return cleaned


class RedactForm(forms.Form):
    words = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. secret, confidential, private-key'
        }),
        required=True,
        label='Words/phrases to redact',
        help_text='Comma separated. Matching text is permanently deleted from the PDF.'
    )


class CropForm(forms.Form):
    left = forms.DecimalField(initial=5, min_value=0, max_value=90, label='Crop left (%)')
    right = forms.DecimalField(initial=5, min_value=0, max_value=90, label='Crop right (%)')
    top = forms.DecimalField(initial=5, min_value=0, max_value=90, label='Crop top (%)')
    bottom = forms.DecimalField(initial=5, min_value=0, max_value=90, label='Crop bottom (%)')
    pages = forms.CharField(required=False, label='Pages',
                            help_text='Optional: e.g. 1-3,5 (leave empty for all pages)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ['left', 'right', 'top', 'bottom', 'pages']:
            self.fields[name].widget.attrs.update({'class': 'form-input'})


class WatermarkForm(forms.Form):
    text = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. CONFIDENTIAL'}),
        required=True,
        label='Watermark text'
    )
    POSITION_CHOICES = [
        ('center', 'Center'),
        ('top-left', 'Top Left'),
        ('top-center', 'Top Center'),
        ('top-right', 'Top Right'),
        ('bottom-left', 'Bottom Left'),
        ('bottom-center', 'Bottom Center'),
        ('bottom-right', 'Bottom Right'),
    ]
    position = forms.ChoiceField(choices=POSITION_CHOICES, initial='center', label='Position')
    opacity = forms.FloatField(initial=0.3, min_value=0.05, max_value=1.0, label='Opacity (0.05-1)')
    fontsize = forms.IntegerField(initial=30, min_value=8, max_value=120, label='Font size')
    pages = forms.CharField(required=False, label='Pages (optional)',
                            help_text='e.g. 1-3,5 (leave empty for all pages)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['position'].widget.attrs.update({'class': 'form-select'})
        self.fields['opacity'].widget.attrs.update({'class': 'form-input'})
        self.fields['fontsize'].widget.attrs.update({'class': 'form-input'})
        self.fields['pages'].widget.attrs.update({'class': 'form-input'})


class PageNumberForm(forms.Form):
    POSITION_CHOICES = [
        ('top-left', 'Top Left'),
        ('top-center', 'Top Center'),
        ('top-right', 'Top Right'),
        ('bottom-left', 'Bottom Left'),
        ('bottom-center', 'Bottom Center'),
        ('bottom-right', 'Bottom Right'),
    ]
    position = forms.ChoiceField(choices=POSITION_CHOICES, initial='bottom-center', label='Position')
    start = forms.IntegerField(initial=1, min_value=1, max_value=100000, label='Starting number')
    fontsize = forms.IntegerField(initial=14, min_value=8, max_value=72, label='Font size')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['position'].widget.attrs.update({'class': 'form-select'})
        self.fields['start'].widget.attrs.update({'class': 'form-input'})
        self.fields['fontsize'].widget.attrs.update({'class': 'form-input'})


class OrganizeForm(forms.Form):
    order = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. 3,1,2  or  4-1,5'
        }),
        required=True,
        label='New page order',
        help_text='Comma separated page numbers or ranges to define the new order.'
    )
    rotation = forms.ChoiceField(
        choices=[(0, 'No rotation'), (90, 'Rotate 90°'), (180, 'Rotate 180°'), (270, 'Rotate 270°')],
        initial=0,
        label='Rotate pages'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rotation'].widget.attrs.update({'class': 'form-select'})


class OcrForm(forms.Form):
    pages = forms.CharField(required=False, label='Pages (optional)',
                            help_text='e.g. 1-3,5 (leave empty for all pages)')
    lang = forms.CharField(initial='eng', label='Language code', help_text='Tesseract language code, e.g. eng')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['pages'].widget.attrs.update({'class': 'form-input'})
        self.fields['lang'].widget.attrs.update({'class': 'form-input'})


class SignatureForm(forms.Form):
    page = forms.IntegerField(min_value=1, widget=forms.HiddenInput(), required=False)
    sig_x = forms.FloatField(widget=forms.HiddenInput(), required=False)
    sig_y = forms.FloatField(widget=forms.HiddenInput(), required=False)
    sig_width = forms.FloatField(widget=forms.HiddenInput(), required=False)
    signature_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('signature_data'):
            raise forms.ValidationError('Please draw or type your signature first.')
        return cleaned


class AddTextForm(forms.Form):
    text = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Enter text to add...'}),
        required=True,
        label='Text to Add'
    )
    page_number = forms.IntegerField(initial=1, min_value=1, label='Page number')
    x = forms.FloatField(initial=50, min_value=0, max_value=100, label='Horizontal position (%)')
    y = forms.FloatField(initial=50, min_value=0, max_value=100, label='Vertical position (%)')
    fontsize = forms.IntegerField(initial=12, min_value=6, max_value=72, label='Font size')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ['page_number', 'x', 'y', 'fontsize']:
            self.fields[name].widget.attrs.update({'class': 'form-input'})


class AddImageForm(forms.Form):
    image = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': 'image/*'}),
        required=True,
        label='Image file'
    )
    page_number = forms.IntegerField(initial=1, min_value=1, label='Page number')
    x = forms.FloatField(initial=50, min_value=0, max_value=100, label='Horizontal position (%)')
    y = forms.FloatField(initial=50, min_value=0, max_value=100, label='Vertical position (%)')
    width_pct = forms.FloatField(initial=25, min_value=5, max_value=80, label='Image width (%)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ['page_number', 'x', 'y', 'width_pct']:
            self.fields[name].widget.attrs.update({'class': 'form-input'})

    def clean_image(self):
        img = self.cleaned_data.get('image')
        if img and not any(img.name.lower().endswith(ext) for ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']):
            raise forms.ValidationError('Please upload an image (JPG, PNG, GIF, or WebP).')
        return img


class AnnotateForm(forms.Form):
    text = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Annotation text...'}),
        required=True,
        label='Annotation Text'
    )
    page_number = forms.IntegerField(initial=1, min_value=1, label='Page number')
    x = forms.FloatField(initial=50, min_value=0, max_value=100, label='Horizontal position (%)')
    y = forms.FloatField(initial=50, min_value=0, max_value=100, label='Vertical position (%)')
    fontsize = forms.IntegerField(initial=12, min_value=6, max_value=72, label='Font size')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ['page_number', 'x', 'y', 'fontsize']:
            self.fields[name].widget.attrs.update({'class': 'form-input'})


class HighlightForm(forms.Form):
    words = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Comma-separated words/phrases to highlight...'}),
        required=True,
        label='Words/phrases to highlight'
    )
    page_number = forms.IntegerField(initial=0, min_value=0, label='Page number (0 = all pages)')
    color = forms.ChoiceField(
        choices=[
            ('yellow', 'Yellow'),
            ('green', 'Green'),
            ('blue', 'Blue'),
            ('pink', 'Pink'),
            ('orange', 'Orange'),
        ],
        initial='yellow',
        label='Highlight color',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ['page_number']:
            self.fields[name].widget.attrs.update({'class': 'form-input'})


class PPTUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': '.pptx'}),
        required=True
    )

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and not file.name.lower().endswith('.pptx'):
            raise forms.ValidationError('Please upload a .pptx file.')
        return file


class ImageUploadAnyForm(forms.Form):
    files = MultipleFileField(
        widget=MultipleFileInput(attrs={
            'class': 'file-input',
            'accept': 'image/*'
        }),
        required=True
    )