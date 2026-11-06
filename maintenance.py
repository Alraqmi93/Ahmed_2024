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
