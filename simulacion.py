"""
Lógica común de las simulaciones.

La usan el menú de consola (index.py) y la página web (web.py): crea el servidor
del escenario elegido, lanza los hilos clientes, espera a que terminen y arma
un resultado con la bitácora de cada operación, el resumen, el estado final del
recurso compartido y una explicación en lenguaje sencillo.
"""
from Basico import BasicClientWorker, BasicServerSinSync, BasicServerConSync
from Complejo import DownloadServerManagerSinSync, DownloadServerManagerConSync, DownloadWorker

ARCHIVOS = ["ubuntu.iso", "dataset.csv", "video_4k.mp4", "backup.zip", "modelo_ia.bin"]
TAMANO_MB = 100
LIMITES = {"capacidad": (1, 10), "clientes": (1, 30)}

# ====================================================
# TEXTOS DE CADA ESCENARIO
# ({cap} = capacidad del servidor, {n} = número de clientes)
# ====================================================
ESCENARIOS = {
    "basico-sin": {
        "titulo": "Servidor básico SIN control",
        "tipo": "basico", "con_sync": False,
        "antes": [
            "El servidor acepta como máximo {cap} conexiones a la vez.",
            "{n} clientes intentan conectarse EXACTAMENTE al mismo tiempo.",
            "No hay control: cada cliente mira el contador de conexiones y, si ve lugar, entra.",
            "",
            "QUÉ OBSERVAR: el contador nunca debería pasar de {cap}.",
            "Si aparece '¡SOBRECUPO!', el servidor se desbordó.",
        ],
        "porque": [
            "Todos los clientes miraron el contador casi al mismo tiempo, cuando todavía "
            "marcaba 0 (mira la columna 'Estado antes'). Todos vieron 'hay lugar' y entraron "
            "antes de que alguno alcanzara a actualizarlo.",
            "",
            "Es como {n} personas que ven una sala de {cap} sillas vacía y entran juntas.",
            "Esto se llama CONDICIÓN DE CARRERA: nadie protege el paso de 'mirar si hay "
            "lugar' y 'ocuparlo'.",
        ],
    },
    "basico-con": {
        "titulo": "Servidor básico CON control (Lock)",
        "tipo": "basico", "con_sync": True,
        "antes": [
            "Mismo servidor (máximo {cap}) y los mismos {n} clientes llegando juntos.",
            "Ahora hay un PORTERO (threading.Lock): solo un cliente a la vez puede mirar "
            "el contador y ocupar su lugar. Los demás esperan su turno.",
            "",
            "QUÉ OBSERVAR: el contador nunca pasa de {cap}. Los que llegan con el servidor "
            "lleno son RECHAZADOS, y eso es lo correcto.",
            "Fíjate en el tiempo: ahora los clientes entran de a uno, no todos juntos.",
        ],
        "porque": [
            "El Lock hace que 'mirar si hay lugar' y 'ocupar el lugar' sean un solo paso: "
            "ningún otro cliente puede meterse en medio.",
            "Por eso el servidor nunca supera su límite.",
        ],
    },
    "complejo-sin": {
        "titulo": "Servidor complejo SIN control",
        "tipo": "complejo", "con_sync": False,
        "antes": [
            "Ahora el servidor tiene {cap} VENTANILLAS (slots) y anota quién descarga qué "
            "archivo en cada una, más el TOTAL de MB entregados.",
            "{n} clientes piden una ventanilla a la vez para bajar archivos de 100 MB.",
            "No hay control.",
            "",
            "QUÉ OBSERVAR:",
            "  • '¡PISÓ!': dos clientes se quedaron con la misma ventanilla.",
            "  • Los clientes descargando a la vez pasando de {cap}.",
            "  • El total de MB registrado al final frente a lo que de verdad se descargó.",
        ],
        "porque": [
            "Todos vieron la ventanilla 0 libre al mismo tiempo y se sentaron ahí, uno "
            "encima del otro: el servidor solo recuerda al último que llegó.",
            "",
            "Con el total de MB pasa lo mismo: varios clientes leyeron el total viejo a la "
            "vez y cada uno escribió su suma encima de la del otro, así que se 'pierden' MB.",
            "Las dos fallas son CONDICIONES DE CARRERA sobre un recurso compartido.",
        ],
    },
    "complejo-con": {
        "titulo": "Servidor complejo CON control (Lock)",
        "tipo": "complejo", "con_sync": True,
        "antes": [
            "Mismo servidor con {cap} ventanillas y los mismos {n} clientes.",
            "Ahora un Lock protege la búsqueda de ventanilla libre y la suma del total de MB.",
            "",
            "QUÉ OBSERVAR: cada cliente tiene su propia ventanilla, nadie pisa a nadie y el "
            "total de MB coincide exactamente con lo descargado.",
        ],
        "porque": [
            "Con el Lock, buscar una ventanilla libre y ocuparla es un solo paso, y sumar al "
            "total también: nadie lee datos viejos ni pisa a otro cliente.",
        ],
    },
}


def formatear(lineas, cap, n):
    return [l.format(cap=cap, n=n) for l in lineas]


def _ejecutar_hilos(hilos):
    for h in hilos: h.start()
    for h in hilos: h.join()


def detectar_problemas(r, maximo):
    """Traduce las cifras de la prueba a frases que cualquiera entienda."""
    problemas = []
    if r["pico"] > maximo:
        problemas.append(f"Llegaron a estar {r['pico']} clientes a la vez con un límite de "
                         f"{maximo} ({r['pico'] - maximo} de más).")
    if r.get("pisados"):
        problemas.append(f"{r['pisados']} cliente(s) se quedaron con un slot que ya era de otro "
                         f"(se pisaron).")
    if "mb_registrados" in r and r["mb_registrados"] != r["mb_reales"]:
        problemas.append(f"El servidor anotó {r['mb_registrados']} MB, pero se descargaron "
                         f"{r['mb_reales']} MB: se perdieron {r['mb_reales'] - r['mb_registrados']} MB "
                         f"del registro.")
    if r.get("contador_final", 0) != 0:
        problemas.append(f"Al terminar, el contador quedó en {r['contador_final']} y debería ser 0.")
    return problemas


def explicacion(esc, r, cap, n):
    """Texto de '¿Por qué pasó esto?' según el resultado obtenido."""
    if r["problemas"] or esc["con_sync"]:
        porque = formatear(esc["porque"], cap, n)
        if esc["con_sync"] and r["rechazados"]:
            porque += ["", f"Los {r['rechazados']} rechazados NO son un error: llegaron cuando "
                           "el servidor estaba lleno y se les avisó."]
        return porque
    if n <= cap:
        return [f"Hay {n} clientes y {cap} lugares: no alcanzan para superar el límite.",
                "Aumente el número de clientes para ver el problema."]
    return ["Esta vez los clientes no coincidieron y el error no se notó.",
            "La condición de carrera depende del momento exacto: ejecute la prueba otra vez."]


# ====================================================
# EJECUCIÓN DE LAS PRUEBAS
# ====================================================
class Pruebas:
    def __init__(self, max_capacidad=3, num_clientes=6):
        self.max_capacidad = max_capacidad
        self.num_clientes = num_clientes

    def _crear(self, esc):
        """Crea el servidor del escenario y los hilos clientes."""
        n = self.num_clientes
        if esc["tipo"] == "basico":
            clase = BasicServerConSync if esc["con_sync"] else BasicServerSinSync
            servidor = clase(max_capacidad=self.max_capacidad)
            hilos = [BasicClientWorker(i, servidor) for i in range(1, n + 1)]
        else:
            clase = DownloadServerManagerConSync if esc["con_sync"] else DownloadServerManagerSinSync
            servidor = clase(max_capacidad=self.max_capacidad)
            hilos = [DownloadWorker(f"C{i}", ARCHIVOS[(i - 1) % len(ARCHIVOS)], TAMANO_MB, servidor)
                     for i in range(1, n + 1)]
        return servidor, hilos

    def ejecutar(self, clave):
        """Ejecuta un escenario y devuelve un diccionario con todo el resultado (apto para JSON)."""
        esc = ESCENARIOS[clave]
        cap, n = self.max_capacidad, self.num_clientes
        servidor, hilos = self._crear(esc)
        _ejecutar_hilos(hilos)

        r = servidor.resumen()
        r["estado_final"] = servidor.estado()
        if esc["tipo"] == "basico":
            r["contador_final"] = servidor.conexiones_activas
        else:
            r["mb_registrados"] = servidor.estado_servidor["total_bytes_servidos"]
        r["problemas"] = detectar_problemas(r, cap)
        r["porque"] = explicacion(esc, r, cap, n)
        r.update(escenario=clave, titulo=esc["titulo"], tipo=esc["tipo"],
                 con_sync=esc["con_sync"], capacidad=cap, clientes=n,
                 eventos=servidor.historial)
        return r
