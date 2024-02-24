from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QGraphicsPolygonItem
from PyQt5.QtGui import QBrush, QColor, QPen
from PyQt5.QtCore import Qt, QPointF
import sys
import json
import sqlite3
import numpy as np
import io
from PIL import Image
from run_simulation import simulate, SimulationControl, reset_simulation_data


def point_in_mask(scene_point, mask_data):
    with io.BytesIO(mask_data) as mask_io:
        mask = Image.open(mask_io)
        mask_array = np.array(mask)

        # Transform the scene point to mask coordinates
        x = int(scene_point.x())
        y = int(scene_point.y())

        # Check if the point is within the bounds of the mask array
        if 0 <= x < mask_array.shape[1] and 0 <= y < mask_array.shape[0]:
            return mask_array[y, x] != 0
        else:
            return False




class HoverablePolygonItem(QGraphicsPolygonItem):
    def __init__(self, polygon, region_id=None, mask_data=None, parent=None):
        super().__init__(polygon, parent)
        self.region_id = region_id
        self.mask_data = mask_data
        self.setAcceptHoverEvents(True)
        self.normal_brush = QBrush(Qt.transparent)
        self.hover_brush = QBrush(QColor(255, 255, 0, 100))
        self.setBrush(self.normal_brush)
        self.setPen(QPen(Qt.black, 2))
    
    def hoverEnterEvent(self, event):
        scene_point = self.mapToScene(event.pos())
        print(f"Hover Enter at Scene: {scene_point}")
        if point_in_mask(scene_point, self.mask_data):
            print(f"Hovered over region {self.region_id}")
            self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        print(f"Leaving region {self.region_id}")
        self.setBrush(self.normal_brush)
        super().hoverLeaveEvent(event)


class MapGraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super(MapGraphicsView, self).__init__(parent)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        self.setMouseTracking(True)

        map_image_path = 'E:/AoC_Sim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
        self.map_pixmap = QtGui.QPixmap(map_image_path)
        self.pixmap_item = QtWidgets.QGraphicsPixmapItem(self.map_pixmap)
        self.pixmap_item.setZValue(-1)
        self.scene.addItem(self.pixmap_item)
        self.setSceneRect(self.pixmap_item.boundingRect())

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

    def resizeEvent(self, event):
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
        self.load_and_draw_regions()

    def load_and_draw_regions(self):
        regions_data = self.load_regions_from_db()
        for region_id, data in regions_data.items():
            vertices = json.loads(data['vertices'])
            qpoints = [QPointF(x, y) for x, y in vertices]
            polygon = QtGui.QPolygonF(qpoints)

            polygon_item = HoverablePolygonItem(polygon, region_id, data['mask'])
            self.mapView.scene.addItem(polygon_item)

    def load_regions_from_db(self):
        regions_data = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT region_id, vertices, mask FROM regions")
                rows = cursor.fetchall()
                for region_id, vertices_json, mask in rows:
                    regions_data[region_id] = {'vertices': vertices_json, 'mask': mask}
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        return regions_data

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
            self.pauseResumeButton.setText('Resume Simulation')
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
