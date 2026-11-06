import json
import sqlite3
import unittest
from datetime import datetime,timezone
from maintenance import apply_seven_books_stock_reset,SUPPLIER_STOCK_SOURCES,SUPPLIER_STOCK_ACTION


class SupplierStockTest(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute("CREATE TABLE products(id INTEGER PRIMARY KEY,source_url TEXT,stock INTEGER,options TEXT DEFAULT '[]',deleted INTEGER DEFAULT 0,active INTEGER DEFAULT 1,price INTEGER DEFAULT 1234)")
        for source in SUPPLIER_STOCK_SOURCES:self.c.execute('INSERT INTO products(source_url,stock) VALUES(?,0)',(source,))
        self.c.execute("INSERT INTO products(source_url,stock) VALUES('https://other.example/product',17)")
        self.now=datetime(2026,11,6,tzinfo=timezone.utc)
    def tearDown(self):self.c.close()
    def test_only_seven_books_once(self):
        self.c.execute('UPDATE products SET active=0 WHERE id=1')
        apply_seven_books_stock_reset(self.c,True,self.now)
        self.assertEqual([r[0] for r in self.c.execute('SELECT stock FROM products ORDER BY id')],[5]*7+[17])
        self.assertEqual(self.c.execute('SELECT active,price FROM products WHERE id=1').fetchone()[:],(0,1234))
        self.assertEqual(self.c.execute('SELECT products_updated FROM maintenance_runs WHERE action_id=?',(SUPPLIER_STOCK_ACTION,)).fetchone()[0],7)
        self.c.execute('UPDATE products SET stock=3 WHERE id=1')
        self.c.execute("INSERT INTO products(source_url,stock) VALUES('new-product',0)")
        apply_seven_books_stock_reset(self.c,True,self.now)
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],3)
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=9').fetchone()[0],0)
    def test_options_deleted_and_new_store(self):
        options=[{'active':True,'stock':1},{'active':True,'stock':0},{'active':False,'stock':8}]
        self.c.execute('UPDATE products SET options=? WHERE id=1',(json.dumps(options),))
        self.c.execute('UPDATE products SET deleted=1 WHERE id=2')
        apply_seven_books_stock_reset(self.c,True,self.now)
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],10)
        self.assertEqual([o['stock'] for o in json.loads(self.c.execute('SELECT options FROM products WHERE id=1').fetchone()[0])],[5,5,8])
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=2').fetchone()[0],0)
        self.c.execute('DELETE FROM maintenance_runs')
        self.c.execute('UPDATE products SET stock=0')
        apply_seven_books_stock_reset(self.c,False,self.now)
        self.assertEqual(self.c.execute('SELECT sum(stock) FROM products').fetchone()[0],0)


if __name__=='__main__':unittest.main()
