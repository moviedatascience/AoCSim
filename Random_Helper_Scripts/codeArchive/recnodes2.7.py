from PIL import Image, ImageDraw
import numpy as np
import sqlite3
from sklearn.cluster import KMeans

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
    land_pixels = np.array([(x, y) for y in range(height) for x in range(width) if img_array[y, x, 3] != 0])

    # Perform k-means clustering to find region centroids
    kmeans = KMeans(n_clusters=num_regions, random_state=0).fit(land_pixels)
    centroids = kmeans.cluster_centers_
    labels = kmeans.labels_

    # Initialize an image for output
    output_img = Image.new("RGBA", img.size)
    draw = ImageDraw.Draw(output_img)
    output_img.paste(img, (0, 0))

    # Group pixels by their region label
    regions = {i: [] for i in range(num_regions)}
    for label, pixel in zip(labels, land_pixels):
        regions[label].append(pixel)

    # Store regions in the database and draw them
    regions_db_format = []
    for region_id, pixels in regions.items():
        pixels = np.array(pixels)
        x0, y0 = pixels.min(axis=0)
        x1, y1 = pixels.max(axis=0)
        regions_db_format.append((region_id, int(x0), int(y0), int(x1), int(y1)))
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