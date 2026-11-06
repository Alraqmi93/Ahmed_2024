import sqlite3
import unittest
from product_identity import existing_product


class ProductIdentityTest(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.execute('CREATE TABLE products(id INTEGER,source_url TEXT,source_sku TEXT,name TEXT,name_en TEXT,active INTEGER,deleted INTEGER)')
        self.c.execute("INSERT INTO products VALUES(1,'https://shop.example/ar/products/book','supplier:123','كِتاب ـ المشاعر','The Feelings Book',0,1)")
    def tearDown(self):self.c.close()
    def test_source_alias_and_tracking(self):
        self.assertEqual(existing_product(self.c,{'source_url':'https://www.shop.example/en/products/book/?utm_source=instagram','name':'Changed title'}),1)
    def test_sku_and_normalized_titles_including_removed_items(self):
        for product in [{'source_sku':'supplier:123'},{'name':'كتاب المشاعر'},{'name':'THE feelings—book'}]:
            self.assertEqual(existing_product(self.c,product),1)
    def test_same_book_from_another_supplier_is_skipped(self):
        self.assertEqual(existing_product(self.c,{'name':'The Feelings Book','source_url':'https://other-shop.example/products/feelings','source_sku':'other:456'}),1)
    def test_distinct_books_and_blank_values_are_not_duplicates(self):
        for product in [{'name':'The Feelings Book 2'},{'name':'Other book','source_sku':'another:123'},{'name':'The Feelings Book','source_url':'https://shop.example/products/different-edition','source_sku':'supplier:456'},{}]:
            self.assertIsNone(existing_product(self.c,product))


if __name__=='__main__':unittest.main()
