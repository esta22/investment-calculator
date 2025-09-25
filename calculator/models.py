from django.db import models


class StockData(models.Model):
    ticker = models.CharField(max_length=10)
    date = models.DateField()
    close_price = models.DecimalField(max_digits=10, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)
    view_count = models.PositiveIntegerField(default=0)  # 이 필드 추가!

    class Meta:
        unique_together = ('ticker', 'date')

    def __str__(self):
        return f"{self.ticker} - {self.date} - {self.close_price}"


class TickerViewCount(models.Model):
    ticker = models.CharField(max_length=10, unique=True)
    view_count = models.PositiveIntegerField(default=0)
    last_viewed = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.ticker} - {self.view_count} views"

