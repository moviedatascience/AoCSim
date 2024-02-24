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

    # Initialize a dictionary to hold the regions
    regions = {i: set() for i in range(num_regions)}

    # Assign each land pixel to the closest seed point
    for x, y in land_pixels:
        distances = [((x - sx)**2 + (y - sy)**2) for sx, sy in seed_points]
        closest_region = distances.index(min(distances))
        regions[closest_region].add((x, y))

    # Convert regions to database format and draw them
    regions_db_format = []
    output_img = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(output_img)
    output_img.paste(img, (0, 0))

    for region_id, pixels in regions.items():
        if not pixels:
            continue
        # Find the bounding box for each region
        x0, y0 = width, height
        x1, y1 = 0, 0
        for x, y in pixels:
            x0 = min(x0, x)
            y0 = min(y0, y)
            x1 = max(x1, x)
            y1 = max(y1, y)
        # Expand the region slightly to ensure it's at least 1 pixel in size
        x1 = max(x1, x0 + 1)
        y1 = max(y1, y0 + 1)
        regions_db_format.append((region_id, x0, y0, x1, y1))
        # Draw the rectangle for the region
        draw.rectangle([x0, y0, x1, y1], outline="red")

    store_regions_in_db(db_path, regions_db_format)

    # Save the output image with the regions drawn on it
    output_image_path = 'E:/AoCSim/Assets/RegionsMap.png'  # Ensure you are using the correct path
    output_img.save(output_image_path)
    print(f"Regions map saved to {output_image_path}")

db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
setup_regions_table(db_path)
process_image('E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png', db_path, 100)

