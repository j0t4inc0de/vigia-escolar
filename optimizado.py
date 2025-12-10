import cv2
import os
import threading
import time
import winsound
from datetime import datetime
from ultralytics import YOLO

# =========================
# CONFIGURACIÓN GENERAL
# =========================
MODEL_PATH = 'argos.pt'
CONFIDENCE_THRESHOLD = 0.65

# 👉 PUEDE SER:
# 0           -> webcam
# 1           -> segunda cámara
# "video.mp4" -> archivo de video
CAMERA_SOURCE = 0

PROCESS_WIDTH = 640
DISPLAY_HEIGHT = 800
FRAME_SKIP = 2

ALARM_FREQUENCY = 2500
ALARM_DURATION = 500
SAVE_COOLDOWN = 1.0
EVIDENCE_FOLDER = "evidencia_argos"

# =========================
# INIT
# =========================
os.makedirs(EVIDENCE_FOLDER, exist_ok=True)

print("🔄 Cargando modelo YOLO...")
model = YOLO(MODEL_PATH)
model.fuse()
print("✅ Modelo listo")

alarm_thread = None
last_save_time = 0
frame_count = 0

def play_alarm():
    try:
        winsound.Beep(ALARM_FREQUENCY, ALARM_DURATION)
    except RuntimeError:
        pass

# =========================
# APERTURA DE FUENTE
# =========================
print("🎥 Abriendo fuente de video...")

if isinstance(CAMERA_SOURCE, int):
    cap = cv2.VideoCapture(CAMERA_SOURCE)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
else:
    if not os.path.exists(CAMERA_SOURCE):
        print(f"❌ El archivo no existe: {CAMERA_SOURCE}")
        exit()
    cap = cv2.VideoCapture(CAMERA_SOURCE)

if not cap.isOpened():
    print("❌ No se pudo abrir la cámara / video")
    exit()

print("✅ Fuente abierta correctamente")
print("▶ Presiona Q para salir")

# =========================
# LOOP PRINCIPAL
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        print("⏹ Fin del video o error de captura")
        break

    frame_count += 1
    annotated_frame = frame
    knife_detected = False

    # -------------------------
    # PREPROCESO (FRAME CHICO)
    # -------------------------
    h, w = frame.shape[:2]
    scale = PROCESS_WIDTH / w
    process_frame = cv2.resize(
        frame,
        (PROCESS_WIDTH, int(h * scale)),
        interpolation=cv2.INTER_LINEAR
    )

    # -------------------------
    # INFERENCIA YOLO
    # -------------------------
    if frame_count % FRAME_SKIP == 0:
        results = model(process_frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

        for r in results:
            if r.boxes is not None and len(r.boxes) > 0:
                knife_detected = True
                annotated_frame = r.plot()

    # -------------------------
    # ALERTA Y EVIDENCIA
    # -------------------------
    if knife_detected:
        now = time.time()

        if alarm_thread is None or not alarm_thread.is_alive():
            alarm_thread = threading.Thread(target=play_alarm, daemon=True)
            alarm_thread.start()

        if now - last_save_time > SAVE_COOLDOWN:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(EVIDENCE_FOLDER, f"detectado_{ts}.jpg")
            cv2.imwrite(path, annotated_frame)
            last_save_time = now
            print(f"📸 Evidencia guardada: {path}")

        cv2.putText(
            annotated_frame,
            "¡ALERTA: ARMA DETECTADA!",
            (50, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.5,
            (0, 0, 255),
            3
        )

    # -------------------------
    # VISUALIZACIÓN
    # -------------------------
    ah, aw = annotated_frame.shape[:2]
    ratio = DISPLAY_HEIGHT / ah
    resized = cv2.resize(
        annotated_frame,
        (int(aw * ratio), DISPLAY_HEIGHT),
        interpolation=cv2.INTER_LINEAR
    )

    cv2.imshow("Monitor Argos", resized)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# =========================
# CLEANUP
# =========================
cap.release()
cv2.destroyAllWindows()
print("✅ Argos finalizado correctamente")