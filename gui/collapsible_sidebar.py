from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QCheckBox, QSizePolicy
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon
import logging
from config.settings import Settings

config = Settings()

class CollapsibleSidebar(QWidget):
    editModeChanged = pyqtSignal(bool)
    keepBoundaryChanges = pyqtSignal()
    discardBoundaryChanges = pyqtSignal()

    def __init__(self, parent=None):
        super(CollapsibleSidebar, self).__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)  # Add spacing between widgets
        self.layout.setContentsMargins(10, 10, 10, 10)  # Add margins around the layout
        self.isSidebarVisible = False
        self.editMode = False

        self.setMinimumWidth(300)  # Set minimum width for the sidebar

        self.closeButton = QPushButton()
        self.closeButton.setIcon(QIcon(config.get('close_icon_path')))
        self.closeButton.setFixedSize(50, 50)
        self.closeButton.clicked.connect(self.toggle)

        self.contentWidget = QWidget()
        self.contentWidget.setMinimumWidth(300)  # Set minimum width for the content widget
        self.contentLayout = QVBoxLayout(self.contentWidget)
        self.contentLayout.setSpacing(10)  # Add spacing between widgets
        self.contentLayout.setContentsMargins(10, 10, 10, 10)  # Add margins around the layout

        button_width = 250  # Set a fixed width for the buttons
        button_height = 40  # Set a fixed height for the buttons

        self.editRegionBoundariesButton = QPushButton('Edit Region Boundaries')
        self.editRegionBoundariesButton.setFixedSize(button_width, button_height)
        self.contentLayout.addWidget(self.editRegionBoundariesButton)

        self.keepChangesButton = QPushButton('Keep Boundary Changes')
        self.keepChangesButton.setFixedSize(button_width, button_height)
        self.discardChangesButton = QPushButton('Discard Boundary Changes')
        self.discardChangesButton.setFixedSize(button_width, button_height)
        self.keepChangesButton.hide()
        self.discardChangesButton.hide()
        self.contentLayout.addWidget(self.keepChangesButton)
        self.contentLayout.addWidget(self.discardChangesButton)

        self.editRegionBoundariesButton.clicked.connect(self.toggleEditMode)
        self.keepChangesButton.clicked.connect(self.keepBoundaryChangesClicked)
        self.discardChangesButton.clicked.connect(self.discardBoundaryChangesClicked)

        self.startButton = QPushButton('Start New Simulation')
        self.startButton.setFixedSize(button_width, button_height)
        self.pauseResumeButton = QPushButton('Pause Simulation')
        self.pauseResumeButton.setFixedSize(button_width, button_height)
        self.allowExpBankingCheckbox = QCheckBox("Allow Experience Banking")
        self.allowExpBankingCheckbox.setFixedWidth(button_width)
        self.contentLayout.addWidget(self.startButton)
        self.contentLayout.addWidget(self.pauseResumeButton)
        self.contentLayout.addWidget(self.allowExpBankingCheckbox)

        self.layout.addWidget(self.closeButton)
        self.layout.addWidget(self.contentWidget)
        self.layout.addStretch()  # Add a stretch to push the content to the top

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

    def keepBoundaryChangesClicked(self):
        try:
            logging.debug("Keep Boundary Changes button clicked")
            self.keepBoundaryChanges.emit()
            self.toggleEditMode()  # Exit edit mode after keeping changes
        except Exception as e:
            logging.error(f"Error in keepBoundaryChangesClicked: {e}")

    def discardBoundaryChangesClicked(self):
        try:
            logging.debug("Discard Boundary Changes button clicked")
            self.discardBoundaryChanges.emit()
            self.toggleEditMode()  # Exit edit mode after discarding changes
        except Exception as e:
            logging.error(f"Error in discardBoundaryChangesClicked: {e}")
