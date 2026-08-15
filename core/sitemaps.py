from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return ['home', 'tools_list', 'ai_tools', 'ai_study', 'pricing', 'faq', 'login', 'register']

    def location(self, item):
        return reverse(item)