from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QGraphicsRectItem
from PyQt5.QtGui import QBrush, QColor, QPen
from PyQt5.QtCore import Qt, QRectF
import sys
import sqlite3
from run_simulation import simulate, SimulationControl, reset_simulation_data

class HoverableRectItem(QGraphicsRectItem):
    def __init__(self, rect, region_id=None, parent=None):
        super().__init__(rect, parent)
        self.region_id = region_id
        self.setAcceptHoverEvents(True)
        self.normal_brush = QBrush(Qt.transparent)
        self.hover_brush = QBrush(QColor(255, 255, 0, 100))
        self.setBrush(self.normal_brush)
        self.setPen(QPen(Qt.black, 2))

    def hoverEnterEvent(self, event):
        print(f"Hovered over region {self.region_id}")
        self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        print(f"Left region {self.region_id}")
        self.setBrush(self.normal_brush)
        super().hoverLeaveEvent(event)

class MapGraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super(MapGraphicsView, self).__init__(parent)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        self.setMouseTracking(True)  # Enable mouse tracking

        # Set the path to your map image
        map_image_path = 'E:/AoC_Sim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
        
        # Load the map image
        self.map_pixmap = QtGui.QPixmap(map_image_path)

        # Create a pixmap item with the map pixmap
        self.pixmap_item = QtWidgets.QGraphicsPixmapItem(self.map_pixmap)

        # Set the z-value to ensure it's drawn below the polygons
        self.pixmap_item.setZValue(-1)

        # Add the pixmap item to the scene
        self.scene.addItem(self.pixmap_item)

        # Set the scene rect to match the pixmap size
        self.setSceneRect(self.pixmap_item.boundingRect())

        # Additional initialization (drag mode, scroll bar policy, etc.)
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setMinimumSize(1, 1)
        self.zoom_level = 0
        self.max_zoom_level = 100

    def wheelEvent(self, event):
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor

        # Save the scene pos
        oldPos = self.mapToScene(event.pos())

        # Zoom
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
            self.zoom_level += 1
        else:
            # Limit zooming out to a reasonable scale factor
            if self.transform().m11() > 0.1:  # This checks the horizontal scaling factor
                zoomFactor = zoomOutFactor
                self.zoom_level -= 1
            else:
                zoomFactor = 1  # Prevent further zooming out

        # Scale the view
        self.scale(zoomFactor, zoomFactor)

        # Get the new position
        newPos = self.mapToScene(event.pos())

        # Move scene to old position
        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())

    
    def draw_regions_from_db(self, db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('SELECT region_id, x0, y0, x1, y1 FROM regions')
        regions = c.fetchall()
        conn.close()

        for region_id, x0, y0, x1, y1 in regions:
            rect = QRectF(x0, y0, x1 - x0, y1 - y0)
            region_item = HoverableRectItem(rect, region_id=region_id)
            self.scene.addItem(region_item)


    def resizeEvent(self, event):
        # Remove the fitInView call from here if you want to allow further zooming
        # super(MapGraphicsView, self).resizeEvent(event)
        # self.fitInView(self.sceneRect(), QtCore.Qt.KeepAspectRatio)
        pass

class SimulationThread(QtCore.QThread):
    def __init__(self, control, db_path):
        super().__init__()
        self.control = control
        self.db_path = db_path

    def run(self):
        simulate(self.control, self.db_path, real_time=False)

    def pause(self):
        self.control.pause()

    def resume(self):
        self.control.resume()

    def reset_simulation_data(self):
        reset_simulation_data(self.db_path)

class SimulationApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
        self.control = SimulationControl()
        self.simulationThread = SimulationThread(self.control, self.db_path)
        self.isPaused = False
        self.initUI()

    def showEvent(self, event):
        super().showEvent(event)
        db_path = 'E:\\AoC_Sim\\SQLite_Queries\\nodes.db'
        self.mapView.draw_regions_from_db(db_path)

    def load_and_draw_regions(self):
        # Get the size of the QGraphicsScene, which should be set to the size of the map image
        scene_size = self.mapView.scene.sceneRect().size()
        displayed_image_width = scene_size.width()
        displayed_image_height = scene_size.height()

        # Load region data from the database
        regions_vertices = self.load_regions_from_db()

        for region_id, vertices_json in regions_vertices.items():
            vertices = json.loads(vertices_json)
            qpoints = [QPointF(x, y) for x, y in vertices]
            polygon = QtGui.QPolygonF(qpoints)
            path = QtGui.QPainterPath()
            path.addPolygon(polygon)
            bounding_rect = path.boundingRect()
            
            print(f"Region ID: {region_id}")
            print(f"Vertices: {vertices}")
            print(f"Bounding rect: {bounding_rect}")
    
            polygon_item = HoverablePolygonItem(polygon, region_id=region_id)
            self.mapView.scene.addItem(polygon_item)

    def load_regions_from_db(self):
        regions_vertices = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT region_id, vertices FROM regions")
                rows = cursor.fetchall()
                for region_id, vertices_json in rows:
                    regions_vertices[region_id] = vertices_json
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        return regions_vertices

    def initUI(self):
        self.setWindowTitle('Node Simulation')
        self.setGeometry(100, 100, 1200, 800)
        self.mapView = MapGraphicsView(self)
        self.setCentralWidget(self.mapView)
        self.startButton = QtWidgets.QPushButton('Start New Simulation', self)
        self.startButton.setGeometry(50, 50, 200, 40)
        self.startButton.clicked.connect(self.startNewSimulation)
        self.pauseResumeButton = QtWidgets.QPushButton('Pause Simulation', self)
        self.pauseResumeButton.setGeometry(50, 100, 200, 40)
        self.pauseResumeButton.clicked.connect(self.toggleSimulationPause)
        self.pauseResumeButton.setEnabled(False)

    def startNewSimulation(self):
        if not self.simulationThread.isRunning():
            self.simulationThread.reset_simulation_data()
            self.simulationThread.start()
            self.pauseResumeButton.setEnabled(True)
            self.startButton.setEnabled(False)

    def toggleSimulationPause(self):
        if self.isPaused:
            self.simulationThread.resume()
            self.pauseResumeButton.setText('Pause Simulation')
            self.isPaused = False
        else:
            self.simulationThread.pause()
            self.pauseResumeButton.setText('Resume Simulation')
            self.isPaused = True

    def closeEvent(self, event):
        if self.simulationThread.isRunning():
            self.control.pause()
            self.simulationThread.wait()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    ex = SimulationApp()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
