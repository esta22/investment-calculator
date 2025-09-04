from django import template

register = template.Library()


@register.filter
def format_currency(value):
    """숫자를 만/억 단위로 포맷팅"""
    if value is None:
        return "₩0"

    try:
        value = float(value)
    except (ValueError, TypeError):
        return "₩0"

    if value == 0:
        return "₩0"

    if value >= 100000000:  # 1억 이상
        result = value / 100000000
        return f"₩{result:.1f}억"
    elif value >= 10000:  # 1만 이상
        result = value / 10000
        return f"₩{result:.0f}만"
    else:
        return f"₩{value:,.0f}"


@register.filter
def format_currency_detail(value):
    """상세한 만/억 단위 포맷팅 (2940만2140 형식)"""
    if value is None:
        return "₩0"

    try:
        value = int(value)
    except (ValueError, TypeError):
        return "₩0"

    if value == 0:
        return "₩0"

    if value >= 100000000:  # 1억 이상
        억 = value // 100000000
        만 = (value % 100000000) // 10000
        원 = value % 10000

        result = []
        if 억 > 0:
            result.append(f"{억}억")
        if 만 > 0:
            result.append(f"{만}만")
        if 원 > 0:
            result.append(f"{원}")

        return "₩" + "".join(result)

    elif value >= 10000:  # 1만 이상
        만 = value // 10000
        원 = value % 10000

        result = []
        if 만 > 0:
            result.append(f"{만}만")
        if 원 > 0:
            result.append(f"{원}")

        return "₩" + "".join(result)

    else:
        return f"₩{value:,}"