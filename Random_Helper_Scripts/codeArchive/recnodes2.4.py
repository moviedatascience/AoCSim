from PIL import Image, ImageDraw
import numpy as np
import sqlite3
import random

def setup_regions_table(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS regions")
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
    # Corrected the SQL statement to match the supplied data
    c.executemany('INSERT INTO regions (region_id, x0, y0, x1, y1) VALUES (?, ?, ?, ?, ?)', regions)
    conn.commit()
    conn.close()

def process_image(image_path, db_path, num_regions):
    img = Image.open(image_path)
    width, height = img.size
    img_array = np.array(img)

    # Initialize an empty image for drawing the regions
    output_img = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(output_img)

    # Get land pixels
    land_pixels = set((x, y) for y in range(height) for x in range(width) if img_array[y, x, 3] != 0)

    # Generate random seed points on land
    seed_points = random.sample(land_pixels, num_regions)

    # Initialize a dictionary to hold the regions
    regions = {i: [] for i in range(num_regions)}

    # Assign pixels to the closest seed point
    while land_pixels:
        for i, seed in enumerate(seed_points):
            if not land_pixels:
                break
            x, y = min(land_pixels, key=lambda p: (p[0] - seed[0])**2 + (p[1] - seed[1])**2)
            regions[i].append((x, y))
            land_pixels.remove((x, y))

    # Store regions in the database and draw them
    regions_db_format = []
    for region_id, pixels in regions.items():
        if not pixels:
            continue
        x0, y0 = min(pixels)
        x1, y1 = max(pixels)
        regions_db_format.append((region_id, x0, y0, x1, y1))
        # Draw the rectangle for the region
        draw.rectangle([x0, y0, x1, y1], outline="red")

    store_regions_in_db(db_path, regions_db_format)

    # Save the output image with the regions drawn on it
    output_image_path = image_path.replace('Map_of_Verra_cleanup_notext_nowater.png', 'RegionsMap.png')
    output_img.save(output_image_path)
    print(f"Regions map saved to {output_image_path}")

db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
setup_regions_table(db_path)
process_image('E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png', db_path, 100)
