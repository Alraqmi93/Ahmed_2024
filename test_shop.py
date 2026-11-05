import unittest, tempfile, subprocess, os, secrets, time, json, urllib.request, urllib.error, http.cookiejar
from pathlib import Path

class ShopTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(); cls.password=secrets.token_urlsafe(24)
        command=['bash','start-production.sh'] if os.environ.get('TEST_PRODUCTION') else ['python3','server.py']
        cls.proc=subprocess.Popen(command,cwd=Path(__file__).parent,env={**os.environ,'DATA_DIR':cls.tmp.name,'PORT':'18080','ADMIN_PASSWORD':cls.password,'COOKIE_SECURE':'0','LOAD_BUNDLED_CATALOG':'0'},stdout=subprocess.DEVNULL)
        cls.client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        for _ in range(60):
            try: cls.call('/api/products'); break
            except OSError: time.sleep(.05)
        else: raise RuntimeError('Server failed to start')
    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.wait(); cls.tmp.cleanup()
    @classmethod
    def call(cls,path,data=None):
        req=urllib.request.Request('http://127.0.0.1:18080'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
        with cls.client.open(req) as r:return json.load(r)
    def test_business_flow(self):
        products=self.call('/api/products'); self.assertEqual(len(products),6); self.assertNotIn('cost',products[0])
        with self.assertRaises(urllib.error.HTTPError) as e:self.call('/api/admin')
        self.assertEqual(e.exception.code,401)
        self.call('/api/login',{'password':self.password})
        self.call('/api/admin/settings',{'transfer_phone':'90000000','bank_name':'TEST ONLY','bank_holder':'TEST ONLY','bank_account':''})
        self.call('/api/admin/settings',{'bank_swift':'TESTSWIFT','bank_iban':'TESTIBAN'})
        settings=self.call('/api/settings')
        self.assertEqual(settings['transfer_phone'],'90000000')
        self.assertEqual(settings['bank_swift'],'TESTSWIFT')
        self.assertEqual(settings['bank_iban'],'TESTIBAN')
        self.call('/api/admin/settings',{'whatsapp_number':'+968 90000000'})
        self.assertEqual(self.call('/api/settings')['whatsapp_number'],'96890000000')
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/api/admin/settings',{'whatsapp_number':'https://invalid.example'})
        self.call('/api/admin/settings',{'bank_iban':''})
        p=products[0]
        order=self.call('/api/orders',{'customer':'Test','phone':'90000000','address':'Test address','delivery_method':'home','items':[{'id':p['id'],'quantity':2}]})
        self.assertEqual(order['delivery_method'],'home')
        self.assertEqual(order['lines'][0]['quantity'],2)
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/api/orders/whatsapp',{'id':order['id'],'token':'wrong'})
        self.call('/api/orders/whatsapp',{'id':order['id'],'token':order['payment_token']})
        saved=self.call('/api/admin')['orders'][0]
        self.assertEqual(saved['delivery_method'],'home')
        self.assertTrue(saved['whatsapp_opened_at'])
        self.assertNotIn('payment_token',saved)
        self.assertEqual(saved['status'],'new')
        self.assertEqual(order['total'],p['price']*2)
        self.assertEqual(self.call('/api/products')[0]['stock'],p['stock']-2)
        with self.assertRaises(urllib.error.HTTPError):self.call('/api/admin/status',{'id':order['id'],'status':'completed'})
        self.call('/api/admin/status',{'id':order['id'],'status':'paid'})
        self.call('/api/admin/status',{'id':order['id'],'status':'completed'})
        o=self.call('/api/admin')['orders'][0]; self.assertEqual(o['status'],'completed'); self.assertGreater(o['total']-o['cost'],0)
        self.call('/api/admin/status',{'id':order['id'],'status':'cancelled'})
        self.call('/api/admin/status',{'id':order['id'],'status':'cancelled'})
        self.assertEqual(self.call('/api/products')[0]['stock'],p['stock'])
        with self.assertRaises(urllib.error.HTTPError):self.call('/api/orders',{'customer':'Test','phone':'90000000','address':'Test','delivery_method':'office','items':[{'id':p['id'],'quantity':100}]})
        self.assertEqual(self.call('/api/products')[0]['stock'],p['stock'])
        self.call('/api/admin/purchase',{'product_id':p['id'],'supplier':'Test supplier','quantity':3,'unit_cost':'2.5'})
        self.assertEqual(self.call('/api/products')[0]['stock'],p['stock']+3)
        self.call('/api/admin/purchase',{'product_id':p['id'],'supplier':'Pending supplier','quantity':4,'unit_cost':'2','status':'ordered'})
        self.assertEqual(self.call('/api/products')[0]['stock'],p['stock']+3)
        purchase=self.call('/api/admin')['purchases'][0]
        self.call('/api/admin/receive',{'id':purchase['id']})
        self.assertEqual(self.call('/api/products')[0]['stock'],p['stock']+7)
        with self.assertRaises(urllib.error.HTTPError):self.call('/api/admin/receive',{'id':purchase['id']})
        self.assertEqual(self.call('/api/products')[0]['stock'],p['stock']+7)
        self.call('/api/admin/product',{'name':'عربي','name_en':'English title','description':'وصف','description_en':'Description','category':'books','age':'3–5','language':'Arabic / English','price':'1.500','cost':'0.500','stock':2,'emoji':'📚'})
        self.assertEqual(self.call('/api/admin')['products'][0]['name_en'],'English title')
        new=self.call('/api/admin')['products'][0]
        self.call('/api/admin/archive',{'id':new['id'],'active':False})
        self.assertNotIn(new['id'],[x['id'] for x in self.call('/api/products')])
        self.call('/api/admin/archive',{'id':new['id'],'active':True})
        self.assertIn(new['id'],[x['id'] for x in self.call('/api/products')])
        self.call('/api/admin/product',{**new,'price':'1.5','cost':'','stock':1})
        unknown=self.call('/api/orders',{'customer':'Unknown cost','phone':'90000000','address':'Test','delivery_method':'office','items':[{'id':new['id'],'quantity':1}]})
        self.call('/api/admin/status',{'id':unknown['id'],'status':'completed','payment_verified':True})
        self.assertEqual(self.call('/api/admin')['orders'][0]['cost_known'],0)
        self.assertEqual(self.call('/api/admin')['orders'][0]['delivery_method'],'office')
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/api/orders',{'customer':'Missing preference','phone':'90000000','address':'Test','items':[{'id':p['id'],'quantity':1}]})
        self.call('/api/logout',{})
        with self.assertRaises(urllib.error.HTTPError):self.call('/api/admin')

if __name__=='__main__':unittest.main()
