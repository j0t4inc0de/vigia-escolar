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
    """Visor de imágenes con zoom, pan y navegación"""
    def __init__(self, image_paths, current_index, parent=None):
        super().__init__(parent)
        self.image_paths = image_paths  # Lista completa de imágenes
        self.current_index = current_index
        self.zoom_level = 1.0
        self.setup_ui()
        self.load_current_image()
        
    def setup_ui(self):
        self.setWindowTitle("🔍 Visor de Evidencia ARGOS")
        self.setModal(True)
        
        # Pantalla completa redimensionable
        screen = QDesktopWidget().screenGeometry()
        self.resize(min(1400, screen.width() - 100), min(900, screen.height() - 100))
        
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header con info
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Área de imagen con zoom y pan
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Habilitar drag y scroll
        self.graphics_view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.graphics_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        main_layout.addWidget(self.graphics_view)
        
        # Footer con controles
        footer = self.create_footer()
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
        
    def create_header(self):
        """Header con metadata"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: #2563eb;
                padding: 16px;
            }
        """)
        
        layout = QHBoxLayout(header)
        
        # Título
        title = QLabel("🔍 Evidencia ARGOS")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        
        # Metadata panel
        self.metadata_label = QLabel()
        self.metadata_label.setStyleSheet("color: #e2e8f0; font-size: 13px;")
        self.metadata_label.setAlignment(Qt.AlignRight)
        
        # Contador de imágenes
        self.counter_label = QLabel()
        self.counter_label.setStyleSheet("""
            color: white;
            font-size: 12px;
            background: rgba(255, 255, 255, 0.15);
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: bold;
        """)
        
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.metadata_label)
        layout.addWidget(self.counter_label)
        
        return header
        
    def create_footer(self):
        """Footer con controles de navegación y zoom"""
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #374151;
                padding: 12px;
            }
        """)
        
        layout = QHBoxLayout(footer)
        layout.setSpacing(12)
        
        # Botones de navegación
        self.prev_btn = QPushButton("⬅️ Anterior")
        self.prev_btn.setStyleSheet(self.get_footer_btn_style())
        self.prev_btn.clicked.connect(self.prev_image)
        
        self.next_btn = QPushButton("Siguiente ➡️")
        self.next_btn.setStyleSheet(self.get_footer_btn_style())
        self.next_btn.clicked.connect(self.next_image)
        
        # Botones de zoom
        zoom_out_btn = QPushButton("🔍-")
        zoom_out_btn.setStyleSheet(self.get_footer_btn_style())
        zoom_out_btn.clicked.connect(self.zoom_out)
        
        zoom_reset_btn = QPushButton("100%")
        zoom_reset_btn.setStyleSheet(self.get_footer_btn_style())
        zoom_reset_btn.clicked.connect(self.zoom_reset)
        
        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setStyleSheet(self.get_footer_btn_style())
        zoom_in_btn.clicked.connect(self.zoom_in)
        
        # Label de zoom
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: #e5e7eb; font-size: 12px; font-weight: bold;")
        
        # Botón cerrar
        close_btn = QPushButton("❌ Cerrar")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        close_btn.clicked.connect(self.close)
        
        # Layout
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.next_btn)
        layout.addStretch()
        layout.addWidget(zoom_out_btn)
        layout.addWidget(self.zoom_label)
        layout.addWidget(zoom_in_btn)
        layout.addWidget(zoom_reset_btn)
        layout.addStretch()
        layout.addWidget(close_btn)
        
        return footer
        
    def get_footer_btn_style(self):
        return """
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
            QPushButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """
        
    def load_current_image(self):
        """Cargar imagen actual con metadata"""
        self.graphics_scene.clear()
        self.zoom_level = 1.0
        
        image_path = self.image_paths[self.current_index]
        
        # Cargar imagen
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.graphics_scene.addPixmap(pixmap)
            self.graphics_view.fitInView(
                self.graphics_scene.itemsBoundingRect(),
                Qt.KeepAspectRatio
            )
        
        # Actualizar metadata
        self.update_metadata(image_path)
        
        # Actualizar contador
        self.counter_label.setText(f"{self.current_index + 1} / {len(self.image_paths)}")
        
        # Actualizar botones de navegación
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_paths) - 1)
        
    def update_metadata(self, image_path):
        """Extraer y mostrar metadata"""
        filename = os.path.basename(image_path)
        
        # Extraer fecha y hora del nombre del archivo
        try:
            parts = filename.replace(".jpg", "").split("_")
            if len(parts) >= 3:
                date_str = parts[1]  # YYYYMMDD
                time_str = parts[2]  # HHMMSS
                
                dt = datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")
                fecha = dt.strftime("%d/%m/%Y")
                hora = dt.strftime("%H:%M:%S")
            else:
                fecha = "Desconocida"
                hora = "Desconocida"
        except:
            fecha = "Desconocida"
            hora = "Desconocida"
        
        # Obtener tamaño del archivo
        try:
            size_bytes = os.path.getsize(image_path)
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        except:
            size_str = "Desconocido"
        
        # Mostrar metadata
        metadata_text = f"📅 {fecha}  |  🕐 {hora}  |  📦 {size_str}"
        self.metadata_label.setText(metadata_text)
        
    def zoom_in(self):
        """Zoom in"""
        self.zoom_level *= 1.2
        self.graphics_view.scale(1.2, 1.2)
        self.update_zoom_label()
        
    def zoom_out(self):
        """Zoom out"""
        self.zoom_level /= 1.2
        self.graphics_view.scale(1/1.2, 1/1.2)
        self.update_zoom_label()
        
    def zoom_reset(self):
        """Reset zoom"""
        self.graphics_view.resetTransform()
        self.zoom_level = 1.0
        self.graphics_view.fitInView(
            self.graphics_scene.itemsBoundingRect(),
            Qt.KeepAspectRatio
        )
        self.update_zoom_label()
        
    def update_zoom_label(self):
        """Actualizar label de zoom"""
        zoom_percent = int(self.zoom_level * 100)
        self.zoom_label.setText(f"{zoom_percent}%")
        
    def prev_image(self):
        """Imagen anterior"""
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()
            
    def next_image(self):
        """Imagen siguiente"""
        if self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            self.load_current_image()
            
    def wheelEvent(self, event):
        """Zoom con rueda del mouse"""
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
            
    def keyPressEvent(self, event):
        """Navegación con teclado"""
        if event.key() == Qt.Key_Left:
            self.prev_image()
        elif event.key() == Qt.Key_Right:
            self.next_image()
        elif event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key_0:
            self.zoom_reset()

class OptimizedScrollArea(QScrollArea):
    """ScrollArea optimizado sin botones de scroll"""
    def __init__(self):
        super().__init__()
        self.cards = []
        self.setup_ui()
        
    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Estilo limpio del scroll SIN BOTONES
        self.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #f1f5f9;
                width: 10px;
                border-radius: 5px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd5e1;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #94a3b8;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #64748b;
            }
            /* OCULTAR BOTONES DE ARRIBA Y ABAJO */
            QScrollBar::add-line:vertical {
                height: 0px;
            }
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
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
        """Header simple y limpio sin problemas de altura"""
        header = QFrame()
        header.setFixedHeight(70)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #3b82f6,
                    stop: 1 #6366f1
                );
                border-radius: 12px;
            }
        """)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(20)
        
        # Título
        title = QLabel(" Vigia Escolar ARGOS")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        
        # Stats en línea horizontal simple
        today_count = len(self.get_images_for_day(0))
        yesterday_count = len(self.get_images_for_day(1))
        
        stats_label = QLabel(f"📊 Hoy: {today_count}  |  Ayer: {yesterday_count}")
        stats_label.setStyleSheet("""
            color: rgba(255, 255, 255, 0.95);
            font-size: 13px;
            font-weight: 600;
            background: rgba(255, 255, 255, 0.15);
            padding: 8px 16px;
            border-radius: 6px;
        """)
        
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(stats_label)
        
        return header

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
        """Mostrar visor con navegación"""
        # Obtener lista completa de imágenes del tab actual
        images = self.get_images_for_day(self.current_tab)
        
        # Encontrar índice de la imagen clickeada
        try:
            current_index = images.index(image_path)
        except ValueError:
            current_index = 0
            
        viewer = ModernImageViewer(images, current_index, self)
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
            # self.process = subprocess.Popen(["python", DETECCION_SCRIPT]) #Esto usa el python del sistema
            self.process = subprocess.Popen([sys.executable, DETECCION_SCRIPT]) # Este usa el python del venv
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