from django.db import models

class AllTimeHigh(models.Model):
    ticker = models.CharField(max_length=10)
    date = models.DateField()
    high_price = models.DecimalField(max_digits=10, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('ticker', 'date')

    def __str__(self):
        return f"{self.ticker} - {self.date} - {self.high_price}"