import json
import os
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, Response

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'furniture.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT,
                created_at   TEXT NOT NULL,
                name         TEXT,
                surname      TEXT,
                phone        TEXT,
                email        TEXT,
                delivery     TEXT,
                address      TEXT,
                comment      TEXT,
                items        TEXT,
                total        INTEGER
            )
        ''')
        conn.commit()


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Нет данных'}), 400

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    with get_db() as conn:
        cursor = conn.execute(
            '''INSERT INTO orders
               (order_number, created_at, name, surname, phone, email,
                delivery, address, comment, items, total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                '',
                created_at,
                data.get('name', ''),
                data.get('surname', ''),
                data.get('phone', ''),
                data.get('email', ''),
                data.get('delivery', ''),
                data.get('address', ''),
                data.get('comment', ''),
                json.dumps(data.get('items', []), ensure_ascii=False),
                data.get('total', 0),
            ),
        )
        order_id = cursor.lastrowid
        order_number = f'ФМ-{order_id:06d}'
        conn.execute('UPDATE orders SET order_number = ? WHERE id = ?',
                     (order_number, order_id))
        conn.commit()

    return jsonify({'order_number': order_number, 'created_at': created_at}), 201


@app.route('/admin/orders')
@require_auth
def admin_orders():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM orders ORDER BY id DESC').fetchall()

    html_rows = ''
    for row in rows:
        items = json.loads(row['items'] or '[]')
        items_str = ', '.join(f"{i['name']} \xd7{i['qty']}" for i in items)
        total_fmt = f"{row['total']:,}".replace(',', ' ')
        delivery_label = 'Курьер' if row['delivery'] == 'courier' else 'Самовывоз'
        html_rows += f'''
          <tr>
            <td>{row["order_number"]}</td>
            <td>{row["created_at"]}</td>
            <td>{row["name"]} {row["surname"]}</td>
            <td>{row["phone"]}</td>
            <td>{row["email"]}</td>
            <td>{delivery_label}</td>
            <td>{row["address"] or "—"}</td>
            <td class="items-cell">{items_str}</td>
            <td><b>{total_fmt} ₽</b></td>
          </tr>'''

    count = len(rows)
    empty_row = '' if count else '<tr><td colspan="9" class="empty">Заказов пока нет</td></tr>'

    return f'''<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>FORMA — Заказы</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: "Segoe UI", system-ui, sans-serif; background: #f7f5f2; padding: 32px 24px; color: #1c1c1c; }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ font-size: 13px; color: #a8a8a8; margin-bottom: 24px; }}
    .logo {{ font-size: 13px; font-weight: 700; letter-spacing: 3px; color: #c8a97e; text-transform: uppercase; margin-bottom: 8px; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.07); }}
    th {{ background: #1c1c1c; color: #fff; padding: 12px 16px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .8px; white-space: nowrap; }}
    td {{ padding: 12px 16px; border-bottom: 1px solid #e4e0db; font-size: 14px; vertical-align: middle; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fdf9f5; }}
    .items-cell {{ font-size: 12px; color: #5a5a5a; max-width: 260px; }}
    .empty {{ text-align: center; color: #a8a8a8; padding: 60px; }}
    @media (max-width: 900px) {{ table {{ font-size: 12px; }} td, th {{ padding: 8px 10px; }} }}
  </style>
</head>
<body>
  <div class="logo">FORMA</div>
  <h1>Заказы</h1>
  <p class="subtitle">Всего: {count}</p>
  <table>
    <thead>
      <tr>
        <th>Заказ</th>
        <th>Дата</th>
        <th>Покупатель</th>
        <th>Телефон</th>
        <th>Email</th>
        <th>Доставка</th>
        <th>Адрес</th>
        <th>Товары</th>
        <th>Сумма</th>
      </tr>
    </thead>
    <tbody>{html_rows or empty_row}</tbody>
  </table>
</body>
</html>'''


ADMIN_LOGIN    = os.environ.get('ADMIN_LOGIN', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'forma2024')

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_LOGIN or auth.password != ADMIN_PASSWORD:
            return Response(
                'Доступ запрещён',
                401,
                {'WWW-Authenticate': 'Basic realm="FORMA Admin"'}
            )
        return f(*args, **kwargs)
    return decorated

init_db()

if __name__ == '__main__':
    print('База данных готова:', DB_PATH)
    print('Магазин:  http://localhost:5000')
    print('Заказы:   http://localhost:5000/admin/orders')
    app.run(debug=True, port=5000)
