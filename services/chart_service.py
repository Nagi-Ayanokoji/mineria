"""
services/chart_service.py
==========================
Módulo de visualización interactiva con Plotly Express.

Responsabilidad única:
  - Recibir DataFrames ya procesados y retornar objetos plotly.graph_objects.Figure.
  - Toda la preparación/agregación de datos ocurre aquí, NO en app.py.
  - app.py únicamente llama a las funciones y pasa la Figure a st.plotly_chart().

Paleta visual: colores pasteles coordinados con el diseño del frontend.
NO depende de Streamlit.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Paleta de colores pasteles — coordinada con el frontend
# ---------------------------------------------------------------------------
PALETTE = [
    "#B5C8E8",  # azul lavanda suave
    "#A8D8C8",  # menta/sage
    "#F2C9B0",  # durazno/peach
    "#D5B8E0",  # lavanda
    "#F9E4A0",  # amarillo mantequilla
    "#F4A8B5",  # rosa blush
    "#A8C8E8",  # azul cielo
    "#C8E8A8",  # verde manzana pastel
    "#E8C8A8",  # naranja crema
    "#B8E8E0",  # turquesa pastel
]

LAYOUT_BASE = dict(
    paper_bgcolor="rgba(255,255,255,0)",
    plot_bgcolor="rgba(255,255,255,0.6)",
    font=dict(family="Inter, Segoe UI, sans-serif", size=13, color="#4A4A6A"),
    margin=dict(l=40, r=40, t=60, b=40),
    hoverlabel=dict(bgcolor="white", font_size=13, font_family="Inter"),
)


def _aplicar_layout(fig: go.Figure, titulo: str = "", **kwargs) -> go.Figure:
    """Aplica el layout base y el título a cualquier figura."""
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=16, color="#4A4A6A"), x=0.02),
        **LAYOUT_BASE,
        **kwargs,
    )
    return fig


# ---------------------------------------------------------------------------
# 1. Distribución de variable numérica (Histograma + curva KDE)
# ---------------------------------------------------------------------------

def grafico_distribucion(
    df: pd.DataFrame,
    columna: str,
    nbins: int = 30,
    mostrar_kde: bool = True,
) -> go.Figure:
    """
    Histograma de la distribución de una variable numérica.
    Opcionalmente superpone una curva de densidad KDE.

    Parámetros
    ----------
    df        - DataFrame fuente.
    columna   - Columna numérica a graficar.
    nbins     - Número de bins del histograma.
    mostrar_kde - Si True, agrega una curva de densidad suavizada.
    """
    if columna not in df.columns:
        raise KeyError(f"Columna '{columna}' no encontrada.")

    serie = df[columna].dropna()

    fig = px.histogram(
        df,
        x=columna,
        nbins=nbins,
        color_discrete_sequence=[PALETTE[0]],
        opacity=0.8,
        histnorm="density" if mostrar_kde else "",
        marginal="box" if mostrar_kde else None,
        labels={columna: columna},
    )

    if mostrar_kde:
        # Curva KDE usando scipy
        try:
            from scipy.stats import gaussian_kde
            kde = gaussian_kde(serie)
            x_range = np.linspace(serie.min(), serie.max(), 300)
            fig.add_trace(
                go.Scatter(
                    x=x_range,
                    y=kde(x_range),
                    mode="lines",
                    name="Densidad KDE",
                    line=dict(color=PALETTE[4], width=2.5, dash="solid"),
                )
            )
        except ImportError:
            pass  # scipy no disponible, se muestra solo el histograma

    fig = _aplicar_layout(fig, titulo=f"Distribución de {columna}")
    fig.update_traces(marker_line_color="white", marker_line_width=0.5)
    return fig


# ---------------------------------------------------------------------------
# 2. Barras — Top N categorías por métrica numérica
# ---------------------------------------------------------------------------

def grafico_barras_top(
    df: pd.DataFrame,
    columna_cat: str,
    columna_num: str,
    top_n: int = 10,
    agregacion: Literal["sum", "mean", "count", "max", "min"] = "sum",
    orientacion: Literal["h", "v"] = "h",
) -> go.Figure:
    """
    Gráfico de barras con el Top N de categorías según una métrica numérica.

    Parámetros
    ----------
    df            - DataFrame fuente.
    columna_cat   - Columna categórica (eje de agrupación).
    columna_num   - Columna numérica (métrica).
    top_n         - Cantidad de categorías a mostrar.
    agregacion    - Función de agregación: 'sum', 'mean', 'count', 'max', 'min'.
    orientacion   - 'h' para horizontal (recomendado), 'v' para vertical.
    """
    if columna_cat not in df.columns or columna_num not in df.columns:
        raise KeyError(f"Columna '{columna_cat}' o '{columna_num}' no encontrada.")

    agrup = df.groupby(columna_cat, observed=True)[columna_num]
    agg_map = {
        "sum": agrup.sum,
        "mean": agrup.mean,
        "count": agrup.count,
        "max": agrup.max,
        "min": agrup.min,
    }
    serie_agg = agg_map[agregacion]().sort_values(ascending=False).head(top_n)
    df_plot = pd.DataFrame({columna_cat: serie_agg.index, columna_num: serie_agg.values})

    if orientacion == "h":
        df_plot = df_plot.sort_values(columna_num, ascending=True)
        fig = px.bar(
            df_plot,
            x=columna_num,
            y=columna_cat,
            orientation="h",
            color=columna_num,
            color_continuous_scale=[PALETTE[1], PALETTE[0], PALETTE[3]],
        )
    else:
        fig = px.bar(
            df_plot,
            x=columna_cat,
            y=columna_num,
            color=columna_num,
            color_continuous_scale=[PALETTE[1], PALETTE[0], PALETTE[3]],
        )

    fig.update_coloraxes(showscale=False)
    fig = _aplicar_layout(
        fig,
        titulo=f"Top {top_n} — {columna_cat} por {agregacion}({columna_num})",
    )
    return fig


# ---------------------------------------------------------------------------
# 3. Dispersión (Scatter Plot)
# ---------------------------------------------------------------------------

def grafico_dispersion(
    df: pd.DataFrame,
    col_x: str,
    col_y: str,
    col_color: str | None = None,
    col_size: str | None = None,
    opacidad: float = 0.65,
) -> go.Figure:
    """
    Scatterplot interactivo para analizar la relación entre dos variables numéricas.

    Parámetros
    ----------
    df        - DataFrame fuente.
    col_x     - Columna para el eje X.
    col_y     - Columna para el eje Y.
    col_color - Columna opcional para colorear puntos por categoría.
    col_size  - Columna numérica opcional para el tamaño de los puntos.
    opacidad  - Opacidad de los puntos (0 a 1).
    """
    for col in [col_x, col_y]:
        if col not in df.columns:
            raise KeyError(f"Columna '{col}' no encontrada.")

    fig = px.scatter(
        df,
        x=col_x,
        y=col_y,
        color=col_color,
        size=col_size,
        opacity=opacidad,
        color_discrete_sequence=PALETTE,
        trendline="ols" if col_color is None else None,
        labels={col_x: col_x, col_y: col_y},
    )
    fig = _aplicar_layout(fig, titulo=f"Dispersión: {col_x} vs {col_y}")
    fig.update_traces(marker=dict(line=dict(width=0.5, color="white")))
    return fig


# ---------------------------------------------------------------------------
# 4. Boxplot — Dispersión y detección visual de outliers
# ---------------------------------------------------------------------------

def grafico_caja_outliers(
    df: pd.DataFrame,
    columna_num: str,
    columna_cat: str | None = None,
    mostrar_puntos: bool = True,
) -> go.Figure:
    """
    Boxplot interactivo. Si se provee una columna categórica, crea un boxplot
    por cada categoría para comparar distribuciones.

    Parámetros
    ----------
    df           - DataFrame fuente.
    columna_num  - Variable numérica a analizar.
    columna_cat  - Agrupación categórica opcional.
    mostrar_puntos - Si True, superpone los puntos individuales (strip).
    """
    if columna_num not in df.columns:
        raise KeyError(f"Columna '{columna_num}' no encontrada.")

    puntos = "all" if mostrar_puntos else False

    fig = px.box(
        df,
        x=columna_cat,
        y=columna_num,
        color=columna_cat,
        points=puntos,
        color_discrete_sequence=PALETTE,
        notched=False,
        labels={columna_num: columna_num, columna_cat: columna_cat or ""},
    )

    fig = _aplicar_layout(
        fig,
        titulo=f"Boxplot de {columna_num}"
        + (f" por {columna_cat}" if columna_cat else ""),
        showlegend=bool(columna_cat),
    )
    return fig


# ---------------------------------------------------------------------------
# 5. Líneas de tiempo — Tendencia cronológica
# ---------------------------------------------------------------------------

def grafico_lineas_tiempo(
    df: pd.DataFrame,
    col_fecha: str,
    col_num: str,
    frecuencia: Literal["D", "W", "ME", "QE", "YE"] = "ME",
    agregacion: Literal["sum", "mean", "count"] = "sum",
) -> go.Figure:
    """
    Gráfico de líneas que muestra la tendencia de una variable numérica a lo largo
    del tiempo, agregada a la frecuencia especificada.

    Parámetros
    ----------
    df         - DataFrame fuente.
    col_fecha  - Columna de fecha (debe ser convertible a datetime).
    col_num    - Variable numérica a agregar.
    frecuencia - Frecuencia de resampleo: 'D' (diario), 'W' (semanal),
                 'ME' (mensual), 'QE' (trimestral), 'YE' (anual).
    agregacion - Función de agregación.
    """
    if col_fecha not in df.columns or col_num not in df.columns:
        raise KeyError(f"Columna '{col_fecha}' o '{col_num}' no encontrada.")

    df_t = df[[col_fecha, col_num]].copy()
    df_t[col_fecha] = pd.to_datetime(df_t[col_fecha], errors="coerce")
    df_t = df_t.dropna(subset=[col_fecha])
    df_t = df_t.set_index(col_fecha)

    resample = df_t[col_num].resample(frecuencia)
    agg_map = {"sum": resample.sum, "mean": resample.mean, "count": resample.count}
    serie_agg = agg_map[agregacion]().reset_index()
    serie_agg.columns = [col_fecha, col_num]

    fig = px.line(
        serie_agg,
        x=col_fecha,
        y=col_num,
        line_shape="spline",
        markers=True,
        color_discrete_sequence=[PALETTE[0]],
        labels={col_fecha: "Fecha", col_num: col_num},
    )
    fig.update_traces(
        line=dict(width=2.5),
        marker=dict(size=6, color=PALETTE[3], line=dict(width=1.5, color="white")),
    )
    labels_frec = {"D": "Diario", "W": "Semanal", "ME": "Mensual",
                   "QE": "Trimestral", "YE": "Anual"}
    fig = _aplicar_layout(
        fig,
        titulo=f"Tendencia {labels_frec.get(frecuencia, frecuencia)} de {col_num}",
    )
    return fig


# ---------------------------------------------------------------------------
# 6. Gráfico de pastel / dona
# ---------------------------------------------------------------------------

def grafico_pastel(
    df: pd.DataFrame,
    columna_cat: str,
    columna_num: str | None = None,
    tipo: Literal["pie", "donut"] = "donut",
    top_n: int = 8,
) -> go.Figure:
    """
    Gráfico de pastel o dona para comparar participaciones de pocas categorías.

    Parámetros
    ----------
    df           - DataFrame fuente.
    columna_cat  - Columna categórica.
    columna_num  - Si se provee, suma esa columna; si no, cuenta frecuencias.
    tipo         - 'pie' o 'donut'.
    top_n        - Máximo de categorías; el resto se agrupa en 'Otros'.
    """
    if columna_cat not in df.columns:
        raise KeyError(f"Columna '{columna_cat}' no encontrada.")

    if columna_num and columna_num in df.columns:
        serie = df.groupby(columna_cat, observed=True)[columna_num].sum().sort_values(ascending=False)
    else:
        serie = df[columna_cat].value_counts()

    if len(serie) > top_n:
        otros = serie.iloc[top_n:].sum()
        serie = serie.iloc[:top_n]
        serie["Otros"] = otros

    hole = 0.45 if tipo == "donut" else 0
    fig = go.Figure(
        go.Pie(
            labels=serie.index.tolist(),
            values=serie.values.tolist(),
            hole=hole,
            marker=dict(colors=PALETTE, line=dict(color="white", width=2)),
            textinfo="percent+label",
            hovertemplate="%{label}: %{value:,.0f} (%{percent})<extra></extra>",
        )
    )
    fig = _aplicar_layout(fig, titulo=f"Distribución de {columna_cat}")
    return fig


# ---------------------------------------------------------------------------
# 7. Heatmap de correlación numérica
# ---------------------------------------------------------------------------

def grafico_correlacion(
    df: pd.DataFrame,
    columnas: list[str] | None = None,
    metodo: Literal["pearson", "spearman", "kendall"] = "pearson",
) -> go.Figure:
    """
    Mapa de calor de la matriz de correlación entre variables numéricas.

    Parámetros
    ----------
    df       - DataFrame fuente.
    columnas - Subconjunto de columnas numéricas. None = todas las numéricas.
    metodo   - Método de correlación: 'pearson', 'spearman' o 'kendall'.
    """
    cols_num = df.select_dtypes(include="number").columns.tolist()
    if columnas:
        cols_num = [c for c in columnas if c in cols_num]

    if len(cols_num) < 2:
        raise ValueError("Se necesitan al menos 2 columnas numéricas para el heatmap.")

    corr = df[cols_num].corr(method=metodo).round(2)

    fig = px.imshow(
        corr,
        text_auto=True,
        color_continuous_scale=[PALETTE[5], "white", PALETTE[0]],
        zmin=-1,
        zmax=1,
        aspect="auto",
    )
    fig = _aplicar_layout(
        fig,
        titulo=f"Matriz de Correlación ({metodo.capitalize()})",
    )
    fig.update_coloraxes(colorbar_title="r")
    return fig


# ---------------------------------------------------------------------------
# 8. Gráfico comparativo Antes vs. Después
# ---------------------------------------------------------------------------

def grafico_antes_despues(
    metricas_antes: dict,
    metricas_despues: dict,
) -> go.Figure:
    """
    Gráfico de barras agrupadas que compara métricas de calidad
    antes y después de la limpieza.

    Parámetros
    ----------
    metricas_antes   - dict con claves y valores numéricos del estado inicial.
                       Ejemplo: {"Faltantes": 45, "Duplicados": 10, "Outliers": 8}
    metricas_despues - dict con las mismas claves pero del estado actual.
    """
    categorias = list(metricas_antes.keys())
    valores_antes = [metricas_antes[k] for k in categorias]
    valores_despues = [metricas_despues.get(k, 0) for k in categorias]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Antes",
            x=categorias,
            y=valores_antes,
            marker_color=PALETTE[5],
            marker_line=dict(width=0),
            text=valores_antes,
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Después",
            x=categorias,
            y=valores_despues,
            marker_color=PALETTE[1],
            marker_line=dict(width=0),
            text=valores_despues,
            textposition="outside",
        )
    )
    fig.update_layout(barmode="group")
    fig = _aplicar_layout(fig, titulo="Comparativa de Calidad: Antes vs. Después")
    return fig

