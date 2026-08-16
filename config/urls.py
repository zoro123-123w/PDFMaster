from django.contrib import admin
from django.http import HttpResponse
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views
from core.sitemaps import StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
}
def google_verification(request):
    return HttpResponse("google-site-verification:googlea604197a80b57310.html",content_type="text/html")

urlpatterns = [
    path("googlea604197a80b57310.html",google_verification),
    path('admin/', admin.site.urls),
    path('', core_views.home, name='home'),
    path('robots.txt', core_views.robots_txt, name='robots_txt'),
    path('tools/', include('pdf_tools.urls')),
    path('ai-tools/', include('ai_tools.urls')),
    path('pricing/', core_views.pricing, name='pricing'),
    path('faq/', core_views.faq, name='faq'),
    path('login/', core_views.CustomLoginView.as_view(), name='login'),
    path('register/', core_views.register, name='register'),
    path('dashboard/', core_views.dashboard, name='dashboard'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
