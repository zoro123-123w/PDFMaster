from django import forms

class AIUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': 'application/pdf'}),
        required=True
    )
    question = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Enter your question about this PDF...'}),
        required=True,
        label="Your Question"
    )