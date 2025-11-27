from ultralytics import YOLO
print("Iniciando la descarga del modelo YOLO11 Nano...")
model = YOLO("yolo11s.pt")

# 2. Información del modelo
# Esto confirma que se cargó (y descargó) correctamente.
print("¡Modelo descargado y cargado con éxito!")
model.info()