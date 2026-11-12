import json,sqlite3,tempfile,unittest
from pathlib import Path
from maintenance import unhide_uploaded_batch_once


class BatchVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute('CREATE TABLE products(id INTEGER PRIMARY KEY,source_url TEXT,source_sku TEXT,name TEXT,name_en TEXT,active INTEGER,deleted INTEGER,stock INTEGER,price INTEGER)')
        self.c.executemany('INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?)',[(1,'https://shop.example/products/one','sku1','One','',0,0,2,777),(2,'https://shop.example/products/two','sku2','Two','',1,0,0,888),(3,'https://shop.example/products/deleted','sku3','Deleted','',0,1,9,999),(4,'https://shop.example/products/unrelated','sku4','Unrelated','',0,0,4,444)])
        products=[{'source_url':row[0],'source_sku':row[1],'name':row[2]} for row in self.c.execute('SELECT source_url,source_sku,name FROM products WHERE id<=3')]
        products.append({'source_url':'https://shop.example/products/missing','name':'Missing'})
        self.manifest={'action_id':'test-unhide-batch','products':products}
        (self.root/'unhide-batch-20261112.json').write_text(json.dumps(self.manifest))
    def tearDown(self):self.c.close();self.temp.cleanup()
    def test_unhide_only_targeted_hidden_items_once(self):
        unhide_uploaded_batch_once(self.c,self.root,True)
        self.assertEqual([tuple(r) for r in self.c.execute('SELECT active,deleted,stock,price FROM products ORDER BY id')],[(1,0,2,777),(1,0,0,888),(0,1,9,999),(0,0,4,444)])
        self.assertEqual(self.c.execute('SELECT products_updated FROM maintenance_runs').fetchone()[0],1)
        self.c.execute('UPDATE products SET active=0 WHERE id=1')
        unhide_uploaded_batch_once(self.c,self.root,True)
        self.assertEqual(self.c.execute('SELECT active FROM products WHERE id=1').fetchone()[0],0)
    def test_no_new_store_default(self):
        unhide_uploaded_batch_once(self.c,self.root,False)
        self.assertEqual(self.c.execute('SELECT active FROM products WHERE id=1').fetchone()[0],0)
        self.assertEqual(self.c.execute('SELECT status FROM maintenance_runs').fetchone()[0],'skipped_new_store')
