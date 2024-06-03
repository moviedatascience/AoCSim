from PyQt5.QtCore import QPointF

class SharedVertexManager:
    def __init__(self):
        self.vertices = {}  # Dictionary to store vertices with their connected polygons

    def add_vertex(self, x, y, polygon):
        key = (x, y)
        if key not in self.vertices:
            self.vertices[key] = []
        self.vertices[key].append(polygon)

    def update_vertex(self, old_pos, new_pos):
        old_key = (old_pos.x(), old_pos.y())  # Convert QPointF to tuple
        new_key = (new_pos.x(), new_pos.y())  # Convert QPointF to tuple
        if old_key in self.vertices:
            polygons = self.vertices.pop(old_key)
            self.vertices[new_key] = polygons
            for polygon in polygons:
                polygon.update_vertex_position(QPointF(old_key[0], old_key[1]), QPointF(new_key[0], new_key[1]))

    def get_connected_polygons(self, x, y):
        return self.vertices.get((x, y), [])
