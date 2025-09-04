from django.contrib import admin
from django.urls import path
from calculator import views
from calculator.views import calculate_investment

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', calculate_investment, name='calculator'),

]
