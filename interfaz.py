import sys
import os
import hashlib
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QHBoxLayout, QMessageBox, QGraphicsOpacityEffect,
    QGridLayout, QFrame, QSizePolicy, QTabWidget, QProgressBar,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QDialog,
    QToolTip, QDesktopWidget, QSplitter, QTextEdit, QSpacerItem,
    QStackedWidget, QGraphicsDropShadowEffect
)
from PyQt5.QtGui import QPixmap, QFont, QPainter, QIcon, QColor, QPalette
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QThread, pyqtSignal, QSize, QEasingCurve, QRect
import subprocess
from concurrent.futures import ThreadPoolExecutor
import threading
from functools import lru_cache

# Configuración
EVIDENCE_FOLDER = "evidencia_argos"
DETECCION_SCRIPT = "main.py"
THUMBNAIL_SIZE = 180
MAX_IMAGES_PER_ROW = 4
CACHE_SIZE = 100
LOAD_BATCH_SIZE = 8

class ImageCache:
    """Sistema de caché inteligente para imágenes"""
    def __init__(self, max_size=CACHE_SIZE):
        self.cache = {}
        self.max_size = max_size
        self.access_order = []
    
    def get(self, path):
        if path in self.cache:
            self.access_order.remove(path)
            self.access_order.append(path)
            return self.cache[path]
        return None
    
    def set(self, path, pixmap):
        if len(self.cache) >= self.max_size and path not in self.cache:
            oldest = self.access_order.pop(0)
            del self.cache[oldest]
        
        self.cache[path] = pixmap
        if path in self.access_order:
            self.access_order.remove(path)
        self.access_order.append(path)
    
    def clear(self):
        self.cache.clear()
        self.access_order.clear()

class ImageLoader(QThread):
    """Thread optimizado para cargar imágenes con caché"""
    imageLoaded = pyqtSignal(str, QPixmap, bool)  # path, pixmap, from_cache
    progressUpdate = pyqtSignal(int)
    
    def __init__(self, image_paths, cache):
        super().__init__()
        self.image_paths = image_paths
        self.cache = cache
        self.running = True
        
    def run(self):
        for i, img_path in enumerate(self.image_paths):
            if not self.running:
                break
                
            try:
                # Verificar caché primero
                cached_pixmap = self.cache.get(img_path)
                if cached_pixmap:
                    self.imageLoaded.emit(img_path, cached_pixmap, True)
                    continue
                
                # Cargar imagen optimizada
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    # Crear thumbnail optimizado con mejor calidad
                    thumbnail = pixmap.scaled(
                        THUMBNAIL_SIZE, THUMBNAIL_SIZE,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    
                    # Guardar en caché
                    self.cache.set(img_path, thumbnail)
                    self.imageLoaded.emit(img_path, thumbnail, False)
                
                self.progressUpdate.emit(i + 1)
                    
            except Exception as e:
                print(f"Error cargando imagen {img_path}: {e}")
    
    def stop(self):
        self.running = False

class CleanImageCard(QFrame):
    """Tarjeta de imagen SIMPLIFICADA y LIMPIA"""
    clicked = pyqtSignal(str)
    
    def __init__(self, image_path, timestamp_str):
        super().__init__()
        self.image_path = image_path
        self.timestamp_str = timestamp_str
        self.loaded = False
        self.setup_ui()
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.NoFrame)
        self.setFixedSize(THUMBNAIL_SIZE + 20, THUMBNAIL_SIZE + 30)
        self.setCursor(Qt.PointingHandCursor)
        
        # UN SOLO ESTILO LIMPIO - sin múltiples contenedores
        self.setStyleSheet("""
            CleanImageCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            CleanImageCard:hover {
                border: 2px solid #3b82f6;
                background-color: #f8fafc;
            }
        """)
        
        # Layout directo y simple
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(6)
        
        # SOLO la imagen - SIN contenedores adicionales
        self.image_label = QLabel("⏳")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #f8fafc;
                border: 1px dashed #d1d5db;
                border-radius: 6px;
                color: #9ca3af;
                font-size: 24px;
            }
        """)
        layout.addWidget(self.image_label)
        
        # SOLO el texto de hora - sin paneles adicionales
        self.time_label = QLabel(self.timestamp_str)
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("""
            QLabel {
                font-size: 10px;
                font-weight: bold;
                color: #6b7280;
                background-color: transparent;
            }
        """)
        layout.addWidget(self.time_label)
        
    def load_image(self):
        """Iniciar carga"""
        if not self.loaded:
            self.image_label.setText("⏳")
            
    def set_image(self, pixmap, from_cache=False):
        """Establecer imagen"""
        if not self.loaded:
            self.image_label.setPixmap(pixmap)
            self.image_label.setText("")
            self.loaded = True
            
            # Simplificar estilo al cargar - SIN borders adicionales
            self.image_label.setStyleSheet("""
                QLabel {
                    background-color: #ffffff;
                    border: none;
                    border-radius: 6px;
                }
            """)
        
    def mousePressEvent(self, event):
        """Click simple"""
        if self.loaded and event.button() == Qt.LeftButton:
            self.clicked.emit(self.image_path)

class ModernImageViewer(QDialog):
    """Visor de imágenes moderno simplificado"""
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("🔍 Visor de Evidencia")
        self.setModal(True)
        
        # Pantalla completa redimensionable
        screen = QDesktopWidget().screenGeometry()
        self.resize(min(1200, screen.width() - 100), min(800, screen.height() - 100))
        
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header simple
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #2563eb;
                padding: 16px;
            }
        """)
        
        header_layout = QHBoxLayout(header)
        
        title = QLabel(f" Evidencia ARGOS")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        
        filename = os.path.basename(self.image_path)
        info = QLabel(f"📁 {filename}")
        info.setStyleSheet("color: #e2e8f0; font-size: 14px;")
        info.setAlignment(Qt.AlignRight)
        
        header_layout.addWidget(title)
        header_layout.addWidget(info)
        main_layout.addWidget(header)
        
        # Área de imagen
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        
        # Cargar imagen
        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            self.graphics_scene.addPixmap(pixmap)
            self.graphics_view.fitInView(
                self.graphics_scene.itemsBoundingRect(),
                Qt.KeepAspectRatio
            )
        
        main_layout.addWidget(self.graphics_view)
        
        # Footer simple
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #374151;
                padding: 12px;
            }
        """)
        
        footer_layout = QHBoxLayout(footer)
        
        close_btn = QPushButton("Cerrar")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        close_btn.clicked.connect(self.close)
        
        footer_layout.addStretch()
        footer_layout.addWidget(close_btn)
        main_layout.addWidget(footer)
        
        # Estilo general
        self.setStyleSheet("""
            QDialog {
                background-color: #1e293b;
            }
            QGraphicsView {
                background-color: #0f172a;
                border: none;
            }
        """)

class OptimizedScrollArea(QScrollArea):
    """ScrollArea optimizado simple"""
    def __init__(self):
        super().__init__()
        self.cards = []
        self.setup_ui()
        
    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Estilo simple del scroll
        self.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #f1f1f1;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #c1c1c1;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a8a8a8;
            }
        """)
        
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
    def set_cards(self, cards):
        """Establecer tarjetas"""
        self.cards = cards
        self.load_visible_items()
        
    def on_scroll(self):
        """Manejar scroll"""
        self.load_visible_items()
        
    def load_visible_items(self):
        """Cargar elementos visibles"""
        if not self.cards:
            return
            
        viewport_rect = self.viewport().rect()
        buffer = 200
        
        for card in self.cards:
            if card.isVisible():
                card_pos = card.mapTo(self.widget(), card.rect().topLeft())
                if (card_pos.y() >= -buffer and 
                    card_pos.y() <= viewport_rect.height() + buffer):
                    card.load_image()

class ArgosGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vigia Escolar - ARGOS")
        self.setGeometry(100, 30, 1400, 900)
        
        # Sistema de caché
        self.image_cache = ImageCache()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.image_loaders = []
        
        self.process = None
        self.current_tab = 0
        
        self.setup_styles()
        self.init_ui()
        
    def setup_styles(self):
        """Estilos globales simplificados"""
        self.setStyleSheet("""
            QWidget {
                background-color: #f8fafc;
                font-family: 'Segoe UI', sans-serif;
            }
            
            QTabWidget::pane {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background-color: #ffffff;
            }
            
            QTabBar::tab {
                background-color: #f1f5f9;
                padding: 12px 24px;
                margin: 2px;
                border-radius: 6px 6px 0 0;
                font-weight: 600;
                color: #374151;
            }
            
            QTabBar::tab:selected {
                background-color: #3b82f6;
                color: white;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #e5e7eb;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header simplificado
        header = self.create_header()
        main_layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.refresh_tabs()
        main_layout.addWidget(self.tabs)

        # Panel de control simple
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.smart_refresh)
        self.timer.start(15000)

    def create_header(self):
        """Header simple y limpio"""
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #3b82f6,
                    stop: 1 #6366f1
                );
                border-radius: 12px;
                padding: 20px;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 15, 20, 15)
        
        # Título simple
        title = QLabel("Vigia Escolar - ARGOS")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        
        # Stats simples
        stats = self.create_simple_stats()
        
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(stats)
        
        return header
        
    def create_simple_stats(self):
        """Panel de estadísticas simple"""
        stats_container = QFrame()
        stats_container.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(stats_container)
        layout.setSpacing(4)
        
        today_count = len(self.get_images_for_day(0))
        yesterday_count = len(self.get_images_for_day(1))
        
        today_label = QLabel(f"Hoy: {today_count}")
        yesterday_label = QLabel(f"Ayer: {yesterday_count}")
        
        for label in [today_label, yesterday_label]:
            label.setStyleSheet("color: white; font-size: 12px; font-weight: bold; background: transparent;")
        
        layout.addWidget(today_label)
        layout.addWidget(yesterday_label)
        
        return stats_container

    def create_control_panel(self):
        """Panel de control simple"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        layout = QHBoxLayout(panel)
        layout.setSpacing(16)
        
        # Indicador de estado simple
        self.status_label = QLabel("🟢 Sistema Listo")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #dcfce7;
                color: #166534;
                padding: 8px 12px;
                border-radius: 6px;
                font-weight: bold;
            }
        """)
        
        # Botones simples
        self.camera_btn = QPushButton("🔴 Iniciar Detección")
        self.camera_btn.setStyleSheet(self.get_button_style("#ef4444", "#dc2626"))
        self.camera_btn.clicked.connect(self.launch_camera)
        
        self.return_btn = QPushButton("⏹️ Detener")
        self.return_btn.setStyleSheet(self.get_button_style("#f59e0b", "#d97706"))
        self.return_btn.clicked.connect(self.return_to_gui)
        self.return_btn.hide()
        
        refresh_btn = QPushButton("🔄 Actualizar")
        refresh_btn.setStyleSheet(self.get_button_style("#10b981", "#059669"))
        refresh_btn.clicked.connect(self.force_refresh)
        
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(refresh_btn)
        layout.addWidget(self.camera_btn)
        layout.addWidget(self.return_btn)
        
        return panel

    def get_button_style(self, color, hover_color):
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                padding: 12px 20px;
                border-radius: 6px;
                border: none;
                font-weight: bold;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: #9ca3af;
                color: #d1d5db;
            }}
        """

    def create_day_tab(self, days_ago):
        """Crear tab simple para un día"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Header simple
        day_name = "Hoy" if days_ago == 0 else "Ayer"
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%d/%m/%Y")
        
        header_layout = QHBoxLayout()
        day_title = QLabel(f"📅 {day_name}")
        day_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        day_title.setStyleSheet("color: #1f2937;")
        
        date_label = QLabel(date_str)
        date_label.setStyleSheet("color: #6b7280; font-size: 14px;")
        date_label.setAlignment(Qt.AlignRight)
        
        header_layout.addWidget(day_title)
        header_layout.addStretch()
        header_layout.addWidget(date_label)
        layout.addLayout(header_layout)
        
        # Scroll area
        scroll = OptimizedScrollArea()
        
        # Container con grid
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(15)
        grid_layout.setContentsMargins(15, 15, 15, 15)
        
        # Obtener imágenes
        images = self.get_images_for_day(days_ago)
        
        if images:
            cards = []
            for i, img_path in enumerate(images):
                timestamp_str = self.extract_timestamp(img_path)
                card = CleanImageCard(img_path, timestamp_str)
                card.clicked.connect(self.show_image_viewer)
                cards.append(card)
                
                row = i // MAX_IMAGES_PER_ROW
                col = i % MAX_IMAGES_PER_ROW
                grid_layout.addWidget(card, row, col)
            
            # Carga asíncrona
            self.load_images_async(images, cards)
            scroll.set_cards(cards)
            
        else:
            # Estado vacío SIMPLE
            empty_label = QLabel(f"📭 No hay incidentes para {day_name.lower()}")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("""
                QLabel {
                    color: #9ca3af;
                    font-size: 16px;
                    padding: 40px;
                    background-color: #f9fafb;
                    border: 1px dashed #d1d5db;
                    border-radius: 8px;
                }
            """)
            grid_layout.addWidget(empty_label, 0, 0, 1, MAX_IMAGES_PER_ROW)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        return tab_widget
        
    def load_images_async(self, image_paths, cards):
        """Cargar imágenes async"""
        loader = ImageLoader(image_paths, self.image_cache)
        loader.imageLoaded.connect(self.on_image_loaded)
        
        self.image_loaders.append(loader)
        self.path_to_card = {card.image_path: card for card in cards}
        loader.start()
        
    def on_image_loaded(self, path, pixmap, from_cache):
        """Callback de imagen cargada"""
        if path in self.path_to_card:
            self.path_to_card[path].set_image(pixmap, from_cache)

    def show_image_viewer(self, image_path):
        """Mostrar visor"""
        viewer = ModernImageViewer(image_path, self)
        viewer.exec_()

    def extract_timestamp(self, img_path):
        """Extraer timestamp"""
        filename = os.path.basename(img_path)
        try:
            parts = filename.replace(".jpg", "").split("_")
            if len(parts) >= 3:
                timestamp_str = parts[1] + parts[2]
                dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                return dt.strftime("%H:%M:%S")
        except:
            pass
        return "??:??:??"

    def get_images_for_day(self, days_ago):
        """Obtener imágenes para día"""
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

    def refresh_tabs(self):
        """Refrescar tabs"""
        self.tabs.clear()
        
        today_tab = self.create_day_tab(0)
        yesterday_tab = self.create_day_tab(1)
        
        self.tabs.addTab(today_tab, "📅 Hoy")
        self.tabs.addTab(yesterday_tab, "📅 Ayer")
        
        self.tabs.setCurrentIndex(self.current_tab)

    def on_tab_changed(self, index):
        """Cambio de tab"""
        self.current_tab = index

    def smart_refresh(self):
        """Actualización inteligente"""
        current_today = len(self.get_images_for_day(0))
        current_yesterday = len(self.get_images_for_day(1))
        
        if hasattr(self, '_last_counts'):
            if (current_today != self._last_counts[0] or 
                current_yesterday != self._last_counts[1]):
                self.force_refresh()
        else:
            self.force_refresh()
            
        self._last_counts = (current_today, current_yesterday)

    def force_refresh(self):
        """Refrescar forzado"""
        for loader in self.image_loaders:
            loader.stop()
        self.image_loaders.clear()
        
        self.refresh_tabs()

    def launch_camera(self):
        """Lanzar cámara"""
        try:
            self.process = subprocess.Popen(["python", DETECCION_SCRIPT])
            self.camera_btn.setEnabled(False)
            self.return_btn.show()
            self.status_label.setText("🔴 Detección Activa")
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #fee2e2;
                    color: #991b1b;
                    padding: 8px 12px;
                    border-radius: 6px;
                    font-weight: bold;
                }
            """)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo iniciar:\n{str(e)}")

    def return_to_gui(self):
        """Volver a GUI"""
        if self.process:
            self.process.terminate()
            self.process = None
            
        self.return_btn.hide()
        self.camera_btn.setEnabled(True)
        self.status_label.setText("🟢 Sistema Listo")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #dcfce7;
                color: #166534;
                padding: 8px 12px;
                border-radius: 6px;
                font-weight: bold;
            }
        """)
        self.force_refresh()

    def closeEvent(self, event):
        """Cleanup"""
        if self.process:
            self.process.terminate()
            
        for loader in self.image_loaders:
            loader.stop()
            
        self.executor.shutdown(wait=False)
        self.image_cache.clear()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    gui = ArgosGUI()
    gui.show()
    
    sys.exit(app.exec_())