"""Little Marvels: dependency-free storefront and inventory service."""
import os, json, sqlite3, secrets, hmac, time, re
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit
from decimal import Decimal, InvalidOperation

ROOT = Path(__file__).parent
DATA = Path(os.environ.get('DATA_DIR', '/workspace/ahmed-business-data'))
DATA.mkdir(parents=True, exist_ok=True)
PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
SESSIONS = {}
ATTEMPTS = {}
AGE_RANGES = ('0–2','3–5','6–8')

def normalize_ages(value):
    if isinstance(value,str):
        if value.startswith('['):
            value=json.loads(value)
        else:
            value=[] if value in ('','unspecified') else [value]
    if not isinstance(value,list) or any(not isinstance(age,str) or age not in AGE_RANGES for age in value):
        raise ValueError('Choose valid age ranges / اختر فئات عمرية صحيحة')
    return [age for age in AGE_RANGES if age in value]

def product_json(row):
    product=dict(row)
    product['ages']=normalize_ages(product['age'])
    # Keep the original single-age field usable by older clients.
    product['age']=product['ages'][0] if product['ages'] else 'unspecified'
    return product

def db():
    c = sqlite3.connect(DATA / 'shop.sqlite3', timeout=20)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, age TEXT NOT NULL, language TEXT NOT NULL, price INTEGER NOT NULL, cost INTEGER NOT NULL, stock INTEGER NOT NULL, emoji TEXT NOT NULL, description TEXT NOT NULL, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, customer TEXT NOT NULL, phone TEXT NOT NULL, address TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new', total INTEGER NOT NULL, cost INTEGER NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS lines(order_id INTEGER REFERENCES orders(id), product_id INTEGER, name TEXT, quantity INTEGER, price INTEGER, cost INTEGER);
        CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY, product_id INTEGER REFERENCES products(id), supplier TEXT NOT NULL, quantity INTEGER NOT NULL, unit_cost INTEGER NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        for col in ('name_en', 'description_en'):
            if col not in [r[1] for r in c.execute('PRAGMA table_info(products)')]:
                c.execute('ALTER TABLE products ADD COLUMN '+col+" TEXT NOT NULL DEFAULT ''")
        if 'image_url' not in [r[1] for r in c.execute('PRAGMA table_info(products)')]:
            c.execute("ALTER TABLE products ADD COLUMN image_url TEXT NOT NULL DEFAULT ''")
        if 'status' not in [r[1] for r in c.execute('PRAGMA table_info(purchases)')]:
            c.execute("ALTER TABLE purchases ADD COLUMN status TEXT NOT NULL DEFAULT 'received'")
        for name,definition in [('whatsapp_opened_at','TEXT'),('payment_token',"TEXT NOT NULL DEFAULT ''"),('delivery_method',"TEXT NOT NULL DEFAULT ''"),('completed_at','TEXT')]:
            if name not in [r[1] for r in c.execute('PRAGMA table_info(orders)')]:
                c.execute('ALTER TABLE orders ADD COLUMN '+name+' '+definition)
        if 'received_at' not in [r[1] for r in c.execute('PRAGMA table_info(purchases)')]:
            c.execute('ALTER TABLE purchases ADD COLUMN received_at TEXT')
        for table in ('products','orders'):
            if 'cost_known' not in [r[1] for r in c.execute('PRAGMA table_info('+table+')')]:
                c.execute('ALTER TABLE '+table+' ADD COLUMN cost_known INTEGER NOT NULL DEFAULT 1')
        if not c.execute('SELECT count(*) FROM products').fetchone()[0]:
            c.executemany('INSERT INTO products(name,category,age,language,price,cost,stock,emoji,description) VALUES(?,?,?,?,?,?,?,?,?)', [
                ('رحلتي مع الحروف','books','3–5','العربية',4500,2200,12,'أ ب ت','كتاب تجريبي للتعرف على الحروف العربية من خلال اللعب والألوان.'),
                ('عالم الحيوانات الصغير','books','0–2','العربية',3900,1800,8,'🦁','منتج تجريبي: رحلة مصوّرة في عالم الحيوانات للصغار.'),
                ('حكايات قبل النوم','books','3–5','العربية',6500,3200,6,'🌙','منتج تجريبي: حكايات قصيرة لوقت هادئ يجمع العائلة.'),
                ('My First Words','books','0–2','English',4200,2000,10,'ABC','Sample product: discover everyday words together.'),
                ('حلّ وامرح','books','6–8','العربية',5800,2800,4,'✏️','منتج تجريبي: أنشطة وألغاز لتطوير التفكير والإبداع.'),
                ('حلقات سيليكون ملونة','toys','0–2','—',7500,4000,5,'🌈','منتج تجريبي. أضف مواصفات العمر والسلامة من المورد قبل البيع.')])
        if os.environ.get('LOAD_BUNDLED_CATALOG','1') != '0':
            from catalog_import import apply_catalog
            apply_catalog(c, ROOT)

def money(value):
    n = round(float(value)*1000)
    if n < 0 or n > 100000000: raise ValueError('قيمة غير صالحة')
    return n

def whole_quantity(value, minimum=0, maximum=100000):
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number!=number.to_integral_value() or not minimum<=number<=maximum:
            raise ValueError('Quantity must be a whole number / الكمية يجب أن تكون عدداً صحيحاً')
        return int(number)
    except InvalidOperation:
        raise ValueError('Quantity must be a whole number / الكمية يجب أن تكون عدداً صحيحاً')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(body)
    def admin(self):
        cookie = SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: return False
        token = cookie.get('session')
        return bool(token and SESSIONS.get(token.value,0) > time.time())
    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/api/settings':
            with db() as c: return self.send(200,dict(c.execute('SELECT key,value FROM settings').fetchall()))
        if path == '/api/products':
            with db() as c:
                rows = [product_json(r) for r in c.execute('SELECT * FROM products WHERE active=1')]
            for r in rows:
                r.pop('cost')
                r.pop('cost_known',None)
            return self.send(200, rows)
        if path.startswith('/api/admin'):
            if not self.admin(): return self.send(401, {'error':'يرجى تسجيل الدخول'})
            if path == '/api/admin/stats':
                from shop_stats import summary
                query=parse_qs(urlsplit(self.path).query)
                try:
                    with db() as c:
                        return self.send(200,summary(c,query.get('period',['all'])[0],query.get('date',[None])[0]))
                except (ValueError,OverflowError):
                    return self.send(400,{'error':'Choose a valid period and date / اختر فترة وتاريخاً صحيحين'})
            with db() as c:
                data = {k:[dict(r) for r in c.execute('SELECT * FROM '+ k + ' ORDER BY id DESC')] for k in ['products','orders','purchases']}
                data['products']=[product_json(p) for p in data['products']]
                for o in data['orders']:
                    o.pop('payment_token',None)
                    o['lines']=[dict(r) for r in c.execute('SELECT * FROM lines WHERE order_id=?',(o['id'],))]
            return self.send(200,data)
        names = {'/':'index.html','/app.js':'app.js','/style.css':'style.css','/brand-logo.png':'brand-logo.png'}
        if re.fullmatch(r'/catalog-images/[a-f0-9]{24}\.webp',path):
            photo=ROOT/path.lstrip('/')
            if not photo.is_file(): return self.send(404,{'error':'Not found'})
            self.send_response(200)
            self.send_header('Content-Type','image/webp')
            self.send_header('Cache-Control','public, max-age=31536000, immutable')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers(); self.wfile.write(photo.read_bytes()); return
        if path not in names: return self.send(404,{'error':'Not found'})
        p = ROOT / names[path]
        self.send_response(200)
        self.send_header('Content-Type', {'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8','png':'image/png'}[p.suffix[1:]])
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(p.read_bytes())
    def do_POST(self):
        try:
            # Reject cross-site writes while allowing same-origin browser requests.
            origin = self.headers.get('Origin')
            if origin and origin not in ('http://'+self.headers.get('Host',''), 'https://'+self.headers.get('Host','')):
                return self.send(403, {'error':'Invalid origin'})
            length = int(self.headers.get('Content-Length','0'))
            if length <= 0: return self.send(400, {'error':'Request body required'})
            if length > 50000: return self.send(413, {'error':'Request too large'})
            a = json.loads(self.rfile.read(length))
            path = self.path
            if path == '/api/login':
                ip=self.client_address[0]; recent=[t for t in ATTEMPTS.get(ip,[]) if t>time.time()-300]
                ATTEMPTS[ip]=recent
                if len(recent)>=10: return self.send(429,{'error':'حاول مرة أخرى بعد خمس دقائق'})
                recent.append(time.time())
                if not PASSWORD or not hmac.compare_digest(str(a.get('password','')).encode(),PASSWORD.encode()): return self.send(401,{'error':'كلمة المرور غير صحيحة'})
                token=secrets.token_urlsafe(32); SESSIONS[token]=time.time()+28800
                self.send_response(200)
                self.send_header('Set-Cookie', f'session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+ ('; Secure' if os.environ.get('COOKIE_SECURE')=='1' else ''))
                self.end_headers(); self.wfile.write(b'{}'); return
            if path == '/api/logout':
                cookie=SimpleCookie(self.headers.get('Cookie',''))
                if 'session' in cookie: SESSIONS.pop(cookie['session'].value,None)
                return self.send(200,{})
            if path not in ('/api/orders','/api/orders/whatsapp') and not self.admin(): return self.send(401,{'error':'يرجى تسجيل الدخول'})
            with db() as c:
                if path == '/api/orders/whatsapp':
                    token=str(a.get('token',''))
                    if not token: return self.send(403,{'error':'Invalid order token'})
                    row=c.execute('SELECT id FROM orders WHERE id=? AND payment_token=?',(int(a['id']),token)).fetchone()
                    if not row: return self.send(403,{'error':'Invalid order token'})
                    c.execute('UPDATE orders SET whatsapp_opened_at=COALESCE(whatsapp_opened_at,CURRENT_TIMESTAMP) WHERE id=?',(int(a['id']),))
                    c.commit()
                    return self.send(200,{'ok':True})
                if path == '/api/orders':
                    payment = dict(c.execute('SELECT key,value FROM settings').fetchall())
                    if not any(payment.get(k) for k in ('transfer_phone', 'bank_account', 'bank_iban')):
                        raise ValueError('Bank transfer is not configured yet / التحويل البنكي غير مفعّل بعد')
                    customer=str(a['customer']).strip(); phone=str(a['phone']).strip(); address=str(a['address']).strip()
                    delivery=str(a.get('delivery_method',''))
                    if delivery not in ('home','office'):
                        raise ValueError('Choose home delivery or delivery-office pickup / اختر التوصيل للمنزل أو الاستلام من مكتب التوصيل')
                    if not customer or not phone or not address or max(map(len,[customer,phone,address]))>1000: raise ValueError('أكمل بيانات التواصل والتوصيل')
                    items=a['items']
                    if not items or len(items)>100: raise ValueError('السلة فارغة')
                    c.execute('BEGIN IMMEDIATE')
                    lines=[]; seen=set()
                    for item in items:
                        pid=int(item['id']); qty=whole_quantity(item['quantity'],1,100)
                        if pid in seen or qty<1 or qty>100: raise ValueError('كمية غير صالحة')
                        seen.add(pid)
                        p=c.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
                        if not p or p['stock']<qty: raise ValueError('الكمية المطلوبة غير متوفرة، حدّث السلة')
                        lines.append((p,qty))
                    total=sum(p['price']*q for p,q in lines); cost=sum(p['cost']*q for p,q in lines)
                    token=secrets.token_urlsafe(32)
                    oid=c.execute('INSERT INTO orders(customer,phone,address,total,cost,payment_token) VALUES(?,?,?,?,?,?)',(customer,phone,address,total,cost,token)).lastrowid
                    c.execute('UPDATE orders SET delivery_method=? WHERE id=?',(delivery,oid))
                    c.execute('UPDATE orders SET cost_known=? WHERE id=?',(int(all(p['cost_known'] for p,q in lines)),oid))
                    for p,q in lines:
                        c.execute('INSERT INTO lines VALUES(?,?,?,?,?,?)',(oid,p['id'],p['name'],q,p['price'],p['cost']))
                        c.execute('UPDATE products SET stock=stock-? WHERE id=?',(q,p['id']))
                    c.commit()
                    return self.send(201,{'id':oid,'total':total,'customer':customer,'phone':phone,'delivery_method':delivery,'address':address,'payment_token':token,'lines':[{'product_id':p['id'],'name':p['name'],'name_en':p['name_en'],'quantity':q,'price':p['price']} for p,q in lines]})
                if path == '/api/admin/archive':
                    c.execute('UPDATE products SET active=? WHERE id=?',(1 if a.get('active') else 0,int(a['id'])))
                elif path == '/api/admin/product':
                    stock=whole_quantity(a['stock'])
                    if stock<0 or stock>100000: raise ValueError('مخزون غير صالح')
                    if not str(a['name']).strip(): raise ValueError('أدخل اسم المنتج')
                    cost_known=str(a.get('cost','')).strip()!=''
                    ages=normalize_ages(a.get('ages',a.get('age','unspecified')))
                    stored_age=ages[0] if len(ages)==1 else json.dumps(ages,ensure_ascii=False) if ages else 'unspecified'
                    language=a.get('language','العربية')
                    if language not in ('العربية','English'):
                        raise ValueError('Choose Arabic or English / اختر العربية أو الإنجليزية')
                    values=(str(a['name'])[:150],a['category'],stored_age,language,money(a['price']),money(a['cost']) if cost_known else 0,stock,str(a['emoji'])[:20],str(a['description'])[:2000])
                    if a.get('id'): c.execute('UPDATE products SET name=?,category=?,age=?,language=?,price=?,cost=?,stock=?,emoji=?,description=? WHERE id=?',(*values,int(a['id'])))
                    else: a['id']=c.execute('INSERT INTO products(name,category,age,language,price,cost,stock,emoji,description) VALUES(?,?,?,?,?,?,?,?,?)',values).lastrowid
                    c.execute('UPDATE products SET name_en=?,description_en=? WHERE id=?',(str(a.get('name_en',''))[:150],str(a.get('description_en',''))[:2000],int(a['id'])))
                    image=str(a.get('image_url','')).strip()
                    if image and not image.startswith('https://') and not re.fullmatch(r'/catalog-images/[a-f0-9]{24}\.webp',image): raise ValueError('Use an HTTPS image URL or a bundled catalog photo')
                    c.execute('UPDATE products SET image_url=? WHERE id=?',(image[:2000],int(a['id'])))
                    c.execute('UPDATE products SET cost_known=? WHERE id=?',(int(cost_known),int(a['id'])))
                elif path == '/api/admin/settings':
                    if 'whatsapp_number' in a:
                        number=str(a['whatsapp_number']).strip().replace(' ','').lstrip('+')
                        if number and (not number.isascii() or not number.isdigit() or not 8<=len(number)<=15 or number.startswith('0')):
                            raise ValueError('Enter WhatsApp number with country code / أدخل رقم واتساب مع رمز الدولة')
                        a['whatsapp_number']=number
                    for key in ['whatsapp_number','transfer_phone','bank_name','bank_holder','bank_account','bank_iban','bank_swift']:
                        if key in a:
                            c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,str(a[key]).strip()[:200]))
                elif path == '/api/admin/purchase':
                    pid=int(a['product_id']); q=whole_quantity(a['quantity'],1); cost=money(a['unit_cost']); supplier=str(a['supplier']).strip()
                    if q<1 or q>100000 or not supplier: raise ValueError('أكمل بيانات الشراء')
                    c.execute('BEGIN IMMEDIATE')
                    p=c.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
                    if not p: raise ValueError('المنتج غير موجود')
                    status=a.get('status','received')
                    if status not in ['ordered','received']: raise ValueError('Invalid purchase status')
                    purchase_id=c.execute('INSERT INTO purchases(product_id,supplier,quantity,unit_cost,status) VALUES(?,?,?,?,?)',(pid,supplier,q,cost,status)).lastrowid
                    if status=='received':
                        c.execute('UPDATE purchases SET received_at=CURRENT_TIMESTAMP WHERE id=?',(purchase_id,))
                        avg=round((p['stock']*p['cost']+q*cost)/(p['stock']+q))
                        c.execute('UPDATE products SET stock=stock+?,cost=?,cost_known=? WHERE id=?',(q,avg,int(p['cost_known'] or p['stock']==0),pid))
                elif path == '/api/admin/receive':
                    c.execute('BEGIN IMMEDIATE')
                    purchase=c.execute("SELECT * FROM purchases WHERE id=? AND status='ordered'",(int(a['id']),)).fetchone()
                    if not purchase: raise ValueError('Purchase already received or missing')
                    p=c.execute('SELECT * FROM products WHERE id=?',(purchase['product_id'],)).fetchone()
                    q=purchase['quantity']; cost=purchase['unit_cost']
                    avg=round((p['stock']*p['cost']+q*cost)/(p['stock']+q))
                    c.execute('UPDATE products SET stock=stock+?,cost=?,cost_known=? WHERE id=?',(q,avg,int(p['cost_known'] or p['stock']==0),p['id']))
                    c.execute("UPDATE purchases SET status='received',received_at=CURRENT_TIMESTAMP WHERE id=?",(purchase['id'],))
                elif path == '/api/admin/status':
                    status=a['status']; oid=int(a['id'])
                    if status not in ['new','confirmed','paid','completed','cancelled']: raise ValueError('حالة غير صالحة')
                    c.execute('BEGIN IMMEDIATE')
                    old=c.execute('SELECT status FROM orders WHERE id=?',(oid,)).fetchone()
                    if not old: raise ValueError('الطلب غير موجود')
                    if status=='completed' and old['status'] not in ('paid','completed') and a.get('payment_verified') is not True:
                        raise ValueError('Verify the bank transfer before completing the order / تحقّق من التحويل أولاً')
                    if old['status']=='cancelled' and status!='cancelled': raise ValueError('أنشئ طلباً جديداً بعد الإلغاء')
                    if status=='cancelled' and old['status']!='cancelled':
                        for line in c.execute('SELECT * FROM lines WHERE order_id=?',(oid,)).fetchall(): c.execute('UPDATE products SET stock=stock+? WHERE id=?',(line['quantity'],line['product_id']))
                    c.execute('UPDATE orders SET status=? WHERE id=?',(status,oid))
                    if status=='completed' and old['status']!='completed':
                        c.execute('UPDATE orders SET completed_at=COALESCE(completed_at,CURRENT_TIMESTAMP) WHERE id=?',(oid,))
                else: return self.send(404,{'error':'Not found'})
            return self.send(200,{'ok':True})
        except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as e:
            return self.send(400,{'error':str(e) or 'بيانات غير صالحة'})

if __name__=='__main__':
    init()
    ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),int(os.environ.get('PORT','8000'))),Handler).serve_forever()
