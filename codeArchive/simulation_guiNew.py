from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWidgets import QGraphicsPolygonItem, QVBoxLayout, QWidget, QPushButton, QCheckBox, QDockWidget
from PyQt5.QtGui import QBrush, QColor, QPen, QIcon
from PyQt5.QtCore import Qt, QPointF, QPropertyAnimation, QRect
import sys
import json
import sqlite3
from runSimulationNew import simulate, SimulationControl, reset_simulation_data

class HoverablePolygonItem(QGraphicsPolygonItem):
    def __init__(self, polygon, region_id=None, parent=None):
        super().__init__(polygon, parent)
        self.region_id = region_id
        self.setAcceptHoverEvents(True)
        self.normal_brush = QBrush(Qt.transparent)
        self.hover_brush = QBrush(QColor(255, 255, 0, 100))
        self.setBrush(self.normal_brush)
        self.setPen(QPen(Qt.black, 2))
    
    def hoverEnterEvent(self, event):
        print(f"Hovered over a region {self.region_id}")
        self.setBrush(self.hover_brush)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        print("Left a region")
        self.setBrush(self.normal_brush)
        super().hoverLeaveEvent(event)

class MapGraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super(MapGraphicsView, self).__init__(parent)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        self.setMouseTracking(True)
        map_image_path = 'E:/AoCSim/Assets/Map_of_Verra_cleanup_notext_nowater.png'
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

class SimulationThread(QtCore.QThread):
    def __init__(self, control, db_path, allow_exp_banking):
        super().__init__()
        self.control = control
        self.db_path = db_path
        self.allow_exp_banking = allow_exp_banking

    def run(self):
        simulate(self.control, self.db_path, self.allow_exp_banking, real_time=False)

    def pause(self):
        self.control.pause()

    def resume(self):
        self.control.resume()

    def reset_simulation_data(self):
        reset_simulation_data(self.db_path)

class CollapsibleSidebar(QWidget):
    def __init__(self, parent=None):
        super(CollapsibleSidebar, self).__init__(parent)
        self.setFixedWidth(200)  # Adjust width as needed
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.isVisible = False  # Track the visibility state

        # This button will be used to collapse the sidebar
        self.closeButton = QPushButton()
        self.closeButton.setIcon(QIcon('E:\\AoCSim\\Assets\\closeIcon.png'))  # Close icon
        self.closeButton.setFixedSize(50, 50)  # Adjust size as needed
        self.closeButton.clicked.connect(self.toggle)

        self.contentWidget = QWidget()
        self.contentLayout = QVBoxLayout(self.contentWidget)

        # Add other widgets to the content layout
        self.startButton = QPushButton('Start New Simulation')
        self.pauseResumeButton = QPushButton('Pause Simulation')
        self.allowExpBankingCheckbox = QCheckBox("Allow Experience Banking")
        self.contentLayout.addWidget(self.startButton)
        self.contentLayout.addWidget(self.pauseResumeButton)
        self.contentLayout.addWidget(self.allowExpBankingCheckbox)

        # Add the close button and content widget to the main layout
        self.layout.addWidget(self.closeButton)  # This ensures the close button is at the top
        self.layout.addWidget(self.contentWidget)

    def toggle(self):
        self.isVisible = not self.isVisible
        self.setVisible(self.isVisible)
        if self.isVisible:
            self.closeButton.setIcon(QIcon('E:\\AoCSim\\Assets\\closeIcon.png'))
        else:
            self.closeButton.setIcon(QIcon('E:\\AoCSim\\Assets\\hamburgerIcon.png'))

class SimulationApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.db_path = 'E:\\AoCSim\\SQLite_Queries\\nodes.db'
        self.control = SimulationControl()
        self.isPaused = False
        self.sidebar = None
        self.initUI()
        
    def showEvent(self, event):
        super().showEvent(event)
        self.load_and_draw_regions()

    def load_and_draw_regions(self):
        scene_size = self.mapView.scene.sceneRect().size()
        regions_vertices = self.load_regions_from_db()
        for region_id, vertices_json in regions_vertices.items():
            vertices = json.loads(vertices_json)
            qpoints = [QPointF(x, y) for x, y in vertices]
            polygon = QtGui.QPolygonF(qpoints)
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

        # Hamburger button to show the sidebar
        self.hamburgerButton = QPushButton(self)
        self.hamburgerButton.setIcon(QIcon('E:\\AoCSim\\Assets\\hamburgerIcon.png'))
        self.hamburgerButton.setFixedSize(50, 50)  # Adjust size as needed
        self.hamburgerButton.clicked.connect(self.toggleSidebar)
        self.hamburgerButton.move(0, 0)  # Position the button at the top left

        # Sidebar
        self.sidebar = CollapsibleSidebar(self)
        self.sidebar.setFixedHeight(self.height())  # Make the sidebar the full height of the window
        self.sidebar.setVisible(True)  # Start with the sidebar visible
        self.sidebar.move(-self.sidebar.width(), 0)  # Start with the sidebar hidden to the left

        # Connect signals of the sidebar
        self.sidebar.startButton.clicked.connect(self.startNewSimulation)
        self.sidebar.pauseResumeButton.clicked.connect(self.toggleSimulationPause)
        self.sidebar.allowExpBankingCheckbox.setChecked(True)
        self.sidebar.pauseResumeButton.setEnabled(False)

        # Prepare the sidebar animation
        self.sidebarAnimation = QPropertyAnimation(self.sidebar, b"geometry")
        self.sidebarAnimation.setDuration(300)  # Animation duration of 300 ms

    def toggleSidebar(self):
        sidebar_width = self.sidebar.width()
        if self.sidebar.isVisible:
            # If the sidebar is visible, hide it
            self.sidebarAnimation.setStartValue(self.sidebar.geometry())
            self.sidebarAnimation.setEndValue(QRect(-sidebar_width, 0, sidebar_width, self.height()))
            self.sidebarAnimation.finished.connect(lambda: self.sidebar.setVisible(False))
        else:
            # If the sidebar is not visible, show it
            self.sidebar.setVisible(True)
            self.sidebarAnimation.setStartValue(QRect(-sidebar_width, 0, sidebar_width, self.height()))
            self.sidebarAnimation.setEndValue(QRect(0, 0, sidebar_width, self.height()))
        
        self.sidebarAnimation.start()
        
    def startNewSimulation(self):
        allow_exp_banking = self.sidebar.allowExpBankingCheckbox.isChecked()
        self.simulationThread = SimulationThread(self.control, self.db_path, allow_exp_banking)
        if not self.simulationThread.isRunning():
            self.simulationThread.reset_simulation_data()
            self.simulationThread.start()
            self.sidebar.pauseResumeButton.setEnabled(True)
            self.sidebar.startButton.setEnabled(False)

    def toggleSimulationPause(self):
        if self.isPaused:
            self.simulationThread.resume()
            self.sidebar.pauseResumeButton.setText('Pause Simulation')
            self.isPaused = False
        else:
            self.simulationThread.pause()
            self.sidebar.pauseResumeButton.setText('Resume Simulation')
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
