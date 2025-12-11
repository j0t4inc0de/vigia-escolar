import sys
import os
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QHBoxLayout, QMessageBox, QGraphicsOpacityEffect,
    QGridLayout, QFrame, QSizePolicy, QTabWidget, QProgressBar,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QDialog
)
from PyQt5.QtGui import QPixmap, QFont, QPainter
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QThread, pyqtSignal, QSize
import subprocess
from concurrent.futures import ThreadPoolExecutor
import threading

EVIDENCE_FOLDER = "evidencia_argos"
DETECCION_SCRIPT = "main.py"
THUMBNAIL_SIZE = 180
MAX_IMAGES_PER_ROW = 4

class ImageLoader(QThread):
    """Thread para cargar imágenes de forma asíncrona"""
    imageLoaded = pyqtSignal(str, QPixmap)
    
    def __init__(self, image_path):
        super().__init__()
        self.image_path = image_path
        
    def run(self):
        try:
            # Cargar y redimensionar imagen en thread separado
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                # Crear thumbnail optimizado
                thumbnail = pixmap.scaled(
                    THUMBNAIL_SIZE, THUMBNAIL_SIZE, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.imageLoaded.emit(self.image_path, thumbnail)
        except Exception as e:
            print(f"Error cargando imagen {self.image_path}: {e}")

class ImageViewer(QDialog):
    """Dialog para mostrar imagen en tamaño completo"""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vista de Imagen")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        
        # Vista gráfica para mostrar imagen completa
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        
        # Cargar imagen completa
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.graphics_scene.addPixmap(pixmap)
            self.graphics_view.fitInView(self.graphics_scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        
        layout.addWidget(self.graphics_view)
        
        # Botón cerrar
        close_btn = QPushButton("Cerrar")
        close_btn.setStyleSheet(self.get_button_style("#6b7280", "#4b5563"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
    
    def get_button_style(self, color, hover_color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                border: 2px solid #ffffff;
            }}
        """

class ImageCard(QFrame):
    """Widget personalizado para mostrar cada imagen con lazy loading"""
    def __init__(self, image_path, timestamp_str):
        super().__init__()
        self.image_path = image_path
        self.timestamp_str = timestamp_str
        self.loaded = False
        self.setup_ui()
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #e5e7eb;
                border-radius: 12px;
                padding: 8px;
            }
            QFrame:hover {
                border: 3px solid #3b82f6;
                background-color: #f0f9ff;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        # Placeholder para imagen
        self.image_label = QLabel("⏳ Cargando...")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #f3f4f6;
                border: 1px dashed #d1d5db;
                border-radius: 8px;
                font-size: 14px;
                color: #6b7280;
            }
        """)
        self.image_label.mousePressEvent = self.show_full_image
        layout.addWidget(self.image_label)
        
        # Información de fecha
        self.date_label = QLabel(f"🕒 {self.timestamp_str}")
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #374151;
                font-weight: bold;
                background-color: #f9fafb;
                padding: 4px;
                border-radius: 6px;
            }
        """)
        layout.addWidget(self.date_label)
        
        self.setLayout(layout)
        self.setMaximumWidth(THUMBNAIL_SIZE + 40)
        
    def load_image(self):
        """Cargar imagen de forma asíncrona"""
        if not self.loaded:
            self.loader = ImageLoader(self.image_path)
            self.loader.imageLoaded.connect(self.on_image_loaded)
            self.loader.start()
            
    def on_image_loaded(self, path, pixmap):
        """Callback cuando la imagen se carga"""
        if path == self.image_path:
            self.image_label.setPixmap(pixmap)
            self.image_label.setText("")
            self.loaded = True
            
    def show_full_image(self, event):
        """Mostrar imagen en tamaño completo"""
        if self.loaded:
            viewer = ImageViewer(self.image_path, self)
            viewer.exec_()

class OptimizedScrollArea(QScrollArea):
    """ScrollArea optimizado con lazy loading"""
    def __init__(self):
        super().__init__()
        self.cards = []
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: none;
                border-radius: 12px;
            }
            QScrollBar:vertical {
                background-color: #f1f5f9;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #94a3b8;
            }
        """)
        
        # Conectar scroll para lazy loading
        self.verticalScrollBar().valueChanged.connect(self.check_visible_items)
        
    def set_cards(self, cards):
        """Establecer las tarjetas y configurar lazy loading"""
        self.cards = cards
        self.check_visible_items()
        
    def check_visible_items(self):
        """Cargar solo las imágenes visibles en el viewport"""
        if not self.cards:
            return
            
        viewport_rect = self.viewport().rect()
        scroll_value = self.verticalScrollBar().value()
        
        for card in self.cards:
            if card.isVisible():
                card_pos = card.mapTo(self.widget(), card.rect().topLeft())
                card_rect = card.rect()
                card_rect.moveTo(card_pos)
                
                # Si la tarjeta está visible o cerca de serlo, cargar imagen
                if (card_rect.bottom() >= -200 and 
                    card_rect.top() <= viewport_rect.height() + 200):
                    card.load_image()

class ArgosGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🛡️ ARGOS - Sistema de Detección de Armas")
        self.setGeometry(100, 30, 1400, 900)
        self.setStyleSheet(self.get_main_style())
        self.process = None
        self.executor = ThreadPoolExecutor(max_workers=4)  # Para carga paralela
        self.init_ui()

    def get_main_style(self):
        return """
            QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc,
                    stop: 1 #e2e8f0
                );
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }
            QTabWidget::pane {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f1f5f9;
                padding: 12px 24px;
                margin: 2px;
                border-radius: 8px 8px 0 0;
                font-weight: bold;
                color: #475569;
            }
            QTabBar::tab:selected {
                background-color: #3b82f6;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #ddd6fe;
            }
        """

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Título principal con mejor diseño
        title_frame = QFrame()
        title_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #667eea,
                    stop: 1 #764ba2
                );
                border-radius: 16px;
                padding: 20px;
            }
        """)
        title_layout = QHBoxLayout()
        
        title = QLabel("🛡️ ARGOS")
        title.setFont(QFont("Segoe UI", 32, QFont.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        
        subtitle = QLabel("Sistema de Detección de Armas\nMonitor de Incidentes")
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setStyleSheet("color: #e2e8f0; background: transparent;")
        subtitle.setAlignment(Qt.AlignRight)
        
        title_layout.addWidget(title)
        title_layout.addStretch()
        title_layout.addWidget(subtitle)
        title_frame.setLayout(title_layout)
        main_layout.addWidget(title_frame)

        # Tabs para organizar mejor el contenido
        self.tabs = QTabWidget()
        
        # Tab para hoy
        self.today_tab = self.create_day_tab(0)
        self.tabs.addTab(self.today_tab, "📅 Hoy")
        
        # Tab para ayer
        self.yesterday_tab = self.create_day_tab(1)
        self.tabs.addTab(self.yesterday_tab, "📅 Ayer")
        
        main_layout.addWidget(self.tabs)

        # Panel de control mejorado
        control_panel = QFrame()
        control_panel.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 2px solid #e5e7eb;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        
        control_layout = QHBoxLayout()
        control_layout.setSpacing(20)
        
        # Botón cámara mejorado
        self.camera_btn = QPushButton("🔴 Iniciar Detección")
        self.camera_btn.setStyleSheet(self.get_button_style("#ef4444", "#dc2626"))
        self.camera_btn.setMinimumHeight(60)
        self.camera_btn.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.camera_btn.clicked.connect(self.launch_camera)
        
        # Botón volver mejorado
        self.return_btn = QPushButton("↩️ Detener y Volver")
        self.return_btn.setStyleSheet(self.get_button_style("#10b981", "#059669"))
        self.return_btn.setMinimumHeight(60)
        self.return_btn.setFont(QFont("Segoe UI", 16, QFont.Bold))
        self.return_btn.clicked.connect(self.return_to_gui)
        self.return_btn.setVisible(False)
        
        # Indicador de estado
        self.status_label = QLabel("🟢 Sistema listo")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #dcfce7;
                color: #166534;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        
        control_layout.addWidget(self.status_label)
        control_layout.addStretch()
        control_layout.addWidget(self.camera_btn)
        control_layout.addWidget(self.return_btn)
        
        control_panel.setLayout(control_layout)
        main_layout.addWidget(control_panel)

        # Timer para actualización
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_all_tabs)
        self.timer.start(10000)  # Reducir frecuencia a 10 segundos

        self.setLayout(main_layout)

    def create_day_tab(self, days_ago):
        """Crear tab para un día específico con grid layout optimizado"""
        tab_widget = QWidget()
        layout = QVBoxLayout()
        
        # Información del día
        day_name = "Hoy" if days_ago == 0 else "Ayer"
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%d/%m/%Y")
        
        header = QLabel(f"📊 Incidentes del {day_name} ({date_str})")
        header.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header.setStyleSheet("color: #1f2937; margin: 10px 0;")
        layout.addWidget(header)
        
        # Scroll area optimizado
        scroll = OptimizedScrollArea()
        
        # Widget contenedor con grid
        container = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)
        grid_layout.setContentsMargins(16, 16, 16, 16)
        
        # Obtener imágenes para este día
        images = self.get_images_for_day(days_ago)
        cards = []
        
        if images:
            for i, img_path in enumerate(images):
                # Extraer timestamp
                timestamp_str = self.extract_timestamp(img_path)
                
                # Crear tarjeta de imagen
                card = ImageCard(img_path, timestamp_str)
                cards.append(card)
                
                # Calcular posición en grid
                row = i // MAX_IMAGES_PER_ROW
                col = i % MAX_IMAGES_PER_ROW
                
                grid_layout.addWidget(card, row, col)
        else:
            # Mensaje cuando no hay imágenes
            no_images = QLabel(f"📭 No hay incidentes registrados para {day_name.lower()}")
            no_images.setAlignment(Qt.AlignCenter)
            no_images.setStyleSheet("""
                QLabel {
                    color: #6b7280;
                    font-size: 16px;
                    font-style: italic;
                    padding: 40px;
                    background-color: #f9fafb;
                    border: 2px dashed #d1d5db;
                    border-radius: 12px;
                }
            """)
            grid_layout.addWidget(no_images, 0, 0, 1, MAX_IMAGES_PER_ROW)
        
        container.setLayout(grid_layout)
        scroll.setWidget(container)
        scroll.set_cards(cards)
        
        layout.addWidget(scroll)
        tab_widget.setLayout(layout)
        
        return tab_widget

    def extract_timestamp(self, img_path):
        """Extraer timestamp legible del nombre del archivo"""
        filename = os.path.basename(img_path)
        try:
            parts = filename.replace(".jpg", "").split("_")
            if len(parts) >= 3:
                timestamp_str = parts[1] + parts[2]
                dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                return dt.strftime("%H:%M:%S")
            else:
                return "Hora desconocida"
        except:
            return "Hora desconocida"

    def get_images_for_day(self, days_ago):
        """Obtener imágenes para un día específico"""
        result = []
        target = (datetime.now() - timedelta(days=days_ago)).strftime("%Y%m%d")
        
        if not os.path.exists(EVIDENCE_FOLDER):
            return []
            
        try:
            for f in os.listdir(EVIDENCE_FOLDER):
                if f.endswith(".jpg") and target in f:
                    result.append(os.path.join(EVIDENCE_FOLDER, f))
        except Exception as e:
            print(f"Error listando imágenes: {e}")
            
        return sorted(result, reverse=True)

    def update_all_tabs(self):
        """Actualizar todos los tabs de forma eficiente"""
        current_tab = self.tabs.currentIndex()
        
        # Recrear tabs solo si hay cambios
        new_today = self.create_day_tab(0)
        new_yesterday = self.create_day_tab(1)
        
        # Reemplazar tabs
        self.tabs.removeTab(1)
        self.tabs.removeTab(0)
        self.tabs.insertTab(0, new_today, "📅 Hoy")
        self.tabs.insertTab(1, new_yesterday, "📅 Ayer")
        
        # Mantener tab actual seleccionado
        self.tabs.setCurrentIndex(current_tab)

    def launch_camera(self):
        """Lanzar detección de cámara"""
        try:
            self.process = subprocess.Popen(["python", DETECCION_SCRIPT])
            self.camera_btn.setEnabled(False)
            self.return_btn.setVisible(True)
            self.status_label.setText("🔴 Detección activa")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #fef2f2;
                    color: #991b1b;
                    padding: 12px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
            """)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar la detección:\n{str(e)}")

    def return_to_gui(self):
        """Volver a la interfaz principal"""
        if self.process:
            self.process.terminate()
            self.process = None
            
        self.return_btn.setVisible(False)
        self.camera_btn.setEnabled(True)
        self.status_label.setText("🟢 Sistema listo")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #dcfce7;
                color: #166534;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        self.update_all_tabs()

    def get_button_style(self, color, hover_color):
        return f"""
            QPushButton {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {color},
                    stop: 1 {self.darken_color(color)}
                );
                color: white;
                padding: 16px 32px;
                border-radius: 12px;
                border: none;
                font-weight: bold;
                text-align: center;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {hover_color},
                    stop: 1 {self.darken_color(hover_color)}
                );
                border: 2px solid #ffffff;
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(hover_color)};
            }}
            QPushButton:disabled {{
                background-color: #d1d5db;
                color: #9ca3af;
            }}
        """

    def darken_color(self, hex_color):
        """Oscurecer un color hex para efectos de gradiente"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(max(0, c - 30) for c in rgb)
        return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"

    def closeEvent(self, event):
        """Cleanup al cerrar la aplicación"""
        if self.process:
            self.process.terminate()
        self.executor.shutdown(wait=False)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Estilo más moderno
    gui = ArgosGUI()
    gui.show()
    sys.exit(app.exec_())