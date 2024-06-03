from scipy.spatial import Voronoi, voronoi_plot_2d
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box, MultiPolygon
import sys
import cv2
import sqlite3
import json


def clip_to_map_bounds(polygon):
    clipped_polygon = polygon.intersection(bounding_box)
    return clipped_polygon if not clipped_polygon.is_empty else None

# Load the map image with transparency
map_image_path = 'E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
map_image = Image.open(map_image_path).convert('RGBA')
map_width, map_height = map_image.size


# Define the bounding box of the map image
bounding_box = box(0, 0, map_width, map_height)

# Create a binary mask where transparent pixels are False and others are True
binary_mask = np.array([pixel[3] != 0 for pixel in map_image.getdata()])
binary_mask = binary_mask.reshape((map_height, map_width))

def setup_regions_table(db_path):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if the table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='regions'")
    table_exists = cursor.fetchone()

    if table_exists:
        # Check if the required columns exist
        cursor.execute("PRAGMA table_info(regions)")
        columns = [info[1] for info in cursor.fetchall()]
        required_columns = {'region_id', 'vertices', 'x_REAL', 'y_REAL'}

        # Add missing columns
        for column in required_columns - set(columns):
            cursor.execute(f'ALTER TABLE regions ADD COLUMN {column} REAL')

    else:
        # Create the table if it does not exist
        cursor.execute('''
            CREATE TABLE regions (
                region_id INTEGER PRIMARY KEY,
                vertices TEXT,
                x_REAL REAL,
                y_REAL REAL
            )
        ''')

    # Commit changes and close the connection
    conn.commit()
    conn.close()


def is_point_on_land(x, y, width, height):
    if x < 0 or y < 0 or x >= width or y >= height:
        return False
    return binary_mask[y, x]

def rasterize_polygon(polygon, mask, width, height):
    """
    Rasterize the polygon onto the binary mask.
    Returns a binary mask where the polygon area is filled.
    """
    rasterized = np.zeros_like(mask, dtype=np.uint8)  # Change dtype to np.uint8
    # Convert polygon points to integer coordinates
    int_coords = lambda x, y: (int(round(x)), int(round(y)))
    polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords])
    
    # Fill the polygon in the rasterized mask
    cv2.fillPoly(rasterized, [polygon_coords], 1)
    return rasterized


def compute_efficient_land_centroid(polygon, mask, width, height):
    """
    Compute the centroid of the land area within a Voronoi cell more efficiently.
    """
    # Rasterize the polygon onto the mask
    rasterized_polygon = rasterize_polygon(polygon, mask, width, height)

    # Calculate the overlap with the land mask
    overlap = rasterized_polygon & mask

    # Use numpy to calculate the centroid of the overlapped area
    y_indices, x_indices = np.nonzero(overlap)
    if len(x_indices) == 0 or len(y_indices) == 0:
        return None
    centroid_x = np.mean(x_indices)
    centroid_y = np.mean(y_indices)
    return centroid_x, centroid_y

# Generate initial Voronoi points only within the land areas
points = []
num_points = 100  # Define the number of initial points
max_attempts = 10000  # Maximum attempts to generate unique points
attempt = 0

while len(points) < num_points and attempt < max_attempts:
    x, y = np.random.randint(0, map_width), np.random.randint(0, map_height)
    if is_point_on_land(x, y, map_width, map_height):
        points.append([x, y])
    attempt += 1

points = np.array(points)
unique_points = np.unique(points, axis=0)

if len(unique_points) < num_points:
    print(f"Warning: Only {len(unique_points)} unique points were generated.")

# Use unique_points for Voronoi diagram
points = unique_points

print("Initial points generated.")

num_iterations = 10
movement_threshold = 1.0
for iteration in range(num_iterations):
    print(f"Iteration {iteration + 1}/{num_iterations}")
    vor = Voronoi(points)
    new_points = np.empty_like(points)
    regions_to_store = {}  # Dictionary to store regions' vertices after clipping

    for idx, point in enumerate(points):
        region_index = vor.point_region[idx]
        region = vor.regions[region_index]
        if not region or -1 in region:
            new_points[idx] = point
            continue
        
        polygon = Polygon([vor.vertices[i] for i in region if i != -1])
        clipped_polygon = clip_to_map_bounds(polygon)
        
        if clipped_polygon:
            # Update this to handle multiple polygons if necessary
            if isinstance(clipped_polygon, MultiPolygon):
                # Handle the case where clipping results in multiple polygons
                # For simplicity, let's take the largest polygon
                clipped_polygon = max(clipped_polygon, key=lambda p: p.area)

            centroid = compute_efficient_land_centroid(clipped_polygon, binary_mask, map_width, map_height)
            if centroid:
                new_point = np.array(centroid)
                if np.linalg.norm(new_point - point) < movement_threshold:
                    new_points[idx] = new_point
                else:
                    new_points[idx] = point
                regions_to_store[idx] = json.dumps([list(p) for p in clipped_polygon.exterior.coords])
            else:
                new_points[idx] = point
        else:
            new_points[idx] = point

    points = np.copy(new_points)

    # Early termination if no points have moved (convergence)
    movement = np.linalg.norm(points - vor.points, axis=1)
    if not np.any(movement >= movement_threshold):
        print("Early termination due to convergence.")
        break


fig, ax = plt.subplots(figsize=(map_width / 100, map_height / 100))
ax.imshow(map_image)

# Plot Voronoi diagram
voronoi_plot_2d(Voronoi(points), ax=ax, show_vertices=False, line_colors='black', point_size=2)

# Invert the y-axis to prevent the image from being flipped
ax.invert_yaxis()

print("Voronoi diagram plotted.")

def update_node_coordinates(db_path, points):
    try:
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()
            for idx, point in enumerate(points):
                # Assuming idx can be used as node_id
                cursor.execute('''
                    UPDATE nodes
                    SET x_coordinate = ?, y_coordinate = ?
                    WHERE node_id = ?
                    ''', (point[0], point[1], idx + 1))  # Adjust node_id if necessary
            connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

# Update nodes table with the coordinates
update_node_coordinates('E:\\AoCSim\\SQLite_Queries\\nodes.db', points)


# Create a dictionary for Voronoi region vertices
regions_vertices = {}
for i, region in enumerate(vor.regions):
    if -1 not in region:
        region_coords = [vor.vertices[j].tolist() for j in region]
        regions_vertices[i] = json.dumps(region_coords)

def store_voronoi_regions(db_path, regions_vertices):
    try:
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()
            for region_id, vertices_json in regions_vertices.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO regions (region_id, vertices)
                    VALUES (?, ?)
                    ''', (region_id, vertices_json))
            connection.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error: {e}")

# Call this function with the path to your database and the regions_vertices dictionary
db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
setup_regions_table(db_path)
store_voronoi_regions(db_path, regions_to_store)

# Save the final image
output_path = 'E:/AoCSim/Assets/voronoi_overlay_map.png'
plt.savefig(output_path, bbox_inches='tight')
plt.close()

print(f"Voronoi overlay saved to {output_path}")


output_path