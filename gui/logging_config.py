import logging
import os

# Set the log file path to the current working directory
log_file_path = os.path.join(os.getcwd(), 'debug.log')

# Ensure the log file directory exists
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_path, filemode='w')
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

logging.debug("Logging initialized")
