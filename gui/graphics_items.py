from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsPolygonItem, QGraphicsItem
from PyQt5.QtGui import QBrush, QColor, QPen
from PyQt5.QtCore import Qt, QPointF
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class SharedVertexManager:
    def __init__(self):
        self.vertices = {}  # Dictionary to store vertices and their associated polygons

    def add_vertex(self, x, y, polygon):
        key = (x, y)  # Convert QPointF to tuple
        logging.debug(f"Adding vertex {key} to polygon {polygon}")
        if key not in self.vertices:
            self.vertices[key] = []
        if polygon not in self.vertices[key]:
            self.vertices[key].append(polygon)
            logging.debug(f"Vertex {key} added to polygon {polygon}")

    def update_vertex(self, old_pos, new_pos):
        old_key = (old_pos.x(), old_pos.y())  # Convert QPointF to tuple
        new_key = (new_pos.x(), new_pos.y())  # Convert QPointF to tuple
        logging.debug(f"Updating vertex from {old_key} to {new_key}")
        if old_key in self.vertices:
            polygons = self.vertices.pop(old_key)
            if new_key not in self.vertices:
                self.vertices[new_key] = []
            self.vertices[new_key].extend(polygons)
            logging.debug(f"Updated vertex from {old_key} to {new_key}")
            for polygon in polygons:
                logging.debug(f"Updating polygon {polygon} with new vertex position {new_pos}")
                polygon.update_vertex_position(QPointF(old_key[0], old_key[1]), QPointF(new_key[0], new_key[1]))
        else:
            logging.error(f"Old key {old_key} not found in vertices")

class VertexItem(QGraphicsEllipseItem):
    """
    A QGraphicsEllipseItem subclass that represents a vertex in a polygon.

    Attributes:
        parent_polygon (PolygonItem): The parent polygon to which this vertex belongs.
    """
    
    def __init__(self, x, y, radius, shared_vertex_manager):
        """
        Initialize a VertexItem.

        Parameters:
            x (float): The x-coordinate of the vertex.
            y (float): The y-coordinate of the vertex.
            radius (float): The radius of the vertex circle.
            shared_vertex_manager (SharedVertexManager): The shared vertex manager.
        """
        super().__init__(-radius, -radius, radius * 2, radius * 2)  # Create a circle with the given radius
        self.setPos(x, y)  # Set the position of the vertex
        self.setBrush(QBrush(QColor(255, 0, 0, 150)))  # Set the fill color of the vertex
        self.setPen(QPen(Qt.NoPen))  # Remove the border of the vertex
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)  # Make the vertex movable
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)  # Enable geometry change notifications
        self.shared_vertex_manager = shared_vertex_manager  # Store the shared vertex manager

    def itemChange(self, change, value):
        """
        Handle item change events.

        Parameters:
            change (QGraphicsItem.GraphicsItemChange): The type of change.
            value (QVariant): The new value of the changed property.

        Returns:
            QVariant: The accepted value of the changed property.
        """
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value
            if new_pos != self.pos():
                # Prevent recursive updates
                try:
                    logging.getLogger().setLevel(logging.CRITICAL)
                    old_pos = self.pos()
                    self.shared_vertex_manager.update_vertex(old_pos, new_pos)
                finally:
                    logging.getLogger().setLevel(logging.DEBUG)
                logging.debug(f"Vertex moved to: {new_pos}")
        return super().itemChange(change, value)  # Call the base class implementation

class PolygonItem(QGraphicsPolygonItem):
    """
    A QGraphicsPolygonItem subclass that represents a polygon with editable vertices.

    Attributes:
        region_id (int): The identifier of the region this polygon represents.
        shared_vertex_manager (SharedVertexManager): Manages shared vertices among multiple polygons.
        edit_mode (bool): Indicates whether the polygon is in edit mode.
        vertex_radius (int): The radius of the vertex items.
        vertex_items (list of VertexItem): The list of vertex items in this polygon.
    """

    def __init__(self, polygon, region_id=None, shared_vertex_manager=None, parent=None):
        """
        Initialize a PolygonItem.

        Parameters:
            polygon (QPolygonF): The polygon shape.
            region_id (int, optional): The identifier for the region.
            shared_vertex_manager (SharedVertexManager, optional): The shared vertex manager.
            parent (QGraphicsItem, optional): The parent QGraphicsItem.
        """
        super().__init__(polygon, parent)  # Initialize the base class with the polygon shape and parent
        self.region_id = region_id  # Store the region identifier
        self.shared_vertex_manager = shared_vertex_manager if shared_vertex_manager else SharedVertexManager()
        self.setAcceptHoverEvents(True)  # Enable hover events
        self.normal_brush = QBrush(Qt.transparent)  # Set the normal fill color to transparent
        self.hover_brush = QBrush(QColor(255, 255, 0, 100))  # Set the hover fill color
        self.edit_mode = False  # Initialize edit mode to False
        self.setBrush(self.normal_brush)  # Set the initial brush
        self.setPen(QPen(Qt.black, 2))  # Set the pen for the polygon border
        self.vertex_radius = 5  # Set the radius for vertex items
        self.vertex_items = []  # Initialize the list of vertex items

        for point in self.polygon():
            self.shared_vertex_manager.add_vertex(point.x(), point.y(), self)  # Add vertices to the shared vertex manager

    def hoverEnterEvent(self, event):
        """
        Handle hover enter events.

        Parameters:
            event (QGraphicsSceneHoverEvent): The hover event.
        """
        if not self.edit_mode:
            self.setBrush(self.hover_brush)  # Change brush to hover brush
        super().hoverEnterEvent(event)  # Call the base class implementation

    def hoverLeaveEvent(self, event):
        """
        Handle hover leave events.

        Parameters:
            event (QGraphicsSceneHoverEvent): The hover event.
        """
        if not self.edit_mode:
            self.setBrush(self.normal_brush)  # Change brush back to normal brush
        super().hoverLeaveEvent(event)  # Call the base class implementation

    def setEditMode(self, mode):
        """
        Set the edit mode for the polygon.

        Parameters:
            mode (bool): True to enable edit mode, False to disable.
        """
        self.edit_mode = mode  # Set the edit mode
        if self.edit_mode:
            self.setBrush(Qt.transparent)  # Set brush to transparent
            self.setFlags(QGraphicsItem.ItemIsSelectable)  # Make the item selectable
            self.createVertexItems()  # Create vertex items
            self.setVerticesVisible(True)  # Make vertices visible
        else:
            self.setBrush(self.normal_brush)  # Set brush to normal brush
            self.setFlags(QGraphicsItem.ItemIsSelectable)  # Ensure item is still selectable
            self.clearVertexItems()  # Clear vertex items

    def createVertexItems(self):
        """
        Create vertex items for each point in the polygon.
        """
        logging.debug("Creating vertex items")
        self.clearVertexItems()  # Clear existing vertex items
        for point in self.polygon():
            vertex_item = VertexItem(point.x(), point.y(), self.vertex_radius, self.shared_vertex_manager)  # Create a new vertex item
            self.scene().addItem(vertex_item)  # Add the vertex item to the scene
            self.vertex_items.append(vertex_item)  # Add the vertex item to the list
            logging.debug(f"Vertex item created at ({point.x()}, {point.y()})")

    def update_vertex_position(self, old_pos, new_pos):
        """
        Update the position of a vertex in the polygon based on the old position.

        Parameters:
            old_pos (QPointF): The old position of the vertex.
            new_pos (QPointF): The new position of the vertex.
        """
        try:
            polygon = self.polygon()  # Get the current polygon
            for i in range(polygon.count()):
                if polygon.at(i) == old_pos:
                    polygon.replace(i, new_pos)  # Replace the old position with the new position
            self.setPolygon(polygon)  # Set the updated polygon
            self.updateVertexItems()  # Update all vertex items
        except Exception as e:
            logging.critical(f"Critical error in update_vertex_position: {e}")

    def updateVertexItems(self):
        """
        Update the positions of all vertex items to match the polygon.
        """
        try:
            for vertex_item, point in zip(self.vertex_items, self.polygon()):
                if vertex_item.pos() != point:
                    vertex_item.setPos(point)  # Update the position of the vertex item
        except Exception as e:
            logging.critical(f"Critical error in updateVertexItems: {e}")

    def clearVertexItems(self):
        """
        Remove all vertex items from the scene.
        """
        logging.debug("Clearing vertex items")
        if self.scene() is not None:
            for vertex_item in self.vertex_items:
                self.scene().removeItem(vertex_item)  # Remove the vertex item from the scene
                logging.debug(f"Vertex item removed at ({vertex_item.pos().x()}, {vertex_item.pos().y()})")
        else:
            logging.error("Cannot clear vertex items: scene is None")
        self.vertex_items.clear()  # Clear the list of vertex items

    def setVerticesVisible(self, visible):
        """
        Set the visibility of all vertex items.

        Parameters:
            visible (bool): True to make vertices visible, False to hide them.
        """
        try:
            for vertex_item in self.vertex_items:
                vertex_item.setVisible(visible)  # Set the visibility of the vertex item
        except Exception as e:
            logging.error(f"Error in setVerticesVisible: {e}")
