import sqlite3
import unittest
from sales_insights import insights


class InsightsTest(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.executescript('''CREATE TABLE products(id INTEGER PRIMARY KEY,name TEXT);
            CREATE TABLE orders(id INTEGER PRIMARY KEY,status TEXT,created TEXT,completed_at TEXT);
            CREATE TABLE lines(order_id INTEGER,product_id INTEGER,name TEXT,quantity INTEGER,price INTEGER);
            INSERT INTO products VALUES(1,'Renamed product'),(2,'Second product');''')
        for oid,status,stamp in [(1,'completed','2026-05-31 20:00:00'),(2,'completed','2025-06-15 00:00:00'),
                (3,'completed','2026-07-01 00:00:00'),(4,'completed','2026-05-31 19:59:59'),
                (5,'cancelled','2026-06-01 00:00:00'),(6,'new','2026-06-01 00:00:00'),
                (7,'paid','2026-06-01 00:00:00'),(8,'completed','2026-12-01 00:00:00')]:
            self.c.execute('INSERT INTO orders VALUES(?,?,?,?)',(oid,status,stamp,stamp))
        self.c.executemany('INSERT INTO lines VALUES(?,?,?,?,?)',[
            (1,1,'Old product name',3,1000),(1,1,'Old product name',2,1500),
            (1,2,'Second product',2,2000),(2,1,'Old product name',2,1000),
            (3,1,'Old product name',1,1000),(4,1,'Old product name',1,1000),
            (5,1,'Cancelled',100,1000),(6,2,'Pending',100,1000),(7,2,'Unfulfilled',100,1000),
            (8,2,'Second product',2,2000)])
    def tearDown(self):self.c.close()
    def test_rankings_combine_options_and_exclude_incomplete_orders(self):
        result=insights(self.c)
        first=result['bestsellers'][0]
        self.assertEqual((first['product_id'],first['units'],first['revenue'],first['orders']),(1,9,10000,4))
        self.assertEqual(first['name'],'Renamed product')
        self.assertEqual(result['bestsellers'][1]['units'],4)
    def test_oman_june_boundary_and_independent_history(self):
        result=insights(self.c,'month','2026-06')
        self.assertEqual(result['bestsellers'][0]['units'],5)
        seasonal=next(p for p in result['seasonal_products'] if p['product_id']==1)
        self.assertEqual((seasonal['peak_months'],seasonal['peak_share'],seasonal['units']),([6],77.8,9))
        self.assertFalse(seasonal['limited_history'])
        year=insights(self.c,history_year='2026')
        p=next(p for p in year['seasonal_products'] if p['product_id']==1)
        self.assertEqual((p['units'],p['months'][5],p['months'][4]),(7,5,1))
        self.assertTrue(p['limited_history'])
    def test_ties_empty_history_and_invalid_year(self):
        result=insights(self.c)
        p=next(p for p in result['seasonal_products'] if p['product_id']==2)
        self.assertEqual((p['peak_months'],p['peak_share']),([6,12],50.0))
        self.assertEqual(insights(self.c,history_year='2020')['seasonal_products'],[])
        self.assertEqual(insights(self.c,'day','2020-01-01')['bestsellers'],[])
        with self.assertRaises(ValueError):insights(self.c,history_year='invalid')


if __name__=='__main__':unittest.main()
