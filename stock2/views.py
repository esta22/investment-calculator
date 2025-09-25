import requests
import pandas as pd
from django.shortcuts import render, redirect
from django.views import View
from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from calculator.models import StockData
from .models import AllTimeHigh
from django.utils import translation
from django.middleware.locale import LocaleMiddleware


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


class Stock2View(View):
    template_name = 'stock2/stock2.html'

    def get(self, request):
        """GET 요청: 입력 폼 표시"""
        # 언어 명시적으로 설정
        lang_code = request.LANGUAGE_CODE or 'ko'
        translation.activate(lang_code)

        context = {
            'LANGUAGE_CODE': lang_code,
        }

        # 세션에서 저장된 입력값이 있는지 확인
        if 'saved_form_data' in request.session:
            form_data = request.session.get('saved_form_data')
            context['form_data'] = form_data
            del request.session['saved_form_data']

        return render(request, self.template_name, context)

    def post(self, request):
        """POST 요청: 계산 수행 후 결과 페이지로 리다이렉트"""
        try:
            # 언어 설정
            lang_code = set_language_from_url(request)

            # 입력값을 세션에 저장
            form_data = {}

            # 기본 입력값
            form_data['ticker'] = request.POST.get('ticker', '').upper()
            form_data['initial_capital'] = request.POST.get('initial_capital', '0')
            form_data['monthly_investment'] = request.POST.get('monthly_investment', '0')
            form_data['monthly_investment_2'] = request.POST.get('monthly_investment_2', '0')
            form_data['start_date'] = request.POST.get('start_date', '')
            form_data['end_date'] = request.POST.get('end_date', '')

            # 추가 적립 종목
            form_data['investment_ticker_2'] = request.POST.get('investment_ticker_2', '').upper()

            # 조건 설정
            for i in range(1, 4):
                condition_ticker = request.POST.get(f'condition_ticker_{i}', '').upper()
                if condition_ticker:
                    form_data[f'condition_ticker_{i}'] = condition_ticker
                    form_data[f'condition_type_{i}'] = request.POST.get(f'condition_type_{i}', 'specific')
                    form_data[f'percent_{i}'] = request.POST.get(f'percent_{i}', '0')
                    form_data[f'comparison_{i}'] = request.POST.get(f'comparison_{i}', 'above')
                    form_data[f'priority_{i}'] = request.POST.get(f'priority_{i}', 'none')

            # 언어 정보도 저장
            form_data['language'] = lang_code

            # 세션에 저장
            request.session['form_data_for_calculation'] = form_data

            # 결과 페이지로 리다이렉트
            return redirect('stock2_result')

        except Exception as e:
            return render(request, self.template_name, {
                'error': f'입력 처리 중 오류가 발생했습니다: {str(e)}'
            })


class Stock2ResultView(View):
    template_name = 'stock2/stock2_result.html'

    def get(self, request):
        """GET 요청: 계산 결과 표시"""
        try:
            # 언어 설정
            lang_code = set_language_from_url(request)

            # 환율 설정 (언어에 따라 다르게 처리)
            exchange_rate = 1400.0 if lang_code == 'ko' else 1.0

            # 세션에서 저장된 입력값 가져오기
            form_data = request.session.get('form_data_for_calculation', {})
            if not form_data:
                return redirect('stock2')

            # 입력값 추출
            ticker = form_data.get('ticker', '').upper()
            ticker2 = form_data.get('investment_ticker_2', '').upper()

            # 저장된 언어 정보 사용
            saved_lang = form_data.get('language', 'ko')

            # 언어에 따라 금액 처리
            if lang_code == 'ko':
                # 한국어인 경우 원화를 달러로 변환
                initial_capital = float(form_data.get('initial_capital', '0')) / exchange_rate
                monthly_investment = float(form_data.get('monthly_investment', '0')) / exchange_rate
                monthly_investment2 = float(form_data.get('monthly_investment_2', '0')) / exchange_rate

            else:
                # 영어인 경우 그대로 사용
                initial_capital = float(form_data.get('initial_capital', 0))
                monthly_investment = float(form_data.get('monthly_investment', 0))
                monthly_investment2 = float(form_data.get('monthly_investment_2', 0))


            start_date = datetime.strptime(form_data.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(form_data.get('end_date'), '%Y-%m-%d').date()

            # 조건 설정 처리
            conditions = []
            for i in range(1, 4):
                condition_ticker = form_data.get(f'condition_ticker_{i}', '').upper()
                if condition_ticker:
                    condition_type = form_data.get(f'condition_type_{i}', 'specific')
                    percent = float(form_data.get(f'percent_{i}', 0))
                    comparison = form_data.get(f'comparison_{i}', 'above')
                    priority = form_data.get(f'priority_{i}', 'none')

                    conditions.append({
                        'ticker': condition_ticker,
                        'type': condition_type,
                        'percent': percent,
                        'comparison': comparison,
                        'priority': priority
                    })

            # 모든 티커 데이터 최신화
            all_tickers = set()
            all_tickers.add(ticker)
            if ticker2:
                all_tickers.add(ticker2)
            for condition in conditions:
                all_tickers.add(condition['ticker'])

            for t in all_tickers:
                if t:  # 빈 문자열 방지
                    self.update_stock_data_optimized2(t)
                    # 전고점 대비 하락 조건이 있는 티커만 전고점 업데이트
                    if any(cond['type'] == 'high' and cond['ticker'] == t for cond in conditions):
                        self.update_all_time_high(t)

            # 투자 시뮬레이션 실행 (달러 기준)
            result = self.run_investment_simulation(
                ticker, ticker2, initial_capital, monthly_investment, monthly_investment2,
                start_date, end_date, conditions, saved_lang
            )

            # 결과에 입력값과 언어 정보 추가
            result['form_data'] = form_data
            result['current_language'] = lang_code
            result['saved_language'] = saved_lang

            return render(request, self.template_name, result)

        except Exception as e:
            return render(request, 'stock2/stock2.html', {
                'error': f'계산 중 오류가 발생했습니다: {str(e)}'
            })

    def post(self, request):
        """POST 요청: 입력값 유지 요청 처리"""
        # 입력값 유지 체크박스 확인
        save_inputs = request.POST.get('save_inputs') == 'on'

        if save_inputs:
            # 세션에서 입력값 가져와서 저장
            form_data = request.session.get('form_data_for_calculation', {})
            request.session['saved_form_data'] = form_data

        # 입력 페이지로 리다이렉트
        return redirect('stock2')

    # 아래 메서드들은 기존과 동일 (update_stock_data_optimized2, update_all_time_high,
    # check_condition, run_investment_simulation, get_stock_price)
    # ...

    def update_stock_data_optimized2(self, ticker):
        """Twelve Data API를 사용한 최적화된 주식 데이터 업데이트"""
        try:
            # 마지막 업데이트 시간 확인
            last_update = StockData.objects.filter(ticker=ticker).order_by('-updated_at').first()

            if last_update:
                time_diff = timezone.now() - last_update.updated_at
                if time_diff < timedelta(hours=18):
                    return  # 최신 데이터임

            # 기존 데이터의 가장 최근 날짜 확인
            latest_data = StockData.objects.filter(ticker=ticker).order_by('-date').first()

            # Twelve Data API 설정
            api_key = "6a14ee0a3a2145aaa74e444093bb63e3"

            if latest_data:
                # 기존 데이터가 있는 경우: 마지막 데이터 다음날부터 최신 데이터만 가져오기
                start_date = latest_data.date + timedelta(days=1)
                # 시작일이 현재보다 미래인 경우 조정
                if start_date > timezone.now().date():
                    return 0

                # Twelve Data API 호출 (특정 기간 데이터)
                url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&start_date={start_date.strftime('%Y-%m-%d')}&apikey={api_key}"
                update_type = "incremental"
            else:
                # 처음 데이터를 가져오는 경우: 전체 데이터 가져오기
                url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&outputsize=5000&apikey={api_key}"
                update_type = "full"

            # API 요청
            response = requests.get(url)
            data = response.json()

            if 'values' not in data or not data['values']:
                return f"{ticker} 데이터가 없습니다."

            new_data = []
            for value in reversed(data['values']):  # 가장 오래된 데이터부터 처리
                date = datetime.strptime(value['datetime'], '%Y-%m-%d').date()

                # 기존 데이터보다 새로운 데이터만 추가 (중복 방지)
                if not latest_data or date > latest_data.date:
                    new_data.append(StockData(
                        ticker=ticker,
                        date=date,
                        close_price=value['close'],
                        updated_at=timezone.now()
                    ))

            # 배치 처리로 저장
            if new_data:
                StockData.objects.bulk_create(new_data, ignore_conflicts=True)

            if update_type == "incremental":
                return f"{ticker} 데이터 증분 업데이트 완료 ({len(new_data)}개 추가)"
            else:
                return f"{ticker} 데이터 전체 업데이트 완료 ({len(new_data)}개 저장)"

        except Exception as e:
            print(f"Update error for {ticker}: {e}")
            return f"업데이트 실패: {str(e)}"

    def update_all_time_high(self, ticker):
        """전고점 데이터 업데이트"""
        # 마지막 업데이트 시간 확인
        last_update = AllTimeHigh.objects.filter(ticker=ticker).order_by('-updated_at').first()

        if last_update:
            time_diff = timezone.now() - last_update.updated_at
            if time_diff < timedelta(hours=18):
                return  # 최신 데이터임

        # 해당 티커의 모든 주가 데이터 가져오기 (날짜순 정렬)
        stock_data = StockData.objects.filter(ticker=ticker).order_by('date')

        if not stock_data:
            return

        # pandas로 전고점 계산
        dates = []
        close_prices = []

        for data in stock_data:
            dates.append(data.date)
            close_prices.append(float(data.close_price))

        df = pd.DataFrame({'date': dates, 'close_price': close_prices})
        df['all_time_high'] = df['close_price'].expanding().max()

        # 전고점 데이터 저장
        new_records = []
        for _, row in df.iterrows():
            # 이미 존재하는 데이터는 건너뛰기
            if not AllTimeHigh.objects.filter(ticker=ticker, date=row['date']).exists():
                new_records.append(AllTimeHigh(
                    ticker=ticker,
                    date=row['date'],
                    high_price=row['all_time_high'],
                    updated_at=timezone.now()
                ))

        if new_records:
            AllTimeHigh.objects.bulk_create(new_records)

        return f"{ticker} 전고점 데이터 업데이트 완료 ({len(new_records)}개 추가)"

    def check_condition(self, condition, date):
        """조건 확인"""
        ticker = condition['ticker']

        # 해당 날짜의 주가 조회 (가장 가까운 날짜의 데이터)
        stock_data = StockData.objects.filter(
            ticker=ticker, date__lte=date
        ).order_by('-date').first()

        if not stock_data:
            return False

        current_price = float(stock_data.close_price)

        if condition['type'] == 'specific':
            target_price = condition['percent']

            if condition['comparison'] == 'above':
                return current_price >= target_price
            else:  # below
                return current_price <= target_price

        elif condition['type'] == 'high':  # 전고점 대비 하락
            # 해당 날짜의 전고점 조회 (가장 가까운 날짜의 전고점)
            all_time_high_data = AllTimeHigh.objects.filter(
                ticker=ticker, date__lte=date
            ).order_by('-date').first()

            if not all_time_high_data:
                return False

            all_time_high = float(all_time_high_data.high_price)
            # 전고점 대비 하락 계산: 주가 <= 전고점 * (100 - percent) / 100
            target_price = all_time_high * (100 - condition['percent']) / 100

            return current_price <= target_price

        return False

    def run_investment_simulation(self, ticker, ticker2, initial_capital, monthly_investment,
                                  monthly_investment2, start_date, end_date, conditions, language='en'):
        """투자 시뮬레이션 실행 (언어에 따라 통화 처리)"""
        # 언어에 따라 환율 설정
        exchange_rate = 1400.0 if language == 'ko' else 1.0

        # 모든 계산은 달러 기준으로 수행
        cash_usd = initial_capital  # 이미 달러로 변환됨
        shares_held = {}
        if ticker:
            shares_held[ticker] = 0
        if ticker2:
            shares_held[ticker2] = 0

        total_investment = initial_capital  # 달러 기준
        records = []

        # 우선순위별 조건 분류
        priority_conditions = {}
        for condition in conditions:
            if condition['priority'] != 'none':
                priority = int(condition['priority'])
                if priority not in priority_conditions:
                    priority_conditions[priority] = []
                priority_conditions[priority].append(condition)

        # 시작일의 일자가 28일을 넘으면 28일로 조정
        investment_day = min(start_date.day, 28)

        # 투자 시뮬레이션
        current_date = start_date
        while current_date <= end_date:
            # 해당 월의 구매일 설정 (28일 이하로 제한)
            try:
                # 현재 월의 마지막 날 확인
                next_month = current_date.replace(day=1) + relativedelta(months=1)
                last_day_of_month = next_month - timedelta(days=1)

                # 실제 구매일 결정 (28일 또는 월말 중 작은 값)
                actual_investment_day = min(investment_day, last_day_of_month.day)
                investment_date = current_date.replace(day=actual_investment_day)

            except ValueError:
                # 날짜 설정 실패 시 월말로 설정
                investment_date = current_date.replace(day=1) + relativedelta(months=1) - timedelta(days=1)

            if investment_date > end_date:
                break

            # 월적립액 추가 (달러 기준)
            cash_usd += monthly_investment + monthly_investment2
            total_investment += monthly_investment + monthly_investment2

            # 조건에 따른 주식 구매
            purchased = False

            # 우선순위 순으로 조건 확인
            for priority in sorted(priority_conditions.keys()):
                for condition in priority_conditions[priority]:
                    if self.check_condition(condition, investment_date):
                        condition_ticker = condition['ticker']
                        stock_price = self.get_stock_price(condition_ticker, investment_date)

                        if stock_price:
                            # 주가는 달러 기준이므로 그대로 사용
                            shares_to_buy = int(cash_usd // stock_price)  # 소수점 제거

                            if shares_to_buy > 0:
                                if condition_ticker not in shares_held:
                                    shares_held[condition_ticker] = 0

                                shares_held[condition_ticker] += shares_to_buy
                                purchase_amount = shares_to_buy * stock_price
                                cash_usd -= purchase_amount
                                purchased = True

                                # 기록 시 통화 변환
                                purchase_amount_converted = purchase_amount * exchange_rate if language == 'ko' else purchase_amount
                                cash_converted = cash_usd * exchange_rate if language == 'ko' else cash_usd

                                records.append({
                                    'date': investment_date.strftime('%Y-%m-%d'),
                                    'action': f"{condition_ticker} (우선순위{priority})" if language == 'ko' else f"{condition_ticker} (priority {priority})" ,
                                    'price': round(stock_price, 2),
                                    'shares_bought': shares_to_buy,
                                    'shares_held': shares_held[condition_ticker],
                                    'purchase_amount': round(purchase_amount_converted, 0),
                                    'cash': round(cash_converted, 0),
                                    'currency': 'KRW' if language == 'ko' else 'USD',
                                })
                                break
                if purchased:
                    break

            # 조건에 맞는 종목이 없으면 기본 종목 구매
            if not purchased:
                # 첫 번째 종목 구매
                if ticker and monthly_investment > 0:
                    stock_price1 = self.get_stock_price(ticker, investment_date)
                    if stock_price1:
                        shares_to_buy1 = int((cash_usd * (monthly_investment / (
                                    monthly_investment + monthly_investment2))) // stock_price1) if (
                                                                                                                monthly_investment + monthly_investment2) > 0 else 0

                        if shares_to_buy1 > 0:
                            shares_held[ticker] += shares_to_buy1
                            purchase_amount1 = shares_to_buy1 * stock_price1
                            cash_usd -= purchase_amount1

                            purchase_amount1_converted = purchase_amount1 * exchange_rate if language == 'ko' else purchase_amount1
                            cash_converted = cash_usd * exchange_rate if language == 'ko' else cash_usd

                            records.append({
                                'date': investment_date.strftime('%Y-%m-%d'),
                                'action': f"{ticker}",
                                'price': round(stock_price1, 2),
                                'shares_bought': shares_to_buy1,
                                'shares_held': shares_held[ticker],
                                'purchase_amount': round(purchase_amount1_converted, 0),
                                'cash': round(cash_converted, 0),
                                'currency': 'KRW' if language == 'ko' else 'USD',
                            })

                # 두 번째 종목 구매
                if ticker2 and monthly_investment2 > 0:
                    stock_price2 = self.get_stock_price(ticker2, investment_date)
                    if stock_price2 and cash_usd > 0:
                        shares_to_buy2 = int(cash_usd // stock_price2)

                        if shares_to_buy2 > 0:
                            shares_held[ticker2] += shares_to_buy2
                            purchase_amount2 = shares_to_buy2 * stock_price2
                            cash_usd -= purchase_amount2

                            purchase_amount2_converted = purchase_amount2 * exchange_rate if language == 'ko' else purchase_amount2
                            cash_converted = cash_usd * exchange_rate if language == 'ko' else cash_usd

                            records.append({
                                'date': investment_date.strftime('%Y-%m-%d'),
                                'action': f"{ticker2}",
                                'price': round(stock_price2, 2),
                                'shares_bought': shares_to_buy2,
                                'shares_held': shares_held[ticker2],
                                'purchase_amount': round(purchase_amount2_converted, 0),
                                'cash': round(cash_converted, 0),
                                'currency': 'KRW' if language == 'ko' else 'USD',
                            })

            # 다음 달로 이동
            current_date = current_date.replace(day=1) + relativedelta(months=1)

        # 최종 결과 계산
        final_stock_value = 0
        ticker_details = {}

        for t, shares in shares_held.items():
            end_price = self.get_stock_price(t, end_date)
            if end_price:
                ticker_value = shares * end_price  # 달러 기준
                final_stock_value += ticker_value

                # 통화 변환
                ticker_value_converted = ticker_value * exchange_rate if language == 'ko' else ticker_value
                end_price_converted = end_price * exchange_rate if language == 'ko' else end_price

                ticker_details[t] = {
                    'shares': int(shares),
                    'value': round(ticker_value_converted, 0),
                    'price': round(end_price_converted, 2),
                    'value_usd': round(ticker_value, 2),
                    'price_usd': round(end_price, 2)
                }

        # 통화 변환
        final_stock_value_converted = final_stock_value * exchange_rate if language == 'ko' else final_stock_value
        cash_converted = cash_usd * exchange_rate if language == 'ko' else cash_usd
        total_investment_converted = total_investment * exchange_rate if language == 'ko' else total_investment

        final_total_assets = final_stock_value + cash_usd
        final_total_assets_converted = final_total_assets * exchange_rate if language == 'ko' else final_total_assets

        final_profit_rate = ((
                                         final_total_assets - total_investment) / total_investment) * 100 if total_investment > 0 else 0
        final_profit_amount = final_total_assets - total_investment
        final_profit_amount_converted = final_profit_amount * exchange_rate if language == 'ko' else final_profit_amount

        return {
            'records': records,
            'final_result': {
                'final_stock_value': round(final_stock_value_converted, 0),
                'final_cash': round(cash_converted, 0),
                'final_total_assets': round(final_total_assets_converted, 0),
                'final_total_investment': round(total_investment_converted, 0),
                'final_profit_rate': round(final_profit_rate, 2),
                'final_profit_amount': round(final_profit_amount_converted, 0),
                'shares_held': shares_held,
                'ticker_details': ticker_details,
                'currency': 'KRW' if language == 'ko' else 'USD',
                'exchange_rate': exchange_rate if language == 'ko' else 1.0
            }
        }

    def get_stock_price(self, ticker, date):
        """특정 날짜의 주가 조회"""
        stock_data = StockData.objects.filter(
            ticker=ticker, date__lte=date
        ).order_by('-date').first()

        return float(stock_data.close_price) if stock_data else None