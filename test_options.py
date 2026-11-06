import http.cookiejar,json,os,secrets,subprocess,tempfile,time,unittest,urllib.request,urllib.error
from pathlib import Path

class OptionTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.password=secrets.token_urlsafe(24)
  cls.proc=subprocess.Popen(['bash','start-production.sh'],cwd=Path(__file__).parent,env={**os.environ,'DATA_DIR':cls.tmp.name,'PORT':'18093','ADMIN_PASSWORD':cls.password,'COOKIE_SECURE':'0','LOAD_BUNDLED_CATALOG':'0'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cls.client=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  for _ in range(60):
   try:cls.call('/api/products');break
   except OSError:time.sleep(.05)
  else:raise RuntimeError('Option test server did not start')
 @classmethod
 def tearDownClass(cls):cls.proc.terminate();cls.proc.wait();cls.tmp.cleanup()
 @classmethod
 def call(cls,path,data=None):
  request=urllib.request.Request('http://127.0.0.1:18093'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
  with cls.client.open(request) as response:return json.load(response)
 def test_option_inventory_prices_orders_and_purchase_receipts(self):
  self.call('/api/login',{'password':self.password});self.call('/api/admin/settings',{'transfer_phone':'90000000'})
  product=self.call('/api/admin')['products'][-1]
  payload={**product,'price':'4.500','cost':'2.000','language':'العربية','options':[{'label':'Boys','stock':2,'price':''},{'label':'Girls','stock':1,'price':'5.500'}]}
  self.call('/api/admin/product',payload)
  p=next(p for p in self.call('/api/products') if p['id']==product['id']);boys,girls=p['options']
  self.assertEqual(p['stock'],3);self.assertNotIn('archived_options',p)
  def order(items):return self.call('/api/orders',{'customer':'Test','phone':'90000001','address':'Muscat','delivery_method':'home','items':items})
  for items in [[{'id':p['id'],'quantity':1}],[{'id':p['id'],'option_id':'forged','quantity':1}],[{'id':p['id'],'option_id':boys['id'],'quantity':3}]]:
   with self.assertRaises(urllib.error.HTTPError):order(items)
  o=order([{'id':p['id'],'option_id':boys['id'],'quantity':2},{'id':p['id'],'option_id':girls['id'],'quantity':1}])
  self.assertEqual(o['total'],14500);self.assertEqual([l['option_label'] for l in o['lines']],['Boys','Girls'])
  self.assertEqual(next(x for x in self.call('/api/products') if x['id']==p['id'])['stock'],0)
  with self.assertRaises(urllib.error.HTTPError):self.call('/api/admin/product',{**payload,'options':[]})
  self.call('/api/admin/status',{'id':o['id'],'status':'cancelled'});self.call('/api/admin/status',{'id':o['id'],'status':'cancelled'})
  p=next(x for x in self.call('/api/products') if x['id']==p['id']);self.assertEqual([x['stock'] for x in p['options']],[2,1])
  self.call('/api/admin/archive',{'id':p['id'],'active':False});self.assertNotIn(p['id'],[x['id'] for x in self.call('/api/products')])
  self.call('/api/admin/archive',{'id':p['id'],'active':True});self.assertIn(p['id'],[x['id'] for x in self.call('/api/products')])
  self.call('/api/admin/purchase',{'product_id':p['id'],'option_id':girls['id'],'supplier':'Test','quantity':3,'unit_cost':'2.000','status':'ordered'})
  purchase=self.call('/api/admin')['purchases'][0];self.call('/api/admin/receive',{'id':purchase['id']})
  p=next(x for x in self.call('/api/products') if x['id']==p['id']);self.assertEqual(p['stock'],6);self.assertEqual(p['options'][1]['stock'],4)
  with self.assertRaises(urllib.error.HTTPError):self.call('/api/admin/receive',{'id':purchase['id']})
  self.call('/api/admin/product',{**payload,'options':[{'id':boys['id'],'label':'Boys renamed','stock':2,'price':''}]})
  private=next(x for x in self.call('/api/admin')['products'] if x['id']==p['id'])
  self.assertEqual(len(private['archived_options']),1);self.assertEqual(private['archived_options'][0]['stock'],4)
  old=next(x for x in self.call('/api/admin')['orders'] if x['id']==o['id']);self.assertEqual(old['lines'][0]['option_label'],'Boys')
  self.assertEqual(next(x for x in self.call('/api/products') if x['id']==p['id'])['stock'],2)

if __name__=='__main__':unittest.main()
