import json
import sqlite3
import numpy as np
from PIL import Image
from scipy.spatial import Voronoi, voronoi_plot_2d
import matplotlib.pyplot as plt
from shapely.geometry import Polygon
import cv2
import logging

class VoronoiMap:
    def __init__(self, map_image_path, db_path, log_file_path, output_path):
        self.map_image_path = map_image_path
        self.db_path = db_path
        self.log_file_path = log_file_path
        self.output_path = output_path
        self.setup_logging()
        self.load_map_image()
        self.initialize_variables()

    def setup_logging(self):
        logging.basicConfig(filename=self.log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def load_map_image(self):
        self.map_image = Image.open(self.map_image_path).convert('RGBA')
        self.map_width, self.map_height = self.map_image.size
        binary_mask = np.array([pixel[3] != 0 for pixel in self.map_image.getdata()])
        self.binary_mask = binary_mask.reshape((self.map_height, self.map_width))

    def initialize_variables(self):
        self.points = []
        self.num_points = 100
        self.max_attempts = 10000
        self.num_iterations = 10
        self.movement_threshold = 1.0
        self.regions_to_store = {}

    def generate_initial_points(self):
        attempt = 0
        while len(self.points) < self.num_points and attempt < self.max_attempts:
            x, y = np.random.randint(0, self.map_width), np.random.randint(0, self.map_height)
            if self.is_point_on_land(x, y):
                self.points.append([x, y])
            attempt += 1

        self.points = np.array(self.points)
        unique_points = np.unique(self.points, axis=0)
        if len(unique_points) < self.num_points:
            logging.warning(f"Warning: Only {len(unique_points)} unique points were generated.")
        self.points = unique_points

    def is_point_on_land(self, x, y):
        if x < 0 or y < 0 or x >= self.map_width or y >= self.map_height:
            return False
        return self.binary_mask[y, x]

    def rasterize_polygon(self, polygon):
        rasterized = np.zeros_like(self.binary_mask, dtype=np.uint8)
        int_coords = lambda x, y: (int(round(x)), int(round(y)))
        polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords])

        cv2.fillPoly(rasterized, [polygon_coords], 1)
        return rasterized

    def run_voronoi_process(self):
        self.generate_initial_points()
        self.vor = Voronoi(self.points)  # Store the Voronoi diagram as a class attribute
        for idx, point in enumerate(self.points):
            region_index = self.vor.point_region[idx]
            region = self.vor.regions[region_index]

            # if -1 in region:  # Skip regions that extend to infinity
            #     logging.info(f"Region {idx} skipped due to infinite region.")
            #     continue

            # if not region:
            #     logging.info(f"Region {idx} skipped due to invalid region indices.")
            #     continue

            polygon = Polygon([self.vor.vertices[i] for i in region if i != -1])
            self.regions_to_store[idx] = json.dumps([list(p) for p in polygon.exterior.coords])

    def plot_and_save_voronoi(self):
        missing_regions = self.get_missing_regions_from_log()
        fig, ax = plt.subplots(figsize=(self.map_width / 100, self.map_height / 100))
        ax.imshow(self.map_image)
        voronoi_plot_2d(self.vor, ax=ax, show_vertices=False, line_colors='black', point_size=2)  # Use the stored Voronoi diagram

        # Highlighting missing regions if any
        for region_index in missing_regions:
            adjusted_index = region_index - 1
            if adjusted_index in self.vor.point_region:
                region = self.vor.regions[self.vor.point_region[adjusted_index]]
                if not -1 in region and region:
                    polygon = [self.vor.vertices[i] for i in region]
                    ax.fill(*zip(*polygon), color='red', alpha=0.4)
                    logging.info(f"Highlighting region {region_index}")

        ax.invert_yaxis()
        plt.savefig(self.output_path, bbox_inches='tight')
        plt.close()
        logging.info(f"Voronoi overlay saved to {self.output_path}")

    def get_missing_regions_from_log(self):
        missing_regions = []
        with open(self.log_file_path, 'r') as log_file:
            for line in log_file:
                if "Missing regions in DB:" in line:
                    missing_regions = [int(x.strip()) for x in line.split(':')[1].split(',')]
        return missing_regions

    def store_voronoi_regions_to_db(self):
        written_regions = set()
        logging.info(f"Storing {len(self.regions_to_store)} regions.")
        try:
            with sqlite3.connect(self.db_path) as connection:
                cursor = connection.cursor()
                for idx, region_json in self.regions_to_store.items():
                    logging.info(f"Processing region {idx} for DB storage.")
                    centroid = self.points[idx]
                    x_real, y_real = centroid[0], centroid[1]

                    if region_json and isinstance(region_json, str) and len(region_json) > 0:
                        try:
                            json.loads(region_json)
                            cursor.execute('''
                                INSERT INTO regions (region_id, vertices, x_REAL, y_REAL)
                                VALUES (?, ?, ?, ?)
                            ''', (idx, region_json, x_real, y_real))

                            if cursor.rowcount > 0:
                                written_regions.add(idx)
                                logging.info(f"Region {idx} successfully written to DB.")
                            else:
                                logging.warning(f"Failed to write region {idx} to DB.")
                        except json.JSONDecodeError:
                            logging.error(f"Invalid JSON format for region {idx}.")
                    else:
                        logging.warning(f"Empty or invalid region data for region {idx}.")

                connection.commit()
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
        except Exception as e:
            logging.error(f"General error: {e}")

        missing_regions = set(range(1, self.num_points + 1)) - written_regions
        if missing_regions:
            logging.warning(f"Missing regions in DB: {sorted(missing_regions)}")
        else:
            logging.info("All regions successfully written to DB.")

    def setup_regions_table(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DROP TABLE IF EXISTS regions")
                cursor.execute('''
                    CREATE TABLE regions (
                        region_id INTEGER PRIMARY KEY,
                        vertices TEXT,
                        x_REAL REAL,
                        y_REAL REAL
                    )
                ''')
                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error setting up the regions table in DB: {e}")

if __name__ == "__main__":
    map_image_path = 'E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
    db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
    log_file_path = 'voronoi_log.log'
    output_path = 'E:/AoCSim/Assets/voronoi_overlay_map.png'

    voronoi_map = VoronoiMap(map_image_path, db_path, log_file_path, output_path)
    voronoi_map.setup_regions_table()
    voronoi_map.run_voronoi_process()
    voronoi_map.store_voronoi_regions_to_db()
    voronoi_map.plot_and_save_voronoi()

