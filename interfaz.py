import sys
import os
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QHBoxLayout, QMessageBox, QGraphicsOpacityEffect
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation
import subprocess

EVIDENCE_FOLDER = "evidencia_argos"
DETECCION_SCRIPT = "main.py"

class ArgosGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🛡️ ARGOS - Sistema de Detección de Armas")
        self.setGeometry(100, 30, 1280, 860)
        self.setStyleSheet("""
            QWidget {
                background-color: #f9fafb;
                font-family: 'Segoe UI', sans-serif;
            }
        """)
        self.process = None
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setSpacing(20)

        # --- Título
        title = QLabel("ARGOS - Monitor de Incidentes")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        title.setStyleSheet("color: #111827; margin: 20px 0;")
        self.layout.addWidget(title)

        # --- Secciones de imágenes
        self.today_section = self.build_section("Hoy", self.get_images_for_day(0))
        self.yesterday_section = self.build_section("Ayer", self.get_images_for_day(1))
        self.layout.addWidget(self.today_section)
        self.layout.addWidget(self.yesterday_section)

        # --- Botones
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setSpacing(40)

        self.camera_btn = QPushButton("🔴 Abrir Cámara")
        self.camera_btn.setStyleSheet(self.button_style("#ef4444", "#dc2626"))
        self.camera_btn.setMinimumHeight(50)
        self.camera_btn.setFont(QFont("Segoe UI", 14))
        self.camera_btn.clicked.connect(self.launch_camera)
        self.buttons_layout.addWidget(self.camera_btn)

        self.return_btn = QPushButton("↩️ Volver a Interfaz")
        self.return_btn.setStyleSheet(self.button_style("#10b981", "#059669"))
        self.return_btn.setMinimumHeight(50)
        self.return_btn.setFont(QFont("Segoe UI", 14))
        self.return_btn.clicked.connect(self.return_to_gui)
        self.return_btn.setVisible(False)
        self.return_opacity = QGraphicsOpacityEffect()
        self.return_btn.setGraphicsEffect(self.return_opacity)
        self.return_opacity.setOpacity(0.0)
        self.buttons_layout.addWidget(self.return_btn)

        self.layout.addLayout(self.buttons_layout)

        # --- Timer para actualización
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_sections)
        self.timer.start(5000)

        self.setLayout(self.layout)

    def build_section(self, title, image_paths):
        group = QWidget()
        layout = QVBoxLayout()
        section_title = QLabel(f"📅 {title}")
        section_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        section_title.setStyleSheet("color: #1f2937; margin-bottom: 5px;")
        layout.addWidget(section_title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 10px;
            }
        """)

        content = QWidget()
        images_layout = QHBoxLayout()
        images_layout.setSpacing(25)

        for img_path in image_paths:
            card = QWidget()
            card_layout = QVBoxLayout()
            card.setStyleSheet("""
                QWidget {
                    background-color: #ffffff;
                    border: 1px solid #d1d5db;
                    border-radius: 12px;
                    padding: 10px;
                    min-width: 230px;
                }
            """)

            pixmap = QPixmap(img_path).scaledToWidth(230, Qt.SmoothTransformation)
            img_label = QLabel()
            img_label.setPixmap(pixmap)
            img_label.setAlignment(Qt.AlignCenter)

            # Extraer timestamp del nombre del archivo
            filename = os.path.basename(img_path)
            try:
                parts = filename.replace(".jpg", "").split("_")
                if len(parts) >= 3:
                    timestamp_str = parts[1] + parts[2]
                    dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                    readable_date = dt.strftime("%d/%m/%Y - %H:%M:%S")
                else:
                    readable_date = "Fecha desconocida"
            except:
                readable_date = "Fecha desconocida"

            date_label = QLabel(f"🕒 {readable_date}")
            date_label.setAlignment(Qt.AlignCenter)
            date_label.setStyleSheet("font-size: 15px; color: #374151; margin-top: 8px;")

            card_layout.addWidget(img_label)
            card_layout.addWidget(date_label)
            card.setLayout(card_layout)

            images_layout.addWidget(card)

        content.setLayout(images_layout)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        group.setLayout(layout)
        return group

    def get_images_for_day(self, days_ago):
        result = []
        target = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
        if not os.path.exists(EVIDENCE_FOLDER):
            return []
        for f in os.listdir(EVIDENCE_FOLDER):
            if f.endswith(".jpg") and target in f:
                result.append(os.path.join(EVIDENCE_FOLDER, f))
        return sorted(result, reverse=True)

    def update_sections(self):
        self.layout.removeWidget(self.today_section)
        self.layout.removeWidget(self.yesterday_section)
        self.today_section.deleteLater()
        self.yesterday_section.deleteLater()
        self.today_section = self.build_section("Hoy", self.get_images_for_day(0))
        self.yesterday_section = self.build_section("Ayer", self.get_images_for_day(1))
        self.layout.insertWidget(1, self.today_section)
        self.layout.insertWidget(2, self.yesterday_section)

    def launch_camera(self):
        try:
            self.process = subprocess.Popen(["python", DETECCION_SCRIPT])
            self.camera_btn.setEnabled(False)
            self.fade_in_return_button()
        except Exception as e:
            QMessageBox.critical(self, "Error al abrir cámara", str(e))

    def return_to_gui(self):
        if self.process:
            self.process.terminate()
            self.process = None
        self.return_btn.setVisible(False)
        self.camera_btn.setEnabled(True)
        self.update_sections()

    def fade_in_return_button(self):
        self.return_btn.setVisible(True)
        self.return_opacity.setOpacity(0.0)
        self.animation = QPropertyAnimation(self.return_opacity, b"opacity")
        self.animation.setDuration(800)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.start()

    def button_style(self, color, hover_color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                padding: 14px 24px;
                border-radius: 12px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ArgosGUI()
    gui.show()
    sys.exit(app.exec_())