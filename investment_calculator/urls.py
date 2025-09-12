from django.contrib import admin
from django.urls import path, include
from calculator.views import calculate_investment

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', calculate_investment, name='calculator'),
    path('stock2/', include('stock2.urls')),  # stock2/ 아래에 포함
]