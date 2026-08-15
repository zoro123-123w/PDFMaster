from django.urls import path
from . import views

urlpatterns = [
    path('', views.ai_tools_list, name='ai_tools'),
    path('summarize/', views.summarize_pdf_view, name='ai_summarize'),
    path('extract/', views.extract_text_view, name='ai_extract'),
    path('translate/', views.translate_text_view, name='ai_translate'),
    path('ask/', views.ask_question_view, name='ai_ask'),
    path('study/', views.ai_study_list, name='ai_study'),
    path('study/quiz/', views.quiz_view, name='ai_study_quiz'),
    path('study/flashcards/', views.flashcards_view, name='ai_study_flashcards'),
    path('study/notes/', views.study_notes_view, name='ai_study_notes'),
    path('study/guide/', views.study_guide_view, name='ai_study_guide'),
    path('study/question-bank/', views.question_bank_view, name='ai_study_questions'),
    path('study/important/', views.important_questions_view, name='ai_study_important'),
    path('study/chapter-summary/', views.chapter_summary_view, name='ai_study_chapters'),
    path('study/key-concepts/', views.key_concepts_view, name='ai_study_concepts'),
    path('study/exam-prep/', views.exam_prep_view, name='ai_study_exam'),
    path('request/<uuid:request_id>/', views.ai_request_detail, name='ai_request_detail'),
    path('request/<uuid:request_id>/download/', views.download_ai_result, name='download_ai_result'),
]
