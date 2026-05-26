"""Set admin flag for a user."""
import sqlite3
import sys

try:
    conn = sqlite3.connect('/home/ubuntu/workspace/stu/cumbre/backend/cumbre.db', timeout=5)
    conn.row_factory = sqlite3.Row
    
    users = conn.execute('SELECT id, name, email, is_admin FROM users').fetchall()
    print("=== Users ===")
    for r in users:
        print(f'  ID={r["id"]} {r["name"]} ({r["email"]}) admin={r["is_admin"]}')
    
    conn.execute('UPDATE users SET is_admin=1 WHERE email="admin@cumbre.com"')
    conn.commit()
    
    r = conn.execute('SELECT id, name, is_admin FROM users WHERE email="admin@cumbre.com"').fetchone()
    if r:
        print(f'\n✅ Admin set: ID={r["id"]} {r["name"]} is_admin={r["is_admin"]}')
    else:
        print('\n❌ User not found')
    
    conn.close()
except Exception as e:
    print(f'❌ Error: {e}')
    sys.exit(1)
