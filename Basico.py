import threading
import time
import random

from interfaz import RegistroEventos, barra_capacidad, color, habilitar_colores, AMARILLO, AZUL


class _VistaServidorBasico(RegistroEventos):
    """Cómo se ve el recurso básico (solo para mostrarlo; no toca la sección crítica)."""

    def estado(self):
        return {"conexiones_activas": self.conexiones_activas, "max": self.MAX_CAPACIDAD}

    def _texto_estado(self, estado):
        return barra_capacidad(estado["conexiones_activas"], self.MAX_CAPACIDAD)


# 1. RECURSO TIPO BÁSICO - SIN SINCRONIZAR

class BasicServerSinSync(_VistaServidorBasico):
    ETIQUETA = color("[SIN SYNC]", AMARILLO)

    def __init__(self, max_capacidad=3):
        self.MAX_CAPACIDAD = max_capacidad
        # Recurso compartido de tipo básico (entero)
        self.conexiones_activas = 0
        # Bitácora solo para registrar y mostrar (no forma parte del recurso compartido)
        self._iniciar_registro()

    def conectar(self, cliente_id):
        t_solicitud = self._ahora()
        antes = self.estado()  # (solo registro) estado del recurso antes de la operación
        # --- INICIO SECCIÓN CRÍTICA (Sin protección) ---
        # 1. Consulta y validación
        if self.conexiones_activas < self.MAX_CAPACIDAD:
            # Simulamos un pequeño retraso de red para forzar la condición de carrera
            time.sleep(0.05)
            # 2. Actualización
            self.conexiones_activas += 1
            self._registrar("CONECTAR", cliente_id, t_solicitud, antes, "ENTRÓ", "entra")
            return True
        else:
            self._registrar("CONECTAR", cliente_id, t_solicitud, antes, "RECHAZADO (lleno)", "rechazado")
            return False
        # --- FIN SECCIÓN CRÍTICA ---

    def desconectar(self, cliente_id):
        t_solicitud = self._ahora()
        antes = self.estado()  # (solo registro)
        # --- INICIO SECCIÓN CRÍTICA (Sin protección) ---
        time.sleep(0.02)
        self.conexiones_activas -= 1
        self._registrar("DESCONECTAR", cliente_id, t_solicitud, antes, "SALIÓ", "sale")
        # --- FIN SECCIÓN CRÍTICA ---


# ==========================================
# 2. RECURSO TIPO BÁSICO - SINCRONIZADO (Lock)
# ==========================================
class BasicServerConSync(_VistaServidorBasico):
    ETIQUETA = color("[CON SYNC]", AZUL)

    def __init__(self, max_capacidad=3):
        self.MAX_CAPACIDAD = max_capacidad
        self.conexiones_activas = 0
        self._lock = threading.Lock() # Mecanismo de exclusión mutua
        # Bitácora solo para registrar y mostrar (no forma parte del recurso compartido)
        self._iniciar_registro()

    def conectar(self, cliente_id):
        t_solicitud = self._ahora()  # momento en que el hilo pide entrar (puede esperar el Lock)
        # Adquirimos el Lock para garantizar exclusión mutua en consulta, validación y actualización
        with self._lock:
            antes = self.estado()  # (solo registro)
            # --- INICIO SECCIÓN CRÍTICA (Protegida) ---
            if self.conexiones_activas < self.MAX_CAPACIDAD:
                time.sleep(0.05)
                self.conexiones_activas += 1
                self._registrar("CONECTAR", cliente_id, t_solicitud, antes, "ENTRÓ", "entra")
                return True
            else:
                self._registrar("CONECTAR", cliente_id, t_solicitud, antes, "RECHAZADO (lleno)", "rechazado")
                return False
            # --- FIN SECCIÓN CRÍTICA (Se libera el Lock automáticamente al salir del bloque) ---

    def desconectar(self, cliente_id):
        t_solicitud = self._ahora()
        with self._lock:
            antes = self.estado()  # (solo registro)
            # --- INICIO SECCIÓN CRÍTICA (Protegida) ---
            time.sleep(0.02)
            self.conexiones_activas -= 1
            self._registrar("DESCONECTAR", cliente_id, t_solicitud, antes, "SALIÓ", "sale")
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
    habilitar_colores()
    print("--- PRUEBA 1: TIPO BÁSICO SIN SINCRONIZACIÓN ---")
    servidor_inseguro = BasicServerSinSync(max_capacidad=3)
    hilos = [BasicClientWorker(i, servidor_inseguro) for i in range(1, 7)]

    for h in hilos: h.start()
    for h in hilos: h.join()
    print(f"Estado final del recurso: {servidor_inseguro.estado()}")
    print(f"Máximo de clientes a la vez: {servidor_inseguro.resumen()['pico']} (límite 3)\n")

    print("--- PRUEBA 2: TIPO BÁSICO CON SINCRONIZACIÓN (LOCK) ---")
    servidor_seguro = BasicServerConSync(max_capacidad=3)
    hilos_sync = [BasicClientWorker(i, servidor_seguro) for i in range(1, 7)]

    for h in hilos_sync: h.start()
    for h in hilos_sync: h.join()
    print(f"Estado final del recurso: {servidor_seguro.estado()}")
    print(f"Máximo de clientes a la vez: {servidor_seguro.resumen()['pico']} (límite 3)")
