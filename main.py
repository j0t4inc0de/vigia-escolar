import cv2
import os
import threading
import time
import winsound
from datetime import datetime
from ultralytics import YOLO

# --- CONFIGURACIÓN ---
MODEL_PATH = 'argos.pt'
CONFIDENCE_THRESHOLD = 0.70
CAMERA_ID = "VID_20251210_160732156.mp4"
ALARM_FREQUENCY = 2500
ALARM_DURATION = 500
EVIDENCE_FOLDER = 'evidencia_argos'
SAVE_COOLDOWN = 1.0 

# CAMBIO AQUÍ: Controlamos la altura para que quepa en tu pantalla
DISPLAY_HEIGHT = 800  # Altura fija en píxeles (800 es seguro para casi cualquier laptop)

# --- INICIALIZACIÓN ---
if not os.path.exists(EVIDENCE_FOLDER):
    os.makedirs(EVIDENCE_FOLDER)
    print(f"Carpeta creada: {EVIDENCE_FOLDER}")

try:
    model = YOLO(MODEL_PATH)
    print("Modelo cargado correctamente.")
except Exception as e:
    print(f"Error cargando el modelo: {e}")
    exit()

alarm_thread = None
last_save_time = 0

def play_alarm():
    try:
        winsound.Beep(ALARM_FREQUENCY, ALARM_DURATION)
    except RuntimeError:
        pass

# Cargar video
cap = cv2.VideoCapture(CAMERA_ID)

if not cap.isOpened():
    print(f"Error: No se pudo abrir el archivo {CAMERA_ID}.")
    exit()

print("Argos procesando video. Presiona 'Q' para salir.")

# --- BUCLE PRINCIPAL ---
while True:
    ret, frame = cap.read()
    if not ret:
        print("Fin del video.")
        break

    # Inferencia (Detección)
    results = model(frame, conf=CONFIDENCE_THRESHOLD, stream=True, verbose=False)
    knife_detected = False
    annotated_frame = frame

    for r in results:
        if len(r.boxes) > 0:
            knife_detected = True
            annotated_frame = r.plot()

    # Lógica de Alarma y Guardado
    if knife_detected:
        current_time = time.time()

        if alarm_thread is None or not alarm_thread.is_alive():
            alarm_thread = threading.Thread(target=play_alarm)
            alarm_thread.start()

        if current_time - last_save_time > SAVE_COOLDOWN:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"detectado_{timestamp}.jpg"
            filepath = os.path.join(EVIDENCE_FOLDER, filename)
            cv2.imwrite(filepath, annotated_frame)
            print(f"Evidencia guardada: {filepath}")
            last_save_time = current_time

        cv2.putText(annotated_frame, "¡ALERTA: ARMA DETECTADA!", (50, 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

    # --- VISUALIZACIÓN (AJUSTE POR ALTURA) ---
    # Obtenemos dimensiones originales
    height, width = annotated_frame.shape[:2]
    
    # Calculamos el ratio basado en la ALTURA deseada (800px)
    ratio = DISPLAY_HEIGHT / height
    new_width = int(width * ratio)
    
    # Redimensionamos respetando la proporción
    frame_resized = cv2.resize(annotated_frame, (new_width, DISPLAY_HEIGHT))

    cv2.imshow('Monitor Argos', frame_resized)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()