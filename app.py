import sys, os, json, subprocess, time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
    QTextEdit, QMessageBox, QLabel, QProgressBar, QSplashScreen
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QColor


DATA_FILE = "repos.json"
ICON_DIR = "icons"


DARK_BLUE_THEME = """
QMainWindow { background-color: #0b1220; }
QLabel { color: #4fc3ff; }

QTableWidget {
    background-color: #0f172a;
    color: #e5f0ff;
    gridline-color: #1e3a5f;
    selection-background-color: #1e40af;
}

QHeaderView::section {
    background-color: #020617;
    color: #4fc3ff;
    border: 1px solid #1e3a5f;
    font-weight: bold;
}

QPushButton {
    background-color: #020617;
    color: #4fc3ff;
    border: 1px solid #1e3a5f;
    border-radius: 6px;
    padding: 6px 12px;
}

QPushButton:hover { background-color: #1e3a5f; }
QPushButton:pressed { background-color: #1e40af; }

QTextEdit {
    background-color: #020617;
    color: #9ae6ff;
    border: 1px solid #1e3a5f;
    font-family: Consolas;
}
"""


class GitWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    status = pyqtSignal(int, str)

    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def run(self):
        total = len(self.paths)

        for idx, path in enumerate(self.paths):
            self.log.emit(f"\n========== {path} ==========\n")

            try:
                subprocess.run(["git", "-C", path, "fetch"], capture_output=True)
                result = subprocess.run(
                    ["git", "-C", path, "pull"],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    self.status.emit(idx, "OK")
                else:
                    self.status.emit(idx, "ERROR")

                if result.stdout:
                    self.log.emit(result.stdout)
                if result.stderr:
                    self.log.emit("ERROR:\n" + result.stderr)

            except Exception as e:
                self.status.emit(idx, "ERROR")
                self.log.emit(f"EXCEPCIÓN: {e}\n")

            self.progress.emit(int((idx + 1) / total * 100))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Git Pull Manager Pro")
        self.setWindowIcon(QIcon("icon.ico"))
        self.resize(1000, 650)

        self.repos = self.load_repos()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        title = QLabel("Git Pull Manager PRO")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        # Tabla
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Repositorio", "Branch", "Estado"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Botones
        btn_layout = QHBoxLayout()
        layout.addLayout(btn_layout)

        self.btn_add = QPushButton(" Agregar")
        self.btn_add.setIcon(QIcon(os.path.join(ICON_DIR, "add.svg")))

        self.btn_remove = QPushButton(" Eliminar")
        self.btn_remove.setIcon(QIcon(os.path.join(ICON_DIR, "delete.svg")))

        self.btn_pull_selected = QPushButton(" Pull Seleccionados")
        self.btn_pull_selected.setIcon(QIcon(os.path.join(ICON_DIR, "pull.svg")))

        self.btn_pull_all = QPushButton(" Pull Todos")
        self.btn_pull_all.setIcon(QIcon(os.path.join(ICON_DIR, "pull_all.svg")))

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_pull_selected)
        btn_layout.addWidget(self.btn_pull_all)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Logs
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box, 2)

        # Eventos
        self.btn_add.clicked.connect(self.add_repo)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_pull_selected.clicked.connect(self.pull_selected)
        self.btn_pull_all.clicked.connect(self.pull_all)

        self.refresh_table()

    def get_branch(self, path):
        try:
            result = subprocess.run(
                ["git", "-C", path, "branch", "--show-current"],
                capture_output=True, text=True
            )
            return result.stdout.strip()
        except:
            return "?"

    def load_repos(self):
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        return []

    def save_repos(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.repos, f, indent=2)

    def refresh_table(self):
        self.table.setRowCount(0)
        for path in self.repos:
            row = self.table.rowCount()
            self.table.insertRow(row)

            branch = self.get_branch(path)

            self.table.setItem(row, 0, QTableWidgetItem(path))
            self.table.setItem(row, 1, QTableWidgetItem(branch))
            self.table.setItem(row, 2, QTableWidgetItem("—"))

    def add_repo(self):
        path = QFileDialog.getExistingDirectory(self, "Selecciona repo")
        if not path:
            return
        if path in self.repos:
            QMessageBox.warning(self, "Aviso", "Repo ya agregado")
            return

        self.repos.append(path)
        self.save_repos()
        self.refresh_table()

    def remove_selected(self):
        rows = {i.row() for i in self.table.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            del self.repos[row]
        self.save_repos()
        self.refresh_table()

    def pull_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            return
        paths = [self.repos[r] for r in rows]
        self.start_worker(paths, rows)

    def pull_all(self):
        self.start_worker(self.repos, list(range(len(self.repos))))

    def start_worker(self, paths, rows):
        self.progress.setValue(0)
        self.log_box.clear()

        self.worker = GitWorker(paths)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(lambda i, s: self.set_status(rows[i], s))
        self.worker.start()

    def set_status(self, row, status):
        item = QTableWidgetItem(status)
        if status == "OK":
            item.setForeground(QColor("#00ff99"))
        else:
            item.setForeground(QColor("#ff4d4d"))
        self.table.setItem(row, 2, item)

    def append_log(self, text):
        self.log_box.insertPlainText(text)
        self.log_box.moveCursor(self.log_box.textCursor().MoveOperation.End)


def show_splash(app):
    pix = QPixmap(400, 250)
    pix.fill(QColor("#020617"))
    splash = QSplashScreen(pix)
    splash.showMessage(
        "Git Pull Manager PRO\nCargando...",
        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignBottom,
        Qt.GlobalColor.cyan
    )
    splash.show()
    app.processEvents()
    time.sleep(1.5)
    return splash


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_BLUE_THEME)

    splash = show_splash(app)

    win = MainWindow()
    win.show()

    splash.finish(win)
    sys.exit(app.exec())
