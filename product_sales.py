"""Completed product-unit sales over Oman calendar date ranges."""
from datetime import date,datetime,timedelta,timezone
from shop_stats import OMAN,period_bounds


def product_sales(connection,product_id,period='all',anchor=None,start_date=None,end_date=None):
    pid=int(product_id)
    if pid<1:raise ValueError('Choose a product / اختر منتجاً')
    product=connection.execute('SELECT id,name,name_en FROM products WHERE id=?',(pid,)).fetchone()
    if product is None:raise ValueError('Product not found / المنتج غير موجود')
    if period=='custom':
        start=date.fromisoformat(start_date or '')
        inclusive_end=date.fromisoformat(end_date or '')
        if inclusive_end<start:raise ValueError('End date must be on or after start date / تاريخ النهاية يجب ألا يسبق البداية')
        end=inclusive_end+timedelta(days=1)
    else:start,end=period_bounds(period,anchor)
    parameters=[pid];window=''
    if start:
        def utc(day):return datetime.combine(day,datetime.min.time(),OMAN).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        window=' AND COALESCE(o.completed_at,o.created)>=? AND COALESCE(o.completed_at,o.created)<?'
        parameters.extend((utc(start),utc(end)))
    result=connection.execute('''SELECT COALESCE(SUM(l.quantity),0) AS units,
        COUNT(DISTINCT o.id) AS orders,
        COALESCE(SUM(l.quantity*l.price-l.discount),0) AS revenue,
        COUNT(DISTINCT CASE WHEN o.completed_at IS NULL THEN o.id END) AS legacy_order_dates
        FROM lines l JOIN orders o ON o.id=l.order_id
        WHERE l.product_id=? AND o.status='completed' '''+window,parameters).fetchone()
    return {**dict(result),'product_id':pid,'name':product['name'],'name_en':product['name_en'],
        'period':period,'start_date':start.isoformat() if start else None,
        'end_date':(end-timedelta(days=1)).isoformat() if end else None,'timezone':'Asia/Muscat'}
