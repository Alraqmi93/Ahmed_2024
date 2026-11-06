"""Named product options with stable IDs, separate available stock and optional prices."""
import json
import uuid


def read_options(product):
    return json.loads(product['options']) if isinstance(product['options'],str) else product['options']


def active_options(product):
    return [o for o in read_options(product) if o.get('active',True)]


def save_options(connection,pid,items,quantity,money):
    if not isinstance(items,list) or len(items)>1000:raise ValueError('Invalid product options')
    product=connection.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
    previous={o['id']:o for o in read_options(product)}
    result=[];ids=set();labels=set()
    for item in items:
        label=str(item.get('label','')).strip()
        if not label or len(label)>150 or label.casefold() in labels:
            raise ValueError('Each option needs a unique name / أدخل اسماً مختلفاً لكل خيار')
        labels.add(label.casefold())
        oid=str(item.get('id') or uuid.uuid4().hex)
        if oid in ids or (item.get('id') and oid not in previous):raise ValueError('Invalid option ID')
        ids.add(oid)
        price=None if item.get('price') in ('',None) else money(item['price'])
        result.append({'id':oid,'label':label,'stock':quantity(item.get('stock',0)),'price':price,'active':True})
    for oid,o in previous.items():
        if oid not in ids and o.get('active',True) and connection.execute("SELECT 1 FROM lines JOIN orders ON orders.id=lines.order_id WHERE option_id=? AND orders.status IN ('new','confirmed','paid') LIMIT 1",(oid,)).fetchone():
            raise ValueError('Complete or cancel open orders before removing this option / أكمل أو ألغِ الطلبات المفتوحة قبل إزالة الخيار')
    result += [{**o,'active':False} for oid,o in previous.items() if oid not in ids]
    total=sum(o['stock'] for o in result if o['active'])
    if total>100000:raise ValueError('Total option stock is too large')
    connection.execute('UPDATE products SET options=? WHERE id=?',(json.dumps(result,ensure_ascii=False),pid))
    if items:connection.execute('UPDATE products SET stock=? WHERE id=?',(total,pid))
    elif any(o.get('active',True) for o in previous.values()):
        connection.execute('UPDATE products SET stock=0 WHERE id=?',(pid,))


def selected_option(product,oid):
    options=active_options(product)
    if options:
        selected=next((o for o in options if o['id']==oid),None)
        if not selected:raise ValueError('Choose an available product option / اختر أحد خيارات المنتج')
        return selected
    if oid:raise ValueError('This option is no longer available / هذا الخيار غير متوفر')
    return None


def adjust_stock(connection,pid,oid,delta,restock=False):
    product=connection.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
    options=read_options(product)
    if not oid:
        if restock and any(o.get('active',True) for o in options):
            # A legacy unconfigured order cannot be assigned to a color/gender automatically.
            returned=next((o for o in options if o['id']=='unassigned-return'),None)
            if not returned:
                returned={'id':'unassigned-return','label':'Returned stock — assign an option / مرتجع غير محدد','stock':0,'price':None,'active':False}
                options.append(returned)
            returned['stock']+=delta
            connection.execute('UPDATE products SET options=? WHERE id=?',(json.dumps(options,ensure_ascii=False),pid))
            return
        if product['stock']+delta<0:raise ValueError('Insufficient stock')
        connection.execute('UPDATE products SET stock=stock+? WHERE id=?',(delta,pid));return
    option=next((o for o in options if o['id']==oid),None)
    if not option or (not restock and not option.get('active',True)):
        raise ValueError('Option is unavailable')
    if option['stock']+delta<0:raise ValueError('Insufficient option stock')
    option['stock']+=delta
    connection.execute('UPDATE products SET options=? WHERE id=?',(json.dumps(options,ensure_ascii=False),pid))
    if any(o.get('active',True) for o in options):
        connection.execute('UPDATE products SET stock=? WHERE id=?',(sum(o['stock'] for o in options if o.get('active',True)),pid))
