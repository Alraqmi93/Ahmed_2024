import sqlite3,unittest
from product_sales import product_sales


class ProductSalesTest(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.executescript('''CREATE TABLE products(id INTEGER PRIMARY KEY,name TEXT,name_en TEXT);
            CREATE TABLE orders(id INTEGER PRIMARY KEY,status TEXT,created TEXT,completed_at TEXT);
            CREATE TABLE lines(order_id INTEGER,product_id INTEGER,quantity INTEGER,price INTEGER,discount INTEGER);
            INSERT INTO products VALUES(1,'Book','Book'),(2,'Another',''),(3,'No sales','');''')
        for oid,status,stamp,completed in [(1,'completed','2026-05-31 20:00:00','2026-05-31 20:00:00'),(2,'completed','2026-06-01 19:59:59','2026-06-01 19:59:59'),(3,'completed','2026-06-01 20:00:00','2026-06-01 20:00:00'),(4,'cancelled','2026-06-01 01:00:00','2026-06-01 01:00:00'),(5,'paid','2026-06-01 01:00:00',None),(6,'new','2026-06-01 01:00:00',None),(7,'completed','2026-06-01 08:00:00',None),(8,'completed','2026-06-01 08:00:00','2026-06-01 08:00:00')]:
            self.c.execute('INSERT INTO orders VALUES(?,?,?,?)',(oid,status,stamp,completed))
        self.c.executemany('INSERT INTO lines VALUES(?,?,?,?,?)',[(1,1,2,1000,100),(1,1,3,2000,200),(2,1,4,1000,0),(3,1,7,1000,0),(4,1,99,1000,0),(5,1,88,1000,0),(6,1,77,1000,0),(7,1,1,1000,0),(8,2,50,1000,0)])
    def tearDown(self):self.c.close()
    def test_oman_day_boundaries_options_combined_and_discounted_sales(self):
        result=product_sales(self.c,1,'day','2026-06-01')
        self.assertEqual((result['units'],result['orders'],result['revenue']),(10,3,12700))
        self.assertEqual(result['legacy_order_dates'],1)
        self.assertEqual((result['start_date'],result['end_date']),('2026-06-01','2026-06-01'))
    def test_custom_inclusive_dates_and_cumulative_default(self):
        result=product_sales(self.c,1,'custom',start_date='2026-06-01',end_date='2026-06-01')
        self.assertEqual(result['units'],10)
        result=product_sales(self.c,1)
        self.assertEqual((result['units'],result['orders'],result['revenue']),(17,4,19700))
        self.assertIsNone(result['start_date'])
        for period,anchor in [('week','2026-06-01'),('month','2026-06'),('year','2026')]:self.assertEqual(product_sales(self.c,1,period,anchor)['units'],17)
    def test_zero_sales_and_invalid_selection(self):
        self.assertEqual(product_sales(self.c,3)['units'],0)
        self.assertEqual(product_sales(self.c,1,'day','2025-01-01')['units'],0)
        for pid in [0,-1,999,'abc']:
            with self.assertRaises(ValueError):product_sales(self.c,pid)
        with self.assertRaises(ValueError):product_sales(self.c,1,'custom',start_date='2026-06-02',end_date='2026-06-01')
        with self.assertRaises(ValueError):product_sales(self.c,1,'custom')
