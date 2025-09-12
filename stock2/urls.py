from django.urls import path
from .views import Stock2View

urlpatterns = [
    path('', Stock2View.as_view(), name='stock2'),
]