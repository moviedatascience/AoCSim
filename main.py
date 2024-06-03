import sys
from PyQt5 import QtWidgets
from gui.main_app import SimulationApp  # Adjusted import path

def main():
    app = QtWidgets.QApplication(sys.argv)
    ex = SimulationApp()
    ex.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
