from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class AIRequest(models.Model):
    TOOL_CHOICES = [
        ('summarize', 'Summarize PDF'),
        ('extract', 'Extract Text'),
        ('translate', 'Translate Text'),
        ('ask', 'Ask Question'),
        ('quiz', 'AI Quiz Generator'),
        ('flashcards', 'Flashcard Generator'),
        ('study_notes', 'Study Notes'),
        ('study_guide', 'Study Guide'),
        ('question_bank', 'Question Bank'),
        ('important_questions', 'Important Questions'),
        ('chapter_summary', 'Chapter Summary'),
        ('key_concepts', 'Key Concepts'),
        ('exam_prep', 'Exam Preparation'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    pdf_file = models.FileField(upload_to='ai_uploads/', null=True, blank=True)
    tool = models.CharField(max_length=25, choices=TOOL_CHOICES)
    prompt = models.TextField(blank=True, help_text="User question or instruction")
    response = models.TextField(blank=True, help_text="AI-generated response")
    status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('PROCESSING', 'Processing'),
            ('COMPLETED', 'Completed'),
            ('FAILED', 'Failed'),
        ],
        default='PENDING'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'AI Request'
        verbose_name_plural = 'AI Requests'

    def __str__(self):
        return f"{self.get_tool_display()} - {self.created_at}"