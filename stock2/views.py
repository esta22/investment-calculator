import requests
import pandas as pd
from django.shortcuts import render, redirect
from django.views import View
from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from calculator.models import StockData
from .models import AllTimeHigh


class Stock2View(View):
    template_name = 'stock2/stock2.html'

    def get(self, request):
        """GET 요청: 입력 폼 표시"""
        return render(request, self.template_name)

    def post(self, request):
        """POST 요청: 계산 수행"""
        try:
            # 기본 입력값 처리
            ticker = request.POST.get('ticker', '').upper()
            ticker2 = request.POST.get('investment_ticker_2', '').upper()
            initial_capital = float(request.POST.get('initial_capital', 0))
            monthly_investment = float(request.POST.get('monthly_investment', 0))
            monthly_investment2 = float(request.POST.get('monthly_investment_2', 0))
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()

            # 모든 티커 데이터 최신화
            all_tickers = set()
            all_tickers.add(ticker)
            if ticker2:
                all_tickers.add(ticker2)

            # 조건 설정 처리
            conditions = []
            for i in range(1, 4):
                condition_ticker = request.POST.get(f'condition_ticker_{i}', '').upper()
                if condition_ticker:
                    condition_type = request.POST.get(f'condition_type_{i}', 'specific')
                    percent = float(request.POST.get(f'percent_{i}', 0))
                    comparison = request.POST.get(f'comparison_{i}', 'above')
                    priority = request.POST.get(f'priority_{i}', 'none')

                    conditions.append({
                        'ticker': condition_ticker,
                        'type': condition_type,
                        'percent': percent,
                        'comparison': comparison,
                        'priority': priority
                    })
                    all_tickers.add(condition_ticker)

            # 모든 티커 데이터 업데이트
            for t in all_tickers:
                if t:  # 빈 문자열 방지
                    self.update_stock_data_optimized2(t)
                    # 전고점 대비 하락 조건이 있는 티커만 전고점 업데이트
                    if any(cond['type'] == 'high' and cond['ticker'] == t for cond in conditions):
                        self.update_all_time_high(t)

            # 투자 시뮬레이션 실행
            result = self.run_investment_simulation(
                ticker, ticker2, initial_capital, monthly_investment, monthly_investment2,
                start_date, end_date, conditions
            )

            return render(request, 'stock2/stock2_result.html', result)

        except Exception as e:
            return render(request, self.template_name, {
                'error': f'계산 중 오류가 발생했습니다: {str(e)}'
            })

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
                                  monthly_investment2, start_date, end_date, conditions):
        """투자 시뮬레이션 실행"""
        exchange_rate = 1400.0
        cash_krw = initial_capital
        shares_held = {}
        if ticker:
            shares_held[ticker] = 0
        if ticker2:
            shares_held[ticker2] = 0

        total_investment = initial_capital
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

            # 월적립액 추가
            cash_krw += monthly_investment + monthly_investment2
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
                            stock_price_krw = stock_price * exchange_rate
                            shares_to_buy = int(cash_krw // stock_price_krw)  # 소수점 제거

                            if shares_to_buy > 0:
                                if condition_ticker not in shares_held:
                                    shares_held[condition_ticker] = 0

                                shares_held[condition_ticker] += shares_to_buy
                                purchase_amount = shares_to_buy * stock_price_krw
                                cash_krw -= purchase_amount
                                purchased = True

                                records.append({
                                    'date': investment_date.strftime('%Y-%m-%d'),
                                    'action': f"{condition_ticker} 구매 (우선순위 {priority})",
                                    'price': round(stock_price, 2),
                                    'shares_bought': shares_to_buy,  # 정수로 저장
                                    'shares_held': shares_held[condition_ticker],  # 정수로 저장
                                    'purchase_amount': round(purchase_amount, 0),
                                    'cash_krw': round(cash_krw, 0),
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
                        stock_price_krw1 = stock_price1 * exchange_rate

                        # === 수정된 부분 시작 ===
                        if monthly_investment + monthly_investment2 > 0:
                            investment_ratio = monthly_investment / (monthly_investment + monthly_investment2)
                        else:
                            investment_ratio = 0  # 또는 1.0으로 설정 가능, 0으로 설정하면 투자되지 않음
                        # === 수정된 부분 끝 ===

                        shares_to_buy1 = int((cash_krw * investment_ratio) // stock_price_krw1)

                        if shares_to_buy1 > 0:
                            shares_held[ticker] += shares_to_buy1
                            purchase_amount1 = shares_to_buy1 * stock_price_krw1
                            cash_krw -= purchase_amount1

                            records.append({
                                'date': investment_date.strftime('%Y-%m-%d'),
                                'action': f"{ticker} 구매",
                                'price': round(stock_price1, 2),
                                'shares_bought': shares_to_buy1,
                                'shares_held': shares_held[ticker],
                                'purchase_amount': round(purchase_amount1, 0),
                                'cash_krw': round(cash_krw, 0),
                            })

                # 두 번째 종목 구매
                if ticker2 and monthly_investment2 > 0:
                    stock_price2 = self.get_stock_price(ticker2, investment_date)
                    if stock_price2 and cash_krw > 0:
                        stock_price_krw2 = stock_price2 * exchange_rate
                        shares_to_buy2 = int(cash_krw // stock_price_krw2)

                        if shares_to_buy2 > 0:
                            shares_held[ticker2] += shares_to_buy2
                            purchase_amount2 = shares_to_buy2 * stock_price_krw2
                            cash_krw -= purchase_amount2

                            records.append({
                                'date': investment_date.strftime('%Y-%m-%d'),
                                'action': f"{ticker2} 구매",
                                'price': round(stock_price2, 2),
                                'shares_bought': shares_to_buy2,
                                'shares_held': shares_held[ticker2],
                                'purchase_amount': round(purchase_amount2, 0),
                                'cash_krw': round(cash_krw, 0),
                            })
            # 다음 달로 이동
            current_date = current_date.replace(day=1) + relativedelta(months=1)

        # 최종 결과 계산
        final_stock_value = 0
        ticker_details = {}

        for t, shares in shares_held.items():
            end_price = self.get_stock_price(t, end_date)
            if end_price:
                ticker_value = shares * end_price * exchange_rate
                final_stock_value += ticker_value
                ticker_details[t] = {
                    'shares': int(shares),
                    'value': round(ticker_value, 0),
                    'price': round(end_price, 2)
                }

        final_total_assets = final_stock_value + cash_krw
        final_profit_rate = ((
                                     final_total_assets - total_investment) / total_investment) * 100 if total_investment > 0 else 0
        final_profit_amount = final_total_assets - total_investment

        return {
            'records': records,
            'final_result': {
                'final_stock_value': round(final_stock_value, 0),
                'final_cash': round(cash_krw, 0),
                'final_total_assets': round(final_total_assets, 0),
                'final_total_investment': round(total_investment, 0),
                'final_profit_rate': round(final_profit_rate, 2),
                'final_profit_amount': round(final_profit_amount, 0),
                'shares_held': shares_held,
                'ticker_details': ticker_details
            }
        }

    def get_stock_price(self, ticker, date):
        """특정 날짜의 주가 조회"""
        stock_data = StockData.objects.filter(
            ticker=ticker, date__lte=date
        ).order_by('-date').first()

        return float(stock_data.close_price) if stock_data else None