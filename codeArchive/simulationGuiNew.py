import sys
import json
import sqlite3
import logging
import os
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import (
    QGraphicsPolygonItem, QGraphicsEllipseItem, QVBoxLayout, QWidget, QPushButton,
    QCheckBox, QGraphicsItem, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)
from PyQt5.QtGui import QBrush, QColor, QPen, QIcon, QPixmap, QPolygonF
from PyQt5.QtCore import Qt, QPointF, QRect, QPropertyAnimation
from config import Settings
from simulation.runSimulationNew import simulate, SimulationControl, reset_simulation_data

# Set the log file path to the current working directory
log_file_path = os.path.join(os.getcwd(), 'debug.log')

# Ensure the log file directory exists
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_path, filemode='w')
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger().addHandler(console)

logging.debug("Logging initialized")

config = Settings()

class SharedVertexManager:
    def __init__(self):
        self.vertices = {}  # Dictionary to store vertices with their connected polygons

    def add_vertex(self, x, y, polygon):
        key = (x, y)
        if key not in self.vertices:
            self.vertices[key] = []
        self.vertices[key].append(polygon)

    def update_vertex(self, old_pos, new_pos):
        if old_pos in self.vertices:
            polygons = self.vertices.pop(old_pos)
            self.vertices[new_pos] = polygons
            for polygon in polygons:
                polygon.update_vertex_position(old_pos, new_pos)

    def get_connected_polygons(self, x, y):
        return self.vertices.get((x, y), [])

class VertexItem(QGraphicsEllipseItem):
    def __init__(self, x, y, radius, parent_polygon):
        super().__init__(-radius, -radius, radius * 2, radius * 2)
        self.setPos(x, y)
        self.setBrush(QBrush(QColor(255, 0, 0, 150)))
        self.setPen(QPen(Qt.NoPen))
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)
        self.parent_polygon = parent_polygon

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.parent_polygon.edit_mode:
            new_pos = value
            if new_pos != self.pos():
                # Prevent recursive updates
                try:
                    logging.getLogger().setLevel(logging.CRITICAL)
                    self.parent_polygon.updateVertex(self, new_pos)
                finally:
                    logging.getLogger().setLevel(logging.DEBUG)
                logging.debug(f"Vertex moved to: {new_pos}")
        return super().itemChange(change, value)

class PolygonItem(QGraphicsPolygonItem):
    def __init__(self, polygon, region_id=None, shared_vertex_manager=None, parent=None):
        super().__init__(polygon, parent)
        self.region_id = region_id
        self.shared_vertex_manager = shared_vertex_manager
        self.setAcceptHoverEvents(True)
        self.normal_brush = QBrush(Qt.transparent)
        self.hover_brush = QBrush(QColor(255, 255, 0, 100))
        self.edit_mode = False
        self.setBrush(self.normal_brush)
        self.setPen(QPen(Qt.black, 2))
        self.vertex_radius = 5
        self.vertex_items = []

        if self.shared_vertex_manager:
            for point in self.polygon():
                self.shared_vertex_manager.add_vertex(point.x(), point.y(), self)

    def hoverEnterEvent(self, event):
        if not self.edit_mode:
            self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self.edit_mode:
            self.setBrush(self.normal_brush)
        super().hoverLeaveEvent(event)

    def setEditMode(self, mode):
        self.edit_mode = mode
        if self.edit_mode:
            self.setBrush(Qt.transparent)
            self.setFlags(QGraphicsItem.ItemIsSelectable)
            self.createVertexItems()
            self.setVerticesVisible(True)
        else:
            self.setBrush(self.normal_brush)
            self.setFlags(QGraphicsItem.ItemIsSelectable)
            self.clearVertexItems()

    def createVertexItems(self):
        logging.debug("Creating vertex items")
        self.clearVertexItems()
        for point in self.polygon():
            vertex_item = VertexItem(point.x(), point.y(), self.vertex_radius, self)
            self.scene().addItem(vertex_item)
            self.vertex_items.append(vertex_item)
            logging.debug(f"Vertex item created at ({point.x()}, {point.y()})")

    def updateVertex(self, vertex_item, new_pos):
        old_pos = vertex_item.pos()
        try:
            index = self.vertex_items.index(vertex_item)
            polygon = self.polygon()
            if polygon.at(index) != new_pos:
                polygon.replace(index, new_pos)
                self.setPolygon(polygon)
                self.updateVertexItems()
                if self.shared_vertex_manager:
                    self.shared_vertex_manager.update_vertex((old_pos.x(), old_pos.y()), (new_pos.x(), new_pos.y()))
        except Exception as e:
            logging.error(f"Error in updateVertex: {e}")

    def update_vertex_position(self, old_pos, new_pos):
        try:
            polygon = self.polygon()
            for i in range(polygon.count()):
                if polygon.at(i) == old_pos:
                    polygon.replace(i, new_pos)
            self.setPolygon(polygon)
            self.updateVertexItems()
        except Exception as e:
            logging.critical(f"Critical error in update_vertex_position: {e}")

    def updateVertexItems(self):
        try:
            for vertex_item, point in zip(self.vertex_items, self.polygon()):
                if vertex_item.pos() != point:
                    vertex_item.setPos(point)
        except Exception as e:
            logging.critical(f"Critical error in updateVertexItems: {e}")

    def clearVertexItems(self):
        logging.debug("Clearing vertex items")
        if self.scene() is not None:
            for vertex_item in self.vertex_items:
                self.scene().removeItem(vertex_item)
                logging.debug(f"Vertex item removed at ({vertex_item.pos().x()}, {vertex_item.pos().y()})")
        else:
            logging.error("Cannot clear vertex items: scene is None")
        self.vertex_items.clear()

    def setVerticesVisible(self, visible):
        try:
            for vertex_item in self.vertex_items:
                vertex_item.setVisible(visible)
        except Exception as e:
            logging.error(f"Error in setVerticesVisible: {e}")

class MyScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.added_items = set()

    def add_item_safe(self, item):
        if item not in self.added_items:
            self.addItem(item)
            self.added_items.add(item)

class MapGraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super(MapGraphicsView, self).__init__(parent)
        self.scene = MyScene(self)
        self.setScene(self.scene)
        self.setMouseTracking(True)
        self.map_pixmap = QPixmap(config.get('map_image_path'))
        self.pixmap_item = QGraphicsPixmapItem(self.map_pixmap)
        self.pixmap_item.setZValue(-1)
        self.scene.addItem(self.pixmap_item)
        self.setSceneRect(self.pixmap_item.boundingRect())
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMinimumSize(1, 1)
        self.zoom_level = 0
        self.max_zoom_level = 100

    def setEditMode(self, editMode):
        logging.debug(f"Setting edit mode to {editMode}")
        for item in self.scene.items():
            if isinstance(item, PolygonItem):
                item.setEditMode(editMode)

        if editMode:
            self.setDragMode(QGraphicsView.NoDrag)
        else:
            self.setDragMode(QGraphicsView.ScrollHandDrag)

    def wheelEvent(self, event):
        try:
            zoomInFactor = 1.25
            zoomOutFactor = 1 / zoomInFactor
            oldPos = self.mapToScene(event.pos())
            if event.angleDelta().y() > 0:
                zoomFactor = zoomInFactor
                self.zoom_level += 1
            else:
                if self.transform().m11() > 0.1:
                    zoomFactor = zoomOutFactor
                    self.zoom_level -= 1
                else:
                    zoomFactor = 1
            self.scale(zoomFactor, zoomFactor)
            newPos = self.mapToScene(event.pos())
            delta = newPos - oldPos
            self.translate(delta.x(), delta.y())
        except Exception as e:
            logging.error(f"Error in wheelEvent: {e}")

class SimulationThread(QtCore.QThread):
    def __init__(self, control, db_path, allow_exp_banking):
        super().__init__()
        self.control = control
        self.db_path = db_path
        self.allow_exp_banking = allow_exp_banking

    def run(self):
        try:
            simulate(self.control, self.db_path, self.allow_exp_banking, real_time=False)
        except Exception as e:
            logging.error(f"Error in SimulationThread run: {e}")

    def pause(self):
        try:
            self.control.pause()
        except Exception as e:
            logging.error(f"Error in SimulationThread pause: {e}")

    def resume(self):
        try:
            self.control.resume()
        except Exception as e:
            logging.error(f"Error in SimulationThread resume: {e}")

    def reset_simulation_data(self):
        try:
            reset_simulation_data(self.db_path)
        except Exception as e:
            logging.error(f"Error in SimulationThread reset_simulation_data: {e}")

class CollapsibleSidebar(QWidget):
    editModeChanged = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super(CollapsibleSidebar, self).__init__(parent)
        self.layout = QVBoxLayout(self)
        self.isSidebarVisible = False
        self.editMode = False

        self.closeButton = QPushButton()
        self.closeButton.setIcon(QIcon(config.get('close_icon_path')))
        self.closeButton.setFixedSize(50, 50)
        self.closeButton.clicked.connect(self.toggle)

        self.contentWidget = QWidget()
        self.contentLayout = QVBoxLayout(self.contentWidget)

        self.editRegionBoundariesButton = QPushButton('Edit Region Boundaries')
        self.contentLayout.addWidget(self.editRegionBoundariesButton)

        self.keepChangesButton = QPushButton('Keep Boundary Changes')
        self.discardChangesButton = QPushButton('Discard Boundary Changes')
        self.keepChangesButton.hide()
        self.discardChangesButton.hide()
        self.contentLayout.addWidget(self.keepChangesButton)
        self.contentLayout.addWidget(self.discardChangesButton)

        self.editRegionBoundariesButton.clicked.connect(self.toggleEditMode)

        self.startButton = QPushButton('Start New Simulation')
        self.pauseResumeButton = QPushButton('Pause Simulation')
        self.allowExpBankingCheckbox = QCheckBox("Allow Experience Banking")
        self.contentLayout.addWidget(self.startButton)
        self.contentLayout.addWidget(self.pauseResumeButton)
        self.contentLayout.addWidget(self.allowExpBankingCheckbox)

        self.layout.addWidget(self.closeButton)
        self.layout.addWidget(self.contentWidget)

    def toggle(self):
        try:
            self.isSidebarVisible = not self.isSidebarVisible
            logging.debug(f"Sidebar visibility toggled to {self.isSidebarVisible}")
            self.setVisible(self.isSidebarVisible)
            if self.isSidebarVisible:
                self.closeButton.setIcon(QIcon(config.get('close_icon_path')))
            else:
                self.closeButton.setIcon(QIcon(config.get('hamburger_icon_path')))
        except Exception as e:
            logging.error(f"Error in toggle: {e}")

    def toggleEditMode(self):
        try:
            self.editMode = not self.editMode
            logging.debug(f"Edit mode toggled to {self.editMode}")
            if self.editMode:
                self.editRegionBoundariesButton.hide()
                self.keepChangesButton.show()
                self.discardChangesButton.show()
            else:
                self.editRegionBoundariesButton.show()
                self.keepChangesButton.hide()
                self.discardChangesButton.hide()
            self.editModeChanged.emit(self.editMode)
        except Exception as e:
            logging.error(f"Error in toggleEditMode: {e}")

class SimulationApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_path = config.get('db_path')
        self.control = SimulationControl()
        self.isPaused = False
        self.sidebar = None
        self.initUI()

    def showEvent(self, event):
        try:
            super().showEvent(event)
            self.load_and_draw_regions()
        except Exception as e:
            logging.error(f"Error in showEvent: {e}")

    def load_and_draw_regions(self):
        try:
            regions_vertices = self.load_regions_from_db()
            for region_id, vertices_json in regions_vertices.items():
                vertices = json.loads(vertices_json)
                qpoints = [QPointF(x, y) for x, y in vertices]
                polygon = QPolygonF(qpoints)
                polygon_item = PolygonItem(polygon, region_id=region_id, shared_vertex_manager=self.shared_vertex_manager)
                self.mapView.scene.add_item_safe(polygon_item)
        except Exception as e:
            logging.error(f"Error in load_and_draw_regions: {e}")

    def load_regions_from_db(self):
        try:
            regions_vertices = {}
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT region_id, vertices FROM regions")
                rows = cursor.fetchall()
                for region_id, vertices_json in rows:
                    regions_vertices[region_id] = vertices_json
            return regions_vertices
        except sqlite3.Error as e:
            logging.error(f"Database error: {e}")
            return {}
        except Exception as e:
            logging.error(f"Error in load_regions_from_db: {e}")
            return {}

    def initUI(self):
        try:
            self.setWindowTitle('Node Simulation')
            self.setGeometry(100, 100, 1200, 800)
            self.mapView = MapGraphicsView(self)
            self.setCentralWidget(self.mapView)

            self.hamburgerButton = QPushButton(self)
            self.hamburgerButton.setIcon(QIcon(config.get('hamburger_icon_path')))
            self.hamburgerButton.setFixedSize(50, 50)
            self.hamburgerButton.clicked.connect(self.toggleSidebar)
            self.hamburgerButton.move(0, 0)

            self.sidebar = CollapsibleSidebar(self)
            self.sidebar.setFixedHeight(self.height())
            self.sidebar.setVisible(False)
            self.sidebar.move(-self.sidebar.width(), 0)

            self.sidebar.startButton.clicked.connect(self.startNewSimulation)
            self.sidebar.pauseResumeButton.clicked.connect(self.toggleSimulationPause)
            self.sidebar.allowExpBankingCheckbox.setChecked(True)
            self.sidebar.pauseResumeButton.setEnabled(False)

            self.sidebarAnimation = QPropertyAnimation(self.sidebar, b"geometry")
            self.sidebarAnimation.setDuration(300)

            self.sidebar.editModeChanged.connect(self.mapView.setEditMode)
            self.shared_vertex_manager = SharedVertexManager()
        except Exception as e:
            logging.error(f"Error in initUI: {e}")

    def toggleSidebar(self):
        try:
            sidebar_width = self.sidebar.width()
            if self.sidebar.isVisible():
                logging.debug("Hiding sidebar")
                self.sidebarAnimation.setStartValue(self.sidebar.geometry())
                self.sidebarAnimation.setEndValue(QRect(-sidebar_width, 0, sidebar_width, self.height()))
                self.sidebarAnimation.finished.connect(lambda: self.sidebar.setVisible(False))
            else:
                logging.debug("Showing sidebar")
                self.sidebar.setVisible(True)
                self.sidebarAnimation.setStartValue(QRect(-sidebar_width, 0, sidebar_width, self.height()))
                self.sidebarAnimation.setEndValue(QRect(0, 0, sidebar_width, self.height()))
            self.sidebarAnimation.start()
        except Exception as e:
            logging.error(f"Error in toggleSidebar: {e}")

    def startNewSimulation(self):
        try:
            allow_exp_banking = self.sidebar.allowExpBankingCheckbox.isChecked()
            self.simulationThread = SimulationThread(self.control, self.db_path, allow_exp_banking)
            if not self.simulationThread.isRunning():
                self.simulationThread.reset_simulation_data()
                self.simulationThread.start()
                self.sidebar.pauseResumeButton.setEnabled(True)
                self.sidebar.startButton.setEnabled(False)
        except Exception as e:
            logging.error(f"Error in startNewSimulation: {e}")

    def toggleSimulationPause(self):
        try:
            if self.isPaused:
                self.simulationThread.resume()
                self.sidebar.pauseResumeButton.setText('Pause Simulation')
                self.isPaused = False
            else:
                self.simulationThread.pause()
                self.sidebar.pauseResumeButton.setText('Resume Simulation')
                self.isPaused = True
        except Exception as e:
            logging.error(f"Error in toggleSimulationPause: {e}")

    def closeEvent(self, event):
        try:
            if self.simulationThread.isRunning():
                self.control.pause()
                self.simulationThread.wait()
            event.accept()
        except Exception as e:
            logging.error(f"Error in closeEvent: {e}")

def main():
    try:
        app = QtWidgets.QApplication(sys.argv)
        ex = SimulationApp()
        ex.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.error(f"Error in main: {e}")

if __name__ == '__main__':
    main()
