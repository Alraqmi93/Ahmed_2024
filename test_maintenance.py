import json
import sqlite3
import unittest
from datetime import datetime,timezone
from maintenance import apply_requested_stock_reset,ACTION_ID


class MaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute("CREATE TABLE products(id INTEGER PRIMARY KEY,stock INTEGER,options TEXT,deleted INTEGER DEFAULT 0,active INTEGER DEFAULT 1)")
        self.c.execute("CREATE TABLE orders(id INTEGER PRIMARY KEY,total INTEGER)")
        self.c.execute('INSERT INTO orders VALUES(1,12345)')
        options=[{'id':'boys','label':'Boys','stock':2,'active':True},{'id':'girls','label':'Girls','stock':0,'active':True},{'id':'removed','label':'Removed','stock':8,'active':False}]
        self.c.executemany('INSERT INTO products VALUES(?,?,?,?,?)',[(1,7,'[]',0,1),(2,2,json.dumps(options),0,1),(3,0,'[]',0,0),(4,9,'[]',1,0)])
    def tearDown(self):self.c.close()
    def test_once_per_option_including_hidden_and_preserving_deleted(self):
        apply_requested_stock_reset(self.c,True,datetime(2026,11,6,tzinfo=timezone.utc))
        self.assertEqual([r[0] for r in self.c.execute('SELECT stock FROM products ORDER BY id')],[5,10,5,9])
        options=json.loads(self.c.execute('SELECT options FROM products WHERE id=2').fetchone()[0])
        self.assertEqual([o['stock'] for o in options],[5,5,8])
        self.assertEqual(self.c.execute('SELECT total FROM orders').fetchone()[0],12345)
        row=self.c.execute('SELECT * FROM maintenance_runs WHERE action_id=?',(ACTION_ID,)).fetchone()
        self.assertEqual((row['status'],row['products_updated'],row['options_updated']),('applied',3,2))
        self.c.execute('UPDATE products SET stock=17 WHERE id=1')
        self.c.execute("INSERT INTO products VALUES(5,0,'[]',0,1)")
        apply_requested_stock_reset(self.c,True,datetime(2026,11,6,tzinfo=timezone.utc))
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],17)
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=5').fetchone()[0],0)
    def test_not_a_new_store_default_or_a_future_repeat_action(self):
        apply_requested_stock_reset(self.c,False,datetime(2026,11,6,tzinfo=timezone.utc))
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],7)
        apply_requested_stock_reset(self.c,True,datetime(2026,11,6,tzinfo=timezone.utc))
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],7)
        self.c.execute('DELETE FROM maintenance_runs')
        apply_requested_stock_reset(self.c,True,datetime(2026,12,1,tzinfo=timezone.utc))
        self.assertEqual(self.c.execute('SELECT status FROM maintenance_runs').fetchone()[0],'skipped_expired')
        self.assertEqual(self.c.execute('SELECT stock FROM products WHERE id=1').fetchone()[0],7)


if __name__=='__main__':unittest.main()
