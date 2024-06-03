import json
import os

class Settings:
    def __init__(self, config_file='config.json'):
        # Compute the path to the config file, assuming it is in the same directory as this script
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_file)
        self.settings = self.load_settings()

    def load_settings(self):
        try:
            with open(self.config_file, 'r') as file:
                return json.load(file)
        except FileNotFoundError:
            print(f"Error: Configuration file '{self.config_file}' not found.")
            exit(1)
        except json.JSONDecodeError:
            print(f"Error: Configuration file '{self.config_file}' contains invalid JSON.")
            exit(1)

    def get(self, key, default=None):
        return self.settings.get(key, default)
