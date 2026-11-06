"""Explicit, recorded one-time inventory action requested by the owner."""
import json
from datetime import datetime, timezone

ACTION_ID='owner-stock-five-2026-11-06'
EXPIRES_AT=datetime(2026,11,8,tzinfo=timezone.utc)


def apply_requested_stock_reset(connection,existing_store,now=None):
    connection.execute('''CREATE TABLE IF NOT EXISTS maintenance_runs(
        action_id TEXT PRIMARY KEY,status TEXT NOT NULL,products_updated INTEGER NOT NULL,
        options_updated INTEGER NOT NULL,applied_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    if connection.execute('SELECT 1 FROM maintenance_runs WHERE action_id=?',(ACTION_ID,)).fetchone():
        return
    now=now or datetime.now(timezone.utc)
    status='applied';products_updated=options_updated=0
    if not existing_store:
        status='skipped_new_store'
    elif now>=EXPIRES_AT:
        status='skipped_expired'
    else:
        for product in connection.execute('SELECT id,options FROM products WHERE deleted=0').fetchall():
            options=json.loads(product['options'])
            active=[option for option in options if option.get('active',True)]
            for option in active:
                option['stock']=5;options_updated+=1
            stock=5*len(active) if active else 5
            connection.execute('UPDATE products SET stock=?,options=? WHERE id=?',(stock,json.dumps(options,ensure_ascii=False),product['id']))
            products_updated+=1
    connection.execute('INSERT INTO maintenance_runs(action_id,status,products_updated,options_updated) VALUES(?,?,?,?)',(ACTION_ID,status,products_updated,options_updated))


SUPPLIER_STOCK_ACTION='owner-seven-books-stock-five-2026-11-06'
SUPPLIER_STOCK_SOURCES=('https://daralmaarefpublisher.com/products/%D9%83%D9%8A%D9%81-%D8%AA%D8%B9%D9%84%D9%85-%D8%AA%D9%86%D9%8A%D9%86%D9%83-%D8%A7%D9%86-%D9%8A%D9%82%D9%88%D9%84-%D9%85%D8%B1%D8%AD%D8%A8%D8%A7',
 'https://daralmaarefpublisher.com/products/%D9%83%D9%8A%D9%81-%D8%AA%D8%B9%D9%84%D9%85-%D8%AA%D9%86%D9%8A%D9%86%D9%83-%D8%A7%D9%84%D8%A5%D8%B5%D8%BA%D8%A7%D8%A1',
 'https://daralmaarefpublisher.com/products/%D9%83%D8%AA%D8%A7%D8%A8-%D8%A7%D9%84%D9%85%D8%B4%D8%A7%D8%B9%D8%B1-%D9%85%D8%A7-%D9%87%D9%88-%D9%87%D8%B0%D8%A7-%D8%A7%D9%84%D8%B4%D8%B9%D9%88%D8%B1',
 'https://daralmaarefpublisher.com/ar/products/%D8%AD%D9%8A%D9%86-%D9%8A%D8%AE%D8%AC%D9%84-%D8%A7%D9%84%D8%A7%D8%B3%D8%AF-%D8%A7%D9%86%D8%A7-%D9%88-%D9%85%D8%B4%D8%A7%D8%B9%D8%B1%D9%8A',
 'https://daralmaarefpublisher.com/products/%D8%AD%D9%8A%D9%86-%D8%AA%D8%BA%D8%B6%D8%A8-%D8%A7%D9%84%D8%A8%D8%B1%D9%86%D9%8A%D9%82%D8%A9-%D8%A7%D9%86%D8%A7-%D9%88-%D9%85%D8%B4%D8%A7%D8%B9%D8%B1%D9%8A',
 'https://daralmaarefpublisher.com/products/my-big-touch-and-feel-book',
 'https://daralmaarefpublisher.com/products/lets-get-dressed-baby-montessori')


def apply_seven_books_stock_reset(connection,existing_store,now=None):
    """Adjust only this uploaded batch, once; never change the product default."""
    connection.execute("""CREATE TABLE IF NOT EXISTS maintenance_runs(
        action_id TEXT PRIMARY KEY,status TEXT NOT NULL,products_updated INTEGER NOT NULL,
        options_updated INTEGER NOT NULL,applied_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    if connection.execute('SELECT 1 FROM maintenance_runs WHERE action_id=?',(SUPPLIER_STOCK_ACTION,)).fetchone():return
    status='applied';products_updated=options_updated=0
    if not existing_store:status='skipped_new_store'
    elif (now or datetime.now(timezone.utc))>=EXPIRES_AT:status='skipped_expired'
    else:
        for source in SUPPLIER_STOCK_SOURCES:
            row=connection.execute('SELECT id,options FROM products WHERE source_url=? AND deleted=0',(source,)).fetchone()
            if row is None:continue
            options=json.loads(row['options']);active=[o for o in options if o.get('active',True)]
            for option in active:option['stock']=5;options_updated+=1
            connection.execute('UPDATE products SET stock=?,options=? WHERE id=?',
                (5*len(active) if active else 5,json.dumps(options,ensure_ascii=False),row['id']))
            products_updated+=1
    connection.execute('INSERT INTO maintenance_runs(action_id,status,products_updated,options_updated) VALUES(?,?,?,?)',
        (SUPPLIER_STOCK_ACTION,status,products_updated,options_updated))
