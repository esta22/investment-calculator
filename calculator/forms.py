from django import forms

class InvestmentForm(forms.Form):
    ticker = forms.CharField(max_length=10, label='티커')
    initial_capital = forms.DecimalField(max_digits=15, decimal_places=2, label='초기자금')
    monthly_investment = forms.DecimalField(max_digits=15, decimal_places=2, label='월적립액')
    start_date = forms.DateField(label='시작일')
    end_date = forms.DateField(label='종료일')