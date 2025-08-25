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


class ViewHistory(models.Model):
    ticker = models.CharField(max_length=10)
    view_date = models.DateField(auto_now_add=True)
    view_time = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-view_time']

    def __str__(self):
        return f"{self.ticker} - {self.view_time}"


class SiteVisit(models.Model):
    """웹사이트 접속 통계 모델"""
    visit_date = models.DateField(auto_now_add=True, verbose_name='접속일')
    visit_time = models.DateTimeField(auto_now_add=True, verbose_name='접속시간')
    page_views = models.PositiveIntegerField(default=0, verbose_name='페이지뷰')
    unique_visits = models.PositiveIntegerField(default=0, verbose_name='고유방문자')

    class Meta:
        ordering = ['-visit_date']
        verbose_name = '사이트 접속 통계'
        verbose_name_plural = '사이트 접속 통계'

    def __str__(self):
        return f"{self.visit_date} - PV: {self.page_views}, UV: {self.unique_visits}"


class DailyVisit(models.Model):
    """일별 접속 통계"""
    date = models.DateField(unique=True, verbose_name='날짜')
    page_views = models.PositiveIntegerField(default=0, verbose_name='페이지뷰')
    unique_visits = models.PositiveIntegerField(default=0, verbose_name='고유방문자')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='마지막 업데이트')

    class Meta:
        ordering = ['-date']
        verbose_name = '일별 접속 통계'
        verbose_name_plural = '일별 접속 통계'

    def __str__(self):
        return f"{self.date} - PV: {self.page_views}, UV: {self.unique_visits}"