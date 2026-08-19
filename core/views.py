from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.contrib import messages
from django.http import HttpResponse
from pdf_tools.views import PDF_TOOLS, PDF_TOOL_CATEGORIES
from ai_tools.views import AI_TOOLS, AI_STUDY_TOOLS
from pdf_tools.models import ProcessingJob
from ai_tools.models import AIRequest


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


def robots_txt(request):
    """Dynamic robots.txt that always points to the correct sitemap URL
    based on the request domain (handles both local and production).

    The sitemap URL always uses HTTPS since the production site is HTTPS-only.
    """
    sitemap_url = request.build_absolute_uri('/sitemap.xml')
    if sitemap_url.startswith('http://'):
        sitemap_url = 'https://' + sitemap_url[7:]
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /accounts/\n"
        "Disallow: /dashboard/\n"
        "Disallow: /media/\n"
        "Disallow: /static/\n"
        "Disallow: /tools/download/\n"
        "Disallow: /ai-tools/request/\n"
        "\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return HttpResponse(content, content_type="text/plain")