from django.contrib import admin
from django.urls import path, include
from core.views import home  # Import the home view
from django.conf import settings # new
from  django.conf.urls.static import static #new


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),  # Serve index.html at /
    path('analyze/', include('core.urls')),  # Ensure analyze/ URL works
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root = settings.STATIC_URL)