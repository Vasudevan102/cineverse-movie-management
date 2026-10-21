from booking.admin_views import admin_dashboard_view, admin_dashboard_export_csv_view
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from movies.views import home_view

urlpatterns = [
    path('admin/dashboard/export/', admin_dashboard_export_csv_view, name='admin_dashboard_export'),
    path('admin/dashboard/', admin_dashboard_view, name='admin_dashboard'),
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('accounts/', include('accounts.urls')),
    path('movies/', include('movies.urls')),
    path('booking/', include('booking.urls')),
    path('reviews/', include('reviews.urls')),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

