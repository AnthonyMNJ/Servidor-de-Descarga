

from Basico import BasicClientWorker, BasicServerSinSync, BasicServerConSync
from Complejo import DownloadServerManagerSinSync, DownloadServerManagerConSync, DownloadWorker

class Pruebas:
    def __init__(self, tipo=1, max_capacidad=3, num_clientes=6):
        self.tipo = tipo
        self.max_capacidad = max_capacidad
        self.num_clientes = num_clientes

    def __call__(self):
        if( self.tipo == 1):
            print("--- PRUEBA 1: TIPO BÁSICO SIN SINCRONIZACIÓN ---")
            servidor_inseguro = BasicServerSinSync(max_capacidad=3)
            hilos = [BasicClientWorker(i, servidor_inseguro) for i in range(1, 7)]
            for h in hilos: h.start()
            for h in hilos: h.join()
            print(f"Conexiones finales (debería ser 0): {servidor_inseguro.conexiones_activas}\n")

        if(self.tipo == 2):
            print("--- PRUEBA 2: TIPO BÁSICO CON SINCRONIZACIÓN (LOCK) ---")
            servidor_seguro = BasicServerConSync(max_capacidad=3)
            hilos = [BasicClientWorker(i, servidor_seguro) for i in range(1, 7)]

            for h in hilos: h.start()
            for h in hilos: h.join()
            print(f"Conexiones finales (debería ser 0): {servidor_seguro.conexiones_activas}\n")
            
        #Prueba de servidor complejo 
        if(self.tipo == 3):
            print("--- PRUEBA 3: TIPO COMPLEJO SIN SINCRONIZACIÓN ---")
            server_inseguro = DownloadServerManagerSinSync(max_capacidad=3)
            clientes_datos = [
                ("C1", "ubuntu.iso", 100),
                ("C2", "dataset.csv", 100),
                ("C3", "video_4k.mp4", 100),
                ("C4", "backup.zip", 100),
                ("C5", "modelo_ia.bin", 100),
            ]
            hilos = [DownloadWorker(c, f, s, server_inseguro) for c, f, s in clientes_datos]

            for h in hilos: h.start()
            for h in hilos: h.join()

        if(self.tipo == 4):
            print("--- PRUEBA 4: TIPO COMPLEJO CON SINCRONIZACIÓN (LOCK) ---")
            server_seguro = DownloadServerManagerConSync(max_capacidad=3)
            clientes_datos = [
                ("C1", "ubuntu.iso", 100),
                ("C2", "dataset.csv", 100),
                ("C3", "video_4k.mp4", 100),
                ("C4", "backup.zip", 100),
                ("C5", "modelo_ia.bin", 100),
            ]
            hilos = [DownloadWorker(c, f, s, server_seguro) for c, f, s in clientes_datos]
            for h in hilos: h.start()
            for h in hilos: h.join()
        
        

if __name__ == "__main__":
    print("=== PRUEBAS DE SERVIDOR DE DESCARGA ===\n")
    print("1. Prueba de servidor básico sin sincronización")
    print("2. Prueba de servidor básico con sincronización")
    print("3. Prueba de servidor complejo sin sincronización")
    print("4. Prueba de servidor complejo con sincronización\n")

    op = input("Seleccione una opción (1-4): ")
    pruebas = Pruebas(tipo=int(op), max_capacidad=3, num_clientes=6)
    pruebas()

