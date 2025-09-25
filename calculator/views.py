import yfinance as yf
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta
from .models import StockData
from .forms import InvestmentForm
from dateutil.relativedelta import relativedelta
from .models import TickerViewCount
from django.db.models import F
from django.utils import translation
from django.conf import settings



def set_language_from_url(request):
    """URL에서 언어 코드를 추출하여 설정"""
    path = request.path_info
    supported_languages = ['ko', 'en']

    # 기본 언어 설정
    lang_code = 'ko'

    # 경로에서 언어 코드 추출
    for language in supported_languages:
        if path.startswith(f'/{language}/') or path == f'/{language}':
            lang_code = language
            break

    # 언어 설정
    if lang_code in supported_languages:
        from django.utils import translation
        translation.activate(lang_code)
        request.LANGUAGE_CODE = translation.get_language()

    return lang_code








def search_stock_data(ticker):
    # 마지막 업데이트 시간 확인
    last_update = StockData.objects.filter(ticker=ticker).order_by('-updated_at').first()

    if last_update:
        time_diff = timezone.now() - last_update.updated_at
        if time_diff < timedelta(hours=18):
            return None, "데이터가 최신 상태입니다."

    # 데이터 업데이트 실행
    try:
        result = update_stock_data_optimized(ticker)
        return result, "업데이트 완료"
    except Exception as e:
        return None, f"업데이트 실패: {str(e)}"


def update_stock_data_optimized(ticker):
    try:
        # 기존 데이터의 가장 최근 날짜 확인
        latest_data = StockData.objects.filter(ticker=ticker).order_by('-date').first()

        stock = yf.Ticker(ticker)

        if latest_data:
            # 기존 데이터가 있는 경우: 마지막 데이터 다음날부터 최신 데이터만 가져오기
            start_date = latest_data.date + timedelta(days=1)
            # 시작일이 현재보다 미래인 경우 조정
            if start_date > timezone.now().date():
                return 0

            hist = stock.history(start=start_date)
            update_type = "incremental"
        else:
            # 처음 데이터를 가져오는 경우: 전체 데이터 가져오기
            hist = stock.history(period="max")
            update_type = "full"

        # 데이터가 없는 경우
        if hist.empty:
            return f"{ticker} 데이터가 없습니다."

        new_data = []
        for date, row in hist.iterrows():
            new_data.append(StockData(
                ticker=ticker,
                date=date.date(),
                close_price=row['Close'],
                updated_at=timezone.now()
            ))

        # 배치 처리로 저장
        if new_data:
            batch_size = 100
            for i in range(0, len(new_data), batch_size):
                batch = new_data[i:i + batch_size]
                StockData.objects.bulk_create(batch, ignore_conflicts=True)

        if update_type == "incremental":
            return f"{ticker} 데이터 증분 업데이트 완료 ({len(new_data)}개 추가)"
        else:
            return f"{ticker} 데이터 전체 업데이트 완료 ({len(new_data)}개 저장)"

    except Exception as e:
        print(f"Update error for {ticker}: {e}")
        return f"업데이트 실패: {str(e)}"


def calculate_investment(request):
    # URL에서 언어 코드 설정
    lang_code = set_language_from_url(request)
    is_english = lang_code == 'en'
    exchange_rate = 1400.0

    if request.method == 'POST':
        form = InvestmentForm(request.POST)
        if form.is_valid():
            # 폼 데이터 추출
            ticker = form.cleaned_data['ticker'].upper()

            # 조회수 증가
            increase_view_count(ticker)

            # 입력값 처리 (언어에 따라 원화/달러 구분)
            if is_english:
                # 영어 선택시: 달러 입력 → 그대로 사용
                initial_capital = float(form.cleaned_data['initial_capital'])
                monthly_investment = float(form.cleaned_data['monthly_investment'])
            else:
                # 한국어 선택시: 원화 입력 → 달러로 변환
                initial_capital = float(form.cleaned_data['initial_capital']) / exchange_rate
                monthly_investment = float(form.cleaned_data['monthly_investment']) / exchange_rate

            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']

            # 데이터 검색 및 업데이트
            update_result, message = search_stock_data(ticker)

            if update_result is None and "최신" not in message:
                response = render(request, 'calculator/calculator.html', {
                    'form': form,
                    'error': message,
                    'is_english': is_english,
                    'LANGUAGE_CODE': lang_code
                })
                response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)
                return response

            # 종료일 기준 주가 데이터 조회
            end_date_stock_data = StockData.objects.filter(
                ticker=ticker,
                date__lte=end_date
            ).order_by('-date').first()

            if end_date_stock_data:
                end_date_price = float(end_date_stock_data.close_price)
                end_date_price_date = end_date_stock_data.date.strftime('%y/%m/%d')
            else:
                end_date_price = 0
                end_date_price_date = end_date.strftime('%y/%m/%d')

            # 계산 수행 (모두 달러로 계산)
            cash = initial_capital
            shares_held = 0.0
            records = []
            total_investment = initial_capital

            current_date = start_date
            while current_date <= end_date:
                # 해당 월의 구매일 설정
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
                        cash += monthly_investment
                        total_investment += monthly_investment

                    # 주식 구매
                    stock_price = float(stock_data.close_price)
                    shares_to_buy = cash // stock_price

                    if shares_to_buy > 0:
                        shares_held += shares_to_buy
                        purchase_amount = shares_to_buy * stock_price
                        cash -= purchase_amount
                        current_stock_value = shares_held * stock_price
                        total_assets = current_stock_value + cash

                        # 수익률 계산
                        if total_investment > 0:
                            profit_rate = ((total_assets - total_investment) / total_investment) * 100
                        else:
                            profit_rate = 0.0

                        # 기록 추가 (달러 기준)
                        record_data = {
                            'date': investment_date.strftime('%y/%m/%d'),
                            'action': f'{ticker}',
                            'price': round(stock_price, 2),
                            'shares_bought': round(shares_to_buy, 0),
                            'shares_held': round(shares_held, 0),
                            'stock_value': round(current_stock_value, 2),
                            'cash': round(cash, 2),
                            'total_assets': round(total_assets, 2),
                            'profit_rate': round(profit_rate, 2),
                            'currency_symbol': '$'
                        }

                        # 한국어인 경우 원화로 변환하여 추가
                        if not is_english:
                            record_data.update({
                                'stock_value_krw': round(current_stock_value * exchange_rate, 0),
                                'cash_krw': round(cash * exchange_rate, 0),
                                'total_assets_krw': round(total_assets * exchange_rate, 0),
                            })

                        records.append(record_data)

                # 다음 달로 이동
                current_date += relativedelta(months=1)

            # 최종 결과 계산 (달러 기준)
            if records:
                final_stock_value = shares_held * end_date_price
                final_cash = cash
                final_total_assets = final_stock_value + final_cash
                final_profit_amount = final_total_assets - total_investment

                if total_investment > 0:
                    final_profit_rate = ((final_total_assets - total_investment) / total_investment) * 100
                else:
                    final_profit_rate = 0.0

                final_result = {
                    # 달러 기준 값
                    'final_stock_value': final_stock_value,
                    'final_cash': final_cash,
                    'final_total_assets': final_total_assets,
                    'final_total_investment': total_investment,
                    'final_profit_amount': final_profit_amount,
                    'final_profit_rate': final_profit_rate,
                    'final_shares_held': shares_held,
                    'end_date_price': end_date_price,
                    'end_date_price_date': end_date_price_date,
                    'is_english': is_english,
                    'currency_symbol': '$',
                    'exchange_rate': exchange_rate
                }

                # 한국어인 경우 원화 값 추가
                if not is_english:
                    final_result.update({
                        'final_stock_value_krw': final_stock_value * exchange_rate,
                        'final_cash_krw': final_cash * exchange_rate,
                        'final_total_assets_krw': final_total_assets * exchange_rate,
                        'final_total_investment_krw': total_investment * exchange_rate,
                        'final_profit_amount_krw': final_profit_amount * exchange_rate,
                    })

            else:
                final_result = None

            response = render(request, 'calculator/calculator.html', {
                'form': form,
                'records': records,
                'final_result': final_result,
                'ticker': ticker,
                'update_message': message if "업데이트" in message or "Update" in message else None,
                'is_english': is_english,
                'LANGUAGE_CODE': lang_code
            })
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)
            return response
        else:
            ticker = request.POST.get('ticker', '').upper()
            response = render(request, 'calculator/calculator.html', {
                'form': form,
                'ticker': ticker,
                'is_english': is_english,
                'LANGUAGE_CODE': lang_code
            })
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)
            return response

    else:
        form = InvestmentForm()
        ticker = ''
        response = render(request, 'calculator/calculator.html', {
            'form': form,
            'ticker': ticker,
            'is_english': is_english,
            'LANGUAGE_CODE': lang_code
        })
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang_code)
        return response


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



