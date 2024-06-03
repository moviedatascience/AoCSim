import sqlite3
import random
import time

# Add the SimulationControl class if not already defined
class SimulationControl:
    def __init__(self):
        self.paused = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

# Define a function to reset simulation data
def reset_simulation_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('UPDATE nodes SET current_level = 0, current_experience = 0')
    conn.commit()
    conn.close()

def simulate(control, db_path, real_time=True):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Experience Required for Each Level
    ERL = {0: 15, 1: 60, 2: 360, 3: 840, 4: 2520, 5: 5040}

    while True:
        # Check for pause
        while control.paused:
            time.sleep(1)  # Sleep briefly while paused

        for node_id in range(1, 101):
            cursor.execute('SELECT current_level, current_experience FROM nodes WHERE node_id = ?', (node_id,))
            level, experience = cursor.fetchone()

            # Random experience gain and atrophy
            exp_gain = random.randint(1, 6)
            atrophy = random.randint(0, 3)
            new_experience = experience + exp_gain - atrophy

            # Check and update level if experience threshold is reached
            if new_experience >= ERL.get(level, float('inf')) and new_experience >= 0:
                level += 1

            # Update level and experience in database
            cursor.execute('UPDATE nodes SET current_level = ?, current_experience = ? WHERE node_id = ?',
                           (level, new_experience, node_id))

        conn.commit()

        # Time delay handling
        if real_time:
            time.sleep(3600)
        else:
            time.sleep(1)

        # Additional logic can be added here to break the loop if certain conditions are met

if __name__ == "__main__":
    db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
    control = SimulationControl()
    reset_simulation_data(db_path)  # Reset simulation data at the start
    simulate(control, db_path, real_time=False)


