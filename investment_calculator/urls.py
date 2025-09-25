# investment_calculator/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from calculator.views import calculate_investment

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += i18n_patterns(
    path('', calculate_investment, name='calculator'),
    path('stock2/', include('stock2.urls')),
    # prefix_default_language를 제거하거나 True로 설정하면 모든 언어에 접두사가 붙습니다.
    # prefix_default_language=True,
)