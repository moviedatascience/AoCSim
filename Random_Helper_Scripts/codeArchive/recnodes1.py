from PIL import Image, ImageDraw
import matplotlib.pyplot as plt
import numpy as np
import sqlite3

# Load the image
image_path = 'E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
img = Image.open(image_path)
width, height = img.size

# Convert image to numpy array for processing
img_array = np.array(img)

# Parameters
num_regions = 100
grid_size = int(np.sqrt(num_regions))  # Assuming a square grid for simplicity

# Initialize an image for output
output_img = Image.new("RGBA", img.size)
draw = ImageDraw.Draw(output_img)
output_img.paste(img, (0, 0))

def setup_regions_table(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop the table if it exists
    cursor.execute("DROP TABLE IF EXISTS regions")

    # Create the table
    cursor.execute('''
        CREATE TABLE regions (
            region_id INTEGER PRIMARY KEY,
            x0 INTEGER,
            y0 INTEGER,
            x1 INTEGER,
            y1 INTEGER
        )
    ''')

    conn.commit()
    conn.close()

def store_regions_in_db(db_path, regions):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.executemany('INSERT INTO regions (x0, y0, x1, y1) VALUES (?, ?, ?, ?)', regions)
    conn.commit()
    conn.close()

def process_image(image_path, db_path, num_regions):
    img = Image.open(image_path)
    width, height = img.size
    img_array = np.array(img)
    grid_size = int(np.sqrt(num_regions))

    regions = []
    for x in range(0, width, width // grid_size):
        for y in range(0, height, height // grid_size):
            cell = img_array[y:y + height // grid_size, x:x + width // grid_size]
            if np.any(cell[:, :, 3] != 0):  # Non-transparent pixel present
                regions.append((x, y, x + width // grid_size, y + height // grid_size))

    store_regions_in_db(db_path, regions)

# Visualization
plt.imshow(output_img)
plt.axis('off')
plt.show()

# Call this function with the path to your database and the regions_vertices dictionary
db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
setup_regions_table(db_path)

process_image('E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png', db_path, 100)