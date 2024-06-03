import sqlite3
import logging

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

def update_boundaries_in_database(new_boundaries):
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        for boundary in new_boundaries:
            cursor.execute('''
                UPDATE regions
                SET vertices = ?
                WHERE region_id = ?
            ''', (boundary['vertices'], boundary['id']))
        connection.commit()
        logging.info("Boundaries updated successfully in the database.")
    except sqlite3.Error as e:
        logging.error(f"Database error during update: {e}")
    finally:
        connection.close()

def revert_boundaries_to_original():
    try:
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute('''
            SELECT region_id, vertices FROM original_regions
        ''')
        original_boundaries = cursor.fetchall()
        for region_id, vertices in original_boundaries:
            cursor.execute('''
                UPDATE regions
                SET vertices = ?
                WHERE region_id = ?
            ''', (vertices, region_id))
        connection.commit()
        logging.info("Boundaries reverted to original successfully in the database.")
    except sqlite3.Error as e:
        logging.error(f"Database error during revert: {e}")
    finally:
        connection.close()

# Call the function with the path to your database
db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
update_database_schema(db_path)
