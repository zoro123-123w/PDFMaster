from django import forms

class AIUploadForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': 'application/pdf'}),
        required=True
    )
    question = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Enter your question about this PDF...'}),
        required=False,
        label="Your Question"
    )


class TranslationForm(forms.Form):
    text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 5,
            'placeholder': 'Enter the text you want to translate...'
        }),
        required=True,
        label='Text to Translate'
    )
    target_language = forms.ChoiceField(
        choices=[
            ('english', 'English'),
            ('spanish', 'Spanish'),
            ('french', 'French'),
            ('german', 'German'),
            ('italian', 'Italian'),
            ('portuguese', 'Portuguese'),
            ('dutch', 'Dutch'),
            ('russian', 'Russian'),
            ('chinese', 'Chinese (Simplified)'),
            ('japanese', 'Japanese'),
            ('arabic', 'Arabic'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='english',
        label='Target Language'
    )


# ---------------------------------------------------------------------------
# AI Study Suite forms
# ---------------------------------------------------------------------------

class QuizForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': 'application/pdf'}),
        required=True
    )
    num_questions = forms.IntegerField(
        initial=10, min_value=3, max_value=50,
        label='Number of questions',
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    difficulty = forms.ChoiceField(
        choices=[
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard'),
            ('mixed', 'Mixed'),
        ],
        initial='medium',
        label='Difficulty',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class StudyForm(forms.Form):
    """Generic study form used by all single-parameter study tools."""
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': 'application/pdf'}),
        required=True
    )
    extra = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-input', 'rows': 3,
            'placeholder': 'Optional: provide additional instructions or focus areas...'
        }),
        required=False,
        label='Additional instructions (optional)'
    )


class FlashcardForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': 'application/pdf'}),
        required=True
    )
    num_flashcards = forms.IntegerField(
        initial=15, min_value=5, max_value=50,
        label='Number of flashcards',
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )


class QuestionBankForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'file-input', 'accept': 'application/pdf'}),
        required=True
    )
    num_questions = forms.IntegerField(
        initial=20, min_value=5, max_value=50,
        label='Number of questions per type',
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )