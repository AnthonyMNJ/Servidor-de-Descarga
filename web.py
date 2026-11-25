"""
INTERFAZ WEB DEL SIMULADOR (servidor local)

Ejecute:   python web.py
y se abrirá http://127.0.0.1:8000 en el navegador. Desde la página se puede
configurar la simulación (tipo de recurso, con o sin Lock, capacidad y número
de clientes), ejecutarla y ver la ejecución de cada hilo y el resultado.

Solo usa la biblioteca estándar de Python: no hay que instalar nada.

API (JSON):
    GET  /api/escenarios  -> textos de cada escenario y límites de configuración
    POST /api/simular     -> {"escenario": "basico-sin", "capacidad": 3, "clientes": 6}
    POST /api/comparar    -> {"capacidad": 3, "clientes": 6}  (ejecuta los 4 escenarios)
"""
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from interfaz import silenciar
from simulacion import ESCENARIOS, LIMITES, Pruebas

CARPETA_WEB = Path(__file__).resolve().parent / "web"
ARCHIVOS_WEB = {  # solo se sirven estos archivos
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/estilos.css": ("estilos.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}
HOST = "127.0.0.1"
PUERTO_INICIAL = 8000

# Se ejecuta una simulación a la vez para que dos pedidos no se mezclen en los
# tiempos medidos. (Este Lock es de la aplicación web, no del problema simulado.)
_una_simulacion_a_la_vez = threading.Lock()


class ErrorDeDatos(ValueError):
    pass


def _leer_entero(datos, nombre):
    minimo, maximo = LIMITES[nombre]
    try:
        valor = int(datos.get(nombre))
    except (TypeError, ValueError):
        raise ErrorDeDatos(f"'{nombre}' debe ser un número entero.")
    if not minimo <= valor <= maximo:
        raise ErrorDeDatos(f"'{nombre}' debe estar entre {minimo} y {maximo}.")
    return valor


def _crear_pruebas(datos):
    return Pruebas(max_capacidad=_leer_entero(datos, "capacidad"),
                   num_clientes=_leer_entero(datos, "clientes"))


def simular(datos):
    clave = datos.get("escenario")
    if clave not in ESCENARIOS:
        raise ErrorDeDatos(f"Escenario desconocido: {clave!r}.")
    pruebas = _crear_pruebas(datos)
    with _una_simulacion_a_la_vez:
        return pruebas.ejecutar(clave)


def comparar(datos):
    pruebas = _crear_pruebas(datos)
    resultados = []
    with _una_simulacion_a_la_vez:
        for clave in ESCENARIOS:
            r = pruebas.ejecutar(clave)
            r.pop("eventos")  # la tabla comparativa no necesita el detalle
            resultados.append(r)
    return {"capacidad": pruebas.max_capacidad, "clientes": pruebas.num_clientes,
            "resultados": resultados}


class Manejador(BaseHTTPRequestHandler):
    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta == "/api/escenarios":
            self._enviar_json({"escenarios": ESCENARIOS, "limites": LIMITES})
        elif ruta in ARCHIVOS_WEB:
            nombre, tipo = ARCHIVOS_WEB[ruta]
            self._enviar(200, (CARPETA_WEB / nombre).read_bytes(), tipo)
        else:
            self._enviar_json({"error": "No encontrado"}, 404)

    def do_POST(self):
        acciones = {"/api/simular": simular, "/api/comparar": comparar}
        accion = acciones.get(self.path)
        if accion is None:
            self._enviar_json({"error": "No encontrado"}, 404)
            return
        try:
            largo = int(self.headers.get("Content-Length") or 0)
            datos = json.loads(self.rfile.read(largo) or b"{}")
            if not isinstance(datos, dict):
                raise ErrorDeDatos("Se esperaba un objeto JSON.")
            self._enviar_json(accion(datos))
        except (ErrorDeDatos, json.JSONDecodeError) as e:
            self._enviar_json({"error": str(e)}, 400)

    def _enviar_json(self, objeto, codigo=200):
        cuerpo = json.dumps(objeto, ensure_ascii=False).encode("utf-8")
        self._enviar(codigo, cuerpo, "application/json; charset=utf-8")

    def _enviar(self, codigo, cuerpo, tipo):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, formato, *args):
        sys.stderr.write("  [web] " + (formato % args) + "\n")


def iniciar_servidor():
    for puerto in range(PUERTO_INICIAL, PUERTO_INICIAL + 20):
        try:
            return ThreadingHTTPServer((HOST, puerto), Manejador)
        except OSError:
            continue  # puerto ocupado: se prueba el siguiente
    raise SystemExit("No se encontró un puerto libre entre 8000 y 8019.")


def main():
    silenciar(True)  # en la versión web el detalle se ve en el navegador, no en la consola
    servidor = iniciar_servidor()
    url = f"http://{HOST}:{servidor.server_address[1]}"
    print(f"\n  Simulador de Servidor de Descargas - interfaz web")
    print(f"  Abra en el navegador:  {url}")
    print(f"  Para detenerlo presione Ctrl+C\n")
    if "--no-abrir" not in sys.argv:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n  Servidor detenido.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
