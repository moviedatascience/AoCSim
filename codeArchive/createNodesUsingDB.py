from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
import sqlite3
import json

# Define the bounding box of the map image
map_image_path = 'E:/AoC_Sim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
map_image = Image.open(map_image_path).convert('RGBA')
map_width, map_height = map_image.size

# Load the map image
binary_mask = np.array([pixel[3] != 0 for pixel in map_image.getdata()])
binary_mask = binary_mask.reshape((map_height, map_width))

# Fetch the Voronoi region vertices from the database
def fetch_voronoi_regions(db_path):
    regions_vertices = {}
    with sqlite3.connect(db_path) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT region_id, vertices FROM regions")
        rows = cursor.fetchall()
        for region_id, vertices_json in rows:
            regions_vertices[region_id] = json.loads(vertices_json)
    return regions_vertices

# Plot Voronoi regions on the map
def plot_voronoi_regions(regions_vertices, ax):
    for region_id, vertices in regions_vertices.items():
        # Convert vertices to a format that matplotlib can understand
        polygon = Polygon(vertices)
        x, y = polygon.exterior.xy
        ax.fill(x, y, alpha=0.5, fc='yellow', ec='black')

# Main plotting logic
def main():
    db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
    regions_vertices = fetch_voronoi_regions(db_path)
    
    fig, ax = plt.subplots(figsize=(map_width / 100, map_height / 100))
    ax.imshow(map_image)
    plot_voronoi_regions(regions_vertices, ax)
    #ax.invert_yaxis()  # Invert y-axis to match image coordinates
    
    # Save the figure to a file
    output_path = 'E:/AoC_Sim/Assets/voronoi_DB_output.png'
    plt.savefig(output_path, bbox_inches='tight')
    print(f"Saved Voronoi diagram to {output_path}")

if __name__ == '__main__':
    main()
