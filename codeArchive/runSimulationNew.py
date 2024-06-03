import sqlite3
import random
import time

class SimulationControl:
    def __init__(self):
        self.paused = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

def initialize_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Add 'vassal_to' column if it doesn't exist
    cursor.execute("SELECT name FROM pragma_table_info('nodes') WHERE name='vassal_to'")
    if not cursor.fetchone():
        cursor.execute('ALTER TABLE nodes ADD COLUMN vassal_to INTEGER DEFAULT NULL')

    # Add 'regent_to' column if it doesn't exist
    cursor.execute("SELECT name FROM pragma_table_info('nodes') WHERE name='regent_to'")
    if not cursor.fetchone():
        cursor.execute('ALTER TABLE nodes ADD COLUMN regent_to INTEGER DEFAULT NULL')

    conn.commit()
    conn.close()

def reset_simulation_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE nodes SET current_level = 0, current_experience = 0, vassal_to = NULL, regent_to = NULL')
    conn.commit()
    conn.close()

def can_level_up(node_id, current_level, cursor):
    cursor.execute('SELECT adjacent_regions FROM regions WHERE region_id = ?', (node_id,))
    adjacent_regions = cursor.fetchone()[0]
    adjacent_regions = list(map(int, adjacent_regions.strip('[]').split(', ')))

    for region_id in adjacent_regions:
        cursor.execute('SELECT current_level FROM nodes WHERE node_id = ?', (region_id,))
        adjacent_level = cursor.fetchone()[0]
        if adjacent_level == current_level + 1:
            return False

    return True

def find_vassal(node_id, level, cursor):
    cursor.execute('SELECT adjacent_regions FROM regions WHERE region_id = ?', (node_id,))
    adjacent_regions = cursor.fetchone()[0]
    adjacent_regions = list(map(int, adjacent_regions.strip('[]').split(', ')))

    potential_vassals = []
    for region_id in adjacent_regions:
        cursor.execute('SELECT current_level FROM nodes WHERE node_id = ?', (region_id,))
        adjacent_level = cursor.fetchone()[0]
        if level == 3 and adjacent_level in [1, 2]:
            potential_vassals.append((region_id, adjacent_level))
        elif level == 4 and adjacent_level == 3:
            potential_vassals.append((region_id, adjacent_level))
        elif level == 5 and adjacent_level in [3, 4]:
            potential_vassals.append((region_id, adjacent_level))
        elif level == 6 and adjacent_level == 5:
            potential_vassals.append((region_id, adjacent_level))

    if potential_vassals:
        # Select the highest level vassal, or randomly if tied
        max_level = max(potential_vassals, key=lambda x: x[1])[1]
        highest_vassals = [v[0] for v in potential_vassals if v[1] == max_level]
        return random.choice(highest_vassals)
    return None

def update_vassal_relationships(node_id, level, cursor):
    vassal_id = find_vassal(node_id, level, cursor)
    if vassal_id:
        cursor.execute('UPDATE nodes SET vassal_to = ? WHERE node_id = ?', (node_id, vassal_id))
        cursor.execute('UPDATE nodes SET regent_to = ? WHERE node_id = ?', (vassal_id, node_id))

def simulate(control, db_path, allow_exp_banking, real_time=True):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    ERL = {0: 15, 1: 60, 2: 360, 3: 840, 4: 2520, 5: 5040}

    while True:
        while control.paused:
            time.sleep(1)

        for node_id in range(1, 101):
            cursor.execute('SELECT current_level, current_experience FROM nodes WHERE node_id = ?', (node_id,))
            level, experience = cursor.fetchone()

            exp_gain = random.randint(1, 6)
            atrophy = random.randint(0, 3)
            new_experience = experience + exp_gain - atrophy

            if new_experience >= ERL.get(level, float('inf')):
                if can_level_up(node_id, level, cursor):
                    level += 1
                    update_vassal_relationships(node_id, level, cursor)
                elif not allow_exp_banking and level < 3:
                    new_experience = ERL[level] - 1

            cursor.execute('UPDATE nodes SET current_level = ?, current_experience = ? WHERE node_id = ?',
                           (level, new_experience, node_id))

        conn.commit()

        if real_time:
            time.sleep(3600)
        else:
            time.sleep(1)

if __name__ == "__main__":
    db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
    control = SimulationControl()
    initialize_database(db_path)  # Ensure the database is properly initialized
    reset_simulation_data(db_path)

    allow_exp_banking = True  # or False based on user input
    simulate(control, db_path, allow_exp_banking, real_time=False)
