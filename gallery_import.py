"""Add gallery photos once per uploaded manifest without overwriting shop edits."""
import hashlib
import json
import re
from product_identity import existing_product


def merge_uploaded_galleries(connection,root,manifest):
    connection.execute('''CREATE TABLE IF NOT EXISTS gallery_imports(
        import_key TEXT PRIMARY KEY,products_updated INTEGER NOT NULL,photos_added INTEGER NOT NULL,
        applied_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    payload=json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()
    key='gallery-v1:'+hashlib.sha256(payload).hexdigest()
    if connection.execute('SELECT 1 FROM gallery_imports WHERE import_key=?',(key,)).fetchone():return
    updated=added=0
    def identity(url):
        if re.fullmatch(r'/catalog-images/[a-f0-9]{24}\.webp',url):
            path=root/url.lstrip('/')
            if path.is_file():return hashlib.sha256(path.read_bytes()).hexdigest()
        return url
    for product in manifest['products']:
        incoming=product.get('images') or ([product['image_url']] if product.get('image_url') else [])
        if not incoming:continue
        for url in incoming:
            if not re.fullmatch(r'/catalog-images/[a-f0-9]{24}\.webp',url) or not (root/url.lstrip('/')).is_file():
                raise ValueError('Missing or invalid imported gallery photo')
        pid=existing_product(connection,product)
        if pid is None:continue
        row=connection.execute('SELECT image_url,images,deleted FROM products WHERE id=?',(pid,)).fetchone()
        if row['deleted']:continue
        photos=list(dict.fromkeys(([row['image_url']] if row['image_url'] else [])+json.loads(row['images'])))
        seen={identity(url) for url in photos};count=0
        for url in incoming:
            fingerprint=identity(url)
            if fingerprint not in seen:
                photos.append(url);seen.add(fingerprint);count+=1
        if count:
            if len(photos)>30:raise ValueError('Imported gallery would exceed 30 photos')
            connection.execute('UPDATE products SET images=?,image_url=? WHERE id=?',(json.dumps(photos),row['image_url'] or photos[0],pid))
            updated+=1;added+=count
    connection.execute('INSERT INTO gallery_imports(import_key,products_updated,photos_added) VALUES(?,?,?)',(key,updated,added))
