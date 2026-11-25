"""
Herramientas de PRESENTACIÓN y REGISTRO para el simulador.

Nada de este archivo forma parte de la sección crítica: solo sirve para mostrar
en consola lo que ocurre (colores, barras, recuadros) y para anotar cada
operación de los hilos, que luego se muestra en la consola o en la página web.
La lógica de sincronización está en Basico.py y Complejo.py.
"""
import os
import re
import sys
import textwrap
import threading
import time

# ==========================================
# COLORES (secuencias ANSI)
# ==========================================
RESET = "\033[0m"
NEGRITA = "\033[1m"
ROJO = "\033[91m"
VERDE = "\033[92m"
AMARILLO = "\033[93m"
AZUL = "\033[94m"
CIAN = "\033[96m"
GRIS = "\033[90m"

_ANSI = re.compile(r"\033\[[0-9;]*m")
_silencio = False


def habilitar_colores():
    """Activa los colores ANSI en la consola de Windows y la salida en UTF-8."""
    if os.name == "nt":
        os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def color(texto, *estilos):
    return "".join(estilos) + str(texto) + RESET


def largo_visible(texto):
    """Largo del texto sin contar los códigos de color."""
    return len(_ANSI.sub("", str(texto)))


# ==========================================
# SALIDA EN CONSOLA
# ==========================================
def silenciar(activo):
    """Permite ejecutar una prueba sin mostrar el detalle en la consola."""
    global _silencio
    _silencio = activo


def log(mensaje):
    """Escribe el mensaje de una sola vez para que los hilos no mezclen sus líneas."""
    if not _silencio:
        sys.stdout.write(mensaje + "\n")
        sys.stdout.flush()


def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")


def pausa(mensaje="Presione Enter para continuar..."):
    try:
        input(color(f"\n  {mensaje}", GRIS))
    except EOFError:
        print()


def barra_capacidad(activas, maximo):
    """
    Dibuja la ocupación del servidor. Ejemplos:
        [■■□] 2/3                 -> 2 de 3 lugares ocupados (correcto)
        [■■■|■■] 5/3 ¡SOBRECUPO!  -> lo que pasa del límite se ve en rojo
    """
    dentro = max(0, min(activas, maximo))
    libres = maximo - dentro
    exceso = max(0, activas - maximo)
    barra = color("■" * dentro, VERDE) + color("□" * libres, GRIS)
    if exceso:
        barra += color("|" + "■" * exceso, ROJO, NEGRITA)
    texto = f"[{barra}] {activas}/{maximo}"
    if exceso:
        texto += color(f"  ¡SOBRECUPO +{exceso}!", ROJO, NEGRITA)
    return texto


def caja(titulo, lineas=(), estilo=CIAN, ancho=78):
    """Imprime un recuadro con título. Las líneas largas sin color se ajustan solas."""
    interior = ancho - 4
    filas = []
    for linea in lineas:
        if largo_visible(linea) > interior and "\033" not in linea:
            sangria = " " * (len(linea) - len(linea.lstrip()))
            filas.extend(textwrap.wrap(linea, interior, subsequent_indent=sangria + "  "))
        else:
            filas.append(linea)
    ancho = max([ancho, largo_visible(titulo) + 4] + [largo_visible(f) + 4 for f in filas])

    def fila(texto):
        relleno = " " * (ancho - 3 - largo_visible(texto))
        return color("│", estilo) + " " + texto + relleno + color("│", estilo)

    print(color("┌" + "─" * (ancho - 2) + "┐", estilo))
    print(fila(color(titulo, estilo, NEGRITA)))
    if filas:
        print(color("├" + "─" * (ancho - 2) + "┤", estilo))
        for f in filas:
            print(fila(f))
    print(color("└" + "─" * (ancho - 2) + "┘", estilo))


def tabla(encabezados, filas):
    """Imprime una tabla alineada (admite celdas con color)."""
    todas = [encabezados] + filas
    anchos = [max(largo_visible(f[i]) for f in todas) for i in range(len(encabezados))]

    def linea(celdas):
        return " │ ".join(str(c) + " " * (anchos[i] - largo_visible(c)) for i, c in enumerate(celdas))

    print("  " + color(linea(encabezados), NEGRITA))
    print("  " + "─┼─".join("─" * a for a in anchos))
    for f in filas:
        print("  " + linea(f))


# ==========================================
# REGISTRO DE OPERACIONES (bitácora de los hilos)
# ==========================================
_COLOR_EVENTO = {"entra": VERDE, "sale": CIAN, "rechazado": AMARILLO}


class RegistroEventos:
    """
    Bitácora de cada operación que un hilo hace sobre el servidor. Por cada
    operación se guarda:
        - identificación del hilo (id que le da el sistema operativo)
        - operación solicitada (CONECTAR, DESCONECTAR, PEDIR SLOT, LIBERAR SLOT)
        - estado del recurso ANTES de la operación
        - resultado de la operación
        - estado del recurso DESPUÉS de la operación
    Se usa para mostrar la ejecución (consola y web) y para medir el resultado.

    list.append es atómico en CPython, por eso aquí no se usa ningún Lock:
    registrar no cambia el comportamiento de las pruebas sin sincronización.
    """
    ETIQUETA = ""

    def _iniciar_registro(self):
        self.historial = []
        self._t0 = time.perf_counter()

    def _ahora(self):
        """Segundos transcurridos desde que se creó el servidor."""
        return round(time.perf_counter() - self._t0, 4)

    # --- Cada servidor define cómo se ve su recurso compartido ---
    def estado(self):
        """Foto del recurso compartido (diccionario simple, apto para JSON)."""
        raise NotImplementedError

    def _texto_estado(self, estado):
        """Cómo se muestra esa foto en la consola."""
        raise NotImplementedError

    def _texto_extra(self, evento):
        return ""

    def _registrar(self, operacion, cliente_id, t_solicitud, antes, resultado, evento, **datos):
        hilo = threading.current_thread()
        e = {
            "t_solicitud": t_solicitud,      # cuándo el hilo pidió la operación
            "t": self._ahora(),              # cuándo terminó la operación
            "hilo_id": hilo.ident,
            "cliente": cliente_id,
            "operacion": operacion,
            "antes": antes,
            "resultado": resultado,
            "despues": self.estado(),
            "evento": evento,                # entra / sale / rechazado
            **datos,
        }
        self.historial.append(e)
        e["dentro"] = self.clientes_dentro()  # clientes usando el servidor en ese momento
        log(self._texto_evento(e))
        return e

    def _texto_evento(self, e):
        estilo = ROJO if e.get("pisado_a") else _COLOR_EVENTO[e["evento"]]
        tiempo = color("t=%.2fs" % e["t"], GRIS)
        hilo = color("Hilo %s" % e["hilo_id"], NEGRITA)
        archivo = " '%s'" % e["archivo"] if e.get("archivo") else ""
        cabecera = (f"{tiempo} {self.ETIQUETA} {hilo} · Cliente {e['cliente']} · "
                    f"solicita {color(e['operacion'], NEGRITA)}{archivo}")
        detalle = (f"{' ' * 8}Antes: {self._texto_estado(e['antes'])}  →  "
                   f"{color(e['resultado'], estilo, NEGRITA)}  →  "
                   f"Después: {self._texto_estado(e['despues'])}")
        return cabecera + "\n" + detalle + self._texto_extra(e)

    def clientes_dentro(self):
        """Cuántos clientes están usando el servidor en este momento según la bitácora."""
        dentro = 0
        for e in list(self.historial):
            if e["evento"] == "entra":
                dentro += 1
            elif e["evento"] == "sale":
                dentro -= 1
        return dentro

    def resumen(self):
        """Cifras finales de la prueba, calculadas a partir de la bitácora."""
        dentro = pico = admitidos = rechazados = pisados = mb = 0
        for e in self.historial:
            if e["evento"] == "entra":
                admitidos += 1
                dentro += 1
                pico = max(pico, dentro)
                if e.get("pisado_a"):
                    pisados += 1
            elif e["evento"] == "sale":
                dentro -= 1
                mb += e.get("mb", 0)
            elif e["evento"] == "rechazado":
                rechazados += 1
        return {
            "pico": pico,
            "admitidos": admitidos,
            "rechazados": rechazados,
            "pisados": pisados,
            "mb_reales": mb,
        }
