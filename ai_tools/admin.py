from django.contrib import admin
from .models import AIRequest


@admin.register(AIRequest)
class AIRequestAdmin(admin.ModelAdmin):
    list_display = ['tool', 'user', 'status', 'created_at', 'completed_at']
    list_filter = ['tool', 'status', 'created_at']
    search_fields = ['prompt', 'response']
    readonly_fields = ['created_at', 'completed_at']
