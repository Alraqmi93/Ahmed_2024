"""Conservative duplicate checks shared by catalog importers."""
import re
import unicodedata
from urllib.parse import unquote, urlsplit


def source_identity(value):
    if not value:return ''
    parsed=urlsplit(value)
    path=unquote(parsed.path).rstrip('/')
    # Store language links refer to the same product, as do tracking parameters.
    path=re.sub(r'^/(?:ar|en)(?:-[a-z]{2})?(?=/products/)', '', path,flags=re.I)
    return (parsed.hostname or '').lower().removeprefix('www.')+path


def title_identity(value):
    value=unicodedata.normalize('NFKC',value or '').casefold()
    value=''.join(c for c in value if unicodedata.category(c)!='Mn' and c!='ـ')
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in value).split())


def existing_product(connection,product):
    source=source_identity(product.get('source_url',''))
    sku=product.get('source_sku','').strip()
    names={title_identity(product.get(key,'')) for key in ('name','name_en')}-{''}
    # Include hidden and deleted rows so imports never recreate removed products.
    for row in connection.execute('SELECT id,source_url,source_sku,name,name_en FROM products'):
        if source and source==source_identity(row[1]):return row[0]
        if sku and sku==row[2]:return row[0]
        # A matching title alone must not merge distinct editions with separate
        # links at the same supplier. Compare titles across suppliers and for
        # manually entered records.
        if source and row[1]:
            if source.split('/')[0]==source_identity(row[1]).split('/')[0]:continue
        elif sku and row[2]:continue
        if names & ({title_identity(row[3]),title_identity(row[4])}-{''}):return row[0]
    return None
