import numpy as np
from scipy.spatial import Voronoi
import matplotlib.pyplot as plt
from PIL import Image
import sqlite3
import random
import os
import json
import cv2
from shapely.geometry import Polygon

def rasterize_and_save_region_masks(regions_to_store, mask, width, height, output_directory):
    """
    Rasterize each region and save the mask as an image file.
    """
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    for region_id, region_json in regions_to_store.items():
        # Convert JSON string back to list of points
        region_points = json.loads(region_json)
        polygon = Polygon(region_points)

        # Rasterize the polygon
        rasterized_mask = rasterize_polygon(polygon, mask, width, height)

        # Save the rasterized mask as an image
        mask_image = Image.fromarray(rasterized_mask * 255)  # Convert binary mask to image
        mask_image_path = os.path.join(output_directory, f'region_mask_{region_id}.png')
        mask_image.save(mask_image_path)

def get_non_transparent_points(image_path, num_points):
    image = Image.open(image_path)
    image = image.convert("RGBA")
    data = np.array(image)

    # Get non-transparent pixels
    non_transparent = np.argwhere(data[:,:,3] != 0)

    # Check if there are enough unique points
    if len(non_transparent) < num_points:
        raise ValueError(f"Not enough non-transparent points. Only found {len(non_transparent)} points.")

    # Randomly select points, ensuring they are unique
    selected_indices = np.random.choice(len(non_transparent), num_points, replace=False)
    selected_points = non_transparent[selected_indices]
   
    print(f"Selected {len(selected_points)} unique points.")  # Debugging information

    # Ensure points are in the correct format
    selected_points_array = np.array(selected_points)
    return selected_points_array[:, [1, 0]]  # Swap columns to get (x, y) format

def rasterize_polygon(polygon, mask, width, height):
    """
    Rasterize the polygon onto the binary mask.
    Returns a binary mask where the polygon area is filled.
    """
    rasterized = np.zeros((height, width), dtype=np.uint8)  # Create a blank mask

    # Convert polygon points to integer coordinates
    int_coords = lambda x, y: (int(round(x)), int(round(y)))
    polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords])
    
    # Fill the polygon in the rasterized mask
    cv2.fillPoly(rasterized, [polygon_coords], 1)

    # Apply the original mask if needed (to clip to non-transparent areas of the image)
    if mask is not None:
        rasterized = rasterized & mask

    return rasterized



def create_voronoi_overlay(image_path, output_path, points):
    image = plt.imread(image_path)
    vor = Voronoi(points)

    fig, ax = plt.subplots()
    ax.imshow(image)
    ax.plot(points[:, 0], points[:, 1], 'ko')

    # Process ridge vertices
    for simplex in vor.ridge_vertices:
        simplex = np.asarray(simplex)
        if np.all(simplex >= 0):  # Check if all vertices are valid (not -1)
            ax.plot(vor.vertices[simplex, 0], vor.vertices[simplex, 1], 'b-')

    plt.axis('off')
    plt.savefig(output_path, bbox_inches='tight', pad_inches=0)
    plt.close()

    return vor

def update_database_with_masks(db_path, voronoi_data, regions_to_store, output_masks_directory):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Modify the table to include a column for mask paths
    cur.execute('''CREATE TABLE IF NOT EXISTS regions (
                    region_id INTEGER PRIMARY KEY,
                    vertices TEXT,
                    mask_path TEXT)''')

    for i, region in enumerate(voronoi_data.regions):
        if not -1 in region:  # Ignore unbounded regions
            region_id = i + 1  # Assuming region IDs are 1-indexed
            vertices = ','.join([str(voronoi_data.vertices[v]) for v in region])
            mask_path = os.path.join(output_masks_directory, f'region_mask_{region_id}.png')
            cur.execute("INSERT INTO regions (region_id, vertices, mask_path) VALUES (?, ?, ?)", 
                        (region_id, vertices, mask_path))

    conn.commit()
    conn.close()

# Create regions_to_store dictionary with the needed data
regions_to_store = {}

# Path to the PNG image
map_image_path = 'E:/AoC_Sim/Assets/Map_of_Verra_cleanup_notext_nowater.png'

# Load map image and create binary mask
map_image = Image.open(map_image_path).convert('RGBA')
map_width, map_height = map_image.size
binary_mask = np.array([pixel[3] != 0 for pixel in map_image.getdata()])
binary_mask = binary_mask.reshape((map_height, map_width))

# Number of Voronoi regions
num_regions = 100

# Get points for Voronoi
points = get_non_transparent_points(map_image_path, num_regions)

# Ensure points are in the correct format before passing to Voronoi
if points.shape[1] != 2:
    raise ValueError("Points array does not have the correct shape.")

# Create Voronoi overlay
output_path = 'E:/AoC_Sim/Assets/voronoi_overlay_map.png'
vor = create_voronoi_overlay(map_image_path, output_path, points)


# Update database
db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'

# Update database with mask paths
update_database_with_masks(db_path, vor, regions_to_store, output_masks_directory)

# Directory to store the masks
output_masks_directory = 'E:/AoC_Sim/Assets/Region_Masks'

# Call the function after storing regions in the database
rasterize_and_save_region_masks(regions_to_store, binary_mask, map_width, map_height, output_masks_directory)