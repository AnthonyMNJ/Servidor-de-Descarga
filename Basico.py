import threading
import time
import random


# 1. RECURSO TIPO BÁSICO - SIN SINCRONIZAR

class BasicServerSinSync:
    def __init__(self, max_capacidad=3):
        self.MAX_CAPACIDAD = max_capacidad
        # Recurso compartido de tipo básico (entero)
        self.conexiones_activas = 0 

    def conectar(self, cliente_id):
        # --- INICIO SECCIÓN CRÍTICA (Sin protección) ---
        # 1. Consulta y validación
        if self.conexiones_activas < self.MAX_CAPACIDAD:
            # Simulamos un pequeño retraso de red para forzar la condición de carrera
            time.sleep(0.05) 
            # 2. Actualización
            self.conexiones_activas += 1
            print(f"[SIN SYNC] Cliente {cliente_id} CONECTADO. Activas: {self.conexiones_activas}/{self.MAX_CAPACIDAD}")
            return True
        else:
            print(f"[SIN SYNC] Cliente {cliente_id} RECHAZADO. Servidor lleno ({self.conexiones_activas}/{self.MAX_CAPACIDAD})")
            return False
        # --- FIN SECCIÓN CRÍTICA ---

    def desconectar(self, cliente_id):
        # --- INICIO SECCIÓN CRÍTICA (Sin protección) ---
        time.sleep(0.02)
        self.conexiones_activas -= 1
        print(f"[SIN SYNC] Cliente {cliente_id} DESCONECTADO. Activas: {self.conexiones_activas}/{self.MAX_CAPACIDAD}")
        # --- FIN SECCIÓN CRÍTICA ---


# ==========================================
# 2. RECURSO TIPO BÁSICO - SINCRONIZADO (Lock)
# ==========================================
class BasicServerConSync:
    def __init__(self, max_capacidad=3):
        self.MAX_CAPACIDAD = max_capacidad
        self.conexiones_activas = 0
        self._lock = threading.Lock() # Mecanismo de exclusión mutua

    def conectar(self, cliente_id):
        # Adquirimos el Lock para garantizar exclusión mutua en consulta, validación y actualización
        with self._lock:
            # --- INICIO SECCIÓN CRÍTICA (Protegida) ---
            if self.conexiones_activas < self.MAX_CAPACIDAD:
                time.sleep(0.05)
                self.conexiones_activas += 1
                print(f"[CON SYNC] Cliente {cliente_id} CONECTADO. Activas: {self.conexiones_activas}/{self.MAX_CAPACIDAD}")
                return True
            else:
                print(f"[CON SYNC] Cliente {cliente_id} RECHAZADO. Servidor lleno ({self.conexiones_activas}/{self.MAX_CAPACIDAD})")
                return False
            # --- FIN SECCIÓN CRÍTICA (Se libera el Lock automáticamente al salir del bloque) ---

    def desconectar(self, cliente_id):
        with self._lock:
            # --- INICIO SECCIÓN CRÍTICA (Protegida) ---
            time.sleep(0.02)
            self.conexiones_activas -= 1
            print(f"[CON SYNC] Cliente {cliente_id} DESCONECTADO. Activas: {self.conexiones_activas}/{self.MAX_CAPACIDAD}")
            # --- FIN SECCIÓN CRÍTICA ---



# HILO CLIENTE PARA PRUEBAS

class BasicClientWorker(threading.Thread):
    def __init__(self, cliente_id, server):
        super().__init__()
        self.cliente_id = cliente_id
        self.server = server

    def run(self):
        if self.server.conectar(self.cliente_id):
            # Simula el tiempo de descarga
            time.sleep(random.uniform(0.1, 0.3))
            self.server.desconectar(self.cliente_id)



# EJECUCIÓN DE PRUEBA

if __name__ == "__main__":
    print("--- PRUEBA 1: TIPO BÁSICO SIN SINCRONIZACIÓN ---")
    servidor_inseguro = BasicServerSinSync(max_capacidad=3)
    hilos = [BasicClientWorker(i, servidor_inseguro) for i in range(1, 7)]
    
    for h in hilos: h.start()
    for h in hilos: h.join()
    print(f"Conexiones finales (debería ser 0): {servidor_inseguro.conexiones_activas}\n")

    print("--- PRUEBA 2: TIPO BÁSICO CON SINCRONIZACIÓN (LOCK) ---")
    servidor_seguro = BasicServerConSync(max_capacidad=3)
    hilos_sync = [BasicClientWorker(i, servidor_seguro) for i in range(1, 7)]
    
    for h in hilos_sync: h.start()
    for h in hilos_sync: h.join()
    print(f"Conexiones finales (debería ser 0): {servidor_seguro.conexiones_activas}")