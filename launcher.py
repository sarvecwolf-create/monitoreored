import os
import sys
import streamlit.web.cli as stcli
import threading
import webbrowser
import time

def resource_path(relative_path):
    """Obtiene la ruta absoluta para recursos internos del EXE."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def open_browser():
    """Espera a que el servidor inicie y abre el navegador."""
    time.sleep(5)
    webbrowser.open("http://localhost:8501")

def main():
    # El nombre del archivo debe coincidir con tu script de Streamlit
    streamlit_script = resource_path("monitor_velocidad.py")
    
    if not os.path.exists(streamlit_script):
        print(f"Error: No se encontro el recurso {streamlit_script}")
        time.sleep(5)
        return

    # Iniciar hilo para abrir el navegador
    threading.Thread(target=open_browser, daemon=True).start()

    # Configurar argumentos para ejecutar Streamlit internamente
    sys.argv = [
        "streamlit",
        "run",
        streamlit_script,
        "--global.developmentMode", "false",
        "--server.headless", "true",
        "--server.port", "8501",
        "--browser.serverAddress", "localhost"
    ]

    # Ejecutar el motor de Streamlit
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()