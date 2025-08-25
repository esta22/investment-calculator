from django.contrib import admin
from .models import StockData, TickerViewCount, ViewHistory
from .models import SiteVisit, DailyVisit



@admin.register(StockData)
class StockDataAdmin(admin.ModelAdmin):
    list_display = ['ticker', 'date', 'close_price', 'view_count', 'updated_at']
    list_filter = ['ticker', 'date']
    search_fields = ['ticker']
    ordering = ['-date']
    readonly_fields = ['updated_at']  # view_count는 readonly에서 제거

    # 액션 추가
    actions = ['reset_view_count']

    def reset_view_count(self, request, queryset):
        updated = queryset.update(view_count=0)
        self.message_user(request, f"{updated}개의 주가 데이터 조회수가 초기화되었습니다.")

    reset_view_count.short_description = "선택된 항목 조회수 초기화"


@admin.register(TickerViewCount)
class TickerViewCountAdmin(admin.ModelAdmin):
    list_display = ['ticker', 'view_count', 'last_viewed']
    list_filter = ['last_viewed']
    search_fields = ['ticker']
    ordering = ['-view_count']
    readonly_fields = ['ticker', 'last_viewed']  # view_count는 수정 가능하게


@admin.register(ViewHistory)
class ViewHistoryAdmin(admin.ModelAdmin):
    list_display = ['ticker', 'view_date', 'view_time', 'ip_address']
    list_filter = ['view_date', 'ticker']
    search_fields = ['ticker', 'ip_address']
    readonly_fields = ['view_date', 'view_time']  # 필요한 필드만 readonly


@admin.register(SiteVisit)
class SiteVisitAdmin(admin.ModelAdmin):
    list_display = ['visit_date', 'page_views', 'unique_visits', 'conversion_rate']
    list_filter = ['visit_date']
    ordering = ['-visit_date']
    readonly_fields = ['visit_date', 'visit_time', 'page_views', 'unique_visits']
    date_hierarchy = 'visit_date'

    def conversion_rate(self, obj):
        if obj.page_views > 0:
            return f"{(obj.unique_visits / obj.page_views * 100):.1f}%"
        return "0%"

    conversion_rate.short_description = '전환율'


@admin.register(DailyVisit)
class DailyVisitAdmin(admin.ModelAdmin):
    list_display = ['date', 'page_views', 'unique_visits', 'conversion_rate', 'last_updated']
    list_filter = ['date']
    ordering = ['-date']
    readonly_fields = ['date', 'page_views', 'unique_visits', 'last_updated']
    date_hierarchy = 'date'

    def conversion_rate(self, obj):
        if obj.page_views > 0:
            return f"{(obj.unique_visits / obj.page_views * 100):.1f}%"
        return "0%"

    conversion_rate.short_description = '전환율'