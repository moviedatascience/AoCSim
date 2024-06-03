import numpy as np
import matplotlib.pyplot as plt
import os
import json
import cv2
from PIL import Image
import sqlite3
from scipy.spatial import Voronoi
from shapely.geometry import Polygon

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

    int_coords = lambda x, y: (int(round(x)), int(round(y)))
    polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords])

    cv2.fillPoly(rasterized, [polygon_coords], 1)

    if mask is not None:
        rasterized = rasterized & mask

    return rasterized

def rasterize_and_save_region_masks(regions_to_store, mask, width, height, output_directory):
    """
    Rasterizes and saves each region mask as an image file.
    """
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for region_id, region_json in regions_to_store.items():
        region_points = json.loads(region_json)
        polygon = Polygon(region_points)

        rasterized_mask = rasterize_polygon(polygon, mask, width, height)

        mask_image = Image.fromarray(rasterized_mask * 255)
        mask_image_path = os.path.join(output_directory, f'region_mask_{region_id}.png')
        mask_image.save(mask_image_path)

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

def update_database_with_masks(db_path, voronoi_data, regions_to_store, output_masks_directory):
    """
    Updates the database with mask paths for each Voronoi region.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS regions (
                    region_id INTEGER PRIMARY KEY,
                    vertices TEXT,
                    mask_path TEXT)''')

    for i, region in enumerate(voronoi_data.regions):
        if not -1 in region:
            region_id = i + 1
            vertices = ','.join([str(voronoi_data.vertices[v]) for v in region])
            mask_path = os.path.join(output_masks_directory, f'region_mask_{region_id}.png')
            cur.execute("INSERT INTO regions (region_id, vertices, mask_path) VALUES (?, ?, ?)", 
                        (region_id, vertices, mask_path))

    conn.commit()
    conn.close()

# Main script execution
if __name__ == "__main__":
    # Paths and parameters
    map_image_path = 'E:/AoC_Sim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
    output_path = 'E:/AoC_Sim/Assets/voronoi_overlay_map.png'
    db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
    output_masks_directory = 'E:/AoC_Sim/Assets/Region_Masks'
    num_regions = 100

    # Processing
    map_image = Image.open(map_image_path).convert('RGBA')
    map_width, map_height = map_image.size
    binary_mask = np.array([pixel[3] != 0 for pixel in map_image.getdata()]).reshape((map_height, map_width))

    points = get_non_transparent_points(map_image_path, num_regions)
    vor, regions_to_store = create_voronoi_overlay(map_image_path, output_path, points)
    update_database_with_masks(db_path, vor, regions_to_store, output_masks_directory)
    rasterize_and_save_region_masks(regions_to_store, binary_mask, map_width, map_height, output_masks_directory)
