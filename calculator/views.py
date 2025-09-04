import yfinance as yf
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from django.db import IntegrityError
from .models import StockData
from .forms import InvestmentForm
from dateutil.relativedelta import relativedelta
from .models import TickerViewCount
from django.db.models import F


def search_stock_data(ticker):
    # 마지막 업데이트 시간 확인
    last_update = StockData.objects.filter(ticker=ticker).order_by('-updated_at').first()

    if last_update:
        time_diff = timezone.now() - last_update.updated_at
        if time_diff < timedelta(hours=18):
            return None, "데이터가 최신 상태입니다."

    # 데이터 업데이트 실행
    try:
        return update_stock_data(ticker), "업데이트 완료"
    except Exception as e:
        return None, f"업데이트 실패: {str(e)}"


def update_stock_data(ticker):
    # 야후 파이낸스에서 데이터 가져오기
    stock = yf.Ticker(ticker)
    hist = stock.history(period="max")

    new_data = []
    for date, row in hist.iterrows():
        new_data.append(StockData(
            ticker=ticker,
            date=date.date(),
            close_price=row['Close']
        ))

    # bulk_create로 데이터 저장
    try:
        StockData.objects.bulk_create(new_data, ignore_conflicts=True)
        return len(new_data)
    except IntegrityError:
        # 중복 데이터 무시
        return f"{ticker} 데이터 업데이트 완료 (일부 데이터는 이미 존재함)"


def calculate_investment(request):
    if request.method == 'POST':
        form = InvestmentForm(request.POST)
        if form.is_valid():
            # 폼 데이터 추출
            ticker = form.cleaned_data['ticker'].upper()

            # 조회수 증가
            increase_view_count(ticker)

            initial_capital = float(form.cleaned_data['initial_capital'])
            monthly_investment = float(form.cleaned_data['monthly_investment'])
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            # 데이터 검색 및 업데이트
            update_result, message = search_stock_data(ticker)

            if update_result is None and "최신" not in message:
                return render(request, 'calculator/calculator.html', {
                    'form': form,
                    'error': message
                })

            # 종료일 기준 주가 데이터 조회
            end_date_stock_data = StockData.objects.filter(
                ticker=ticker,
                date__lte=end_date
            ).order_by('-date').first()

            if end_date_stock_data:
                end_date_price = float(end_date_stock_data.close_price)
                end_date_price_date = end_date_stock_data.date.strftime('%y/%m/%d')
            else:
                # 종료일 이전 데이터가 없는 경우
                end_date_price = 0
                end_date_price_date = end_date.strftime('%y/%m/%d')

            # 계산 수행
            exchange_rate = 1400.0
            cash_krw = initial_capital
            shares_held = 0.0
            records = []
            total_investment = initial_capital

            current_date = start_date
            while current_date <= end_date:
                # 해당 월의 구매일 설정 (시작일의 일자로)
                investment_day = start_date.day
                investment_date = current_date.replace(day=investment_day)

                # 주가 데이터 조회
                stock_data = StockData.objects.filter(
                    ticker=ticker,
                    date__lte=investment_date
                ).order_by('-date').first()

                if stock_data:
                    # 현금에 월적립액 추가 (첫 달 제외)
                    if current_date > start_date:
                        cash_krw += monthly_investment
                        total_investment += monthly_investment

                    # 주식 구매
                    stock_price_usd = float(stock_data.close_price)
                    stock_price_krw = stock_price_usd * exchange_rate
                    shares_to_buy = cash_krw // stock_price_krw

                    if shares_to_buy > 0:
                        shares_held += shares_to_buy
                        purchase_amount = shares_to_buy * stock_price_krw
                        cash_krw -= purchase_amount

                        # 평가금액 계산 (현재 가격 기준)
                        current_stock_value_usd = shares_held * stock_price_usd
                        current_stock_value_krw = current_stock_value_usd * exchange_rate
                        total_assets = current_stock_value_krw + cash_krw

                        # 수익률 계산
                        if total_investment > 0:
                            profit_rate = ((total_assets - total_investment) / total_investment) * 100
                        else:
                            profit_rate = 0.0

                        # 기록 추가
                        records.append({
                            'date': investment_date.strftime('%y/%m/%d'),
                            'action': f'{ticker} 구매',
                            'price': round(stock_price_usd, 2),
                            'shares_bought': round(shares_to_buy, 0),
                            'shares_held': round(shares_held, 0),
                            'stock_value_krw': round(current_stock_value_krw, 0),
                            'cash_krw': round(cash_krw, 0),
                            'total_assets': round(total_assets, 0),
                            'total_investment': round(total_investment, 0),
                            'profit_rate': round(profit_rate, 2)
                        })

                # 다음 달로 이동
                current_date += relativedelta(months=1)

            # 최종 결과 계산 (종료일 기준 주가 사용)
            if records:
                # 종료일 기준 주가 사용
                end_date_stock_price_krw = end_date_price * exchange_rate

                # 최종 평가금액 계산
                final_stock_value_usd = shares_held * end_date_price
                final_stock_value_krw = final_stock_value_usd * exchange_rate
                final_total_assets = final_stock_value_krw + cash_krw

                # 최종 수익률 계산
                if total_investment > 0:
                    final_profit_rate = ((final_total_assets - total_investment) / total_investment) * 100
                else:
                    final_profit_rate = 0.0

                final_profit_amount = final_total_assets - total_investment

                final_result = {
                    'final_stock_value': round(final_stock_value_krw, 0),
                    'final_cash': round(cash_krw, 0),
                    'final_total_assets': round(final_total_assets, 0),
                    'final_total_investment': round(total_investment, 0),
                    'final_profit_rate': round(final_profit_rate, 2),
                    'final_profit_amount': round(final_profit_amount, 0),
                    'final_shares_held': round(shares_held, 0),
                    'end_date_price': round(end_date_price, 2),
                    'end_date_price_date': end_date_price_date
                }
            else:
                final_result = None

            return render(request, 'calculator/calculator.html', {
                'form': form,
                'records': records,
                'final_result': final_result,
                'ticker': ticker,
                'update_message': message if "업데이트" in message else None
            })
        else:
            # ✅ 폼 검증 실패 시 ticker 변수 처리
            ticker = request.POST.get('ticker', '').upper()

    else:
        form = InvestmentForm()
        ticker = ''  # ✅ GET 요청 시 ticker 초기화

    return render(request, 'calculator/calculator.html', {
        'form': form,
        'ticker': ticker  # ✅ 항상 ticker 변수 전달
    })


def increase_view_count(ticker):
    """티커 조회수 증가 함수"""
    try:
        # StockData의 각 레코드 조회수 증가
        StockData.objects.filter(ticker=ticker).update(view_count=F('view_count') + 1)

        # TickerViewCount 모델에 집계
        ticker_view, created = TickerViewCount.objects.get_or_create(
            ticker=ticker,
            defaults={'view_count': 1}
        )
        if not created:
            ticker_view.view_count = F('view_count') + 1
            ticker_view.last_viewed = timezone.now()
            ticker_view.save()

    except Exception as e:
        print(f"조회수 증가 중 오류: {e}")