import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from catalog_import import apply_catalog


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {'DATA_DIR':self.directory.name, 'LOAD_BUNDLED_CATALOG':'1'})
        self.environment.start()
        spec = importlib.util.spec_from_file_location('catalog_test_server', Path(__file__).with_name('server.py'))
        self.server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.server)

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def test_import_prices_assets_and_repeatability(self):
        self.server.init()
        expected=json.loads(Path(__file__).with_name('catalog.json').read_text(encoding='utf-8'))['products']
        with self.server.db() as c:
            rows=c.execute("SELECT * FROM products WHERE source_url<>''").fetchall()
            self.assertEqual(len(rows),len(expected))
            self.assertEqual(c.execute('SELECT count(*) FROM products WHERE active=1').fetchone()[0],len(expected))
            for row in rows:
                product=next(p for p in expected if p['source_url']==row['source_url'])
                self.assertEqual(row['price'],product['price'])
                self.assertEqual(row['source_currency'],'OMR')
                self.assertEqual(row['stock'],0)
                self.assertEqual(row['cost_known'],0)
                self.assertTrue((Path(__file__).parent/row['image_url'].lstrip('/')).is_file())
            first=rows[0]['id']
            c.execute('UPDATE products SET price=1234,stock=9,active=0 WHERE id=?',(first,))
            c.execute("INSERT INTO settings VALUES('whatsapp_number','96890000000')")
        self.server.init()
        with self.server.db() as c:
            row=c.execute('SELECT * FROM products WHERE id=?',(first,)).fetchone()
            self.assertEqual((row['price'],row['stock'],row['active']),(1234,9,0))
            self.assertEqual(c.execute("SELECT count(*) FROM products WHERE source_url<>''").fetchone()[0],len(expected))
            self.assertEqual(c.execute("SELECT value FROM settings WHERE key='whatsapp_number'").fetchone()[0],'96890000000')

    def test_modified_demo_is_preserved(self):
        os.environ['LOAD_BUNDLED_CATALOG']='0'
        self.server.init()
        with self.server.db() as c:c.execute('UPDATE products SET price=9999 WHERE id=1')
        os.environ['LOAD_BUNDLED_CATALOG']='1'
        self.server.init()
        with self.server.db() as c:
            self.assertEqual(c.execute('SELECT active,price FROM products WHERE id=1').fetchone()[:],(1,9999))
            self.assertEqual(c.execute('SELECT active FROM products WHERE id=2').fetchone()[0],0)

    def test_incremental_upgrade_preserves_edits_visibility_and_orders(self):
        os.environ['LOAD_BUNDLED_CATALOG']='0'
        self.server.init()
        root=Path(__file__).parent
        manifest=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as old_root:
            old_root=Path(old_root)
            (old_root/'catalog-images').symlink_to(root/'catalog-images',target_is_directory=True)
            previous={**manifest,'version':'previous-17-product-export','products':manifest['products'][:17]}
            (old_root/'catalog.json').write_text(json.dumps(previous,ensure_ascii=False),encoding='utf-8')
            with self.server.db() as c:
                apply_catalog(c,old_root)
                sku=previous['products'][0]['source_sku']
                pid=c.execute('SELECT id FROM products WHERE source_sku=?',(sku,)).fetchone()[0]
                c.execute("UPDATE products SET price=1234,stock=7,active=0,source_url='https://darheba.com/ar-om/products/old-alias' WHERE id=?",(pid,))
                c.execute('UPDATE products SET active=1 WHERE id=2')
                oid=c.execute("INSERT INTO orders(customer,phone,address,total,cost) VALUES('Test','90000000','Test',1234,0)").lastrowid
                c.execute("INSERT INTO lines(order_id,product_id,name,quantity,price,cost) VALUES(?,?,'Test',1,1234,0)",(oid,pid))
            with self.server.db() as c:apply_catalog(c,root)
            with self.server.db() as c:
                self.assertEqual(c.execute("SELECT count(*) FROM products WHERE source_sku<>''").fetchone()[0],len(manifest['products']))
                self.assertEqual(c.execute('SELECT price,stock,active FROM products WHERE id=?',(pid,)).fetchone()[:],(1234,7,0))
                self.assertEqual(c.execute('SELECT active FROM products WHERE id=2').fetchone()[0],1)
                self.assertEqual(c.execute('SELECT total FROM orders WHERE id=?',(oid,)).fetchone()[0],1234)
                self.assertEqual(c.execute('SELECT quantity FROM lines WHERE order_id=?',(oid,)).fetchone()[0],1)


if __name__=='__main__':unittest.main()
