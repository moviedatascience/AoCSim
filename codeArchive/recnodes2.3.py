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
    c.executemany('INSERT INTO regions (region_id, x0, y0, x1, y1) VALUES (?, ?, ?, ?, ?)', regions)
    conn.commit()
    conn.close()

def process_image(image_path, db_path, num_regions):
    img = Image.open(image_path)
    width, height = img.size
    img_array = np.array(img)

    # Get land pixels
    land_pixels = [(x, y) for y in range(height) for x in range(width) if img_array[y, x, 3] != 0]

    # Generate random seed points on land
    seed_points = random.sample(land_pixels, num_regions)

    # Initialize region list
    regions = [[(float('inf'), float('inf')), (float('-inf'), float('-inf'))] for _ in range(num_regions)]

    # Assign each pixel to the closest seed point
    for x in range(width):
        for y in range(height):
            if img_array[y, x, 3] != 0:  # Check for land
                distances = [abs(x - sx) + abs(y - sy) for sx, sy in seed_points]
                closest_region = distances.index(min(distances))
                regions[closest_region][0] = (min(regions[closest_region][0][0], x), min(regions[closest_region][0][1], y))
                regions[closest_region][1] = (max(regions[closest_region][1][0], x), max(regions[closest_region][1][1], y))

    # Convert regions to database format
    regions_db_format = [(i, x0, y0, x1, y1) for i, ((x0, y0), (x1, y1)) in enumerate(regions)]
    store_regions_in_db(db_path, regions_db_format)

    # Drawing the regions on the image
    draw = ImageDraw.Draw(img)
    for _, x0, y0, x1, y1 in regions_db_format:
        draw.rectangle([x0, y0, x1, y1], outline="red")

    # Save the image with regions
    output_image_path = image_path.replace('Map_of_Verra_cleanup_notext_nowater.png', 'RegionsMap.png')
    img.save(output_image_path)

db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
setup_regions_table(db_path)
process_image('E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png', db_path, 100)
