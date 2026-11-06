import unittest,tempfile,subprocess,os,secrets,time,json,urllib.request,urllib.error,http.cookiejar,sqlite3
from pathlib import Path
from promo_codes import init_promos,save_promo,discount_for,allocate_discount


class PromoMathTest(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.executescript('CREATE TABLE orders(id INTEGER);CREATE TABLE lines(order_id INTEGER);')
        init_promos(self.c)
    def tearDown(self):self.c.close()
    def test_rounding_caps_minimum_expiry_and_disabled(self):
        save_promo(self.c,{'code':'welcome','kind':'percent','value':'12.5','minimum':'2','expires_on':'2026-11-06'})
        self.assertEqual(discount_for(self.c,' welcome ',2004,'2026-11-06'),('WELCOME',251))
        with self.assertRaises(ValueError):discount_for(self.c,'WELCOME',1999,'2026-11-06')
        with self.assertRaises(ValueError):discount_for(self.c,'WELCOME',2004,'2026-11-07')
        save_promo(self.c,{'code':'fixed','kind':'fixed','value':'50','active':True})
        self.assertEqual(discount_for(self.c,'fixed',1001)[1],1001)
        save_promo(self.c,{'code':'fixed','kind':'fixed','value':'50','active':False})
        with self.assertRaises(ValueError):discount_for(self.c,'fixed',1001)
        for value in ['NaN','Infinity','-1','101']:
            with self.assertRaises(ValueError):save_promo(self.c,{'code':'bad','kind':'percent','value':value})
    def test_allocation_balances_exactly_without_negative_lines(self):
        for amounts in ([1,1,1],[4500,7800],[0,1001,3]):
            for discount in [0,1,sum(amounts)//3,sum(amounts)]:
                allocations=allocate_discount(amounts,discount)
                self.assertEqual(sum(allocations),discount)
                self.assertTrue(all(0<=d<=a for a,d in zip(amounts,allocations)))


class PromoCheckoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.password=secrets.token_urlsafe(24)
        cls.proc=subprocess.Popen(['python3','server.py'],cwd=Path(__file__).parent,env={**os.environ,'DATA_DIR':cls.tmp.name,'PORT':'18139','ADMIN_PASSWORD':cls.password,'COOKIE_SECURE':'0','LOAD_BUNDLED_CATALOG':'0'},stdout=subprocess.DEVNULL)
        cls.client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        cls.public=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        for _ in range(80):
            try:cls.call('/api/products');break
            except OSError:time.sleep(.05)
        else:raise RuntimeError('Test server failed to start')
    @classmethod
    def tearDownClass(cls):cls.proc.terminate();cls.proc.wait();cls.tmp.cleanup()
    @classmethod
    def call(cls,path,data=None,public=False):
        request=urllib.request.Request('http://127.0.0.1:18139'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
        with (cls.public if public else cls.client).open(request) as response:return json.load(response)
    def test_discount_checkout_snapshot_profit_and_cancel(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.call('/api/admin/promo',{'code':'SAVE10','kind':'percent','value':10},True)
        self.assertEqual(error.exception.code,401)
        self.call('/api/login',{'password':self.password})
        self.call('/api/admin/settings',{'transfer_phone':'99192820'})
        self.call('/api/admin/promo',{'code':'SAVE10','kind':'percent','value':10})
        items=[{'id':1,'quantity':2},{'id':2,'quantity':1}]
        before=self.call('/api/products')
        quote=self.call('/api/promos/quote',{'items':items,'promo_code':'save10','discount':999999,'total':1},True)
        self.assertEqual((quote['subtotal'],quote['discount'],quote['total']),(12900,1290,11610))
        self.assertEqual(self.call('/api/products'),before)
        payload={'customer':'Test','phone':'90000000','address':'Muscat','delivery_method':'home','items':items,'promo_code':'SAVE10','total':1,'discount':999999}
        with self.assertRaises(urllib.error.HTTPError):self.call('/api/orders',{**payload,'promo_code':'UNKNOWN'},True)
        self.assertEqual(self.call('/api/products'),before)
        order=self.call('/api/orders',payload,True)
        self.assertEqual((order['discount'],order['total'],order['promo_code']),(1290,11610,'SAVE10'))
        self.call('/api/admin/promo',{'code':'SAVE10','kind':'percent','value':50,'active':False})
        data=self.call('/api/admin');saved=next(o for o in data['orders'] if o['id']==order['id'])
        self.assertEqual(saved['total'],11610);self.assertEqual(sum(l['discount'] for l in saved['lines']),1290)
        self.call('/api/admin/status',{'id':order['id'],'status':'completed','payment_verified':True})
        stats=self.call('/api/admin/stats');self.assertEqual(stats['sales'],11610);self.assertEqual(stats['gross_profit'],5410)
        insight=self.call('/api/admin/insights');self.assertEqual(sum(p['revenue'] for p in insight['bestsellers']),11610)
        # A no-code order keeps its original total and returns stock on cancellation.
        plain=self.call('/api/orders',{**payload,'promo_code':''},True)
        self.assertEqual((plain['discount'],plain['total']),(0,12900))
        stock=self.call('/api/products')
        self.call('/api/admin/status',{'id':plain['id'],'status':'cancelled'})
        restored=self.call('/api/products')
        self.assertEqual(next(p['stock'] for p in restored if p['id']==1),next(p['stock'] for p in stock if p['id']==1)+2)
