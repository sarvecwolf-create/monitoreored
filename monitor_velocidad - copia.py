import streamlit as st
import pandas as pd
import subprocess
import json
import plotly.express as px
from datetime import datetime
import os
import sys
import time

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

st.set_page_config(page_title="Herramienta IT - Diagnóstico", layout="wide")

SPEEDTEST_BIN = resource_path("speedtest.exe")
CSV_PATH = "diagnostico_red.csv"

def run_test(server_id):
    try:
        command = [SPEEDTEST_BIN, "-s", str(server_id), "--format=json", "--accept-license", "--accept-gdpr"]
        result = subprocess.run(command, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        new_data = {
            "Fecha_Hora": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "PC": os.environ.get('COMPUTERNAME', 'Unknown'),
            "Servidor": data['server']['name'],
            "ISP": data['isp'],
            "Latencia_ms": data['ping']['latency'],
            "Descarga_Mbps": round(data['download']['bandwidth'] * 8 / 1000000, 2),
            "Carga_Mbps": round(data['upload']['bandwidth'] * 8 / 1000000, 2),
            "PacketLoss_pct": data.get('packetLoss', 0)
        }
        
        df_new = pd.DataFrame([new_data])
        df_new.to_csv(CSV_PATH, mode='a', header=not os.path.exists(CSV_PATH), index=False)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# --- ESTADOS DE SESIÓN ---
if 'bucle_activo' not in st.session_state:
    st.session_state.bucle_activo = False
if 'servers' not in st.session_state:
    st.session_state.servers = []
# NUEVO: Guardar cuándo toca la siguiente prueba
if 'proxima_ejecucion' not in st.session_state:
    st.session_state.proxima_ejecucion = 0

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Configuración")
    
    if st.button("🔄 Cargar Servidores") or not st.session_state.servers:
        try:
            cmd = [SPEEDTEST_BIN, "--format=json", "--accept-license", "--accept-gdpr", "-L"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            st.session_state.servers = json.loads(res.stdout)['servers']
        except: st.error("Error al cargar")

    if st.session_state.servers:
        opciones = {f"{s['name']} ({s['location']})": s['id'] for s in st.session_state.servers}
        server_name = st.selectbox("Servidor:", list(opciones.keys()))
        sid = opciones[server_name]
        
        st.divider()
        if st.button("🚀 Test Único (Manual)"):
            run_test(sid)

        st.divider()
        st.subheader("⏲️ Modo Bucle")
        intervalo = st.slider("Minutos entre pruebas:", 1, 60, 10)
        
        if not st.session_state.bucle_activo:
            if st.button("▶️ Iniciar Bucle"):
                st.session_state.bucle_activo = True
                # Programar ejecución inmediata al empezar
                st.session_state.proxima_ejecucion = time.time()
                st.rerun()
        else:
            if st.button("⏹️ Detener Bucle"):
                st.session_state.bucle_activo = False
                st.rerun()

# --- CUERPO PRINCIPAL ---
st.title("🌐 Diagnóstico de Red IT")

if st.session_state.bucle_activo:
    st.success(f"🔄 MODO BUCLE ACTIVO - Servidor: {server_name}")

if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
    last = df.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Descarga", f"{last['Descarga_Mbps']} Mbps")
    c2.metric("Latencia", f"{last['Latencia_ms']} ms")
    c3.metric("Última Prueba", last['Fecha_Hora'].split(" ")[1])
    c4.metric("PC", last['PC'])

    fig = px.line(df, x="Fecha_Hora", y="Descarga_Mbps", color="Servidor", markers=True, title="Historial de Velocidad")
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Ver Datos"):
        st.dataframe(df.sort_index(ascending=False))
else:
    st.info("Esperando primera prueba...")

# --- LÓGICA DEL BUCLE REFORMADA (SIN BLOQUEO) ---
if st.session_state.bucle_activo:
    ahora = time.time()
    
    # ¿Ya es hora de hacer el test?
    if ahora >= st.session_state.proxima_ejecucion:
        with st.spinner("Ejecutando prueba automática..."):
            run_test(sid)
            # Programar la siguiente
            st.session_state.proxima_ejecucion = ahora + (intervalo * 60)
            st.rerun() # Recarga para mostrar el nuevo punto en la gráfica
    else:
        # Si no es hora, calculamos cuánto falta y esperamos solo 1 segundo antes de recargar
        faltan = int(st.session_state.proxima_ejecucion - ahora)
        st.info(f"⏳ Próxima actualización en {faltan} segundos...")
        time.sleep(1) 
        st.rerun() # Esto mantiene la interfaz viva y la gráfica visible
