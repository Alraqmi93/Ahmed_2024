"""Idempotent additions from owner-supplied product exports."""
import json
import re
from product_identity import existing_product


def apply_supplier_catalog(connection,root):
    for filename in ('supplier-catalog.json','asfar-catalog.json','supplier-batch-20261106-02.json'):
        apply_supplier_file(connection,root,filename)


def apply_supplier_file(connection,root,filename):
    path=root/filename
    if not path.exists():return
    manifest=json.loads(path.read_text(encoding='utf-8'))
    connection.execute('CREATE TABLE IF NOT EXISTS catalog_imports(version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    if connection.execute('SELECT 1 FROM catalog_imports WHERE version=?',(manifest['version'],)).fetchone():return
    for product in manifest['products']:
        if not product['source_url'].startswith(('https://daralmaarefpublisher.com/','https://darasfarstore.com/')):raise ValueError('Unexpected supplier source')
        if not isinstance(product['price'],int) or product['price']<0:raise ValueError('Invalid converted price')
        if not 1<=len(product['images'])<=30:raise ValueError('Invalid gallery size')
        for image in product['images']:
            if not re.fullmatch(r'/catalog-images/[a-f0-9]{24}\.webp',image) or not (root/image.lstrip('/')).is_file():raise ValueError('Invalid or missing supplier image')
        if existing_product(connection,product) is not None:continue
        initial_stock=product.get('initial_stock',0)
        if type(initial_stock) is not int or not 0<=initial_stock<=100000:raise ValueError('Invalid batch stock')
        connection.execute('''INSERT INTO products
            (name,category,age,language,price,cost,stock,emoji,description,active,
             name_en,description_en,image_url,images,cost_known,source_url,source_price,source_currency,source_sku)
            VALUES(?,'books','unspecified',?,?,0,?,'📚',?,1,?,?,?,?,0,?,?,?,?)''',
            (product['name'],product['language'],product['price'],initial_stock,product['description'],
             product['name'] if product['language']=='English' else '',
             product['description'] if product['language']=='English' else '',
             product['images'][0],json.dumps(product['images']),product['source_url'],
             product['source_price'],product['source_currency'],product['source_sku']))
    connection.execute('INSERT INTO catalog_imports(version) VALUES(?)',(manifest['version'],))
