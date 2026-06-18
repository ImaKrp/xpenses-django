from django.contrib import admin
from django.urls import path, re_path, include
from django.contrib.staticfiles.views import serve as serve_static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    re_path(r'^static/(?P<path>.*)$', serve_static, kwargs={'insecure': True}),
]
