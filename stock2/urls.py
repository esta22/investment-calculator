#stock2/urls.py

from django.urls import path
from .views import Stock2View, Stock2ResultView

urlpatterns = [
    path('', Stock2View.as_view(), name='stock2'),
    path('result/', Stock2ResultView.as_view(), name='stock2_result'),
]