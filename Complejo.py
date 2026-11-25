import threading
import time
import random

from interfaz import RegistroEventos, barra_capacidad, color, habilitar_colores, AMARILLO, AZUL, GRIS


class _VistaServidorComplejo(RegistroEventos):
    """Cómo se ve el recurso complejo (solo para mostrarlo; no toca la sección crítica)."""

    def estado(self):
        slots = self.estado_servidor["slots"]
        ocupantes = []
        for slot_id in range(self.MAX_CAPACIDAD):
            ocupante = slots[slot_id]  # se lee una sola vez: otro hilo puede cambiarlo
            ocupantes.append(ocupante["cliente_id"] if ocupante else None)
        return {
            "slots": ocupantes,
            "total_mb": self.estado_servidor["total_bytes_servidos"],
            "max": self.MAX_CAPACIDAD,
        }

    def _texto_estado(self, estado):
        slots = "|".join(c or "--" for c in estado["slots"])
        return f"[{slots}] {estado['total_mb']} MB"

    def _texto_extra(self, e):
        return (f"\n{' ' * 8}" + color("Clientes descargando: ", GRIS)
                + barra_capacidad(e["dentro"], self.MAX_CAPACIDAD))


# 1. RECURSO TIPO COMPLEJO - SIN SINCRONIZACIÓN

class DownloadServerManagerSinSync(_VistaServidorComplejo):
    ETIQUETA = color("[SIN SYNC]", AMARILLO)

    def __init__(self, max_capacidad=3):
        self.MAX_CAPACIDAD = max_capacidad
        # Recurso compartido complejo (diccionario detallado)
        self.estado_servidor = {
            "slots": {i: None for i in range(self.MAX_CAPACIDAD)},
            "total_bytes_servidos": 0
        }
        # Bitácora solo para registrar y mostrar (no forma parte del recurso compartido)
        self._iniciar_registro()

    def request_slot(self, hilo_id, cliente_id, archivo, tamano_bytes) -> int:
        t_solicitud = self._ahora()
        antes = self.estado()  # (solo registro) estado del recurso antes de la operación
        # --- INICIO SECCIÓN CRÍTICA (Sin protección) ---
        # 1. Consulta y validación: busca un slot en None
        for slot_id in range(self.MAX_CAPACIDAD):
            if self.estado_servidor["slots"][slot_id] is None:
                # Retraso artificial para provocar que otro hilo lea el mismo slot libre
                time.sleep(0.05)

                # (Solo registro) ¿otro cliente ocupó este slot mientras esperábamos?
                anterior = self.estado_servidor["slots"][slot_id]
                pisado_a = anterior["cliente_id"] if anterior else None

                # 2. Actualización: asigna el subdiccionario con los datos de la descarga
                self.estado_servidor["slots"][slot_id] = {
                    "hilo_id": hilo_id,
                    "cliente_id": cliente_id,
                    "archivo": archivo,
                    "tamano_bytes": tamano_bytes
                }
                resultado = f"OCUPÓ SLOT {slot_id}" + (f" ¡PISÓ a {pisado_a}!" if pisado_a else "")
                self._registrar("PEDIR SLOT", cliente_id, t_solicitud, antes, resultado, "entra",
                                slot=slot_id, archivo=archivo, pisado_a=pisado_a)
                return slot_id

        self._registrar("PEDIR SLOT", cliente_id, t_solicitud, antes,
                        "RECHAZADO (sin slots libres)", "rechazado", archivo=archivo)
        return -1
        # --- FIN SECCIÓN CRÍTICA ---

    def release_slot(self, slot_id, cliente_id, bytes_transferidos):
        t_solicitud = self._ahora()
        antes = self.estado()  # (solo registro)
        # --- INICIO SECCIÓN CRÍTICA (Sin protección) ---
        # Lectura del acumulador global
        trafico_actual = self.estado_servidor["total_bytes_servidos"]
        time.sleep(0.03) # Retraso que provoca pérdida de actualizaciones en el tráfico

        # Liberación del slot y suma del tráfico
        self.estado_servidor["slots"][slot_id] = None
        self.estado_servidor["total_bytes_servidos"] = trafico_actual + bytes_transferidos
        self._registrar("LIBERAR SLOT", cliente_id, t_solicitud, antes,
                        f"LIBERÓ SLOT {slot_id} (+{bytes_transferidos} MB)", "sale",
                        slot=slot_id, mb=bytes_transferidos)
        # --- FIN SECCIÓN CRÍTICA ---


# ====================================================
# 2. RECURSO TIPO COMPLEJO - CON SINCRONIZACIÓN (Lock)
# ====================================================
class DownloadServerManagerConSync(_VistaServidorComplejo):
    ETIQUETA = color("[CON SYNC]", AZUL)

    def __init__(self, max_capacidad=3):
        self.MAX_CAPACIDAD = max_capacidad
        self.estado_servidor = {
            "slots": {i: None for i in range(self.MAX_CAPACIDAD)},
            "total_bytes_servidos": 0
        }
        # Mecanismo de exclusión mutua para proteger slots y total_bytes_servidos
        self._lock = threading.Lock()
        # Bitácora solo para registrar y mostrar (no forma parte del recurso compartido)
        self._iniciar_registro()

    def request_slot(self, hilo_id, cliente_id, archivo, tamano_bytes) -> int:
        t_solicitud = self._ahora()  # momento en que el hilo pide (puede esperar el Lock)
        # Se adquiere el cerrojo antes de consultar los slots libres
        with self._lock:
            antes = self.estado()  # (solo registro)
            # --- INICIO SECCIÓN CRÍTICA (Protegida) ---
            for slot_id in range(self.MAX_CAPACIDAD):
                if self.estado_servidor["slots"][slot_id] is None:
                    time.sleep(0.05)

                    # (Solo registro) misma verificación que en la versión sin sincronizar
                    anterior = self.estado_servidor["slots"][slot_id]
                    pisado_a = anterior["cliente_id"] if anterior else None

                    self.estado_servidor["slots"][slot_id] = {
                        "hilo_id": hilo_id,
                        "cliente_id": cliente_id,
                        "archivo": archivo,
                        "tamano_bytes": tamano_bytes
                    }
                    resultado = f"OCUPÓ SLOT {slot_id}" + (f" ¡PISÓ a {pisado_a}!" if pisado_a else "")
                    self._registrar("PEDIR SLOT", cliente_id, t_solicitud, antes, resultado, "entra",
                                    slot=slot_id, archivo=archivo, pisado_a=pisado_a)
                    return slot_id

            self._registrar("PEDIR SLOT", cliente_id, t_solicitud, antes,
                            "RECHAZADO (sin slots libres)", "rechazado", archivo=archivo)
            return -1
            # --- FIN SECCIÓN CRÍTICA (Se libera automáticamente el cerrojo) ---

    def release_slot(self, slot_id, cliente_id, bytes_transferidos):
        t_solicitud = self._ahora()
        # Se adquiere el cerrojo para liberar el slot y actualizar el tráfico atómicamente
        with self._lock:
            antes = self.estado()  # (solo registro)
            # --- INICIO SECCIÓN CRÍTICA (Protegida) ---
            trafico_actual = self.estado_servidor["total_bytes_servidos"]
            time.sleep(0.03)
            self.estado_servidor["slots"][slot_id] = None
            self.estado_servidor["total_bytes_servidos"] = trafico_actual + bytes_transferidos
            self._registrar("LIBERAR SLOT", cliente_id, t_solicitud, antes,
                            f"LIBERÓ SLOT {slot_id} (+{bytes_transferidos} MB)", "sale",
                            slot=slot_id, mb=bytes_transferidos)
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
    habilitar_colores()
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

    resumen_1 = server_inseguro.resumen()
    print(f"Estado final del recurso: {server_inseguro.estado()}")
    print(f"Tráfico total registrado: {server_inseguro.estado_servidor['total_bytes_servidos']} MB "
          f"de {resumen_1['mb_reales']} MB descargados (Inconsistente)\n")

    print("--- PRUEBA 2: RECURSO COMPLEJO CON SINCRONIZACIÓN (LOCK) ---")
    server_seguro = DownloadServerManagerConSync(max_capacidad=3)
    workers_2 = [DownloadWorker(c, f, s, server_seguro) for c, f, s in clientes_datos]

    for w in workers_2: w.start()
    for w in workers_2: w.join()

    resumen_2 = server_seguro.resumen()
    print(f"Estado final del recurso: {server_seguro.estado()}")
    print(f"Tráfico total registrado: {server_seguro.estado_servidor['total_bytes_servidos']} MB "
          f"de {resumen_2['mb_reales']} MB descargados (Exacto)")
