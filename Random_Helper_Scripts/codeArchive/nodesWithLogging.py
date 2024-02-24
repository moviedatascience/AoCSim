import json
import sqlite3
import numpy as np
from PIL import Image
from scipy.spatial import Voronoi, voronoi_plot_2d
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box, MultiPolygon
import cv2
import logging

# Set up logging
logging.basicConfig(filename='voronoi_log.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clip_to_map_bounds(polygon):
    # Log the original polygon
    logging.debug(f"Original polygon: {polygon}")

    try:
        clipped_polygon = polygon.intersection(bounding_box)

        # Log the clipped polygon
        logging.debug(f"Clipped polygon: {clipped_polygon}")

        if clipped_polygon.is_empty:
            logging.info(f"Clipping resulted in an empty polygon: Original {polygon}")
            return None
        else:
            # Handle degenerate polygons
            if clipped_polygon.geom_type == 'LineString' or clipped_polygon.geom_type == 'Point':
                logging.warning(f"Clipping resulted in a degenerate polygon: {clipped_polygon}")
                return None

            # Apply a buffer to clean up the polygon geometry
            cleaned_polygon = clipped_polygon.buffer(0)

            if isinstance(cleaned_polygon, MultiPolygon):
                # Log details about MultiPolygon instances
                num_polygons = len(cleaned_polygon.geoms)
                polygon_areas = [p.area for p in cleaned_polygon.geoms]
                logging.info(f"Clipped MultiPolygon with {num_polygons} polygons, areas: {polygon_areas}")

                # Handling strategy for MultiPolygons (e.g., choose the largest polygon)
                largest_polygon = max(cleaned_polygon, key=lambda p: p.area)
                return largest_polygon

            return cleaned_polygon
    except Exception as e:
        logging.error(f"Error in clipping polygon: {e}")
        return None



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
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop the table if it exists
    cursor.execute("DROP TABLE IF EXISTS regions")

    # Create the table
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

def is_point_on_land(x, y, width, height):
    if x < 0 or y < 0 or x >= width or y >= height:
        return False
    return binary_mask[y, x]

def rasterize_polygon(polygon, mask, width, height):
    """
    Rasterize the polygon onto the binary mask.
    Returns a binary mask where the polygon area is filled.
    """
    rasterized = np.zeros_like(mask, dtype=np.uint8)
    int_coords = lambda x, y: (int(round(x)), int(round(y)))
    polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords])

    cv2.fillPoly(rasterized, [polygon_coords], 1)
    return rasterized

def compute_efficient_land_centroid(polygon, mask, width, height, region_id=None):
    rasterized_polygon = rasterize_polygon(polygon, mask, width, height)
    overlap = rasterized_polygon & mask
    y_indices, x_indices = np.nonzero(overlap)

    if len(x_indices) == 0 or len(y_indices) == 0:
        logging.info(f"Region {region_id} processing: No overlap with land. Using fallback methods.")
        logging.info(f"Region {region_id} vertices: {polygon.exterior.coords[:]}")
        logging.info(f"Region {region_id} area: {polygon.area}")

        x_center, y_center = np.mean(polygon.exterior.coords, axis=0)

        if np.isnan(x_center) or np.isnan(y_center):
            logging.info(f"Region {region_id}: Geometric center failed. Using bounding box midpoint.")
            bounds = polygon.bounds
            x_center, y_center = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2

        if np.isnan(x_center) or np.isnan(y_center):
            logging.info(f"Region {region_id}: Bounding box center failed. Using first vertex.")
            x_center, y_center = polygon.exterior.coords[0]

        return x_center, y_center

    centroid_x, centroid_y = np.mean(x_indices), np.mean(y_indices)
    return centroid_x, centroid_y

# Generate initial Voronoi points only within the land areas
points = []
num_points = 100
max_attempts = 10000
attempt = 0

while len(points) < num_points and attempt < max_attempts:
    x, y = np.random.randint(0, map_width), np.random.randint(0, map_height)
    if is_point_on_land(x, y, map_width, map_height):
        points.append([x, y])
    attempt += 1

points = np.array(points)
unique_points = np.unique(points, axis=0)

if len(unique_points) < num_points:
    logging.warning(f"Warning: Only {len(unique_points)} unique points were generated.")

# Use unique_points for Voronoi diagram
points = unique_points

logging.info("Initial points generated.")

num_iterations = 10
movement_threshold = 1.0
missing_regions_to_check = [1, 3, 7, 19, 22, 92, 94, 95, 99, 100]
regions_to_check = [r - 1 for r in missing_regions_to_check]

for iteration in range(num_iterations):
    logging.info(f"Iteration {iteration + 1}/{num_iterations}")
    vor = Voronoi(points)
    new_points = np.empty_like(points)
    regions_to_store = {}

    for idx, point in enumerate(points):
        region_index = vor.point_region[idx]
        region = vor.regions[region_index]

        if not region or -1 in region:
            logging.debug(f"Region {idx} skipped due to invalid region indices.")
            new_points[idx] = point
            continue

        polygon = Polygon([vor.vertices[i] for i in region if i != -1])
        clipped_polygon = clip_to_map_bounds(polygon)

        if clipped_polygon:
            if isinstance(clipped_polygon, MultiPolygon):
                clipped_polygon = max(clipped_polygon, key=lambda p: p.area)

            centroid = compute_efficient_land_centroid(clipped_polygon, binary_mask, map_width, map_height, region_id=idx)
            if centroid:
                new_point = np.array(centroid)
                if np.linalg.norm(new_point - point) < movement_threshold:
                    new_points[idx] = new_point
                else:
                    new_points[idx] = point
                regions_to_store[idx] = json.dumps([list(p) for p in clipped_polygon.exterior.coords])

                if idx in regions_to_check:
                    logging.info(f"Region {idx} processed and added to store with data: {regions_to_store[idx]}")
            else:
                new_points[idx] = point
                if idx in regions_to_check:
                    logging.debug(f"Region {idx} has no valid centroid.")
        else:
            if idx in regions_to_check:
                logging.debug(f"Region {idx} skipped due to empty clipped polygon.")
            continue

    points = np.copy(new_points)

    movement = np.linalg.norm(points - vor.points, axis=1)
    if not np.any(movement >= movement_threshold):
        logging.info("Early termination due to convergence.")
        break

fig, ax = plt.subplots(figsize=(map_width / 100, map_height / 100))
ax.imshow(map_image)
voronoi_plot_2d(Voronoi(points), ax=ax, show_vertices=False, line_colors='black', point_size=2)
ax.invert_yaxis()
logging.info("Voronoi diagram plotted.")

def update_node_coordinates(db_path, points):
    try:
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()
            for idx, point in enumerate(points):
                cursor.execute('''
                    UPDATE nodes
                    SET x_coordinate = ?, y_coordinate = ?
                    WHERE node_id = ?
                    ''', (point[0], point[1], idx + 1))
            connection.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
    except Exception as e:
        logging.error(f"Error: {e}")

update_node_coordinates('E:\\AoCSim\\SQLite_Queries\\nodes.db', points)

def store_voronoi_regions(db_path, regions_to_store, points):
    written_regions = set()
    logging.info(f"Storing {len(regions_to_store)} regions.")
    try:
        with sqlite3.connect(db_path) as connection:
            cursor = connection.cursor()
            for idx, region_json in regions_to_store.items():
                logging.info(f"Processing region {idx} for DB storage.")
                centroid = points[idx]
                x_real, y_real = centroid[0], centroid[1]

                if region_json and isinstance(region_json, str) and len(region_json) > 0:
                    try:
                        json.loads(region_json)
                        if not (np.isnan(x_real) or np.isnan(y_real)):
                            cursor.execute('''
                                INSERT INTO regions (region_id, vertices, x_REAL, y_REAL)
                                VALUES (?, ?, ?, ?)
                            ''', (idx, region_json, x_real, y_real))

                            if cursor.rowcount > 0:
                                written_regions.add(idx)
                                logging.info(f"Region {idx} successfully written to DB.")
                            else:
                                logging.warning(f"Failed to write region {idx} to DB.")
                        else:
                            logging.warning(f"Invalid centroid coordinates for region {idx}.")
                    except json.JSONDecodeError:
                        logging.error(f"Invalid JSON format for region {idx}.")
                else:
                    logging.warning(f"Empty or invalid region data for region {idx}.")

            connection.commit()
    except sqlite3.Error as e:
        logging.error(f"Database connection error: {e}")
    except Exception as e:
        logging.error(f"General error: {e}")
    
    missing_regions = set(range(1, 101)) - written_regions
    if missing_regions:
        logging.warning(f"Missing regions in DB: {sorted(missing_regions)}")
    else:
        logging.info("All regions successfully written to DB.")

db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
setup_regions_table(db_path)
store_voronoi_regions(db_path, regions_to_store, new_points)

output_path = 'E:/AoCSim/Assets/voronoi_overlay_map.png'
plt.savefig(output_path, bbox_inches='tight')
plt.close()
logging.info(f"Voronoi overlay saved to {output_path}")