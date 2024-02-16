import sqlite3
from datetime import datetime

def initialize_db():
    conn = sqlite3.connect('nodes.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nodes (
            node_id INTEGER PRIMARY KEY,
            current_level INTEGER NOT NULL,
            current_experience INTEGER NOT NULL,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()

initialize_db()

def populate_nodes():
    conn = sqlite3.connect('nodes.db')
    cursor = conn.cursor()
    for node_id in range(1, 101):
        cursor.execute('INSERT INTO nodes (node_id, current_level, current_experience) VALUES (?, ?, ?)',
                       (node_id, 0, 0))
    conn.commit()
    conn.close()

populate_nodes()