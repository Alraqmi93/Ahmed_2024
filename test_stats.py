import sqlite3
import unittest
from shop_stats import summary, period_bounds


class StatisticsTest(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.row_factory=sqlite3.Row
        self.c.executescript('''CREATE TABLE orders(status TEXT,total INTEGER,cost INTEGER,cost_known INTEGER,created TEXT,completed_at TEXT);
            CREATE TABLE purchases(status TEXT,quantity INTEGER,unit_cost INTEGER,created TEXT,received_at TEXT);
            CREATE TABLE adjustments(kind TEXT,category TEXT,amount INTEGER,incurred_on TEXT,voided INTEGER DEFAULT 0);''')
        for index,stamp in enumerate(['2026-10-31 19:59:59','2026-10-31 20:00:00','2026-11-04 19:59:59',
                '2026-11-04 20:00:00','2026-11-05 19:59:59','2026-11-05 20:00:00',
                '2026-11-07 20:00:00','2026-11-30 20:00:00','2026-12-31 20:00:00']):
            self.c.execute('INSERT INTO orders VALUES(?,?,?,?,?,?)',('completed',10000,4000,int(index!=4),'2026-01-01 00:00:00',stamp))
        self.c.execute("INSERT INTO orders VALUES('completed',10000,4000,1,'2026-11-04 21:00:00',NULL)")
        for status in ('new','paid','cancelled'):
            self.c.execute('INSERT INTO orders VALUES(?,999000,1,1,?,?)',(status,'2026-11-05 00:00:00','2026-11-05 00:00:00'))
        self.c.executemany('INSERT INTO purchases VALUES(?,?,?,?,?)',[
            ('received',3,2000,'2026-10-01 00:00:00','2026-11-04 20:00:00'),
            ('received',2,1000,'2026-11-05 19:00:00',None),
            ('received',1,3000,'2026-11-01 00:00:00','2026-11-05 20:00:00'),
            ('ordered',100,9999,'2026-11-05 00:00:00',None)])
        self.c.executemany('INSERT INTO adjustments VALUES(?,?,?,?,?)',[
            ('expense','shipping',6000,'2026-11-05',0),('expense','transfer',500,'2026-11-05',0),
            ('income','shipping',2000,'2026-11-05',0),('expense','other',1000,'2026-11-06',0),
            ('expense','other',99999,'2026-11-05',1)])

    def tearDown(self):self.c.close()

    def test_oman_daily_boundaries_and_unknown_costs(self):
        s=summary(self.c,'day','2026-11-05')
        self.assertEqual((s['sales'],s['product_cost'],s['gross_profit']),(30000,8000,12000))
        self.assertEqual((s['completed_orders'],s['unknown_cost_orders']),(3,1))
        self.assertEqual(s['supplier_purchases'],8000)
        self.assertEqual((s['legacy_order_dates'],s['legacy_purchase_dates']),(1,1))
        self.assertEqual((s['additional_costs'],s['additional_income'],s['net_profit']),(6500,2000,7500))
        self.assertEqual((s['shipping_costs'],s['transfer_fees']),(6000,500))

    def test_week_month_year_and_cumulative(self):
        for period,anchor,sales,profit in [('week','2026-11-05',60000,30000),('month','2026-11',70000,36000),
                ('year','2026',90000,48000),('all',None,100000,54000)]:
            with self.subTest(period=period):
                s=summary(self.c,period,anchor)
                self.assertEqual((s['sales'],s['gross_profit']),(sales,profit))
        s=summary(self.c,'week','2026-11-05')
        self.assertEqual((s['start_date'],s['end_date']),('2026-11-01','2026-11-07'))
        self.assertEqual(s['net_profit'],24500)
        self.assertEqual(summary(self.c)['net_profit'],48500)

    def test_empty_period_invalid_input_and_calendar_edges(self):
        self.assertEqual(summary(self.c,'day','2020-01-01')['sales'],0)
        self.assertEqual(period_bounds('month','2024-02')[1].isoformat(),'2024-03-01')
        self.assertEqual(period_bounds('month','2026-12')[1].isoformat(),'2027-01-01')
        for period,anchor in [('bad','2026'),('day','2026-02-30'),('month','bad'),('year','oops')]:
            with self.assertRaises(ValueError):period_bounds(period,anchor)


if __name__=='__main__':unittest.main()
