"""Observed sales rankings and monthly patterns from completed order lines."""
from datetime import datetime, timezone
from shop_stats import OMAN, period_bounds


def insights(connection,period='all',anchor=None,history_year='all'):
    start,end=period_bounds(period,anchor)
    params=()
    window=''
    if start:
        def utc(day):return datetime.combine(day,datetime.min.time(),OMAN).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        window=' AND COALESCE(o.completed_at,o.created)>=? AND COALESCE(o.completed_at,o.created)<?'
        params=(utc(start),utc(end))
    best=connection.execute('''SELECT l.product_id,COALESCE(p.name,MAX(l.name)) AS name,
        SUM(l.quantity) AS units,SUM(l.quantity*l.price) AS revenue,COUNT(DISTINCT o.id) AS orders
        FROM lines l JOIN orders o ON o.id=l.order_id LEFT JOIN products p ON p.id=l.product_id
        WHERE o.status='completed' '''+window+''' GROUP BY l.product_id ORDER BY units DESC,revenue DESC,l.product_id LIMIT 10''',params).fetchall()
    # Oman has a UTC+04:00 calendar; SQLite groups each completed sale in that local month.
    stamp="datetime(COALESCE(o.completed_at,o.created),'+4 hours')"
    years=[r[0] for r in connection.execute("SELECT DISTINCT strftime('%Y',"+stamp+") FROM orders o JOIN lines l ON l.order_id=o.id WHERE o.status='completed' ORDER BY 1 DESC") if r[0]]
    history_params=()
    history_window=''
    if history_year!='all':
        year=int(history_year)
        if not 1900<=year<=9998:raise ValueError('Invalid analysis year')
        history_window=" AND strftime('%Y',"+stamp+")=?"
        history_params=(str(year),)
    rows=connection.execute('''SELECT l.product_id,COALESCE(p.name,MAX(l.name)) AS name,
        strftime('%Y-%m','''+stamp+''') AS month_key,SUM(l.quantity) AS units,
        SUM(l.quantity*l.price) AS revenue,COUNT(DISTINCT o.id) AS orders
        FROM lines l JOIN orders o ON o.id=l.order_id LEFT JOIN products p ON p.id=l.product_id
        WHERE o.status='completed' '''+history_window+''' GROUP BY l.product_id,month_key ORDER BY month_key''',history_params).fetchall()
    products={};monthly=[0]*12;observed_months=set()
    for row in rows:
        if not row['month_key']:continue
        year,month=map(int,row['month_key'].split('-'))
        p=products.setdefault(row['product_id'],{'product_id':row['product_id'],'name':row['name'],'months':[0]*12,'units':0,'revenue':0,'orders':0,'years':set(),'observed_months':set()})
        p['months'][month-1]+=row['units'];p['units']+=row['units'];p['revenue']+=row['revenue'];p['orders']+=row['orders'];p['years'].add(year);p['observed_months'].add(row['month_key'])
        monthly[month-1]+=row['units'];observed_months.add(row['month_key'])
    for p in products.values():
        peak=max(p['months'])
        p['peak_months']=[i+1 for i,n in enumerate(p['months']) if n==peak and n>0]
        p['peak_units']=peak;p['peak_share']=round(100*peak/p['units'],1) if p['units'] else 0
        p['years']=sorted(p['years']);p['observed_month_count']=len(p.pop('observed_months'))
        p['limited_history']=len(p['years'])<2 or p['observed_month_count']<3
    return {'bestsellers':[dict(r) for r in best],'seasonal_products':sorted(products.values(),key=lambda p:(-p['units'],p['product_id'])),
        'monthly_totals':monthly,'years_available':years,'history_year':str(history_year),
        'observed_month_count':len(observed_months),'period':period,'timezone':'Asia/Muscat'}
