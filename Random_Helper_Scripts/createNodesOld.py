import json
import sqlite3
import numpy as np
from PIL import Image
from scipy.spatial import Voronoi, voronoi_plot_2d
import matplotlib.pyplot as plt
from shapely.geometry import Polygon, box, MultiPolygon
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
        self.bounding_box = box(0, 0, self.map_width, self.map_height)
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

    def clip_to_map_bounds(self, polygon):
        logging.debug(f"Original polygon: {polygon}")

        try:
            clipped_polygon = polygon.intersection(self.bounding_box)
            logging.debug(f"Clipped polygon: {clipped_polygon}")

            if clipped_polygon.is_empty:
                logging.info(f"Clipping resulted in an empty polygon: Original {polygon}")
                return None
            else:
                if clipped_polygon.geom_type == 'LineString' or clipped_polygon.geom_type == 'Point':
                    logging.warning(f"Clipping resulted in a degenerate polygon: {clipped_polygon}")
                    return None

                cleaned_polygon = clipped_polygon.buffer(0)

                if isinstance(cleaned_polygon, MultiPolygon):
                    num_polygons = len(cleaned_polygon.geoms)
                    polygon_areas = [p.area for p in cleaned_polygon.geoms]
                    logging.info(f"Clipped MultiPolygon with {num_polygons} polygons, areas: {polygon_areas}")
                    largest_polygon = max(cleaned_polygon, key=lambda p: p.area)
                    return largest_polygon

                return cleaned_polygon
        except Exception as e:
            logging.error(f"Error in clipping polygon: {e}")
            return None

    def compute_efficient_land_centroid(self, polygon, region_id=None):
        rasterized_polygon = self.rasterize_polygon(polygon)
        overlap = rasterized_polygon & self.binary_mask
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

    def rasterize_polygon(self, polygon):
        rasterized = np.zeros_like(self.binary_mask, dtype=np.uint8)
        int_coords = lambda x, y: (int(round(x)), int(round(y)))
        polygon_coords = np.array([int_coords(*point) for point in polygon.exterior.coords])

        cv2.fillPoly(rasterized, [polygon_coords], 1)
        return rasterized
    
    def voronoi_finite_polygons_2d(self, vor, radius=None):
        """
        Reconstruct infinite voronoi regions in a 2D diagram to finite
        regions.
        Parameters
        ----------
        vor : Voronoi
            Input diagram
        radius : float, optional
            Distance to 'points at infinity'.
        Returns
        -------
        regions : list of tuples
            Indices of vertices in each revised Voronoi regions.
        vertices : list of tuples
            Coordinates for revised Voronoi vertices. Same as coordinates
            of input vertices, with 'points at infinity' appended to the
            end.
        """

        if vor.points.shape[1] != 2:
            raise ValueError("Requires 2D input")

        new_regions = []
        new_vertices = vor.vertices.tolist()

        center = vor.points.mean(axis=0)
        if radius is None:
            radius = vor.points.ptp().max() * 2

        # Construct a map containing all ridges for a given point
        all_ridges = {}
        for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
            all_ridges.setdefault(p1, []).append((p2, v1, v2))
            all_ridges.setdefault(p2, []).append((p1, v1, v2))

        # Reconstruct infinite regions
        for p1, region in enumerate(vor.point_region):
            vertices = vor.regions[region]

            if all(v >= 0 for v in vertices):
                # finite region
                new_regions.append(vertices)
                continue

            # reconstruct a non-finite region
            ridges = all_ridges[p1]
            new_region = [v for v in vertices if v >= 0]

            for p2, v1, v2 in ridges:
                if v2 < 0:
                    v1, v2 = v2, v1
                if v1 >= 0:
                    # finite ridge: already in the region
                    continue

                # Compute the missing endpoint of an infinite ridge
                t = vor.points[p2] - vor.points[p1]  # tangent
                t /= np.linalg.norm(t)
                n = np.array([-t[1], t[0]])  # normal

                midpoint = vor.points[[p1, p2]].mean(axis=0)
                direction = np.sign(np.dot(midpoint - center, n)) * n
                far_point = vor.vertices[v2] + direction * radius

                new_region.append(len(new_vertices))
                new_vertices.append(far_point.tolist())

            # sort region counterclockwise
            vs = np.asarray([new_vertices[v] for v in new_region])
            c = vs.mean(axis=0)
            angles = np.arctan2(vs[:, 1] - c[1], vs[:, 0] - c[0])
            new_region = np.array(new_region)[np.argsort(angles)]

            # finish
            new_regions.append(new_region.tolist())

        return new_regions, np.asarray(new_vertices)


    def run_voronoi_process(self):
        self.generate_initial_points()
        self.vor = Voronoi(self.points)  # Save the Voronoi object as an attribute

        # Use voronoi_finite_polygons_2d to get finite regions and vertices
        finite_regions, finite_vertices = self.voronoi_finite_polygons_2d(self.vor)

        # Create a mapping from original region indices to finite_regions indices
        region_mapping = {self.vor.point_region[i]: i for i in range(len(self.vor.point_region))}

        for iteration in range(self.num_iterations):
            logging.info(f"Iteration {iteration + 1}/{self.num_iterations}")
            new_points = np.empty_like(self.points)

            for idx, point in enumerate(self.points):
                original_region_index = self.vor.point_region[idx]
                if original_region_index not in region_mapping:
                    logging.debug(f"Region {idx} skipped due to invalid region indices.")
                    continue

                finite_region_index = region_mapping[original_region_index]
                region = finite_regions[finite_region_index]
                polygon = Polygon([finite_vertices[i] for i in region])

                clipped_polygon = self.clip_to_map_bounds(polygon)

                if clipped_polygon:
                    centroid = self.compute_efficient_land_centroid(clipped_polygon, region_id=idx)
                    if centroid:
                        new_point = np.array(centroid)
                        if np.linalg.norm(new_point - point) < self.movement_threshold:
                            new_points[idx] = new_point
                        else:
                            new_points[idx] = point
                        self.regions_to_store[idx] = json.dumps([list(p) for p in clipped_polygon.exterior.coords])

            self.points = np.copy(new_points)
            movement = np.linalg.norm(self.points - self.vor.points, axis=1)
            if not np.any(movement >= self.movement_threshold):
                logging.info("Early termination due to convergence.")
                break

    def plot_and_save_voronoi(self):
        missing_regions = self.get_missing_regions_from_log()
        fig, ax = plt.subplots(figsize=(self.map_width / 100, self.map_height / 100))
        ax.imshow(self.map_image)
        voronoi_plot_2d(self.vor, ax=ax, show_vertices=False, line_colors='black', point_size=2)  # Use the stored Voronoi diagram
        for region_index in missing_regions:
            adjusted_index = region_index - 1
            if adjusted_index + 1 in self.vor.point_region:  # Use the stored Voronoi diagram
                region = self.vor.regions[self.vor.point_region[adjusted_index + 1]]
                if not -1 in region and region:
                    polygon = [self.vor.vertices[i] for i in region]
                    ax.fill(*zip(*polygon), color='red', alpha=0.4)
                    logging.debug(f"Highlighting region {region_index}")
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
                    log_idx = idx + 1  # Create a separate variable for logging
                    logging.info(f"Processing region {log_idx} for DB storage.")
                    centroid = self.points[idx]
                    x_real, y_real = centroid[0], centroid[1]

                    if region_json and isinstance(region_json, str) and len(region_json) > 0:
                        try:
                            json.loads(region_json)
                            if not (np.isnan(x_real) or np.isnan(y_real)):
                                cursor.execute('''
                                    INSERT INTO regions (region_id, vertices, x_REAL, y_REAL)
                                    VALUES (?, ?, ?, ?)
                                ''', (idx + 1, region_json, x_real, y_real))

                                if cursor.rowcount > 0:
                                    written_regions.add(idx + 1)
                                    logging.info(f"Region {log_idx} successfully written to DB.")
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