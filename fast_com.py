"""
Monitor de Velocidad de Red - Fast.com"""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
import time

# --- LIBRERÍAS PARA AUTOMATIZACIÓN ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException

# ──────────────────────────────────────────────
# CONFIGURACIÓN Y PERSISTENCIA
# ──────────────────────────────────────────────
CSV_PATH = "diagnostico_fast_completo.csv"

st.set_page_config(page_title="Monitor WAN Fast.com - IT Support", layout="wide")


def ejecutar_prueba_fast():
    """Ejecuta el test en Fast.com usando un navegador invisible."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    try:
        service = Service(ChromeDriverManager().install())
        # pylint: disable=not-callable      
        driver = webdriver.Chrome(service=service, options=chrome_options)
        # pylint: enable=not-callable
        driver.get("https://fast.com")

        # Esperar descarga inicial
        wait = WebDriverWait(driver, 60)
        wait.until(
    EC.presence_of_element_located(
        (By.CSS_SELECTOR, ".speed-results-container.succeeded")
    )
        )

        
        try:
            driver.find_element(By.ID, "show-more-details-link").click()
        except NoSuchElementException:
            pass

        # Esperar a que la sección de Carga (Upload) termine
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#upload-section.succeeded")))

        # Captura de datos
        datos = {
            "Fecha_Hora": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            "PC": os.environ.get("COMPUTERNAME", "Unknown"),
            "Descarga_Mbps": float(driver.find_element(By.ID, "speed-value").text),
            "Carga_Mbps": float(driver.find_element(By.ID, "upload-value").text),
            "Latencia_ms": float(driver.find_element(By.ID, "latency-value").text)
        }
        driver.quit()
        return datos
    except (WebDriverException, TimeoutException) as e:
        st.error(f"Error en la prueba: {e}")
        return None

def guardar_datos(row):
    """Guarda los datos en un archivo CSV."""
    # Asegurar que los valores numéricos mantengan sus decimales
    data_frame = pd.DataFrame([row])
    # Formatear columnas numéricas para mantener 2 decimales
    for col in ["Descarga_Mbps", "Carga_Mbps", "Latencia_ms"]:
        if col in data_frame.columns:
            data_frame[col] = data_frame[col].round(2)
    data_frame.to_csv(CSV_PATH, mode="a", header=not os.path.exists(CSV_PATH), index=False)

# ──────────────────────────────────────────────
# INTERFAZ (SIDEBAR)
# ──────────────────────────────────────────────
if "bucle" not in st.session_state:
    st.session_state.update({"bucle": False, "proxima": 0.0})

with st.sidebar:
    st.header("⚙️ Configuración")
    intervalo = st.slider("Intervalo de test (min):", 1, 60, 10)

    if st.button("▶️ Test Manual", use_container_width=True):
        with st.spinner("Midiendo red..."):
            res = ejecutar_prueba_fast()
            if res:
                guardar_datos(res)
                st.rerun()

    c1, c2 = st.columns(2)
    if c1.button("🚀 INICIAR", use_container_width=True):
        st.session_state.bucle = True
        st.session_state.proxima = time.time()
        st.rerun()
    if c2.button("⏹️ PARAR", use_container_width=True, type="primary"):
        st.session_state.bucle = False
        st.rerun()

# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────
st.title("📊 Monitor de Red Fast.com")

if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
    if not df.empty:
        ult = df.iloc[-1]
        m1, m2, m3 = st.columns(3)
        m1.metric("⬇️ Descarga", f"{ult['Descarga_Mbps']} Mbps")
        m2.metric("⬆️ Carga", f"{ult['Carga_Mbps']} Mbps")
        m3.metric("📡 Latencia", f"{ult['Latencia_ms']} ms")

        # Gráfico 1: Velocidades (Dos líneas)
        fig_v = px.line(df, x="Fecha_Hora", y=["Descarga_Mbps", "Carga_Mbps"],
                        title="Velocidades de Red (Mbps)", markers=True,
                        color_discrete_map={"Descarga_Mbps": "#00CC96", "Carga_Mbps": "#636EFA"})
        st.plotly_chart(fig_v, use_container_width=True)

        # Gráfico 2: Latencia
        fig_l = px.line(df, x="Fecha_Hora", y="Latencia_ms", title="Latencia / Ping (ms)",
                        markers=True)
        fig_l.update_traces(line_color="#EF553B")
        st.plotly_chart(fig_l, use_container_width=True)
else:
    st.info("Sin datos. Inicia el monitoreo.")

# Lógica automática
if st.session_state.bucle:
    ahora = time.time()
    if ahora >= st.session_state.proxima:
        res = ejecutar_prueba_fast()
        if res:
            guardar_datos(res)
        st.session_state.proxima = ahora + (intervalo * 60)
        st.rerun()
    else:
        st.info(f"⏳ Próximo test en {int(st.session_state.proxima - ahora)}s")
        time.sleep(5)
        st.rerun()
