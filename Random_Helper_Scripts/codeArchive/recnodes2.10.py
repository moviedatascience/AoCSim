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

def get_adjacent_pixels(pixel, land_pixels, assigned_pixels):
    x, y = pixel
    adjacent = []
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        if (x + dx, y + dy) in land_pixels and (x + dx, y + dy) not in assigned_pixels:
            adjacent.append((x + dx, y + dy))
    return adjacent

def process_image(image_path, db_path, num_regions):
    img = Image.open(image_path)
    width, height = img.size
    img_array = np.array(img)

    # Get land pixels
    land_pixels = {(x, y) for y in range(height) for x in range(width) if img_array[y, x, 3] != 0}
    assigned_pixels = set()
    regions = {i: set() for i in range(num_regions)}

    # Generate seed points
    seed_points = random.sample(land_pixels, num_regions)
    for i, seed in enumerate(seed_points):
        regions[i].add(seed)
        assigned_pixels.add(seed)

    # Grow regions until all land is assigned
    while len(assigned_pixels) < len(land_pixels):
        for i, region in regions.items():
            if len(assigned_pixels) >= len(land_pixels):
                break
            new_pixels = set()
            for pixel in region:
                for adj in get_adjacent_pixels(pixel, land_pixels, assigned_pixels):
                    new_pixels.add(adj)
                    assigned_pixels.add(adj)
            regions[i].update(new_pixels)
    
    # Draw the regions
    output_img = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(output_img)
    output_img.paste(img, (0, 0))

    # Store regions in the database
    regions_db_format = []
    colors = [(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for _ in range(num_regions)]
    for i, region in regions.items():
        region = list(region)
        if region:
            x0, y0 = min(region)
            x1, y1 = max(region)
            regions_db_format.append((i, x0, y0, x1, y1))
            for pixel in region:
                output_img.putpixel(pixel, colors[i])  # Color the region
        else:
            regions_db_format.append((i, 0, 0, 0, 0))  # Dummy values for empty regions

    store_regions_in_db(db_path, regions_db_format)

    # Save the output image with the regions colored
    output_image_path = image_path.replace('Map_of_Verra_cleanup_notext_nowater.png', 'ColoredRegionsMap.png')
    output_img.save(output_image_path)
    print(f"Regions map saved to {output_image_path}")

db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
setup_regions_table(db_path)
process_image('E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png', db_path, 100)