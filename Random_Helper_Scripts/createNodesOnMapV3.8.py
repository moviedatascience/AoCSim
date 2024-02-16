import numpy as np
import matplotlib.pyplot as plt
import json
import cv2
from PIL import Image
import sqlite3
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, MultiPoint, Point
import io

def get_non_transparent_points(image_path, num_points):
    image = Image.open(image_path).convert("RGBA")
    data = np.array(image)

    non_transparent = np.argwhere(data[:, :, 3] != 0)

    if len(non_transparent) < num_points:
        raise ValueError(f"Not enough non-transparent points. Only found {len(non_transparent)} points.")

    selected_indices = np.random.choice(len(non_transparent), num_points, replace=False)
    selected_points = non_transparent[selected_indices]

    return selected_points[:, [1, 0]]  # Convert to (x, y) format

def rasterize_polygon(polygon, mask, width, height):
    rasterized = np.zeros((height, width), dtype=np.uint8)
    int_coords = lambda x, y: (int(round(x)), int(round(y)))
    polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords], dtype=np.int32)
    cv2.fillPoly(rasterized, [polygon_coords], 1)
    if mask is not None:
        rasterized = rasterized & mask
    return rasterized

def rasterize_and_save_region_masks(regions_to_store, mask, width, height):
    masks = {}
    for region_id, region_json in regions_to_store.items():
        region_points = json.loads(region_json)
        polygon = Polygon(region_points)
        rasterized_mask = rasterize_polygon(polygon, mask, width, height)
        with io.BytesIO() as output:
            mask_image = Image.fromarray(rasterized_mask * 255)
            mask_image.save(output, format="PNG")
            masks[region_id] = output.getvalue()
    return masks

def create_voronoi_overlay(image_path, output_path, points, mask):
    image = plt.imread(image_path)
    vor = Voronoi(points)
    
    # Create a bounding box that is larger than the map
    min_x, min_y = points.min(axis=0)
    max_x, max_y = points.max(axis=0)
    margin = 100 # You can increase the margin if needed
    bounding_box = Polygon([(min_x-margin, min_y-margin), (max_x+margin, min_y-margin), (max_x+margin, max_y+margin), (min_x-margin, max_y+margin)])
    
    # Create a boundary polygon from the non-transparent areas of the image
    boundary = MultiPoint([Point(x, y) for y, x in np.argwhere(mask)]).convex_hull

    fig, ax = plt.subplots()
    ax.imshow(image)
    ax.plot(points[:, 0], points[:, 1], 'ko')

    regions_to_store = {}
    for pointidx, region in enumerate(vor.point_region):
        region_id = pointidx + 1
        vertices = vor.regions[region]
        
        # Handle points at infinity
        if -1 in vertices:
            vertices = [v if v != -1 else len(vor.vertices) for v in vertices]
            # Find the ridge vertices that are connected to the current point
            # and are not at infinity
            infinite_ridge_indices = np.where(vor.ridge_points == pointidx)[0]
            for ridge_index in infinite_ridge_indices:
                ridge_vertices = vor.ridge_vertices[ridge_index]
                finite_vertices = [v for v in ridge_vertices if v >= 0]
                vertices.extend(finite_vertices)
            vertices = list(set(vertices))  # remove duplicates

        # If the region is empty, skip
        if not vertices or len(vertices) == 0:
            continue

        # Create the polygon for this region
        region_poly = Polygon([vor.vertices[v] for v in vertices])

        # Clip the polygon to the bounding box
        region_poly = region_poly.intersection(bounding_box)

        # Clip the polygon to the boundary (non-transparent area)
        region_poly = region_poly.intersection(boundary)

        # If the region is empty after clipping, skip
        if region_poly.is_empty:
            continue

        # Plot the polygon
        x, y = region_poly.exterior.xy
        ax.plot(x, y, 'b-')
        
        regions_to_store[region_id] = json.dumps(list(zip(x, y)))

    plt.axis('off')
    plt.savefig(output_path, bbox_inches='tight', pad_inches=0)
    plt.close()

    return vor, regions_to_store

def update_database_with_masks(db_path, regions_to_store, masks):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('DROP TABLE IF EXISTS regions')
    cur.execute('''CREATE TABLE regions (
                    region_id INTEGER PRIMARY KEY,
                    vertices TEXT,
                    mask BLOB)''')

    for region_id, mask_data in masks.items():
        vertices = regions_to_store[region_id]
        cur.execute("INSERT INTO regions (region_id, vertices, mask) VALUES (?, ?, ?)", 
                    (region_id, vertices, mask_data))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    map_image_path = 'E:/AoC_Sim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
    output_path = 'E:/AoC_Sim/Assets/voronoi_overlay_map.png'
    db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
    num_regions = 100

    map_image = Image.open(map_image_path).convert('RGBA')
    map_width, map_height = map_image.size
    binary_mask = np.array(map_image)[:, :, 3] != 0

    points = get_non_transparent_points(map_image_path, num_regions)
    vor, regions_to_store = create_voronoi_overlay(map_image_path, output_path, points, binary_mask)
    masks = rasterize_and_save_region_masks(regions_to_store, binary_mask, map_width, map_height)
    update_database_with_masks(db_path, regions_to_store, masks)
