from django.utils import timezone
from .models import SiteVisit, DailyVisit
import hashlib


class VisitCounterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 관리자 페이지나 특정 경로는 제외
        if request.path.startswith('/admin/') or request.path.startswith('/static/'):
            return response

        self.record_visit(request)
        return response

    def record_visit(self, request):
        try:
            today = timezone.now().date()

            # 일별 통계 업데이트
            daily_visit, created = DailyVisit.objects.get_or_create(
                date=today,
                defaults={'page_views': 1, 'unique_visits': 1}
            )

            if not created:
                daily_visit.page_views += 1

                # 세션을 이용한 고유 방문자 확인 (개인정보 없음)
                session_key = request.session.session_key
                if not request.session.get('visited_today', False):
                    daily_visit.unique_visits += 1
                    request.session['visited_today'] = True
                    request.session.set_expiry(86400)  # 24시간

                daily_visit.save()

            # 전체 접속 통계 업데이트
            site_visit, created = SiteVisit.objects.get_or_create(
                visit_date=today,
                defaults={'page_views': 1, 'unique_visits': 1}
            )

            if not created:
                site_visit.page_views += 1
                if not request.session.get('visited_today', False):
                    site_visit.unique_visits += 1
                site_visit.save()

        except Exception as e:
            # 오류 발생해도 사이트 동작에는 영향 없음
            pass