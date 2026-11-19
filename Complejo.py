import threading
import time
import random


# 1. RECURSO TIPO COMPLEJO - SIN SINCRONIZACIÓN

class DownloadServerManagerSinSync:
    def __init__(self, max_capacidad=3):
        self.MAX_CAPACIDAD = max_capacidad
        # Recurso compartido complejo (diccionario detallado)
        self.estado_servidor = {
            "slots": {i: None for i in range(self.MAX_CAPACIDAD)},
            "total_bytes_servidos": 0
        }

    def request_slot(self, hilo_id, cliente_id, archivo, tamano_bytes) -> int:
        # --- INICIO SECCIÓN CRÍTICA (Sin protección) ---
        # 1. Consulta y validación: busca un slot en None
        for slot_id in range(self.MAX_CAPACIDAD):
            if self.estado_servidor["slots"][slot_id] is None:
                # Retraso artificial para provocar que otro hilo lea el mismo slot libre
                time.sleep(0.05) 
                
                # 2. Actualización: asigna el subdiccionario con los datos de la descarga
                self.estado_servidor["slots"][slot_id] = {
                    "hilo_id": hilo_id,
                    "cliente_id": cliente_id,
                    "archivo": archivo,
                    "tamano_bytes": tamano_bytes
                }
                print(f"[SIN SYNC] Cliente {cliente_id} (Hilo {hilo_id}) asignado al Slot {slot_id} -> '{archivo}'")
                return slot_id
        
        print(f"[SIN SYNC] Cliente {cliente_id} RECHAZADO: Todos los slots ocupados.")
        return -1
        # --- FIN SECCIÓN CRÍTICA ---

    def release_slot(self, slot_id, cliente_id, bytes_transferidos):
        # --- INICIO SECCIÓN CRÍTICA (Sin protección) ---
        # Lectura del acumulador global
        trafico_actual = self.estado_servidor["total_bytes_servidos"]
        time.sleep(0.03) # Retraso que provoca pérdida de actualizaciones en el tráfico
        
        # Liberación del slot y suma del tráfico
        self.estado_servidor["slots"][slot_id] = None
        self.estado_servidor["total_bytes_servidos"] = trafico_actual + bytes_transferidos
        print(f"[SIN SYNC] Cliente {cliente_id} liberó Slot {slot_id} (+{bytes_transferidos} MB).")
        # --- FIN SECCIÓN CRÍTICA ---


# ====================================================
# 2. RECURSO TIPO COMPLEJO - CON SINCRONIZACIÓN (Lock)
# ====================================================
class DownloadServerManagerConSync:
    def __init__(self, max_capacidad=3):
        self.MAX_CAPACIDAD = max_capacidad
        self.estado_servidor = {
            "slots": {i: None for i in range(self.MAX_CAPACIDAD)},
            "total_bytes_servidos": 0
        }
        # Mecanismo de exclusión mutua para proteger slots y total_bytes_servidos
        self._lock = threading.Lock()

    def request_slot(self, hilo_id, cliente_id, archivo, tamano_bytes) -> int:
        # Se adquiere el cerrojo antes de consultar los slots libres
        with self._lock:
            # --- INICIO SECCIÓN CRÍTICA (Protegida) ---
            for slot_id in range(self.MAX_CAPACIDAD):
                if self.estado_servidor["slots"][slot_id] is None:
                    time.sleep(0.05)
                    self.estado_servidor["slots"][slot_id] = {
                        "hilo_id": hilo_id,
                        "cliente_id": cliente_id,
                        "archivo": archivo,
                        "tamano_bytes": tamano_bytes
                    }
                    print(f"[CON SYNC] Cliente {cliente_id} (Hilo {hilo_id}) asignado al Slot {slot_id} -> '{archivo}'")
                    return slot_id
            
            print(f"[CON SYNC] Cliente {cliente_id} RECHAZADO: Todos los slots ocupados.")
            return -1
            # --- FIN SECCIÓN CRÍTICA (Se libera automáticamente el cerrojo) ---

    def release_slot(self, slot_id, cliente_id, bytes_transferidos):
        # Se adquiere el cerrojo para liberar el slot y actualizar el tráfico atómicamente
        with self._lock:
            # --- INICIO SECCIÓN CRÍTICA (Protegida) ---
            trafico_actual = self.estado_servidor["total_bytes_servidos"]
            time.sleep(0.03)
            self.estado_servidor["slots"][slot_id] = None
            self.estado_servidor["total_bytes_servidos"] = trafico_actual + bytes_transferidos
            print(f"[CON SYNC] Cliente {cliente_id} liberó Slot {slot_id} (+{bytes_transferidos} MB).")
            # --- FIN SECCIÓN CRÍTICA ---


# ====================================================
# CLASE HILO CLIENTE (DownloadWorker)
# ====================================================
class DownloadWorker(threading.Thread):
    def __init__(self, client_id, file_name, file_size, server):
        super().__init__()
        self.client_id = client_id
        self.file_name = file_name
        self.file_size = file_size
        self.server = server

    def run(self):
        # Usamos self.ident para obtener el ID real asignado por el sistema operativo al hilo
        slot_asignado = self.server.request_slot(
            hilo_id=self.ident,
            cliente_id=self.client_id,
            archivo=self.file_name,
            tamano_bytes=self.file_size
        )
        
        if slot_asignado != -1:
            # Simula la transferencia de datos fuera de la sección crítica
            time.sleep(random.uniform(0.1, 0.25))
            self.server.release_slot(slot_asignado, self.client_id, self.file_size)


# ====================================================
# EJECUCIÓN DE PRUEBA
# ====================================================
if __name__ == "__main__":
    # 5 clientes intentando descargar archivos de 100 MB cada uno en un servidor de 3 slots
    clientes_datos = [
        ("C1", "ubuntu.iso", 100),
        ("C2", "dataset.csv", 100),
        ("C3", "video_4k.mp4", 100),
        ("C4", "backup.zip", 100),
        ("C5", "modelo_ia.bin", 100),
    ]

    print("--- PRUEBA 1: RECURSO COMPLEJO SIN SINCRONIZACIÓN ---")
    server_inseguro = DownloadServerManagerSinSync(max_capacidad=3)
    workers_1 = [DownloadWorker(c, f, s, server_inseguro) for c, f, s in clientes_datos]
    
    for w in workers_1: w.start()
    for w in workers_1: w.join()
    
    print(f"Estado final de slots: {server_inseguro.estado_servidor['slots']}")
    print(f"Tráfico total registrado: {server_inseguro.estado_servidor['total_bytes_servidos']} MB (Inconsistente)\n")

    print("--- PRUEBA 2: RECURSO COMPLEJO CON SINCRONIZACIÓN (LOCK) ---")
    server_seguro = DownloadServerManagerConSync(max_capacidad=3)
    workers_2 = [DownloadWorker(c, f, s, server_seguro) for c, f, s in clientes_datos]
    
    for w in workers_2: w.start()
    for w in workers_2: w.join()
    
    print(f"Estado final de slots: {server_seguro.estado_servidor['slots']}")
    print(f"Tráfico total registrado: {server_seguro.estado_servidor['total_bytes_servidos']} MB (Exacto: 3 clientes x 100 MB = 300 MB)")