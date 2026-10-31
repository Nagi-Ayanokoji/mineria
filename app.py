"""
app.py
======
Frontend interactivo para DataCleaner Studio.
Diseño moderno con paleta pastel, transiciones suaves y soporte completo
tanto para TEMA CLARO como TEMA OSCURO (sin texto invisible).
Menú superior por pestañas.

Arquitectura:
  - Presentación pura (Streamlit + CSS adaptativo).
  - Toda la lógica de negocio se delega a la capa 'services/'.
"""

import os
from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np

# Importación de servicios desacoplados
from services.data_loader import cargar_archivo, obtener_resumen_fuente
from services.quality_service import (
    perfilar_dataset,
    detectar_problemas,
    resumen_problemas,
    calcular_limites_iqr,
)
from services.cleaning_service import (
    eliminar_duplicados,
    imputar_faltantes,
    normalizar_textos,
    convertir_tipos,
    filtrar_o_recortar_outliers,
    exportar_csv,
    exportar_excel,
    tomar_snapshot,
)
from services.chart_service import (
    grafico_distribucion,
    grafico_barras_top,
    grafico_dispersion,
    grafico_caja_outliers,
    grafico_lineas_tiempo,
    grafico_pastel,
    grafico_correlacion,
    grafico_antes_despues,
    PALETTE,
)

# ---------------------------------------------------------------------------
# 1. Configuración de página y estilos pasteles adaptativos (Light & Dark)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="DataCleaner Studio",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ADAPTIVE_CSS = """
<style>
/* Tipografía moderna */
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

/* Variables CSS para modo claro por defecto */
:root {
    --bg-gradient: linear-gradient(135deg, #F8FAFC 0%, #EEF2F6 50%, #FAF5FF 100%);
    --card-bg: rgba(255, 255, 255, 0.9);
    --card-border: rgba(226, 232, 240, 0.95);
    --text-primary: #1E293B;
    --text-secondary: #64748B;
    --nav-bg: rgba(255, 255, 255, 0.92);
    --nav-border: rgba(226, 232, 240, 0.9);
    --tab-text: #64748B;
    --tab-hover: #4F46E5;
    --tab-active-bg: linear-gradient(135deg, #E0E7FF 0%, #EDE9FE 100%);
    --tab-active-text: #4338CA;
    --tab-active-border: #C7D2FE;
    --metric-bg: rgba(255, 255, 255, 0.92);
    --metric-border: #E2E8F0;
    --card-shadow: 0 8px 24px -6px rgba(148, 163, 184, 0.12);
    --timeline-bg: rgba(255, 255, 255, 0.85);
    --timeline-text: #334155;
    --btn-bg: #FFFFFF;
    --btn-text: #334155;
    --btn-border: #CBD5E1;
}

/* Variables cuando el sistema o Streamlit están en MODO OSCURO */
@media (prefers-color-scheme: dark) {
    :root {
        --bg-gradient: linear-gradient(135deg, #0B0F19 0%, #111827 50%, #1E1B4B 100%);
        --card-bg: rgba(17, 24, 39, 0.88);
        --card-border: rgba(55, 65, 81, 0.9);
        --text-primary: #F3F4F6;
        --text-secondary: #9CA3AF;
        --nav-bg: rgba(17, 24, 39, 0.92);
        --nav-border: rgba(55, 65, 81, 0.9);
        --tab-text: #9CA3AF;
        --tab-hover: #A5B4FC;
        --tab-active-bg: linear-gradient(135deg, #312E81 0%, #4C1D95 100%);
        --tab-active-text: #EEF2FF;
        --tab-active-border: #6366F1;
        --metric-bg: rgba(17, 24, 39, 0.9);
        --metric-border: #374151;
        --card-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.5);
        --timeline-bg: rgba(17, 24, 39, 0.85);
        --timeline-text: #E5E7EB;
        --btn-bg: #1F2937;
        --btn-text: #F3F4F6;
        --btn-border: #4B5563;
    }
}

/* Soporte explícito cuando Streamlit tiene tema dark */
[data-theme="dark"], .stApp[data-theme="dark"] {
    --bg-gradient: linear-gradient(135deg, #0B0F19 0%, #111827 50%, #1E1B4B 100%);
    --card-bg: rgba(17, 24, 39, 0.88);
    --card-border: rgba(55, 65, 81, 0.9);
    --text-primary: #F3F4F6;
    --text-secondary: #9CA3AF;
    --nav-bg: rgba(17, 24, 39, 0.92);
    --nav-border: rgba(55, 65, 81, 0.9);
    --tab-text: #9CA3AF;
    --tab-hover: #A5B4FC;
    --tab-active-bg: linear-gradient(135deg, #312E81 0%, #4C1D95 100%);
    --tab-active-text: #EEF2FF;
    --tab-active-border: #6366F1;
    --metric-bg: rgba(17, 24, 39, 0.9);
    --metric-border: #374151;
    --card-shadow: 0 8px 24px -6px rgba(0, 0, 0, 0.5);
    --timeline-bg: rgba(17, 24, 39, 0.85);
    --timeline-text: #E5E7EB;
    --btn-bg: #1F2937;
    --btn-text: #F3F4F6;
    --btn-border: #4B5563;
}

/* Aplicación del fondo adaptativo */
.stApp {
    background: var(--bg-gradient) !important;
    background-attachment: fixed !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* Transiciones suaves sin romper controles internos */
button, div[role="tab"], .stMetric, .pastel-card {
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Cabecera superior */
.top-header-banner {
    background: var(--card-bg);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid var(--card-border);
    border-radius: 20px;
    padding: 18px 26px;
    margin-bottom: 20px;
    box-shadow: var(--card-shadow);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.brand-title {
    font-size: 24px;
    font-weight: 700;
    background: linear-gradient(135deg, #818CF8 0%, #A78BFA 50%, #EC4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}

.brand-subtitle {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
    margin-bottom: 0;
}

/* Badges adaptables */
.badge-pastel {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.badge-mint { background: rgba(52, 211, 153, 0.18); color: #10B981; border: 1px solid rgba(52, 211, 153, 0.4); }
.badge-lavender { background: rgba(167, 139, 250, 0.18); color: #8B5CF6; border: 1px solid rgba(167, 139, 250, 0.4); }
.badge-peach { background: rgba(251, 146, 60, 0.18); color: #F97316; border: 1px solid rgba(251, 146, 60, 0.4); }

/* Menú de navegación superior (Tabs pasteles) */
div[data-baseweb="tab-list"] {
    background: var(--nav-bg) !important;
    backdrop-filter: blur(12px) !important;
    border-radius: 18px !important;
    padding: 8px 12px !important;
    border: 1px solid var(--nav-border) !important;
    box-shadow: var(--card-shadow) !important;
    display: flex !important;
    justify-content: space-between !important;
    gap: 8px !important;
    margin-bottom: 22px !important;
}

div[data-baseweb="tab"] {
    border-radius: 12px !important;
    padding: 10px 18px !important;
    color: var(--tab-text) !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    border: 1px solid transparent !important;
    background: transparent !important;
}

div[data-baseweb="tab"]:hover {
    color: var(--tab-hover) !important;
    background: rgba(129, 140, 248, 0.1) !important;
    transform: translateY(-1px);
}

div[data-baseweb="tab"][aria-selected="true"] {
    background: var(--tab-active-bg) !important;
    color: var(--tab-active-text) !important;
    border: 1px solid var(--tab-active-border) !important;
    box-shadow: 0 4px 14px -3px rgba(99, 102, 241, 0.3) !important;
}

div[data-baseweb="tab-highlight"] {
    display: none !important;
}

/* Tarjetas pastel adaptativas */
.pastel-card {
    background: var(--card-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid var(--card-border);
    border-radius: 18px;
    padding: 22px;
    margin-bottom: 20px;
    box-shadow: var(--card-shadow);
    color: var(--text-primary);
}

.pastel-card h3, .pastel-card h4, .pastel-card b {
    color: var(--text-primary) !important;
}

.pastel-card p, .pastel-card span, .pastel-card li {
    color: var(--text-secondary);
}

.pastel-card-mint { border-left: 5px solid #34D399; }
.pastel-card-lavender { border-left: 5px solid #A78BFA; }
.pastel-card-peach { border-left: 5px solid #FB923C; }
.pastel-card-sky { border-left: 5px solid #60A5FA; }

/* Métricas st.metric adaptables */
div[data-testid="stMetric"] {
    background: var(--metric-bg) !important;
    border: 1px solid var(--metric-border) !important;
    border-radius: 16px !important;
    padding: 14px 18px !important;
    box-shadow: var(--card-shadow) !important;
}

div[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
}

/* Timeline del historial */
.timeline-item {
    padding: 10px 16px;
    margin-bottom: 8px;
    border-radius: 12px;
    background: var(--timeline-bg);
    border-left: 4px solid #818CF8;
    font-size: 13.5px;
    color: var(--timeline-text);
    display: flex;
    align-items: center;
    gap: 10px;
    border: 1px solid var(--card-border);
}

/* Tablas estilizadas */
div[data-testid="stDataFrame"] {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid var(--card-border);
}
</style>
"""
st.markdown(ADAPTIVE_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 2. Inicialización del Estado de Sesión (Session State)
# ---------------------------------------------------------------------------
if "df_original" not in st.session_state:
    st.session_state.df_original = None

if "df_actual" not in st.session_state:
    st.session_state.df_actual = None

if "archivo_nombre" not in st.session_state:
    st.session_state.archivo_nombre = None

if "historial" not in st.session_state:
    st.session_state.historial = []

if "snapshot_metricas_inicio" not in st.session_state:
    st.session_state.snapshot_metricas_inicio = None


def registrar_historial(descripcion: str):
    """Agrega una entrada descriptiva al historial de operaciones."""
    st.session_state.historial.append(descripcion)


# ---------------------------------------------------------------------------
# 3. Cabecera Superior (Top Banner)
# ---------------------------------------------------------------------------
dataset_cargado = st.session_state.df_actual is not None
filas_actuales = len(st.session_state.df_actual) if dataset_cargado else 0
cols_actuales = st.session_state.df_actual.shape[1] if dataset_cargado else 0
n_cambios = len(st.session_state.historial)

badge_html = (
    f'<span class="badge-pastel badge-mint">✓ {st.session_state.archivo_nombre} ({filas_actuales:,} filas · {cols_actuales} cols)</span> '
    f'<span class="badge-pastel badge-lavender">{n_cambios} cambios</span>'
    if dataset_cargado
    else '<span class="badge-pastel badge-peach">Esperando carga de datos</span>'
)

st.markdown(
    f"""
    <div class="top-header-banner">
        <div>
            <h1 class="brand-title">✨ DataCleaner Studio</h1>
            <p class="brand-subtitle">Plataforma de Inspección, Limpieza Asistida y Exploración de Datos</p>
        </div>
        <div>
            {badge_html}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 4. Menú de Navegación Superior (Top Navigation Tabs)
# ---------------------------------------------------------------------------
tab_nombres = [
    "📂 1. Ingesta",
    "🔎 2. Diagnóstico",
    "⚠️ 3. Evidencia",
    "🧹 4. Limpieza",
    "🔄 5. Comparativa",
    "📊 6. Gráficos",
    "💾 7. Exportar",
]
tabs = st.tabs(tab_nombres)


# ===========================================================================
# TAB 1: CARGA & VISTA PREVIA
# ===========================================================================
with tabs[0]:
    st.markdown('<div class="pastel-card pastel-card-sky">', unsafe_allow_html=True)
    st.markdown("### 📂 Ingesta y Carga de Datos")
    st.caption("Carga un archivo CSV o Excel para comenzar el diagnóstico de calidad.")

    col_up1, col_up2 = st.columns([2.5, 1])

    with col_up1:
        archivo_subido = st.file_uploader(
            "Selecciona o arrastra tu archivo (CSV, TSV, XLSX):",
            type=["csv", "tsv", "txt", "xlsx", "xls"],
            help="Soporta autodetección de separador y codificaciones UTF-8, Latin-1, etc.",
        )

    with col_up2:
        st.markdown("**Opciones rápidas:**")
        dataset_ejemplo = Path("top_15000_anime.csv")
        if dataset_ejemplo.exists():
            if st.button("🚀 Cargar Dataset Ejemplo (Anime)", use_container_width=True):
                with st.spinner("Cargando dataset de ejemplo..."):
                    df_ej = cargar_archivo(str(dataset_ejemplo))
                    st.session_state.df_original = df_ej.copy()
                    st.session_state.df_actual = df_ej.copy()
                    st.session_state.archivo_nombre = "top_15000_anime.csv"
                    st.session_state.historial = ["Dataset 'top_15000_anime.csv' cargado"]
                    
                    p_init = perfilar_dataset(df_ej)
                    st.session_state.snapshot_metricas_inicio = {
                        "Faltantes": p_init["total_faltantes"],
                        "Duplicados": p_init["duplicados_exactos"],
                        "Filas": p_init["filas"],
                    }
                    st.rerun()

    # Procesar archivo subido por el usuario
    if archivo_subido is not None and (
        st.session_state.archivo_nombre != archivo_subido.name
    ):
        with st.spinner("Leyendo y validando estructura del archivo..."):
            try:
                df_cargado = cargar_archivo(archivo_subido)
                st.session_state.df_original = df_cargado.copy()
                st.session_state.df_actual = df_cargado.copy()
                st.session_state.archivo_nombre = archivo_subido.name
                st.session_state.historial = [f"Archivo '{archivo_subido.name}' cargado"]
                
                p_init = perfilar_dataset(df_cargado)
                st.session_state.snapshot_metricas_inicio = {
                    "Faltantes": p_init["total_faltantes"],
                    "Duplicados": p_init["duplicados_exactos"],
                    "Filas": p_init["filas"],
                }
                st.success(f"Archivo '{archivo_subido.name}' cargado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")

    st.markdown("</div>", unsafe_allow_html=True)

    # Vista previa si hay datos cargados
    if st.session_state.df_actual is not None:
        df_ver = st.session_state.df_actual
        resumen = obtener_resumen_fuente(df_ver)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Filas", f"{resumen['filas']:,}")
        c2.metric("Total Columnas", f"{resumen['columnas']}")
        c3.metric("Uso en Memoria", f"{resumen['memoria_mb']:.2f} MB")
        c4.metric("Estado", "Listo para Auditoría")

        st.markdown("#### Vista Previa del Dataset")
        vista_opc = st.radio(
            "Mostrar registros:",
            ["Primeras 10 filas", "Últimas 10 filas", "Muestra aleatoria (10 filas)"],
            horizontal=True,
        )

        if vista_opc == "Primeras 10 filas":
            st.dataframe(df_ver.head(10), use_container_width=True)
        elif vista_opc == "Últimas 10 filas":
            st.dataframe(df_ver.tail(10), use_container_width=True)
        else:
            st.dataframe(df_ver.sample(min(10, len(df_ver))), use_container_width=True)
    else:
        st.info("👆 Carga un archivo o usa el botón de ejemplo para desbloquear las demás fases.")


# ===========================================================================
# TAB 2: DIAGNÓSTICO & PERFIL
# ===========================================================================
with tabs[1]:
    if st.session_state.df_actual is None:
        st.info("📂 Por favor carga un dataset en la pestaña 1 para ver el diagnóstico.")
    else:
        df_diag = st.session_state.df_actual
        perfil = perfilar_dataset(df_diag)

        st.markdown('<div class="pastel-card pastel-card-lavender">', unsafe_allow_html=True)
        st.markdown("### 🔎 Diagnóstico General de Salud del Dataset")
        st.caption("Visión panorámica de dimensiones, completitud, tipos de datos y duplicados.")

        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        col_m1.metric("Total Filas", f"{perfil['filas']:,}")
        col_m2.metric("Total Columnas", f"{perfil['columnas']}")
        
        pct_falt = perfil['pct_faltantes_global']
        col_m3.metric(
            "Celdas Vacías",
            f"{perfil['total_faltantes']:,}",
            f"{pct_falt:.1f}% del total",
            delta_color="inverse",
        )
        col_m4.metric(
            "Filas Duplicadas",
            f"{perfil['duplicados_exactos']:,}",
            delta_color="inverse" if perfil['duplicados_exactos'] > 0 else "normal",
        )
        col_m5.metric("Memoria RAM", f"{perfil['memoria_mb']:.2f} MB")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("#### Detalle Estructural por Columna")
        df_cols_info = pd.DataFrame({
            "Columna": perfil["nombres_cols"],
            "Tipo de Dato": [perfil["tipos"][c] for c in perfil["nombres_cols"]],
            "Valores Faltantes": [perfil["faltantes_por_col"][c] for c in perfil["nombres_cols"]],
            "% Faltante": [f"{perfil['faltantes_pct'][c]:.1f}%" for c in perfil["nombres_cols"]],
            "Valores Únicos": [df_diag[c].nunique(dropna=True) for c in perfil["nombres_cols"]],
        })

        st.dataframe(df_cols_info, use_container_width=True, hide_index=True)

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown(
                f"""
                <div class="pastel-card pastel-card-mint">
                    <b>Clasificación de Columnas:</b>
                    <ul>
                        <li><b>Numéricas ({len(perfil['cols_numericas'])}):</b> {', '.join(perfil['cols_numericas'][:8])}{'...' if len(perfil['cols_numericas']) > 8 else ''}</li>
                        <li><b>Texto / Categóricas ({len(perfil['cols_categoricas'])}):</b> {', '.join(perfil['cols_categoricas'][:8])}{'...' if len(perfil['cols_categoricas']) > 8 else ''}</li>
                        <li><b>Fechas ({len(perfil['cols_fecha'])}):</b> {', '.join(perfil['cols_fecha']) if perfil['cols_fecha'] else 'Ninguna detectada'}</li>
                    </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_t2:
            if perfil["cols_numericas"]:
                st.markdown("##### Resumen Estadístico Rápido (Numéricas)")
                st.dataframe(df_diag[perfil["cols_numericas"]].describe().T[["mean", "std", "min", "50%", "max"]], use_container_width=True)


# ===========================================================================
# TAB 3: AUDITORÍA & EVIDENCIA
# ===========================================================================
with tabs[2]:
    if st.session_state.df_actual is None:
        st.info("📂 Por favor carga un dataset en la pestaña 1.")
    else:
        df_ev = st.session_state.df_actual
        st.markdown('<div class="pastel-card pastel-card-peach">', unsafe_allow_html=True)
        st.markdown("### ⚠️ Auditoría y Evidencia de Problemas")
        st.caption("Principio: Un problema → Una evidencia. Inspecciona los registros afectados antes de corregir.")

        col_cfg1, col_cfg2 = st.columns([1, 2])
        with col_cfg1:
            metodo_out = st.selectbox("Método de detección de outliers:", ["IQR (Rango Intercuartílico)", "Z-Score (Desviaciones)"])
            factor_iqr = 1.5
            umbral_z = 3.0
            if "IQR" in metodo_out:
                factor_iqr = st.slider("Multiplicador IQR:", 1.0, 3.0, 1.5, 0.1)
            else:
                umbral_z = st.slider("Umbral Z-Score:", 2.0, 4.0, 3.0, 0.2)

        with col_cfg2:
            st.info("💡 Cada problema detectado te permite abrir una sub-tabla con los registros exactos que presentan la anomalía.")

        st.markdown("</div>", unsafe_allow_html=True)

        with st.spinner("Analizando anomalías y recopilando evidencias..."):
            problemas_dict = detectar_problemas(
                df_ev,
                metodo_outlier="iqr" if "IQR" in metodo_out else "zscore",
                factor_iqr=factor_iqr,
                umbral_zscore=umbral_z,
            )
            resumen_tab = resumen_problemas(problemas_dict)

        if not resumen_tab:
            st.success("🎉 ¡Excelente! No se detectaron problemas evidentes ni valores corruptos en el dataset.")
        else:
            st.markdown(f"#### Se detectaron **{len(resumen_tab)}** tipos de incidencias:")

            for item in resumen_tab:
                clave = item["tipo"]
                sub_df = problemas_dict[clave]
                
                with st.expander(f"⚠️ {item['descripcion']} — ({item['cantidad']:,} registros afectados)"):
                    st.caption(f"Clave interna: `{clave}` | Filas afectadas: {len(sub_df):,}")
                    st.dataframe(sub_df.head(50), use_container_width=True)
                    if len(sub_df) > 50:
                        st.info(f"Mostrando 50 de {len(sub_df):,} registros. Pasa a la pestaña 'Limpieza' para tratarlos.")


# ===========================================================================
# TAB 4: LIMPIEZA ASISTIDA
# ===========================================================================
with tabs[3]:
    if st.session_state.df_actual is None:
        st.info("📂 Carga un dataset en la pestaña 1.")
    else:
        df_limpiar = st.session_state.df_actual

        st.markdown('<div class="pastel-card pastel-card-mint">', unsafe_allow_html=True)
        st.markdown("### 🧹 Taller de Limpieza Asistida y Controlada")
        st.caption("Ninguna modificación se aplica a ciegas. Cada panel cuenta con botón de confirmación explícita.")

        col_top_a, col_top_b = st.columns([3, 1])
        with col_top_b:
            if st.button("↺ Restaurar Dataset Original", use_container_width=True):
                st.session_state.df_actual = st.session_state.df_original.copy()
                st.session_state.historial.append("↺ Dataset restaurado al estado original")
                st.success("Dataset reiniciado al estado inicial.")
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        p1, p2, p3, p4 = st.tabs([
            "1. Duplicados",
            "2. Valores Faltantes",
            "3. Normalización Texto",
            "4. Outliers Estadísticos",
        ])

        # --- PANEL 1: DUPLICADOS ---
        with p1:
            st.markdown("#### Deduplicación")
            n_dups = int(df_limpiar.duplicated().sum())
            st.write(f"Duplicados exactos actuales: **{n_dups}**")

            col_dup1, col_dup2 = st.columns(2)
            with col_dup1:
                cols_sub = st.multiselect(
                    "Columnas clave para considerar duplicado (deja vacío para fila exacta):",
                    options=df_limpiar.columns.tolist(),
                    default=[],
                )
            with col_dup2:
                keep_opc = st.selectbox(
                    "¿Qué ocurrencia conservar?",
                    options=["first (primera)", "last (última)", "False (eliminar todas)"],
                )
                keep_val = "first" if "first" in keep_opc else ("last" if "last" in keep_opc else False)

            if st.button("✨ Aplicar Deduplicación", key="btn_dup", type="primary"):
                df_nuevo, meta = eliminar_duplicados(
                    df_limpiar,
                    subset=cols_sub if cols_sub else None,
                    keep=keep_val,
                )
                st.session_state.df_actual = df_nuevo
                registrar_historial(f"Eliminadas {meta['eliminadas']:,} filas duplicadas ({keep_opc})")
                st.success(f"✓ Operación completada: {meta['eliminadas']} filas eliminadas.")
                st.rerun()

        # --- PANEL 2: FALTANTES ---
        with p2:
            st.markdown("#### Imputación y Tratamiento de Nulos")
            cols_con_nulos = [c for c in df_limpiar.columns if df_limpiar[c].isnull().any()]

            if not cols_con_nulos:
                st.success("✓ No quedan columnas con valores faltantes en el dataset.")
            else:
                col_nulo1, col_nulo2 = st.columns(2)
                with col_nulo1:
                    col_sel = st.selectbox("Selecciona columna a tratar:", cols_con_nulos)
                    n_nulos_col = int(df_limpiar[col_sel].isnull().sum())
                    pct_col = (n_nulos_col / len(df_limpiar)) * 100
                    st.info(f"Columna: **{col_sel}** | Nulos: **{n_nulos_col:,}** ({pct_col:.1f}%) | Tipo: `{df_limpiar[col_sel].dtype}`")

                with col_nulo2:
                    es_num = pd.api.types.is_numeric_dtype(df_limpiar[col_sel])
                    opciones_strat = ["eliminar (descartar filas)", "moda (valor más frecuente)", "valor_fijo"]
                    if es_num:
                        opciones_strat = ["mediana", "media"] + opciones_strat

                    estrat = st.selectbox("Estrategia de imputación:", opciones_strat)
                    clave_estrat = estrat.split(" ")[0]

                    val_fijo = None
                    if clave_estrat == "valor_fijo":
                        val_fijo = st.text_input("Valor fijo personalizado:", value="Desconocido")

                if st.button("✨ Aplicar Imputación", key="btn_imputar", type="primary"):
                    try:
                        df_nuevo, meta = imputar_faltantes(
                            df_limpiar,
                            columna=col_sel,
                            estrategia=clave_estrat,
                            valor_personalizado=val_fijo,
                        )
                        st.session_state.df_actual = df_nuevo
                        registrar_historial(
                            f"Tratados {meta['resueltos']} nulos en '{col_sel}' con estrategia '{clave_estrat}'"
                        )
                        st.success(f"✓ Resueltos {meta['resueltos']} valores faltantes en '{col_sel}'.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Error al imputar: {exc}")

        # --- PANEL 3: TEXTOS ---
        with p3:
            st.markdown("#### Normalización y Limpieza de Cadenas de Texto")
            cols_str = df_limpiar.select_dtypes(include=["object", "string"]).columns.tolist()

            if not cols_str:
                st.info("No se encontraron columnas de texto en el dataset.")
            else:
                cols_norm_sel = st.multiselect("Columnas de texto a normalizar:", cols_str, default=cols_str[:3])
                
                col_opt1, col_opt2, col_opt3 = st.columns(3)
                with col_opt1:
                    chk_espacios = st.checkbox("Quitar espacios sobrantes (strip)", value=True)
                with col_opt2:
                    chk_min = st.checkbox("Convertir a minúsculas", value=True)
                with col_opt3:
                    chk_tildes = st.checkbox("Remover acentos/tildes", value=False)

                if st.button("✨ Normalizar Textos", key="btn_texto", type="primary"):
                    if not cols_norm_sel:
                        st.warning("Selecciona al menos una columna.")
                    else:
                        df_nuevo, meta = normalizar_textos(
                            df_limpiar,
                            columnas=cols_norm_sel,
                            minusculas=chk_min,
                            quitar_espacios=chk_espacios,
                            quitar_tildes=chk_tildes,
                        )
                        st.session_state.df_actual = df_nuevo
                        registrar_historial(
                            f"Normalizadas {len(cols_norm_sel)} columnas ({meta['celdas_modificadas']} celdas modificadas)"
                        )
                        st.success(f"✓ Normalización completada en: {', '.join(cols_norm_sel)}.")
                        st.rerun()

        # --- PANEL 4: OUTLIERS ---
        with p4:
            st.markdown("#### Tratamiento de Outliers Numéricos")
            cols_num = df_limpiar.select_dtypes(include="number").columns.tolist()

            if not cols_num:
                st.info("No hay columnas numéricas para analizar.")
            else:
                col_o1, col_o2 = st.columns(2)
                with col_o1:
                    col_out_sel = st.selectbox("Columna numérica:", cols_num)
                    limites = calcular_limites_iqr(df_limpiar, col_out_sel)
                    st.caption(
                        f"Q1: {limites['q1']:.2f} | Q3: {limites['q3']:.2f} | IQR: {limites['iqr']:.2f}  \n"
                        f"Límite Inf: **{limites['lim_inf']:.2f}** | Límite Sup: **{limites['lim_sup']:.2f}**"
                    )

                with col_o2:
                    accion_out = st.selectbox(
                        "Acción a tomar con los outliers:",
                        ["filtrar (eliminar filas)", "recortar (clamp/winsorizar)", "marcar (nueva columna flag)"],
                    )
                    clave_acc = accion_out.split(" ")[0]

                if st.button("✨ Aplicar Tratamiento de Outliers", key="btn_outlier", type="primary"):
                    try:
                        df_nuevo, meta = filtrar_o_recortar_outliers(
                            df_limpiar,
                            columna=col_out_sel,
                            lim_inf=limites["lim_inf"],
                            lim_sup=limites["lim_sup"],
                            accion=clave_acc,
                        )
                        st.session_state.df_actual = df_nuevo
                        registrar_historial(meta["descripcion"])
                        st.success(f"✓ {meta['descripcion']}.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Error: {exc}")


# ===========================================================================
# TAB 5: COMPARATIVA (ANTES VS DESPUÉS)
# ===========================================================================
with tabs[4]:
    if st.session_state.df_actual is None:
        st.info("📂 Carga un dataset en la pestaña 1.")
    else:
        st.markdown('<div class="pastel-card pastel-card-lavender">', unsafe_allow_html=True)
        st.markdown("### 🔄 Comparativa de Calidad: Antes vs. Después")
        st.caption("Verifica el impacto real de las transformaciones aplicadas.")

        p_actual = perfilar_dataset(st.session_state.df_actual)
        init_m = st.session_state.snapshot_metricas_inicio or {
            "Faltantes": p_actual["total_faltantes"],
            "Duplicados": p_actual["duplicados_exactos"],
            "Filas": p_actual["filas"],
        }

        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        delta_filas = p_actual["filas"] - init_m["Filas"]
        delta_falt = p_actual["total_faltantes"] - init_m["Faltantes"]
        delta_dup = p_actual["duplicados_exactos"] - init_m["Duplicados"]

        col_c1.metric("Filas Resultantes", f"{p_actual['filas']:,}", f"{delta_filas:+d} filas")
        col_c2.metric("Faltantes Pendientes", f"{p_actual['total_faltantes']:,}", f"{delta_falt:+d}", delta_color="inverse")
        col_c3.metric("Duplicados Pendientes", f"{p_actual['duplicados_exactos']:,}", f"{delta_dup:+d}", delta_color="inverse")
        col_c4.metric("Operaciones Realizadas", f"{len(st.session_state.historial)}")

        st.markdown("</div>", unsafe_allow_html=True)

        col_g1, col_g2 = st.columns([1.5, 1])
        with col_g1:
            dict_antes = {"Faltantes": init_m["Faltantes"], "Duplicados": init_m["Duplicados"]}
            dict_despues = {"Faltantes": p_actual["total_faltantes"], "Duplicados": p_actual["duplicados_exactos"]}
            fig_comp = grafico_antes_despues(dict_antes, dict_despues)
            st.plotly_chart(fig_comp, use_container_width=True)

        with col_g2:
            st.markdown("#### Historial de Transformaciones")
            if not st.session_state.historial:
                st.caption("Aún no has aplicado ninguna transformación.")
            else:
                for idx, paso in enumerate(st.session_state.historial, 1):
                    st.markdown(
                        f"""
                        <div class="timeline-item">
                            <span><b>#{idx}</b></span>
                            <span>{paso}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )


# ===========================================================================
# TAB 6: GRÁFICOS (VISUALIZACIÓN EDA)
# ===========================================================================
with tabs[5]:
    if st.session_state.df_actual is None:
        st.info("📂 Carga un dataset en la pestaña 1.")
    else:
        df_plot = st.session_state.df_actual
        st.markdown('<div class="pastel-card pastel-card-mint">', unsafe_allow_html=True)
        st.markdown("### 📊 Exploración Visual Interactiva (EDA)")
        st.caption("Visualiza patrones, distribuciones y rankings sin bloqueos.")

        tipo_grafico = st.selectbox(
            "Selecciona el tipo de gráfico:",
            [
                "1. Histograma / Distribución",
                "2. Barras (Top Categorías)",
                "3. Dispersión (Scatter)",
                "4. Boxplot (Outliers)",
                "5. Matriz de Correlación",
            ],
        )
        st.markdown("</div>", unsafe_allow_html=True)

        cols_numericas = df_plot.select_dtypes(include="number").columns.tolist()
        cols_categoricas = df_plot.select_dtypes(include=["object", "category", "string"]).columns.tolist()
        # Filtrar columnas categóricas con cardinalidad manejable para agrupaciones visuales
        cols_cat_utiles = [c for c in cols_categoricas if df_plot[c].nunique() <= 40]

        try:
            if "Histograma" in tipo_grafico:
                if not cols_numericas:
                    st.warning("No hay columnas numéricas disponibles en este dataset.")
                else:
                    c_col, c_bins = st.columns([2, 1])
                    with c_col:
                        col_h = st.selectbox("Columna numérica:", cols_numericas)
                    with c_bins:
                        nbins = st.slider("Número de Bins:", 10, 80, 30)
                    
                    fig = grafico_distribucion(df_plot, col_h, nbins=nbins)
                    st.plotly_chart(fig, use_container_width=True)

            elif "Barras" in tipo_grafico:
                if not cols_categoricas or not cols_numericas:
                    st.warning("Se requiere al menos una columna categórica y una numérica.")
                else:
                    c_cat, c_num, c_agg, c_top = st.columns([1.5, 1.5, 1, 1])
                    with c_cat:
                        col_c = st.selectbox("Columna categórica:", cols_categoricas)
                    with c_num:
                        col_n = st.selectbox("Métrica numérica:", cols_numericas)
                    with c_agg:
                        agg_opc = st.selectbox("Agregación:", ["sum", "mean", "count", "max", "min"])
                    with c_top:
                        top_n = st.slider("Top N:", 5, 25, 10)
                    
                    fig = grafico_barras_top(df_plot, col_c, col_n, top_n=top_n, agregacion=agg_opc)
                    st.plotly_chart(fig, use_container_width=True)

            elif "Dispersión" in tipo_grafico:
                if len(cols_numericas) < 2:
                    st.warning("Se requieren al menos 2 columnas numéricas para un diagrama de dispersión.")
                else:
                    cx, cy, ccolor = st.columns(3)
                    with cx:
                        col_x = st.selectbox("Eje X (Numérico):", cols_numericas, index=0)
                    with cy:
                        idx_y = 1 if len(cols_numericas) > 1 else 0
                        col_y = st.selectbox("Eje Y (Numérico):", cols_numericas, index=idx_y)
                    with ccolor:
                        col_col = st.selectbox(
                            "Color por categoría (opcional):",
                            [None] + (cols_cat_utiles if cols_cat_utiles else cols_categoricas[:5]),
                        )
                    
                    fig = grafico_dispersion(df_plot, col_x, col_y, col_color=col_col)
                    st.plotly_chart(fig, use_container_width=True)

            elif "Boxplot" in tipo_grafico:
                if not cols_numericas:
                    st.warning("No hay columnas numéricas.")
                else:
                    cb_num, cb_cat = st.columns(2)
                    with cb_num:
                        col_b_num = st.selectbox("Variable numérica:", cols_numericas)
                    with cb_cat:
                        col_b_cat = st.selectbox(
                            "Agrupar por categoría (opcional):",
                            [None] + (cols_cat_utiles if cols_cat_utiles else cols_categoricas[:5]),
                        )
                    
                    fig = grafico_caja_outliers(df_plot, col_b_num, col_b_cat)
                    st.plotly_chart(fig, use_container_width=True)

            elif "Correlación" in tipo_grafico:
                if len(cols_numericas) < 2:
                    st.warning("Se requieren al menos 2 variables numéricas.")
                else:
                    cols_corr_sel = st.multiselect(
                        "Selecciona variables numéricas para el heatmap:",
                        cols_numericas,
                        default=cols_numericas[:8],
                    )
                    if len(cols_corr_sel) >= 2:
                        fig = grafico_correlacion(df_plot, columnas=cols_corr_sel)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Selecciona al menos 2 variables numéricas.")
        except Exception as exc:
            st.error(f"Error al generar gráfico: {exc}")


# ===========================================================================
# TAB 7: EXPORTAR DATASET LIMPIO
# ===========================================================================
with tabs[6]:
    if st.session_state.df_actual is None:
        st.info("📂 Carga un dataset en la pestaña 1.")
    else:
        df_export = st.session_state.df_actual
        p_final = perfilar_dataset(df_export)

        st.markdown('<div class="pastel-card pastel-card-mint">', unsafe_allow_html=True)
        st.markdown("### 💾 Exportación del Dataset Limpio")
        st.caption("Descarga tu dataset completamente transformado y listo para modelos o analítica.")

        col_e1, col_e2, col_e3 = st.columns(3)
        col_e1.metric("Filas Finales", f"{p_final['filas']:,}")
        col_e2.metric("Columnas Preservadas", f"{p_final['columnas']}")
        col_e3.metric("Faltantes Remanentes", f"{p_final['total_faltantes']:,}")

        st.markdown("---")

        col_btn1, col_btn2 = st.columns(2)
        nombre_base = Path(st.session_state.archivo_nombre or "dataset").stem
        nombre_salida = f"{nombre_base}_limpio.csv"

        with col_btn1:
            csv_bytes = exportar_csv(df_export)
            st.download_button(
                label="📥 Descargar como CSV (.csv con UTF-8 BOM)",
                data=csv_bytes,
                file_name=nombre_salida,
                mime="text/csv",
                type="primary",
                use_container_width=True,
            )

        with col_btn2:
            try:
                excel_bytes = exportar_excel(df_export)
                st.download_button(
                    label="📊 Descargar como Excel (.xlsx)",
                    data=excel_bytes,
                    file_name=f"{nombre_base}_limpio.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            except Exception as exc:
                st.caption(f"Descarga Excel no disponible: {exc}")

        st.markdown("</div>", unsafe_allow_html=True)
