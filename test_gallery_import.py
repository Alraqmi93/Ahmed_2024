import hashlib,json,sqlite3,tempfile,unittest
from pathlib import Path
from gallery_import import merge_uploaded_galleries


class GalleryImportTest(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name);(self.root/'catalog-images').mkdir()
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.c.execute("CREATE TABLE products(id INTEGER PRIMARY KEY,source_url TEXT,source_sku TEXT,name TEXT,name_en TEXT,image_url TEXT,images TEXT,deleted INTEGER,active INTEGER,stock INTEGER,price INTEGER,description TEXT)")
        self.cover=self.photo(b'cover');self.other=self.photo(b'other')
        self.c.execute('INSERT INTO products VALUES(1,?,?,?,?,?,?,0,0,3,999,?)',('https://shop.example/products/book','sku:1','Book','',self.cover,'[]','Owner description'))
        self.product={'name':'Book','source_url':'https://shop.example/products/book','source_sku':'sku:1','images':[self.cover,self.other,self.other]}
        self.manifest={'version':'uploaded-again','products':[self.product]}
    def tearDown(self):self.c.close();self.directory.cleanup()
    def photo(self,data):
        url='/catalog-images/'+hashlib.sha256(data).hexdigest()[:24]+'.webp';(self.root/url.lstrip('/')).write_bytes(data);return url
    def test_add_missing_only_preserve_main_and_owner_edits(self):
        merge_uploaded_galleries(self.c,self.root,self.manifest)
        row=self.c.execute('SELECT * FROM products').fetchone()
        self.assertEqual(json.loads(row['images']),[self.cover,self.other])
        self.assertEqual((row['image_url'],row['stock'],row['price'],row['active'],row['description']),(self.cover,3,999,0,'Owner description'))
        self.assertEqual(self.c.execute('SELECT count(*) FROM products').fetchone()[0],1)
        # A photo removed by the owner after import stays removed after a restart.
        self.c.execute('UPDATE products SET images=?',(json.dumps([self.cover]),))
        merge_uploaded_galleries(self.c,self.root,self.manifest)
        self.assertEqual(json.loads(self.c.execute('SELECT images FROM products').fetchone()[0]),[self.cover])
    def test_deleted_and_duplicate_content_are_skipped(self):
        duplicate='/catalog-images/'+'a'*24+'.webp';(self.root/duplicate.lstrip('/')).write_bytes(b'cover')
        self.product['images']=[duplicate,self.other]
        merge_uploaded_galleries(self.c,self.root,self.manifest)
        self.assertEqual(json.loads(self.c.execute('SELECT images FROM products').fetchone()[0]),[self.cover,self.other])
        self.c.execute("UPDATE products SET deleted=1,images='[]'")
        self.manifest['version']='another-upload'
        merge_uploaded_galleries(self.c,self.root,self.manifest)
        self.assertEqual(self.c.execute('SELECT images FROM products').fetchone()[0],'[]')
    def test_later_upload_adds_photo_without_creating_product(self):
        merge_uploaded_galleries(self.c,self.root,self.manifest)
        new=self.photo(b'another page');self.product['images'].append(new)
        merge_uploaded_galleries(self.c,self.root,self.manifest)
        self.assertEqual(json.loads(self.c.execute('SELECT images FROM products').fetchone()[0]),[self.cover,self.other,new])
        self.assertEqual(self.c.execute('SELECT sum(photos_added) FROM gallery_imports').fetchone()[0],2)
