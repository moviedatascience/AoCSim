from scipy.spatial import Voronoi, voronoi_plot_2d
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box, MultiPolygon, Point
import sys
import cv2
import sqlite3
import json
import random

# Function to clip the Voronoi polygon to the map bounds
def clip_to_map_bounds(polygon):
    clipped_polygon = polygon.intersection(bounding_box)
    return clipped_polygon if not clipped_polygon.is_empty else None

# Function to set up the regions table in the database
def setup_regions_table(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='regions'")
    table_exists = cursor.fetchone()
    if table_exists:
        cursor.execute("PRAGMA table_info(regions)")
        columns = [info[1] for info in cursor.fetchall()]
        required_columns = {'region_id', 'vertices', 'x_REAL', 'y_REAL'}
        for column in required_columns - set(columns):
            cursor.execute(f'ALTER TABLE regions ADD COLUMN {column} REAL')
    else:
        cursor.execute('''
            CREATE TABLE regions (
                region_id INTEGER PRIMARY KEY,
                vertices TEXT,
                x_REAL REAL,
                y_REAL REAL
            )
        ''')
    conn.commit()
    conn.close()

# Function to rasterize the polygon onto the binary mask
def rasterize_polygon(polygon, mask, width, height):
    rasterized = np.zeros_like(mask, dtype=np.uint8)
    int_coords = lambda x, y: (int(round(x)), int(round(y)))
    polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords])
    cv2.fillPoly(rasterized, [polygon_coords], 1)
    return rasterized

# Function to compute the centroid of a Voronoi region
def compute_efficient_land_centroid(polygon, mask, width, height, region_id=None):
    rasterized_polygon = rasterize_polygon(polygon, mask, width, height)
    overlap = rasterized_polygon & mask
    y_indices, x_indices = np.nonzero(overlap)
    if len(x_indices) == 0 or len(y_indices) == 0:
        print(f"Region {region_id} processing: No overlap. Using fallback methods.")
        return None  # Returning None to indicate that the fallback is needed
    centroid_x = np.mean(x_indices)
    centroid_y = np.mean(y_indices)
    return centroid_x, centroid_y

# Function to find a random point within a polygon
def find_random_point_in_polygon(polygon):
    minx, miny, maxx, maxy = polygon.bounds
    while True:
        pnt = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        if polygon.contains(pnt):
            return pnt.x, pnt.y


# Function to find a random point within a polygon
def find_random_point_in_polygon(polygon):
    minx, miny, maxx, maxy = polygon.bounds
    for _ in range(100):  # Limit the number of attempts
        pnt = Point(random.uniform(minx, maxx), random.uniform(miny, maxy))
        if polygon.contains(pnt):
            return pnt.x, pnt.y
    return polygon.centroid.x, polygon.centroid.y  # Fallback to centroid if random point fails

# Load the map image and create binary mask
map_image_path = 'E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
map_image = Image.open(map_image_path).convert('RGBA')
map_width, map_height = map_image.size
bounding_box = box(0, 0, map_width, map_height)
binary_mask = np.array([pixel[3] != 0 for pixel in map_image.getdata()]).reshape((map_height, map_width))

# Generate random points within the land area
points = []
num_points = 100
max_attempts = 10000
attempt = 0
while len(points) < num_points and attempt < max_attempts:
    x, y = np.random.randint(0, map_width), np.random.randint(0, map_height)
    if binary_mask[y, x]:
        points.append([x, y])
    attempt += 1
points = np.array(points)
unique_points = np.unique(points, axis=0)


# Voronoi diagram generation and processing
num_iterations = 10
movement_threshold = 1.0
for iteration in range(num_iterations):
    vor = Voronoi(points)
    new_points = np.empty_like(points)
    regions_to_store = {}
    for idx, point in enumerate(points):
        region_index = vor.point_region[idx]
        region = vor.regions[region_index]
        if not region or -1 in region:
            continue
        polygon = Polygon([vor.vertices[i] for i in region if i != -1])
        clipped_polygon = clip_to_map_bounds(polygon)
        if clipped_polygon:
            centroid = compute_efficient_land_centroid(clipped_polygon, binary_mask, map_width, map_height, idx)
            if centroid is None:  # Check if the centroid computation was successful
                centroid = find_random_point_in_polygon(clipped_polygon)  # Use the fallback function
                print(f"Random centroid for region {idx}: {centroid}")
            new_point = np.array(centroid)
            new_points[idx] = new_point
            regions_to_store[idx] = json.dumps([list(p) for p in clipped_polygon.exterior.coords])
    points = np.copy(new_points)
    if np.linalg.norm(new_points - points, axis=1).max() < movement_threshold:
        print("Convergence reached.")
        break
    else:
        points = new_points

# Update the database with the new points
db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
setup_regions_table(db_path)

def store_voronoi_regions(db_path, regions_to_store, points):
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        for idx, region_json in regions_to_store.items():
            centroid = points[idx]
            cursor.execute('''
                INSERT OR REPLACE INTO regions (region_id, vertices, x_REAL, y_REAL)
                VALUES (?, ?, ?, ?)
            ''', (idx, region_json, centroid[0], centroid[1]))
        connection.commit()

store_voronoi_regions(db_path, regions_to_store, new_points)

# Plotting and saving the Voronoi diagram
fig, ax = plt.subplots(figsize=(map_width / 100, map_height / 100))
ax.imshow(map_image)
voronoi_plot_2d(Voronoi(points), ax=ax, show_vertices=False, line_colors='black', point_size=2)
ax.invert_yaxis()  # Invert the y-axis to match the image
output_path = 'E:/AoCSim/Assets/voronoi_overlay_map.png'
plt.savefig(output_path, bbox_inches='tight')
plt.close()
print(f"Voronoi overlay saved to {output_path}")
