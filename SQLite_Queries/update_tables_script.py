import sqlite3

def update_database_schema(db_path):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    # Alter the 'nodes' table to add x and y coordinates separately
    try:
        cursor.execute('ALTER TABLE nodes ADD COLUMN x_coordinate REAL')
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute('ALTER TABLE nodes ADD COLUMN y_coordinate REAL')
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Create the 'regions' table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS regions (
            region_id INTEGER PRIMARY KEY,
            vertices TEXT,
            additional_info TEXT
        )
    ''')

    # Create the 'node_region_mapping' table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS node_region_mapping (
            mapping_id INTEGER PRIMARY KEY,
            node_id INTEGER,
            region_id INTEGER,
            FOREIGN KEY (node_id) REFERENCES nodes(node_id),
            FOREIGN KEY (region_id) REFERENCES regions(region_id)
        )
    ''')

    connection.commit()
    connection.close()

# Call the function with the path to your database
db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
update_database_schema(db_path)
