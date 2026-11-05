"""Apply bundled product additions once without overwriting owner edits."""
import json
import re


def apply_catalog(connection, root):
    path = root / 'catalog.json'
    if not path.exists():
        return
    manifest = json.loads(path.read_text(encoding='utf-8'))
    products = manifest['products']
    for p in products:
        if p['source_currency'] != 'OMR' or not isinstance(p['price'], int) or p['price'] < 0:
            raise ValueError('Catalog must contain verified nonnegative OMR prices')
        if not p['source_url'].startswith('https://darheba.com/'):
            raise ValueError('Unexpected catalog source')
        if not re.fullmatch(r'/catalog-images/[a-f0-9]{24}\.webp', p['image_url']):
            raise ValueError('Invalid catalog image path')
        if not (root / p['image_url'].lstrip('/')).is_file():
            raise ValueError('Missing bundled product photo')
    connection.execute('CREATE TABLE IF NOT EXISTS catalog_imports(version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    for name in ('source_url', 'source_price', 'source_currency', 'source_sku'):
        if name not in [r[1] for r in connection.execute('PRAGMA table_info(products)')]:
            connection.execute('ALTER TABLE products ADD COLUMN '+name+" TEXT NOT NULL DEFAULT ''")
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS product_source_identity ON products(source_url) WHERE source_url<>''")
    if connection.execute('SELECT 1 FROM catalog_imports WHERE version=?', (manifest['version'],)).fetchone():
        return
    first_import = connection.execute('SELECT COUNT(*) FROM catalog_imports').fetchone()[0] == 0
    for p in products:
        if connection.execute("SELECT 1 FROM products WHERE source_url=? OR (source_sku<>'' AND source_sku=?)", (p['source_url'],p['source_sku'])).fetchone():
            continue
        connection.execute('''INSERT INTO products
            (name,category,age,language,price,cost,stock,emoji,description,active,
             name_en,description_en,image_url,cost_known,source_url,source_price,source_currency,source_sku)
            VALUES(?,?,?,?,?,0,0,'📚',?,1,'','',?,0,?,?,?,?)''',
            (p['name'],p['category'],p['age'],p['language'],p['price'],p['description'],
             p['image_url'],p['source_url'],p['source_price'],p['source_currency'],p['source_sku']))
    # Hide only untouched, unused demo rows; preserve modified items and order history.
    demos = [
        ('رحلتي مع الحروف',4500,2200,12), ('عالم الحيوانات الصغير',3900,1800,8),
        ('حكايات قبل النوم',6500,3200,6), ('My First Words',4200,2000,10),
        ('حلّ وامرح',5800,2800,4), ('حلقات سيليكون ملونة',7500,4000,5),
    ]
    for name,price,cost,stock in demos if first_import else []:
        connection.execute('''UPDATE products SET active=0 WHERE id<=6 AND name=? AND price=? AND cost=? AND stock=?
            AND image_url='' AND name_en='' AND description_en=''
            AND (description LIKE '%تجريبي%' OR description LIKE 'Sample product:%')
            AND id NOT IN (SELECT product_id FROM lines)''', (name,price,cost,stock))
    connection.execute('INSERT INTO catalog_imports(version) VALUES(?)', (manifest['version'],))
