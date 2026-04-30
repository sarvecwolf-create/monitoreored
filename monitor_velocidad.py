"""
Monitor de Velocidad de Internet
"""
import streamlit as st
import pandas as pd
import subprocess
import json
import plotly.express as px
from datetime import datetime
import os
import sys
import time
import subprocess

# ──────────────────────────────────────────────
# CONFIGURACIÓN INICIAL
# ──────────────────────────────────────────────
def resource_path(relative_path):
    """Obtiene la ruta absoluta para recursos internos del EXE."""

    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

SPEEDTEST_BIN = resource_path("speedtest.exe")
CSV_PATH      = "diagnostico_red.csv"

st.set_page_config(page_title="Monitor de Velocidad de Internet", layout="wide")

# ──────────────────────────────────────────────
# FUNCIONES CORE
# ──────────────────────────────────────────────
def verificar_speedtest():
    """Verifica la existencia de speedtest.exe."""
    if not os.path.exists(SPEEDTEST_BIN):
        st.error(f"No se encontró speedtest.exe en: {SPEEDTEST_BIN}")
        st.info("Descarga speedtest-cli desde:"
                "https://install.speedtest.net/app/"
                "cli/ookla-speedtest-1.2.0-win64.zip")
        return False
    return True
def aceptar_licencia():
    """Primero verifica la existencia de speedtest.exe y luego acepta la licencia."""
    if not verificar_speedtest(): return
    subprocess.run(
        [SPEEDTEST_BIN,
         "--accept-license",
         "--accept-gdpr"],
        capture_output=True,
        check=False
        )

@st.cache_data(ttl=3600)
def cargar_servidores() -> list:
    """Carga la lista de servidores"""
    try:
        res = subprocess.run(
            [SPEEDTEST_BIN, "--format=json", "-L", "--accept-license", "--accept-gdpr"],
            capture_output=True, text=True, encoding="utf-8", timeout=20
            )

        if "Limit reached" in res.stderr:
            st.error(
                "Speedtest bloqueó la lista de servidores por exceso "
                "de peticiones. Reintenta en unos minutos."
                )
            return []
        return json.loads(res.stdout).get("servers", [])
    except Exception as e:
        st.error(f"Error al cargar servidores: {e}")
        return []

CREATE_NO_WINDOW = 0x08000000
def ejecutar_prueba(server_id: int) -> dict | str | None:
    """Ejecuta una prueba de velocidad utilizando speedtest.exe."""
    if not verificar_speedtest():
        return None
    try:
        res = subprocess.run(
            [SPEEDTEST_BIN, "-s", str(server_id),
             "--format=json", "--accept-license", "--accept-gdpr"],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=CREATE_NO_WINDOW,
            check=False
            )

        # Detectar bloqueo por frecuencia
        output = res.stdout + res.stderr
        if "Limit reached" in res.stderr or "Too many requests" in output:
            return "RATE_LIMIT"


        data = json.loads(res.stdout)
        if not all(k in data for k in ["server", "ping", "download", "upload"]):
            st.error("Respuesta inesperada de speedtest")
            return None
        return {
            "Fecha_Hora":      datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "PC":              os.environ.get("COMPUTERNAME", "Unknown"),
            "Servidor":        f"{data['server']['name']} ({data['server']['location']})",
            "Latencia_ms":     round(data["ping"]["latency"], 2),
            "Descarga_Mbps":   round(data["download"]["bandwidth"] * 8 / 1_000_000, 2),
            "Carga_Mbps":      round(data["upload"]["bandwidth"] * 8 / 1_000_000, 2),
            "PacketLoss_pct":  data.get("packetLoss", 0),
        }
    except json.JSONDecodeError:
        st.error("Error decodificando respuesta JSON de speedtest")
        return None
    except subprocess.TimeoutExpired:
        st.error("Timeout ejecutando speedtest")
        return None
    except Exception as e:
        st.error(f"Error inesperado: {e}")
        return None

def guardar_resultado(row: dict):
    """Guarda el resultado en un archivo CSV."""
    for _ in range(3):
        try:
            pd.DataFrame([row]).to_csv(
                CSV_PATH, mode="a", header=not os.path.exists(CSV_PATH), index=False
            )
            return
        except PermissionError:
            time.sleep(0.5)

def leer_y_procesar_csv() -> pd.DataFrame:
    """Lee y procesa el archivo CSV."""
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame()
    try:
        df = pd.read_csv(CSV_PATH)
        df.columns = df.columns.str.strip()
        # Convertir a fecha y crear el punto de acoplamiento cada 5 min
        df['Fecha_Hora_dt'] = pd.to_datetime(df['Fecha_Hora'], dayfirst=True)
        df['Punto_Control'] = df['Fecha_Hora_dt'].dt.floor('5min')
        return df.sort_values('Fecha_Hora_dt')
    except Exception:
        return pd.DataFrame()

# ──────────────────────────────────────────────
# ESTADO DE SESIÓN
# ──────────────────────────────────────────────
if "servers" not in st.session_state:
    st.session_state.update({
        "servers": [], "dict_serv": {}, "bucle_activo": False,
        "proxima_ejecucion": 0.0, "indice_servidor": 0,
        "servidores_elegidos": [], "intervalo_min": 15,
    })

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")

    if st.button("🔄 Cargar Servidores", use_container_width=True):
        with st.spinner("Consultando..."):
            servidores = cargar_servidores()
            if servidores:
                st.session_state.servers = servidores
                st.session_state.dict_serv = {
                    f"{s['name']} ({s['location']})": s["id"]
                    for s in servidores
                    }

    if st.session_state.servers:
        opciones = list(st.session_state.dict_serv.keys())
        st.session_state.servidores_elegidos = st.multiselect(
            "Nodos a monitorear:", options=opciones,
            default=st.session_state.servidores_elegidos or opciones[:1]
        )

        st.divider()
        st.session_state.intervalo_min = st.slider(
            "Intervalo Rondas (min):", 1, 60,
            st.session_state.intervalo_min
            )

        c1, c2 = st.columns(2)
        if c1.button("▶️ INICIAR", use_container_width=True):
            st.session_state.bucle_activo = True
            st.session_state.proxima_ejecucion = time.time()
            st.rerun()
        if c2.button("⏹️ PARAR", use_container_width=True, type="primary"):
            st.session_state.bucle_activo = False
            st.rerun()

    if st.button("🗑️ Borrar CSV", use_container_width=True):
        if os.path.exists(CSV_PATH): os.remove(
            CSV_PATH
            )
        """
        st.session_state.servers = []"""
        st.rerun()

# ──────────────────────────────────────────────
# ÁREA PRINCIPAL
# ──────────────────────────────────────────────
st.title("📊 Monitor de Velocidad de Internet")

df = leer_y_procesar_csv()

if not df.empty:
    last = df.iloc[-1]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("⬇️ Descarga", f"{last['Descarga_Mbps']} Mbps")
    c2.metric("⬆️ Carga",    f"{last['Carga_Mbps']} Mbps")
    c3.metric("📡 Latencia", f"{last['Latencia_ms']} ms")
    c4.metric("📍 Nodo",     last["Servidor"].split(" (")[0])
    c5.metric("🕐 Hora",     last["Fecha_Hora"].split(" ")[1])

    st.divider()

    # Gráfica Acoplada (Descarga)
    fig_dl = px.line(
        df, x="Punto_Control",
        y="Descarga_Mbps",
        color="Servidor",
        markers=True,
        title="📉 Descarga (Mbps) - Agrupado 5min"
        )
    fig_dl.update_layout(hovermode="x unified")
    st.plotly_chart(fig_dl, use_container_width=True)

    fig_dl = px.line(
        df, x="Punto_Control",
        y="Carga_Mbps",
        color="Servidor",
        markers=True,
        title="📉 Carga (Mbps) - Agrupado 5min"
        )
    fig_dl.update_layout(hovermode="x unified")
    st.plotly_chart(fig_dl, use_container_width=True)

    # Gráfica Acoplada (Latencia)
    fig_lat = px.line(
        df, x="Punto_Control",
        y="Latencia_ms",
        color="Servidor",
        markers=True,
        title="📶 Latencia (ms)"
        )
    fig_lat.update_layout(hovermode="x unified")
    st.plotly_chart(fig_lat, use_container_width=True)

    with st.expander("📋 Historial de Datos"):
        st.dataframe(df.sort_values("Fecha_Hora_dt", ascending=False), use_container_width=True)
else:
    st.info("⬅️ Configura los servidores y presiona 'Iniciar'.")

# ──────────────────────────────────────────────
# LÓGICA DE MONITOREO (CON MANEJO DE RATE LIMIT)
# ──────────────────────────────────────────────
if st.session_state.bucle_activo and st.session_state.servidores_elegidos:
    ahora = time.time()
    if ahora >= st.session_state.proxima_ejecucion:
        elegidos = st.session_state.servidores_elegidos
        idx = st.session_state.indice_servidor % len(elegidos)
        nombre_actual = elegidos[idx]
        sid = st.session_state.dict_serv.get(nombre_actual)

        if sid:
            with st.status(f"Probando {nombre_actual}..."):
                res = ejecutar_prueba(sid)

                if res == "RATE_LIMIT":
                    st.session_state.proxima_ejecucion = ahora + (30 * 60)
                    st.rerun()
                elif res:
                    guardar_resultado(res)
                    if idx + 1 >= len(elegidos):
                        st.session_state.proxima_ejecucion = (
                            ahora + (st.session_state.intervalo_min * 60)
                            )
                        st.session_state.indice_servidor = 0
                    else:
                        st.session_state.indice_servidor += 1
                        st.session_state.proxima_ejecucion = ahora + 10
                    st.rerun()
                else:
                    st.session_state.proxima_ejecucion = ahora + 60
                    st.rerun()
    else:  # Solo este else (para cuando no es hora de ejecutar)
        faltan = int(st.session_state.proxima_ejecucion - ahora)
        if faltan > 600:
            st.warning(f"⚠️ Speedtest Rate Limit: Reintentando en {faltan // 60} minutos...")
            time.sleep(60)
        else:
            st.info(f"⏳ Siguiente prueba en {faltan}s...")
            time.sleep(min(10, faltan))
        st.rerun()
# ❌ Se eliminó el bloque else externo que causaba el error
