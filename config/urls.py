from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Clinic System Administration'
admin.site.site_title = 'Clinic System Admin'

urlpatterns = [
    path('', include('reports.urls')),
    path('', include('pharmacy.urls')),
    path('patients/', include('patients.urls')),
    path('billing/', include('billing.urls')),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
]
