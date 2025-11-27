# Codigo para mantener la pestaña del COLAB activa y asi aevitar el cierre de sesion de google colab, ya que el modelo pide 8 horas entrenando xd

import pyautogui
import time
import random
from datetime import datetime
import winsound  # Librería nativa de Windows para sonidos

# Configuración del sonido
FRECUENCIA = 2500  # Hertz (Agudo para que se escuche claro)
DURACION = 200     # Milisegundos (Cortito, para no molestar)

try:
    while True:
        # 1. Esperar 60 segundos
        # Puedes bajar esto a 10 si quieres probar que el sonido funciona primero
        time.sleep(60)
        
        # 2. Mover el mouse
        x = random.randint(-10, 10)
        y = random.randint(-10, 10)
        pyautogui.moveRel(x, y)
        pyautogui.click()
        
        # 3. HACER RUIDO (El Heartbeat)
        # Esto emitirá un sonido del sistema
        winsound.Beep(FRECUENCIA, DURACION)
        
        # 4. Confirmación visual
        hora_actual = datetime.now().strftime("%H:%M:%S")
        print(f"[{hora_actual}] 🔊 Bip! Movimiento realizado.")

except KeyboardInterrupt:
    print("\n🛑 Script detenido. Puedes descansar.")
except ImportError:
    # Por si acaso no estás en Windows, usaremos un sonido genérico
    print("No se detectó Windows, usando sonido de sistema genérico.")
    print('\a') # Intenta hacer el sonido de "campana" del sistema