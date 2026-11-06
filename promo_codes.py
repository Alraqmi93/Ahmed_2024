"""Server-authoritative, single-code order discounts in integer baisa."""
import re
from datetime import datetime,date
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from zoneinfo import ZoneInfo


def init_promos(c):
    c.execute('''CREATE TABLE IF NOT EXISTS promos(code TEXT PRIMARY KEY,kind TEXT NOT NULL,value INTEGER NOT NULL,minimum INTEGER NOT NULL DEFAULT 0,expires_on TEXT NOT NULL DEFAULT '',active INTEGER NOT NULL DEFAULT 1)''')
    for name,definition in [('promo_code',"TEXT NOT NULL DEFAULT ''"),('discount','INTEGER NOT NULL DEFAULT 0'),('subtotal','INTEGER NOT NULL DEFAULT 0')]:
        if name not in [r[1] for r in c.execute('PRAGMA table_info(orders)')]:c.execute('ALTER TABLE orders ADD COLUMN '+name+' '+definition)
    if 'discount' not in [r[1] for r in c.execute('PRAGMA table_info(lines)')]:c.execute('ALTER TABLE lines ADD COLUMN discount INTEGER NOT NULL DEFAULT 0')


def code_value(value):
    code=str(value or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9_-]{3,32}',code):raise ValueError('Use a code with 3–32 letters, numbers, - or _ / استخدم رمزاً من ٣ إلى ٣٢ حرفاً إنجليزياً أو رقماً')
    return code


def amount(value,scale=1000):
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number<0 or number>100000:raise ValueError()
        return int((number*scale).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError,OverflowError):raise ValueError('Invalid discount amount / قيمة خصم غير صالحة')


def save_promo(c,data):
    code=code_value(data.get('code'));kind=data.get('kind')
    if kind not in ('percent','fixed'):raise ValueError('Choose percentage or fixed discount / اختر نوع الخصم')
    value=amount(data.get('value'),100 if kind=='percent' else 1000)
    if value<=0 or (kind=='percent' and value>10000):raise ValueError('Enter a positive discount, at most 100% / أدخل خصماً موجباً لا يزيد عن ١٠٠٪')
    minimum=amount(data.get('minimum',0));expires=str(data.get('expires_on',''))
    if expires:expires=date.fromisoformat(expires).isoformat()
    active=data.get('active',True)
    if type(active) is not bool:raise ValueError('Invalid active status')
    c.execute('''INSERT INTO promos(code,kind,value,minimum,expires_on,active) VALUES(?,?,?,?,?,?)
        ON CONFLICT(code) DO UPDATE SET kind=excluded.kind,value=excluded.value,minimum=excluded.minimum,expires_on=excluded.expires_on,active=excluded.active''',(code,kind,value,minimum,expires,int(active)))


def discount_for(c,code,subtotal,today=None):
    if not str(code or '').strip():return '',0
    code=code_value(code);row=c.execute('SELECT * FROM promos WHERE code=?',(code,)).fetchone()
    today=today or datetime.now(ZoneInfo('Asia/Muscat')).date().isoformat()
    if not row or not row['active'] or (row['expires_on'] and row['expires_on']<today):raise ValueError('Promo code is invalid, inactive or expired / رمز الخصم غير صالح أو منتهي')
    if subtotal<row['minimum']:raise ValueError('Cart does not meet the minimum for this code / لم تصل السلة للحد الأدنى لهذا الرمز')
    discount=(subtotal*row['value']+5000)//10000 if row['kind']=='percent' else row['value']
    return code,min(subtotal,discount)


def allocate_discount(amounts,discount):
    subtotal=sum(amounts)
    if not subtotal:return [0]*len(amounts)
    allocations=[discount*value//subtotal for value in amounts]
    remainder=discount-sum(allocations)
    ranked=sorted(range(len(amounts)),key=lambda i:discount*amounts[i]%subtotal,reverse=True)
    for i in ranked[:remainder]:allocations[i]+=1
    return allocations
