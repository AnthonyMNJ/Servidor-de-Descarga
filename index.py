"""
SIMULADOR DEL SERVIDOR DE DESCARGAS (menú de consola)

Menú interactivo que muestra, con palabras sencillas, qué pasa cuando varios
clientes (hilos) intentan usar un servidor con capacidad limitada al mismo
tiempo, con y sin sincronización (threading.Lock).

Para la versión en el navegador, ejecute:  python web.py
"""
import textwrap

from interfaz import (barra_capacidad, caja, color, habilitar_colores, limpiar_pantalla,
                      pausa, silenciar, tabla, NEGRITA, ROJO, VERDE, AMARILLO, CIAN, GRIS)
from simulacion import ESCENARIOS, LIMITES, Pruebas, formatear

# Opción del menú -> escenario
MENU = {"2": "basico-sin", "3": "basico-con", "4": "complejo-sin", "5": "complejo-con"}


def _valor(texto, malo):
    return color(texto, ROJO, NEGRITA) if malo else color(texto, VERDE)


def texto_estado_final(r):
    """Estado final del recurso compartido, en una línea."""
    e = r["estado_final"]
    if r["tipo"] == "basico":
        return f"conexiones_activas = {e['conexiones_activas']}"
    slots = " ".join(f"[{i}:{c or '--'}]" for i, c in enumerate(e["slots"]))
    return f"slots {slots}  total = {e['total_mb']} MB"


# ====================================================
# PANTALLAS DEL MENÚ
# ====================================================
def mostrar_menu(pruebas):
    caja("SIMULADOR DE SERVIDOR DE DESCARGAS", [
        f"Capacidad: {color(pruebas.max_capacidad, NEGRITA)} descargas a la vez"
        f"  |  Clientes que llegan juntos: {color(pruebas.num_clientes, NEGRITA)}",
        "",
        "EL PROBLEMA: si muchos clientes llegan al mismo tiempo y nadie controla",
        "la entrada, el servidor acepta MÁS clientes de los que puede atender.",
    ])
    sin = color("-> muestra el problema", ROJO)
    con = color("-> muestra la solución", VERDE)
    print(f"""
  {color('1.', NEGRITA)} ¿Qué estamos simulando? (explicación sencilla)

  {color('2.', NEGRITA)} Servidor básico   - SIN control        {sin}
  {color('3.', NEGRITA)} Servidor básico   - CON control (Lock) {con}
  {color('4.', NEGRITA)} Servidor complejo - SIN control        {sin}
  {color('5.', NEGRITA)} Servidor complejo - CON control (Lock) {con}

  {color('6.', NEGRITA)} Comparar SIN vs CON (tabla resumen)
  {color('7.', NEGRITA)} Cambiar capacidad / número de clientes
  {color('0.', NEGRITA)} Salir

  {color('Versión web: ejecute  python web.py  y se abrirá en el navegador.', GRIS)}
""")


def explicar(pruebas):
    cap, n = pruebas.max_capacidad, pruebas.num_clientes
    limpiar_pantalla()
    caja("¿QUÉ ESTAMOS SIMULANDO?", [
        "Un servidor de descargas es una computadora que entrega archivos a varios "
        f"clientes. Por su capacidad, solo puede atender {cap} descargas al mismo tiempo.",
        "",
        f"Imagina una SALA CON {cap} SILLAS y {n} PERSONAS que llegan a la vez:",
        "  • Sin portero: todas miran la sala al mismo tiempo, ven sillas libres y "
        f"entran juntas. Resultado: {n} personas para {cap} sillas (SOBRECUPO).",
        "  • Con portero: deja pasar de a UNA persona; cuando las sillas se llenan, a "
        "las demás les dice 'está lleno'.",
    ])
    print()
    caja("LO MISMO, EN EL PROGRAMA", [
        "Sala con sillas     ->  el servidor y su límite (MAX_CAPACIDAD)",
        "Cada persona        ->  un cliente (un hilo / thread)",
        "El portero          ->  threading.Lock() (exclusión mutua)",
        "Mirar y sentarse    ->  sección crítica (consultar, validar, actualizar)",
        "Entrar sin control  ->  condición de carrera (race condition)",
    ])
    print()
    caja("CÓMO LEER LA PANTALLA", [
        "Cada operación de un hilo se muestra así:",
        f"  t=0.05s [SIN SYNC] {color('Hilo 28988', NEGRITA)} · Cliente 4 · solicita {color('CONECTAR', NEGRITA)}",
        f"      Antes: {barra_capacidad(0, 3)}  →  {color('ENTRÓ', VERDE, NEGRITA)}  →  "
        f"Después: {barra_capacidad(4, 3)}",
        "",
        "Hilo = identificador del hilo · solicita = operación pedida · Antes/Después =",
        "estado del recurso compartido · en el centro, el resultado de la operación.",
        "",
        "Básico:   el recurso compartido es un número (el contador de conexiones).",
        "Complejo: el recurso compartido son las ventanillas (slots) con los datos de "
        "cada descarga, más el total de MB entregados: [C1|--|--] 100 MB.",
    ])
    pausa("Presione Enter para volver al menú...")


def ejecutar_escenario(pruebas, clave):
    esc = ESCENARIOS[clave]
    cap, n = pruebas.max_capacidad, pruebas.num_clientes
    limpiar_pantalla()
    estilo = VERDE if esc["con_sync"] else AMARILLO
    caja(f"{esc['titulo'].upper()} - ¿Qué va a pasar?", formatear(esc["antes"], cap, n), estilo)
    if n <= cap:
        print(color(f"\n  Aviso: hay {n} clientes y {cap} lugares; no alcanzan para superar el "
                    f"límite. Cambie la configuración con la opción 7.", AMARILLO))
    pausa("Presione Enter para iniciar la simulación...")

    print(color("\n  ── EJECUCIÓN DE LOS HILOS ─────────────────────────────────────\n", NEGRITA))
    r = pruebas.ejecutar(clave)
    problemas = r["problemas"]

    # --- Resultado ---
    lineas = [
        f"Límite del servidor:            {cap} a la vez",
        f"Máximo de clientes a la vez:    {_valor(r['pico'], r['pico'] > cap)}",
        f"Clientes atendidos:             {r['admitidos']}",
        f"Clientes rechazados:            {r['rechazados']}",
    ]
    if esc["tipo"] == "complejo":
        lineas += [
            f"Clientes que pisaron a otro:    {_valor(r['pisados'], r['pisados'] > 0)}",
            f"MB descargados de verdad:       {r['mb_reales']} MB",
            f"MB que registró el servidor:    "
            f"{_valor(str(r['mb_registrados']) + ' MB', r['mb_registrados'] != r['mb_reales'])}",
        ]
    lineas += ["", f"Estado final del recurso:       {texto_estado_final(r)}", ""]
    if problemas:
        lineas.append(color("✘ PROBLEMA:", ROJO, NEGRITA))
        for p in problemas:
            for i, parte in enumerate(textwrap.wrap(p, 68)):
                lineas.append(color(("  • " if i == 0 else "    ") + parte, ROJO))
    else:
        lineas.append(color(f"✔ CORRECTO: el servidor nunca superó su límite de {cap}.", VERDE, NEGRITA))
    print()
    caja("RESULTADO", lineas, ROJO if problemas else VERDE)
    print()
    caja("¿POR QUÉ PASÓ ESTO?", r["porque"])
    pausa("Presione Enter para volver al menú...")


def comparar(pruebas):
    cap = pruebas.max_capacidad
    limpiar_pantalla()
    caja("COMPARACIÓN: SIN CONTROL vs CON CONTROL (Lock)", [
        f"Se ejecutan los 4 escenarios con capacidad {cap} y {pruebas.num_clientes} clientes.",
        f"'Máx. a la vez' nunca debería pasar de {cap}.",
        "'MB anotados' = MB que registró el servidor / MB descargados de verdad.",
    ])
    filas = []
    silenciar(True)
    try:
        for clave in MENU.values():
            esc = ESCENARIOS[clave]
            print(color(f"  Ejecutando: {esc['titulo'].lower()}...", GRIS))
            r = pruebas.ejecutar(clave)
            complejo = esc["tipo"] == "complejo"
            mb = f"{r['mb_registrados']}/{r['mb_reales']}" if complejo else "-"
            filas.append([
                ("Básico" if not complejo else "Complejo")
                + (" CON Lock" if esc["con_sync"] else " SIN control"),
                _valor(r["pico"], r["pico"] > cap),
                str(r["admitidos"]),
                str(r["rechazados"]),
                _valor(r["pisados"], r["pisados"] > 0) if complejo else "-",
                _valor(mb, complejo and r["mb_registrados"] != r["mb_reales"]),
                color("✘ PROBLEMA", ROJO, NEGRITA) if r["problemas"] else color("✔ CORRECTO", VERDE, NEGRITA),
            ])
    finally:
        silenciar(False)

    print()
    tabla(["Escenario", "Máx. a la vez", "Atendidos", "Rechazados",
           "Pisados", "MB anotados", "Resultado"], filas)
    print()
    caja("CONCLUSIÓN", [
        "Sin control, varios clientes ocupan el servidor al mismo tiempo y se supera el "
        "límite (o se pierden datos). Con Lock, el límite se respeta siempre: los que "
        "sobran son rechazados en lugar de sobrecargar el servidor.",
    ])
    pausa("Presione Enter para volver al menú...")


def pedir_entero(mensaje, minimo, maximo, actual):
    while True:
        texto = input(f"  {mensaje} [{minimo}-{maximo}] (Enter = {actual}): ").strip()
        if not texto:
            return actual
        if texto.isdigit() and minimo <= int(texto) <= maximo:
            return int(texto)
        print(color(f"  Valor no válido. Escriba un número entre {minimo} y {maximo}.", ROJO))


def configurar(pruebas):
    limpiar_pantalla()
    caja("CONFIGURACIÓN", [
        "Cambie cuántas descargas soporta el servidor y cuántos clientes llegan juntos.",
        "Para ver el problema, los clientes tienen que ser MÁS que la capacidad.",
    ])
    print()
    pruebas.max_capacidad = pedir_entero("Capacidad del servidor", *LIMITES["capacidad"],
                                         pruebas.max_capacidad)
    pruebas.num_clientes = pedir_entero("Número de clientes", *LIMITES["clientes"],
                                        pruebas.num_clientes)
    if pruebas.num_clientes <= pruebas.max_capacidad:
        print(color("\n  Aviso: con esta configuración no hay clientes suficientes para "
                    "superar el límite.", AMARILLO))
    pausa("Configuración guardada. Presione Enter para volver al menú...")


def main():
    habilitar_colores()
    pruebas = Pruebas(max_capacidad=3, num_clientes=6)
    while True:
        limpiar_pantalla()
        mostrar_menu(pruebas)
        op = input("  Seleccione una opción: ").strip()
        if op == "0":
            print(color("\n  ¡Hasta luego!\n", CIAN))
            break
        elif op == "1":
            explicar(pruebas)
        elif op in MENU:
            ejecutar_escenario(pruebas, MENU[op])
        elif op == "6":
            comparar(pruebas)
        elif op == "7":
            configurar(pruebas)
        else:
            print(color(f"\n  '{op}' no es una opción válida. Escriba un número del 0 al 7.", ROJO))
            pausa()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print(color("\n\n  Programa terminado.\n", CIAN))
