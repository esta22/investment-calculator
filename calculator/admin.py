from django.contrib import admin
from .models import StockData, TickerViewCount



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

