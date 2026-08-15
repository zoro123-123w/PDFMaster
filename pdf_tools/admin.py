from django.contrib import admin
from .models import ProcessingJob

@admin.register(ProcessingJob)
class ProcessingJobAdmin(admin.ModelAdmin):
    list_display = ['tool_name', 'original_filename', 'status', 'created_at', 'completed_at']
    list_filter = ['tool_name', 'status', 'created_at']
    search_fields = ['original_filename', 'tool_name']
    readonly_fields = ['created_at', 'completed_at']