from PyQt5.QtCore import QThread
import logging
from simulation.runSimulationNew import simulate, reset_simulation_data

class SimulationThread(QThread):
    def __init__(self, control, db_path, allow_exp_banking):
        super().__init__()
        self.control = control
        self.db_path = db_path
        self.allow_exp_banking = allow_exp_banking

    def run(self):
        try:
            simulate(self.control, self.db_path, self.allow_exp_banking, real_time=False)
        except Exception as e:
            logging.error(f"Error in SimulationThread run: {e}")

    def pause(self):
        try:
            self.control.pause()
        except Exception as e:
            logging.error(f"Error in SimulationThread pause: {e}")

    def resume(self):
        try:
            self.control.resume()
        except Exception as e:
            logging.error(f"Error in SimulationThread resume: {e}")

    def reset_simulation_data(self):
        try:
            reset_simulation_data(self.db_path)
        except Exception as e:
            logging.error(f"Error in SimulationThread reset_simulation_data: {e}")
