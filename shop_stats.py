"""Financial summaries in Oman calendar periods, using captured order costs."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

OMAN = ZoneInfo('Asia/Muscat')


def period_bounds(period='all', anchor=None):
    if period == 'all':
        return None, None
    if period not in ('day','week','month','year'):
        raise ValueError('Invalid statistics period')
    today = datetime.now(OMAN).date()
    if period == 'month':
        start = date.fromisoformat((anchor or today.strftime('%Y-%m'))+'-01')
        end = date(start.year+1,1,1) if start.month==12 else date(start.year,start.month+1,1)
    elif period == 'year':
        year = int(anchor or today.year)
        start, end = date(year,1,1), date(year+1,1,1)
    else:
        start = date.fromisoformat(anchor) if anchor else today
        if period == 'week':
            start -= timedelta(days=(start.weekday()+1)%7)  # Sunday–Saturday.
        end = start + timedelta(days=7 if period=='week' else 1)
    return start, end


def summary(connection, period='all', anchor=None):
    start,end = period_bounds(period,anchor)
    parameters = ()
    sales_window = purchase_window = ''
    if start:
        def utc(day):
            return datetime.combine(day,datetime.min.time(),OMAN).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        parameters = (utc(start),utc(end))
        sales_window = ' AND COALESCE(completed_at,created)>=? AND COALESCE(completed_at,created)<?'
        purchase_window = ' AND COALESCE(received_at,created)>=? AND COALESCE(received_at,created)<?'
    result = connection.execute('''SELECT
        COALESCE(SUM(total),0) AS sales,
        COALESCE(SUM(CASE WHEN cost_known=1 THEN cost ELSE 0 END),0) AS product_cost,
        COALESCE(SUM(CASE WHEN cost_known=1 THEN total-cost ELSE 0 END),0) AS gross_profit,
        COUNT(*) AS completed_orders,
        COALESCE(SUM(CASE WHEN cost_known=0 THEN 1 ELSE 0 END),0) AS unknown_cost_orders,
        COALESCE(SUM(CASE WHEN completed_at IS NULL THEN 1 ELSE 0 END),0) AS legacy_order_dates
        FROM orders WHERE status='completed' '''+sales_window,parameters).fetchone()
    purchases = connection.execute("SELECT COALESCE(SUM(quantity*unit_cost),0),COALESCE(SUM(CASE WHEN received_at IS NULL THEN 1 ELSE 0 END),0) FROM purchases WHERE status='received' "+purchase_window,parameters).fetchone()
    return {**dict(result),'supplier_purchases':purchases[0],'legacy_purchase_dates':purchases[1],'period':period,
            'start_date':start.isoformat() if start else None,
            'end_date':(end-timedelta(days=1)).isoformat() if end else None,
            'timezone':'Asia/Muscat','week_starts_on':'Sunday'}
