from django.urls import path
from . import views

urlpatterns = [
    path('', views.tools_list, name='tools_list'),
    path('merge-pdf/', views.merge_pdf, name='merge_pdf'),
    path('split-pdf/', views.split_pdf, name='split_pdf'),
    path('compress-pdf/', views.compress_pdf, name='compress_pdf'),
    path('jpg-to-pdf/', views.jpg_to_pdf, name='jpg_to_pdf'),
    path('pdf-to-jpg/', views.pdf_to_jpg, name='pdf_to_jpg'),
    path('rotate-pdf/', views.rotate_pdf, name='rotate_pdf'),
    path('delete-pages/', views.delete_pages, name='delete_pages'),
    path('extract-pages/', views.extract_pages, name='extract_pages'),
    path('download/<uuid:job_id>/', views.download_file, name='download_file'),
]