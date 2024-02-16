import numpy as np
import matplotlib.pyplot as plt
import json
import cv2
from PIL import Image
import sqlite3
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, MultiPoint, Point
from shapely.ops import unary_union
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

    # Create a boundary polygon from the non-transparent areas of the image
    boundary = MultiPoint([Point(x, y) for y, x in np.argwhere(mask)]).convex_hull
    bounding_box = boundary.envelope

    fig, ax = plt.subplots()
    ax.imshow(image)
    ax.plot(points[:, 0], points[:, 1], 'ko')

    regions_to_store = {}
    for pointidx, region_index in enumerate(vor.point_region):
        region_id = pointidx + 1
        vertices = vor.regions[region_index]
        if not vertices:
            continue  # Skip regions that have no vertices

        # Handle infinite vertices
        if -1 in vertices:
            vertices = [v for v in vertices if v != -1]  # Remove -1
            # Create a polygon from the finite vertices
            region_poly = Polygon(vor.vertices[vertices])
            # Find the missing points for infinite vertices
            new_vertices = []
            for v_pair in vor.ridge_vertices:
                if -1 in v_pair:
                    v_pair = [v for v in v_pair if v != -1]  # Get the finite point
                    if len(v_pair) == 0:
                        continue
                    finite_point = vor.vertices[v_pair[0]]
                    t = points[region_index] - finite_point
                    t = t / np.linalg.norm(t)
                    far_point = finite_point + t * np.max([map_width, map_height])
                    new_vertices.append(far_point)
            if new_vertices:
                new_vertices = np.array(new_vertices)
                region_poly = Polygon(np.concatenate((region_poly.exterior.coords, new_vertices)))
        else:
            # Create the polygon for this region from the vertices
            region_poly = Polygon(vor.vertices[vertices])

        # Clip the polygon to the boundary (non-transparent area)
        region_poly = region_poly.intersection(boundary)

        # If the polygon is empty after clipping, skip
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
