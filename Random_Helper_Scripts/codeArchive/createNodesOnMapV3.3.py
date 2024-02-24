import numpy as np
import matplotlib.pyplot as plt
import json
import cv2
from PIL import Image
import sqlite3
from scipy.spatial import Voronoi
from shapely.geometry import Polygon
import io

def get_non_transparent_points(image_path, num_points):
    """
    Selects a specified number of non-transparent points from an image.
    """
    image = Image.open(image_path).convert("RGBA")
    data = np.array(image)

    non_transparent = np.argwhere(data[:, :, 3] != 0)

    if len(non_transparent) < num_points:
        raise ValueError(f"Not enough non-transparent points. Only found {len(non_transparent)} points.")

    selected_indices = np.random.choice(len(non_transparent), num_points, replace=False)
    selected_points = non_transparent[selected_indices]

    return selected_points[:, [1, 0]]  # Convert to (x, y) format

def rasterize_polygon(polygon, mask, width, height):
    """
    Rasterizes a polygon onto a binary mask.
    """
    rasterized = np.zeros((height, width), dtype=np.uint8)

    if not polygon.exterior.coords:
        return rasterized  # Return an empty mask if no coordinates

    int_coords = lambda x, y: (int(round(x)), int(round(y)))
    polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords], dtype=np.int32)

    if polygon_coords.shape[0] < 3:  # A valid polygon needs at least 3 points
        return rasterized  # Return an empty mask for invalid polygons

    cv2.fillPoly(rasterized, [polygon_coords], 1)

    if mask is not None:
        rasterized = rasterized & mask

    return rasterized


def rasterize_and_save_region_masks(regions_to_store, mask, width, height):
    """
    Rasterizes each region mask and returns them.
    """
    masks = {}
    for region_id, region_json in regions_to_store.items():
        region_points = json.loads(region_json)
        polygon = Polygon(region_points)

        rasterized_mask = rasterize_polygon(polygon, mask, width, height)

        # Converting mask to a binary format
        with io.BytesIO() as output:
            mask_image = Image.fromarray(rasterized_mask * 255)
            mask_image.save(output, format="PNG")
            masks[region_id] = output.getvalue()

    return masks

def create_voronoi_overlay(image_path, output_path, points):
    """
    Creates a Voronoi overlay on an image and saves it.
    """
    image = plt.imread(image_path)
    vor = Voronoi(points)

    fig, ax = plt.subplots()
    ax.imshow(image)
    ax.plot(points[:, 0], points[:, 1], 'ko')

    for simplex in vor.ridge_vertices:
        simplex = np.asarray(simplex)
        if np.all(simplex >= 0):
            ax.plot(vor.vertices[simplex, 0], vor.vertices[simplex, 1], 'b-')

    regions_to_store = {}
    for i, region in enumerate(vor.regions):
        if not -1 in region:
            region_id = i + 1
            region_vertices = [vor.vertices[v].tolist() for v in region]
            regions_to_store[region_id] = json.dumps(region_vertices)

    plt.axis('off')
    plt.savefig(output_path, bbox_inches='tight', pad_inches=0)
    plt.close()

    return vor, regions_to_store

def update_database_with_masks(db_path, regions_to_store, masks):
    """
    Updates the database with mask data for each Voronoi region.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Drop the existing table if it exists and create a new one
    cur.execute('DROP TABLE IF EXISTS regions')
    cur.execute('''CREATE TABLE regions (
                    region_id INTEGER PRIMARY KEY,
                    vertices TEXT,
                    mask BLOB)''')

    for region_id, mask_data in masks.items():
        vertices = regions_to_store[region_id]
        # Insert or update record
        cur.execute("INSERT INTO regions (region_id, vertices, mask) VALUES (?, ?, ?)", 
                    (region_id, vertices, mask_data))

    conn.commit()
    conn.close()

# Main script execution
if __name__ == "__main__":
    # Paths and parameters
    map_image_path = 'E:/AoC_Sim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
    output_path = 'E:/AoC_Sim/Assets/voronoi_overlay_map.png'
    db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
    num_regions = 100

    # Processing
    map_image = Image.open(map_image_path).convert('RGBA')
    map_width, map_height = map_image.size
    binary_mask = np.array([pixel[3] != 0 for pixel in map_image.getdata()]).reshape((map_height, map_width))

    points = get_non_transparent_points(map_image_path, num_regions)
    vor, regions_to_store = create_voronoi_overlay(map_image_path, output_path, points)
    masks = rasterize_and_save_region_masks(regions_to_store, binary_mask, map_width, map_height)
    update_database_with_masks(db_path, regions_to_store, masks)
