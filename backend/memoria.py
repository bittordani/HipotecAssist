# # Memoria minimalista de sesión
# historial_sesion = []

# def agregar_a_memoria(pregunta: str, respuesta: str):
#     historial_sesion.append({"usuario": pregunta, "bot": respuesta})

# def obtener_historial() -> str:
#     """
#     Devuelve todo el historial de la sesión como texto para contexto.
#     """
#     lineas = []
#     for entry in historial_sesion:
#         lineas.append(f"Tú: {entry['usuario']}")
#         lineas.append(f"Bot: {entry['bot']}")
#     return "\n".join(lineas)


# backend/memoria.py

# Diccionario: session_id -> historial de la sesión
memoria_sesiones = {}

def agregar_a_memoria(session_id: str, pregunta: str, respuesta: str):
    if session_id not in memoria_sesiones:
        memoria_sesiones[session_id] = []
    memoria_sesiones[session_id].append({"usuario": pregunta, "bot": respuesta})

def obtener_historial(session_id: str) -> str:
    """
    Devuelve el historial de la sesión como texto, listo para contexto.
    """
    return "\n".join(
        f"Tú: {e['usuario']}\nBot: {e['bot']}" 
        for e in memoria_sesiones.get(session_id, [])
    )

def reiniciar_sesion(session_id: str):
    memoria_sesiones[session_id] = []
