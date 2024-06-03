import sys
import json
import sqlite3
import logging
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QPointF, QRect, QPropertyAnimation
from PyQt5.QtGui import QPolygonF, QIcon, QPixmap
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QPushButton
from config.settings import Settings
from gui.vertex_manager import SharedVertexManager
from gui.graphics_items import PolygonItem
from gui.simulation_thread import SimulationThread
from gui.collapsible_sidebar import CollapsibleSidebar
from simulation.runSimulationNew import SimulationControl
from database.update_tables_script import update_boundaries_in_database, revert_boundaries_to_original

settings = Settings()
db_path = settings.get('db_path')
original_boundaries_table = settings.get('original_boundaries_table', 'original_regions')

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
        self.map_pixmap = QPixmap(settings.get('map_image_path'))
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

class SimulationApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_path = settings.get('db_path')
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
            self.hamburgerButton.setIcon(QIcon(settings.get('hamburger_icon_path')))
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
            self.sidebar.keepBoundaryChanges.connect(self.handleKeepChanges)
            self.sidebar.discardBoundaryChanges.connect(self.handleDiscardChanges)

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

    def handleKeepChanges(self):
        try:
            logging.debug("Handling keep boundary changes")
            new_boundaries = self.get_current_boundary_data()
            update_boundaries_in_database(new_boundaries)
            self.mapView.setEditMode(False)
        except Exception as e:
            logging.error(f"Error in handleKeepChanges: {e}")

    def handleDiscardChanges(self):
        try:
            logging.debug("Handling discard boundary changes")
            
            # Clear current boundaries from the scene
            for item in self.mapView.scene.items():
                if isinstance(item, PolygonItem):
                    self.mapView.scene.removeItem(item)
            
            # Revert to original boundaries
            revert_boundaries_to_original()
            
            # Reload and redraw regions to show original boundaries
            self.load_and_draw_regions()
            
            # Exit edit mode
            self.mapView.setEditMode(False)
        except Exception as e:
            logging.error(f"Error in handleDiscardChanges: {e}")

    def get_current_boundary_data(self):
        try:
            current_boundaries = []
            for item in self.mapView.scene.items():
                if isinstance(item, PolygonItem):
                    vertices = [(point.x(), point.y()) for point in item.polygon()]
                    current_boundaries.append({
                        "id": item.region_id,
                        "vertices": json.dumps(vertices)
                    })
            return current_boundaries
        except Exception as e:
            logging.error(f"Error in get_current_boundary_data: {e}")
            return []

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
