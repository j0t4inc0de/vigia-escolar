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
THUMBNAIL_SIZE = 200
MAX_IMAGES_PER_ROW = 5
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

class AnimatedImageCard(QFrame):
    """Tarjeta de imagen con animaciones suaves"""
    clicked = pyqtSignal(str)
    
    def __init__(self, image_path, timestamp_str):
        super().__init__()
        self.image_path = image_path
        self.timestamp_str = timestamp_str
        self.loaded = False
        self.hovered = False
        self.setup_ui()
        self.setup_animations()
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.NoFrame)
        self.setFixedSize(THUMBNAIL_SIZE + 30, THUMBNAIL_SIZE + 70)
        self.setCursor(Qt.PointingHandCursor)
        
        # Estilo base con gradiente sutil
        self.setStyleSheet("""
            AnimatedImageCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 1 #f8fafc
                );
                border: 2px solid #e2e8f0;
                border-radius: 16px;
                padding: 8px;
            }
            AnimatedImageCard:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f0f9ff,
                    stop: 1 #e0f2fe
                );
                border: 3px solid #3b82f6;
            }
        """)
        
        # Layout principal
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Contenedor de imagen con efecto shadow
        self.image_container = QFrame()
        self.image_container.setFixedSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE)
        self.image_container.setStyleSheet("""
            QFrame {
                background-color: #f1f5f9;
                border: 2px dashed #cbd5e1;
                border-radius: 12px;
            }
        """)
        
        # Label de imagen con loading
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedSize(THUMBNAIL_SIZE - 4, THUMBNAIL_SIZE - 4)
        
        # Loading placeholder animado
        self.loading_label = QLabel("⏳")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setFixedSize(THUMBNAIL_SIZE - 4, THUMBNAIL_SIZE - 4)
        self.loading_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                font-size: 32px;
                color: #64748b;
            }
        """)
        
        # Stack para alternar entre loading e imagen
        container_layout = QVBoxLayout(self.image_container)
        container_layout.setContentsMargins(2, 2, 2, 2)
        container_layout.addWidget(self.loading_label)
        container_layout.addWidget(self.image_label)
        self.image_label.hide()
        
        layout.addWidget(self.image_container)
        
        # Info panel con mejor diseño
        info_panel = QFrame()
        info_panel.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc,
                    stop: 1 #e2e8f0
                );
                border-radius: 8px;
                padding: 6px;
            }
        """)
        
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(6, 4, 6, 4)
        
        # Timestamp con icono
        self.time_label = QLabel(f"🕒 {self.timestamp_str}")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                font-weight: bold;
                color: #475569;
                background-color: transparent;
            }
        """)
        
        # Indicador de estado
        self.status_dot = QLabel("●")
        self.status_dot.setAlignment(Qt.AlignCenter)
        self.status_dot.setStyleSheet("""
            QLabel {
                color: #22c55e;
                font-size: 12px;
                background-color: transparent;
            }
        """)
        
        info_layout.addWidget(self.time_label)
        info_layout.addWidget(self.status_dot)
        layout.addWidget(info_panel)
        
        # Efecto de opacidad inicial
        self.opacity_effect = QGraphicsOpacityEffect()
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.7)
        
    def setup_animations(self):
        """Configurar animaciones suaves"""
        # Animación de opacidad
        self.opacity_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.opacity_animation.setDuration(300)
        self.opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Animación de loading (rotación del emoji)
        self.loading_timer = QTimer()
        self.loading_timer.timeout.connect(self.animate_loading)
        self.loading_states = ["⏳", "⌛", "⏳", "⌛"]
        self.loading_index = 0
        
    def start_loading_animation(self):
        """Iniciar animación de loading"""
        self.loading_timer.start(500)
        
    def stop_loading_animation(self):
        """Detener animación de loading"""
        self.loading_timer.stop()
        
    def animate_loading(self):
        """Animar indicador de carga"""
        self.loading_index = (self.loading_index + 1) % len(self.loading_states)
        self.loading_label.setText(self.loading_states[self.loading_index])
        
    def load_image(self):
        """Iniciar carga de imagen"""
        if not self.loaded:
            self.start_loading_animation()
            
    def set_image(self, pixmap, from_cache=False):
        """Establecer imagen cargada con animación"""
        if not self.loaded:
            self.stop_loading_animation()
            self.loading_label.hide()
            self.image_label.setPixmap(pixmap)
            self.image_label.show()
            self.loaded = True
            
            # Animación de aparición
            if not from_cache:
                self.fade_in()
            
            # Actualizar estilo del contenedor
            self.image_container.setStyleSheet("""
                QFrame {
                    background-color: #ffffff;
                    border: 1px solid #d1d5db;
                    border-radius: 12px;
                }
            """)
            
            # Cambiar indicador de estado
            self.status_dot.setStyleSheet("""
                QLabel {
                    color: #3b82f6;
                    font-size: 12px;
                    background-color: transparent;
                }
            """)
            
    def fade_in(self):
        """Animación de aparición suave"""
        self.opacity_animation.setStartValue(0.3)
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()
        
    def enterEvent(self, event):
        """Efecto hover entrada"""
        self.hovered = True
        self.opacity_animation.setStartValue(self.opacity_effect.opacity())
        self.opacity_animation.setEndValue(1.0)
        self.opacity_animation.start()
        
        # Tooltip con información adicional
        file_size = self.get_file_size()
        QToolTip.showText(
            event.globalPos(),
            f"Archivo: {os.path.basename(self.image_path)}\n"
            f"Hora: {self.timestamp_str}\n"
            f"Tamaño: {file_size}",
            self
        )
        
    def leaveEvent(self, event):
        """Efecto hover salida"""
        self.hovered = False
        self.opacity_animation.setStartValue(self.opacity_effect.opacity())
        self.opacity_animation.setEndValue(0.8)
        self.opacity_animation.start()
        
    def mousePressEvent(self, event):
        """Click en la tarjeta"""
        if self.loaded and event.button() == Qt.LeftButton:
            self.clicked.emit(self.image_path)
            
    def get_file_size(self):
        """Obtener tamaño del archivo formateado"""
        try:
            size = os.path.getsize(self.image_path)
            for unit in ['B', 'KB', 'MB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} GB"
        except:
            return "Desconocido"

class ModernImageViewer(QDialog):
    """Visor de imágenes moderno con controles"""
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
        
        # Header con información
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Área de imagen
        self.graphics_view = QGraphicsView()
        self.graphics_scene = QGraphicsScene()
        self.graphics_view.setScene(self.graphics_scene)
        self.graphics_view.setRenderHint(QPainter.Antialiasing)
        self.graphics_view.setDragMode(QGraphicsView.RubberBandDrag)
        
        # Cargar imagen
        pixmap = QPixmap(self.image_path)
        if not pixmap.isNull():
            self.graphics_scene.addPixmap(pixmap)
            self.graphics_view.fitInView(
                self.graphics_scene.itemsBoundingRect(),
                Qt.KeepAspectRatio
            )
        
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
        """Crear header con información"""
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #1e40af,
                    stop: 1 #3730a3
                );
                padding: 16px;
            }
        """)
        
        layout = QHBoxLayout(header)
        
        # Información del archivo
        filename = os.path.basename(self.image_path)
        timestamp = self.extract_full_timestamp(filename)
        
        title = QLabel(f"🛡️ Evidencia ARGOS")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        
        info = QLabel(f"📁 {filename} | 🕒 {timestamp}")
        info.setStyleSheet("color: #e2e8f0; font-size: 14px;")
        info.setAlignment(Qt.AlignRight)
        
        layout.addWidget(title)
        layout.addWidget(info)
        
        return header
        
    def create_footer(self):
        """Crear footer con controles"""
        footer = QFrame()
        footer.setStyleSheet("""
            QFrame {
                background-color: #334155;
                padding: 12px;
            }
        """)
        
        layout = QHBoxLayout(footer)
        
        # Botones de control
        zoom_in_btn = QPushButton("🔍 Zoom +")
        zoom_in_btn.clicked.connect(lambda: self.graphics_view.scale(1.2, 1.2))
        
        zoom_out_btn = QPushButton("🔍 Zoom -")
        zoom_out_btn.clicked.connect(lambda: self.graphics_view.scale(0.8, 0.8))
        
        fit_btn = QPushButton("📏 Ajustar")
        fit_btn.clicked.connect(self.fit_to_view)
        
        close_btn = QPushButton("❌ Cerrar")
        close_btn.clicked.connect(self.close)
        
        # Aplicar estilo a botones
        button_style = """
            QPushButton {
                background-color: #475569;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #64748b;
            }
            QPushButton:pressed {
                background-color: #334155;
            }
        """
        
        for btn in [zoom_in_btn, zoom_out_btn, fit_btn, close_btn]:
            btn.setStyleSheet(button_style)
            layout.addWidget(btn)
            
        layout.addStretch()
        
        return footer
        
    def fit_to_view(self):
        """Ajustar imagen a la vista"""
        self.graphics_view.fitInView(
            self.graphics_scene.itemsBoundingRect(),
            Qt.KeepAspectRatio
        )
        
    def extract_full_timestamp(self, filename):
        """Extraer timestamp completo"""
        try:
            parts = filename.replace(".jpg", "").split("_")
            if len(parts) >= 3:
                timestamp_str = parts[1] + parts[2]
                dt = datetime.strptime(timestamp_str, "%Y%m%d%H%M%S")
                return dt.strftime("%d/%m/%Y - %H:%M:%S")
        except:
            pass
        return "Fecha desconocida"

class OptimizedScrollArea(QScrollArea):
    """ScrollArea optimizado con loading progresivo"""
    def __init__(self):
        super().__init__()
        self.cards = []
        self.visible_range = (0, 0)
        self.setup_ui()
        
    def setup_ui(self):
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Estilo moderno del scroll
        self.setStyleSheet("""
            QScrollArea {
                background-color: #f8fafc;
                border: none;
                border-radius: 12px;
            }
            QScrollBar:vertical {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                width: 14px;
                border-radius: 7px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #cbd5e1,
                    stop: 1 #94a3b8
                );
                border-radius: 5px;
                min-height: 25px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #94a3b8,
                    stop: 1 #64748b
                );
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Conectar eventos de scroll
        self.verticalScrollBar().valueChanged.connect(self.on_scroll)
        
    def set_cards(self, cards):
        """Establecer tarjetas y configurar carga progresiva"""
        self.cards = cards
        self.load_visible_items()
        
    def on_scroll(self):
        """Manejar scroll para carga lazy"""
        self.load_visible_items()
        
    def load_visible_items(self):
        """Cargar solo elementos visibles y cercanos"""
        if not self.cards:
            return
            
        viewport_rect = self.viewport().rect()
        scroll_value = self.verticalScrollBar().value()
        
        # Buffer de carga (cargar elementos 300px antes/después)
        buffer = 300
        
        for card in self.cards:
            if card.isVisible():
                card_pos = card.mapTo(self.widget(), card.rect().topLeft())
                
                # Verificar si está en el área visible + buffer
                if (card_pos.y() >= -buffer and 
                    card_pos.y() <= viewport_rect.height() + buffer):
                    card.load_image()

class ArgosGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vigía Escolar - ARGOS")
        self.setGeometry(100, 30, 1500, 950)
        
        # Sistema de caché e hilos
        self.image_cache = ImageCache()
        self.executor = ThreadPoolExecutor(max_workers=6)
        self.image_loaders = []
        
        # Estado de la aplicación
        self.process = None
        self.current_tab = 0
        
        self.setup_styles()
        self.init_ui()
        
    def setup_styles(self):
        """Configurar estilos globales modernos"""
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc,
                    stop: 0.5 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                font-family: 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', sans-serif;
            }
            
            QTabWidget::pane {
                border: 2px solid #cbd5e1;
                border-radius: 12px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 1 #f8fafc
                );
                margin-top: -2px;
            }
            
            QTabBar::tab {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                padding: 14px 28px;
                margin: 3px 2px 0px 2px;
                border-radius: 10px 10px 0 0;
                font-weight: 600;
                color: #475569;
                font-size: 14px;
                min-width: 120px;
                border: 2px solid #d1d5db;
            }
            
            QTabBar::tab:selected {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6,
                    stop: 1 #1d4ed8
                );
                color: white;
                border-color: #3b82f6;
            }
            
            QTabBar::tab:hover:!selected {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 1 #bfdbfe
                );
                color: #1e40af;
            }
        """)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # Header moderno con gradiente y shadow
        header = self.create_modern_header()
        main_layout.addWidget(header)

        # Splitter para layout flexible
        splitter = QSplitter(Qt.Vertical)
        
        # Tabs mejorados
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Crear tabs
        self.refresh_tabs()
        splitter.addWidget(self.tabs)
        
        # Panel de control premium
        control_panel = self.create_control_panel()
        splitter.addWidget(control_panel)
        
        # Configurar proporciones
        splitter.setSizes([700, 150])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        
        main_layout.addWidget(splitter)

        # Timer optimizado
        self.timer = QTimer()
        self.timer.timeout.connect(self.smart_refresh)
        self.timer.start(15000)  # 15 segundos

    def create_modern_header(self):
        """Crear header moderno con efectos"""
        header_container = QFrame()
        header_container.setFixedHeight(100)
        
        # Efecto shadow
        shadow_effect = QGraphicsDropShadowEffect()
        shadow_effect.setBlurRadius(20)
        shadow_effect.setColor(QColor(0, 0, 0, 60))
        shadow_effect.setOffset(0, 4)
        header_container.setGraphicsEffect(shadow_effect)
        
        header_container.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #667eea,
                    stop: 0.5 #764ba2,
                    stop: 1 #f093fb
                );
                border-radius: 20px;
                padding: 20px;
            }
        """)
        
        layout = QHBoxLayout(header_container)
        layout.setContentsMargins(30, 20, 30, 20)
        
        # Logo y título principal
        title_section = QVBoxLayout()
        
        main_title = QLabel("Vigía Escolar - ARGOS")
        main_title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        main_title.setStyleSheet("color: white; background: transparent;")
        
        title_section.addWidget(main_title)
        
        # Panel de estadísticas
        stats_panel = self.create_stats_panel()
        
        layout.addLayout(title_section)
        layout.addStretch()
        layout.addWidget(stats_panel)
        
        return header_container
        
    def create_stats_panel(self):
        """Panel de estadísticas en tiempo real"""
        stats_container = QFrame()
        stats_container.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                padding: 16px;
            }
        """)
        
        layout = QVBoxLayout(stats_container)
        layout.setSpacing(8)
        
        # Contadores
        today_count = len(self.get_images_for_day(0))
        yesterday_count = len(self.get_images_for_day(1))
        total_count = today_count + yesterday_count
        
        stats_title = QLabel("📊 Estadísticas")
        stats_title.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background: transparent;")
        
        today_label = QLabel(f"Hoy: {today_count} incidentes")
        yesterday_label = QLabel(f"Ayer: {yesterday_count} incidentes")
        total_label = QLabel(f"Total: {total_count} incidentes")
        
        for label in [today_label, yesterday_label, total_label]:
            label.setStyleSheet("color: rgba(255, 255, 255, 0.9); font-size: 12px; background: transparent;")
        
        layout.addWidget(stats_title)
        layout.addWidget(today_label)
        layout.addWidget(yesterday_label)
        layout.addWidget(total_label)
        
        return stats_container

    def create_control_panel(self):
        """Panel de control moderno"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 1 #f8fafc
                );
                border: 2px solid #e2e8f0;
                border-radius: 16px;
                padding: 20px;
            }
        """)
        
        layout = QHBoxLayout(panel)
        layout.setSpacing(20)
        
        # Status indicator mejorado
        self.status_indicator = QFrame()
        self.status_indicator.setFixedSize(120, 60)
        self.update_status_indicator(False)
        
        # Botones principales
        self.camera_btn = self.create_premium_button(
            "🔴 Iniciar Detección", "#ef4444", "#dc2626"
        )
        self.camera_btn.clicked.connect(self.launch_camera)
        
        self.return_btn = self.create_premium_button(
            "⏹️ Detener", "#f59e0b", "#d97706"
        )
        self.return_btn.clicked.connect(self.return_to_gui)
        self.return_btn.hide()
        
        refresh_btn = self.create_premium_button(
            "🔄 Actualizar", "#10b981", "#059669"
        )
        refresh_btn.clicked.connect(self.force_refresh)
        
        layout.addWidget(self.status_indicator)
        layout.addStretch()
        layout.addWidget(refresh_btn)
        layout.addWidget(self.camera_btn)
        layout.addWidget(self.return_btn)
        
        return panel
        
    def create_premium_button(self, text, color, hover_color):
        """Crear botón premium con efectos"""
        btn = QPushButton(text)
        btn.setMinimumHeight(60)
        btn.setMinimumWidth(180)
        btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        
        # Efecto shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 3)
        btn.setGraphicsEffect(shadow)
        
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {color},
                    stop: 1 {self.darken_color(color)}
                );
                color: white;
                padding: 18px 36px;
                border-radius: 16px;
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {hover_color},
                    stop: 1 {self.darken_color(hover_color)}
                );
                border: 2px solid rgba(255, 255, 255, 0.3);
            }}
            QPushButton:pressed {{
                background-color: {self.darken_color(hover_color)};
                padding-top: 20px;
                padding-bottom: 16px;
            }}
            QPushButton:disabled {{
                background-color: #9ca3af;
                color: #d1d5db;
            }}
        """)
        
        return btn
        
    def update_status_indicator(self, active):
        """Actualizar indicador de estado visual"""
        if active:
            color = "#ef4444"
            text = "🔴 ACTIVO"
            bg_color = "#fef2f2"
        else:
            color = "#22c55e"
            text = "🟢 LISTO"
            bg_color = "#dcfce7"
            
        self.status_indicator.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 3px solid {color};
                border-radius: 12px;
                padding: 8px;
            }}
        """)
        
        # Layout del indicador
        if not self.status_indicator.layout():
            layout = QVBoxLayout(self.status_indicator)
            layout.setContentsMargins(8, 4, 8, 4)
            
            self.status_label = QLabel()
            self.status_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(self.status_label)
        
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                font-size: 12px;
                background: transparent;
            }}
        """)

    def create_day_tab(self, days_ago):
        """Crear tab optimizado para un día"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header del día
        day_name = "Hoy" if days_ago == 0 else "Ayer"
        date_str = (datetime.now() - timedelta(days=days_ago)).strftime("%d/%m/%Y")
        
        header_layout = QHBoxLayout()
        
        day_title = QLabel(f"📅 {day_name}")
        day_title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        day_title.setStyleSheet("color: #1f2937;")
        
        date_label = QLabel(date_str)
        date_label.setFont(QFont("Segoe UI", 16))
        date_label.setStyleSheet("color: #6b7280;")
        date_label.setAlignment(Qt.AlignRight)
        
        header_layout.addWidget(day_title)
        header_layout.addStretch()
        header_layout.addWidget(date_label)
        
        layout.addLayout(header_layout)
        
        # Scroll area optimizado
        scroll = OptimizedScrollArea()
        
        # Contenedor con grid responsive
        container = QWidget()
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(20)
        grid_layout.setContentsMargins(20, 20, 20, 20)
        
        # Obtener imágenes
        images = self.get_images_for_day(days_ago)
        
        if images:
            # Progreso de carga
            progress_bar = QProgressBar()
            progress_bar.setMaximum(len(images))
            progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #d1d5db;
                    border-radius: 8px;
                    text-align: center;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background: qlineargradient(
                        x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 #3b82f6,
                        stop: 1 #1d4ed8
                    );
                    border-radius: 6px;
                }
            """)
            layout.addWidget(progress_bar)
            
            # Crear cards
            cards = []
            for i, img_path in enumerate(images):
                timestamp_str = self.extract_timestamp(img_path)
                card = AnimatedImageCard(img_path, timestamp_str)
                card.clicked.connect(self.show_image_viewer)
                cards.append(card)
                
                # Posición en grid responsive
                row = i // MAX_IMAGES_PER_ROW
                col = i % MAX_IMAGES_PER_ROW
                grid_layout.addWidget(card, row, col)
            
            # Carga asíncrona optimizada
            self.load_images_async(images, cards, progress_bar)
            
            scroll.set_cards(cards)
            
        else:
            # Mensaje elegante cuando no hay imágenes
            empty_widget = self.create_empty_state(day_name.lower())
            grid_layout.addWidget(empty_widget, 0, 0, 1, MAX_IMAGES_PER_ROW)
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        return tab_widget
        
    def create_empty_state(self, day_name):
        """Crear estado vacío elegante"""
        empty_container = QFrame()
        empty_container.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc,
                    stop: 1 #f1f5f9
                );
                border: 2px dashed #cbd5e1;
                border-radius: 16px;
                padding: 60px;
            }
        """)
        
        layout = QVBoxLayout(empty_container)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)
        
        icon = QLabel("🛡️")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 64px; background: transparent;")
        
        title = QLabel(f"No hay incidentes para {day_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #64748b; background: transparent;")
        
        subtitle = QLabel("El sistema está funcionando correctamente")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setStyleSheet("color: #94a3b8; background: transparent;")
        
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        
        return empty_container
        
    def load_images_async(self, image_paths, cards, progress_bar):
        """Cargar imágenes de forma asíncrona con progreso"""
        # Crear loader
        loader = ImageLoader(image_paths, self.image_cache)
        loader.imageLoaded.connect(self.on_image_loaded)
        loader.progressUpdate.connect(progress_bar.setValue)
        loader.finished.connect(lambda: progress_bar.hide())
        
        self.image_loaders.append(loader)
        
        # Mapear paths a cards para callback
        self.path_to_card = {card.image_path: card for card in cards}
        
        loader.start()
        
    def on_image_loaded(self, path, pixmap, from_cache):
        """Callback cuando una imagen se carga"""
        if path in self.path_to_card:
            self.path_to_card[path].set_image(pixmap, from_cache)

    def show_image_viewer(self, image_path):
        """Mostrar visor de imagen moderno"""
        viewer = ModernImageViewer(image_path, self)
        viewer.exec_()

    def extract_timestamp(self, img_path):
        """Extraer timestamp del archivo"""
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

    def refresh_tabs(self):
        """Refrescar todos los tabs"""
        # Limpiar tabs existentes
        self.tabs.clear()
        
        # Recrear tabs
        today_tab = self.create_day_tab(0)
        yesterday_tab = self.create_day_tab(1)
        
        self.tabs.addTab(today_tab, "📅 Hoy")
        self.tabs.addTab(yesterday_tab, "📅 Ayer")
        
        # Mantener tab seleccionado
        self.tabs.setCurrentIndex(self.current_tab)

    def on_tab_changed(self, index):
        """Manejar cambio de tab"""
        self.current_tab = index

    def smart_refresh(self):
        """Actualización inteligente solo si hay cambios"""
        # Verificar si hay nuevas imágenes
        current_today = len(self.get_images_for_day(0))
        current_yesterday = len(self.get_images_for_day(1))
        
        # Solo refrescar si detectamos cambios
        if hasattr(self, '_last_counts'):
            if (current_today != self._last_counts[0] or 
                current_yesterday != self._last_counts[1]):
                self.force_refresh()
        else:
            self.force_refresh()
            
        self._last_counts = (current_today, current_yesterday)

    def force_refresh(self):
        """Forzar actualización completa"""
        # Detener loaders activos
        for loader in self.image_loaders:
            loader.stop()
        self.image_loaders.clear()
        
        # Refrescar interfaz
        self.refresh_tabs()
        
        # Actualizar stats en header
        header_stats = self.findChild(QFrame, "stats_panel")
        if header_stats:
            self.update_header_stats()

    def update_header_stats(self):
        """Actualizar estadísticas en header"""
        # Implementar actualización de estadísticas
        pass

    def launch_camera(self):
        """Lanzar sistema de detección"""
        try:
            self.process = subprocess.Popen(["python", DETECCION_SCRIPT])
            self.camera_btn.setEnabled(False)
            self.return_btn.show()
            self.update_status_indicator(True)
        except Exception as e:
            QMessageBox.critical(
                self, "Error de Sistema",
                f"No se pudo iniciar la detección:\n\n{str(e)}\n\n"
                f"Verifique que el archivo '{DETECCION_SCRIPT}' existe."
            )

    def return_to_gui(self):
        """Detener detección y volver"""
        if self.process:
            self.process.terminate()
            self.process = None
            
        self.return_btn.hide()
        self.camera_btn.setEnabled(True)
        self.update_status_indicator(False)
        self.force_refresh()

    def darken_color(self, hex_color):
        """Oscurecer color para gradientes"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(max(0, c - 40) for c in rgb)
        return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"

    def closeEvent(self, event):
        """Cleanup al cerrar"""
        # Detener proceso si está activo
        if self.process:
            self.process.terminate()
            
        # Detener loaders
        for loader in self.image_loaders:
            loader.stop()
            
        # Cleanup executor
        self.executor.shutdown(wait=False)
        
        # Limpiar caché
        self.image_cache.clear()
        
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Configuración de la app
    app.setApplicationName("ARGOS")
    app.setApplicationDisplayName("ARGOS - Sistema de Detección")
    app.setApplicationVersion("2.0")
    
    # Inicializar GUI
    gui = ArgosGUI()
    gui.show()
    
    sys.exit(app.exec_())