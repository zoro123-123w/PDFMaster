from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.contrib import messages
from pdf_tools.views import PDF_TOOLS
from ai_tools.views import AI_TOOLS, AI_STUDY_TOOLS
from pdf_tools.models import ProcessingJob
from ai_tools.models import AIRequest
from pdf_tools.services.ocr import tesseract_available


def home(request):
    return render(request, 'home.html', {
        'tools': PDF_TOOLS,
        'ai_tools': AI_TOOLS,
        'ai_study_tools': AI_STUDY_TOOLS,
    })


def pricing(request):
    return render(request, 'pricing.html')


def faq(request):
    return render(request, 'faq.html')


def about(request):
    return render(request, 'static_pages/about.html')


def contact(request):
    return render(request, 'static_pages/contact.html')


def privacy_policy(request):
    return render(request, 'static_pages/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'static_pages/terms_of_service.html')


def cookie_policy(request):
    return render(request, 'static_pages/cookie_policy.html')


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'

    def form_valid(self, form):
        messages.success(self.request, 'Welcome back!')
        return super().form_valid(form)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Account created successfully! You can now log in.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    jobs = ProcessingJob.objects.filter(user=request.user).order_by('-created_at')[:20]
    ai_requests = AIRequest.objects.filter(user=request.user).order_by('-created_at')[:20]
    return render(request, 'dashboard.html', {'jobs': jobs, 'ai_requests': ai_requests})


def health(request):
    """Liveness probe for Render / nginx / uptime monitors.

    Render's ``healthCheckPath`` points here. It must return 200 with no database
    or template work so a warm container answers instantly. ``ocr_ready`` reports
    whether Tesseract is present, which is useful when debugging why OCR fails -
    it does not affect the status code, because the web app itself is healthy.
    """
    payload = {
        'status': 'ok',
        'ocr_ready': tesseract_available(),
    }
    return JsonResponse(payload)


def ads_txt(request):
    """IAB ads.txt - declares who may sell ad inventory on this domain.

    Only rendered when AdSense is configured; otherwise an empty allow-all file
    keeps crawlers from reporting a missing ads.txt.
    """
    lines = ['google.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0']
    client = getattr(settings, 'ADSENSE_CLIENT_ID', '')
    if client.startswith('ca-pub-'):
        # ca-pub-XXXXXXXX -> publisher id without the 'ca-' prefix.
        lines[0] = f'google.com, {client[3:]}, DIRECT, f08c47fec0942fa0'
    return HttpResponse('\n'.join(lines) + '\n', content_type='text/plain')


def robots_txt(request):
    """Dynamic robots.txt.

    The Sitemap line is built from settings.SITE_URL (the canonical origin
    used by the SEO tags and the sitemap itself), never from the request host,
    so a spoofed Host header cannot poison the advertised sitemap URL.
    """
    sitemap_url = f"{settings.SITE_URL}/sitemap.xml"
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /accounts/\n"
        "Disallow: /dashboard/\n"
        "Disallow: /media/\n"
        "Disallow: /static/\n"
        "Disallow: /download/\n"
        "Disallow: /tools/download/\n"
        "Disallow: /ai-tools/request/\n"
        "\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return HttpResponse(content, content_type="text/plain")