from django.contrib import admin
from django.urls import path
from calculator import views
from calculator.views import calculate_investment, visit_statistics

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.calculate_investment, name='calculator'),
    path('admin/visit-stats/', visit_statistics, name='visit_stats'),
    path('', calculate_investment, name='calculator'),
]
