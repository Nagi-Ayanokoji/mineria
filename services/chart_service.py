"""
services/chart_service.py
==========================
Módulo de visualización interactiva con Plotly Express y Graph Objects.

Responsabilidad única:
  - Recibir DataFrames ya procesados y retornar objetos plotly.graph_objects.Figure.
  - Toda la preparación y agregación de datos ocurre aquí, NO en app.py.
  - Resiliente ante valores nulos, columnas de alta cardinalidad y conjuntos grandes.
  - Paleta visual pastel compatible con tema claro y tema oscuro.

NO depende de Streamlit.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Paleta de colores pasteles armónica y de alto contraste
# ---------------------------------------------------------------------------
PALETTE = [
    "#818CF8",  # Índigo pastel vibrante
    "#34D399",  # Menta / Esmeralda suave
    "#F472B6",  # Rosa pastel
    "#FBBF24",  # Ámbar suave
    "#60A5FA",  # Azul cielo
    "#A78BFA",  # Lavanda / Púrpura pastel
    "#FB923C",  # Durazno / Coral pastel
    "#2DD4BF",  # Turquesa pastel
    "#A3E635",  # Lima suave
    "#E879F9",  # Fucsia pastel
]

LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Plus Jakarta Sans, Inter, Segoe UI, sans-serif", size=13),
    margin=dict(l=50, r=40, t=60, b=50),
    hoverlabel=dict(font_size=13, font_family="Plus Jakarta Sans"),
)


def _aplicar_layout(fig: go.Figure, titulo: str = "", **kwargs) -> go.Figure:
    """Aplica el layout base transparente y estilizado a cualquier figura."""
    fig.update_layout(
        title=dict(
            text=f"<b>{titulo}</b>",
            font=dict(size=16),
            x=0.02,
            y=0.96,
        ),
        **LAYOUT_BASE,
        **kwargs,
    )
    # Ejes con cuadrículas tenues adaptables a light y dark mode
    fig.update_xaxes(
        gridcolor="rgba(148, 163, 184, 0.2)",
        zerolinecolor="rgba(148, 163, 184, 0.3)",
        showline=True,
        linecolor="rgba(148, 163, 184, 0.3)",
    )
    fig.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.2)",
        zerolinecolor="rgba(148, 163, 184, 0.3)",
        showline=True,
        linecolor="rgba(148, 163, 184, 0.3)",
    )
    return fig


# ---------------------------------------------------------------------------
# 1. Distribución de variable numérica (Histograma + KDE)
# ---------------------------------------------------------------------------

def grafico_distribucion(
    df: pd.DataFrame,
    columna: str,
    nbins: int = 30,
    mostrar_kde: bool = True,
) -> go.Figure:
    """
    Histograma de distribución con boxplot marginal y curva KDE opcional.
    Resiliente ante valores constantes, nulos o distribuciones singulares.
    """
    if columna not in df.columns:
        raise KeyError(f"Columna '{columna}' no encontrada.")

    serie = pd.to_numeric(df[columna], errors="coerce").dropna()
    if serie.empty:
        raise ValueError(f"La columna '{columna}' no contiene datos numéricos válidos.")

    df_clean = pd.DataFrame({columna: serie})

    fig = px.histogram(
        df_clean,
        x=columna,
        nbins=nbins,
        color_discrete_sequence=[PALETTE[0]],
        opacity=0.85,
        marginal="box",
        labels={columna: columna},
    )

    if mostrar_kde and len(serie) > 3 and serie.nunique() > 1:
        try:
            from scipy.stats import gaussian_kde
            # Si hay más de 5,000 datos, muestrear para que el cálculo sea instantáneo
            muestra_kde = serie.sample(min(len(serie), 5000), random_state=42) if len(serie) > 5000 else serie
            kde = gaussian_kde(muestra_kde)
            x_range = np.linspace(float(serie.min()), float(serie.max()), 200)
            y_kde = kde(x_range)
            
            # Escalar KDE a la altura del histograma
            # El área del histograma approx = N * bin_width
            bin_width = (serie.max() - serie.min()) / nbins if nbins > 0 else 1.0
            y_scaled = y_kde * len(serie) * bin_width

            fig.add_trace(
                go.Scatter(
                    x=x_range,
                    y=y_scaled,
                    mode="lines",
                    name="Densidad KDE",
                    line=dict(color=PALETTE[2], width=2.5),
                )
            )
        except Exception:
            # Si falla la aproximación KDE (ej. matriz singular), el histograma se dibuja intacto
            pass

    fig = _aplicar_layout(fig, titulo=f"Distribución de {columna}")
    fig.update_traces(marker_line_color="rgba(255,255,255,0.4)", marker_line_width=1)
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
    Gráfico de barras horizontal o vertical para comparar categorías por una métrica.
    Limpia valores nulos en la categoría y valida tipos numéricos.
    """
    if columna_cat not in df.columns or columna_num not in df.columns:
        raise KeyError(f"Columna '{columna_cat}' o '{columna_num}' no encontrada.")

    # Asegurar tipo numérico y manejar nulos
    df_temp = pd.DataFrame({
        columna_cat: df[columna_cat].fillna("Sin dato").astype(str),
        columna_num: pd.to_numeric(df[columna_num], errors="coerce"),
    }).dropna(subset=[columna_num])

    if df_temp.empty:
        raise ValueError(f"No hay registros válidos para graficar '{columna_cat}' vs '{columna_num}'.")

    agrup = df_temp.groupby(columna_cat, observed=True)[columna_num]
    agg_map = {
        "sum": agrup.sum,
        "mean": agrup.mean,
        "count": agrup.count,
        "max": agrup.max,
        "min": agrup.min,
    }
    serie_agg = agg_map.get(agregacion, agrup.sum)().sort_values(ascending=False).head(top_n)
    df_plot = pd.DataFrame({columna_cat: serie_agg.index, columna_num: serie_agg.values})

    if orientacion == "h":
        df_plot = df_plot.sort_values(columna_num, ascending=True)
        fig = px.bar(
            df_plot,
            x=columna_num,
            y=columna_cat,
            orientation="h",
            color=columna_num,
            color_continuous_scale=[PALETTE[1], PALETTE[0], PALETTE[5]],
        )
    else:
        fig = px.bar(
            df_plot,
            x=columna_cat,
            y=columna_num,
            color=columna_num,
            color_continuous_scale=[PALETTE[1], PALETTE[0], PALETTE[5]],
        )

    fig.update_coloraxes(showscale=False)
    fig = _aplicar_layout(
        fig,
        titulo=f"Top {len(df_plot)} — {columna_cat} por {agregacion}({columna_num})",
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
    opacidad: float = 0.7,
    max_puntos: int = 4000,
) -> go.Figure:
    """
    Scatterplot interactivo entre dos variables numéricas continuas.
    - NO depende de statsmodels para evitar fallos por dependencias faltantes.
    - Si el dataset supera max_puntos, toma una muestra aleatoria representativa
      para garantizar 60 FPS y prevenir congelamiento del navegador.
    - Agrupa categorías con demasiados valores únicos para no colapsar la leyenda.
    """
    for col in [col_x, col_y]:
        if col not in df.columns:
            raise KeyError(f"Columna '{col}' no encontrada.")

    cols_a_usar = [col_x, col_y]
    if col_color and col_color in df.columns:
        cols_a_usar.append(col_color)
    if col_size and col_size in df.columns:
        cols_a_usar.append(col_size)

    df_sub = df[cols_a_usar].copy()
    df_sub[col_x] = pd.to_numeric(df_sub[col_x], errors="coerce")
    df_sub[col_y] = pd.to_numeric(df_sub[col_y], errors="coerce")
    df_sub = df_sub.dropna(subset=[col_x, col_y])

    if df_sub.empty:
        raise ValueError(f"No hay pares de datos válidos entre '{col_x}' y '{col_y}'.")

    # Si hay una columna de color con más de 15 categorías, agrupar las menores en 'Otros'
    color_param = col_color
    if col_color and col_color in df_sub.columns:
        df_sub[col_color] = df_sub[col_color].fillna("Sin dato").astype(str)
        top_cats = df_sub[col_color].value_counts().head(12).index.tolist()
        df_sub[col_color] = df_sub[col_color].apply(lambda x: x if x in top_cats else "Otros")

    # Muestreo si supera max_puntos
    total_pts = len(df_sub)
    es_muestra = False
    if total_pts > max_puntos:
        df_sub = df_sub.sample(max_puntos, random_state=42)
        es_muestra = True

    fig = px.scatter(
        df_sub,
        x=col_x,
        y=col_y,
        color=color_param,
        size=col_size if col_size and col_size in df_sub.columns else None,
        opacity=opacidad,
        color_discrete_sequence=PALETTE,
        labels={col_x: col_x, col_y: col_y},
    )

    titulo_txt = f"Dispersión: {col_x} vs {col_y}"
    if es_muestra:
        titulo_txt += f" (Muestra representativa de {max_puntos:,} de {total_pts:,} filas)"

    fig = _aplicar_layout(fig, titulo=titulo_txt)
    fig.update_traces(marker=dict(line=dict(width=0.5, color="rgba(255,255,255,0.6)")))
    return fig


# ---------------------------------------------------------------------------
# 4. Boxplot — Dispersión y detección visual de outliers
# ---------------------------------------------------------------------------

def grafico_caja_outliers(
    df: pd.DataFrame,
    columna_num: str,
    columna_cat: str | None = None,
    max_cats: int = 12,
) -> go.Figure:
    """
    Boxplot interactivo para inspección de outliers y cuartiles.
    Usa points='outliers' en lugar de 'all' para no sobrecargar el renderizado
    cuando hay miles de filas.
    """
    if columna_num not in df.columns:
        raise KeyError(f"Columna '{columna_num}' no encontrada.")

    cols_usar = [columna_num]
    if columna_cat and columna_cat in df.columns:
        cols_usar.append(columna_cat)

    df_sub = df[cols_usar].copy()
    df_sub[columna_num] = pd.to_numeric(df_sub[columna_num], errors="coerce")
    df_sub = df_sub.dropna(subset=[columna_num])

    if df_sub.empty:
        raise ValueError(f"La columna '{columna_num}' no contiene números válidos.")

    cat_col = None
    if columna_cat and columna_cat in df_sub.columns:
        cat_col = columna_cat
        df_sub[columna_cat] = df_sub[columna_cat].fillna("Sin dato").astype(str)
        # Limitar a las top categorías más frecuentes
        top_cats = df_sub[columna_cat].value_counts().head(max_cats).index.tolist()
        df_sub = df_sub[df_sub[columna_cat].isin(top_cats)]

    fig = px.box(
        df_sub,
        x=cat_col,
        y=columna_num,
        color=cat_col,
        points="outliers",  # Solo puntos que son outliers estadísticos (>1.5 IQR)
        color_discrete_sequence=PALETTE,
        notched=False,
        labels={columna_num: columna_num, cat_col: cat_col or ""},
    )

    titulo_txt = f"Boxplot de {columna_num}" + (f" por {cat_col}" if cat_col else "")
    fig = _aplicar_layout(
        fig,
        titulo=titulo_txt,
        showlegend=False if not cat_col else True,
    )
    return fig


# ---------------------------------------------------------------------------
# 5. Heatmap de correlación numérica
# ---------------------------------------------------------------------------

def grafico_correlacion(
    df: pd.DataFrame,
    columnas: list[str] | None = None,
    metodo: Literal["pearson", "spearman", "kendall"] = "pearson",
) -> go.Figure:
    """
    Mapa de calor interactivo de la matriz de correlación.
    Resiliente ante columnas con varianza cero o valores NaN.
    """
    cols_num = df.select_dtypes(include="number").columns.tolist()
    if columnas:
        cols_num = [c for c in columnas if c in cols_num]

    if len(cols_num) < 2:
        raise ValueError("Se necesitan al menos 2 columnas numéricas para calcular correlación.")

    # Convertir a numérico y calcular matriz
    df_num = df[cols_num].apply(pd.to_numeric, errors="coerce")
    corr = df_num.corr(method=metodo).fillna(0).round(2)

    fig = px.imshow(
        corr,
        text_auto=True,
        color_continuous_scale=[PALETTE[2], "rgba(255,255,255,0.9)", PALETTE[0]],
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
# 6. Gráfico de líneas de tiempo — Tendencia cronológica
# ---------------------------------------------------------------------------

def grafico_lineas_tiempo(
    df: pd.DataFrame,
    col_fecha: str,
    col_num: str,
    frecuencia: Literal["D", "W", "ME", "QE", "YE"] = "ME",
    agregacion: Literal["sum", "mean", "count"] = "sum",
) -> go.Figure:
    """Gráfico de tendencia temporal suavizada para series de tiempo."""
    if col_fecha not in df.columns or col_num not in df.columns:
        raise KeyError(f"Columna '{col_fecha}' o '{col_num}' no encontrada.")

    df_t = df[[col_fecha, col_num]].copy()
    df_t[col_fecha] = pd.to_datetime(df_t[col_fecha], errors="coerce")
    df_t[col_num] = pd.to_numeric(df_t[col_num], errors="coerce")
    df_t = df_t.dropna(subset=[col_fecha, col_num])

    if df_t.empty:
        raise ValueError("No hay datos válidos de fecha y valor para la serie temporal.")

    df_t = df_t.set_index(col_fecha)
    resample = df_t[col_num].resample(frecuencia)
    agg_map = {"sum": resample.sum, "mean": resample.mean, "count": resample.count}
    serie_agg = agg_map.get(agregacion, resample.sum)().reset_index()
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
        marker=dict(size=6, color=PALETTE[2], line=dict(width=1.5, color="white")),
    )
    labels_frec = {"D": "Diario", "W": "Semanal", "ME": "Mensual", "QE": "Trimestral", "YE": "Anual"}
    return _aplicar_layout(fig, titulo=f"Tendencia {labels_frec.get(frecuencia, frecuencia)} de {col_num}")


# ---------------------------------------------------------------------------
# 7. Gráfico de pastel / dona
# ---------------------------------------------------------------------------

def grafico_pastel(
    df: pd.DataFrame,
    columna_cat: str,
    columna_num: str | None = None,
    tipo: Literal["pie", "donut"] = "donut",
    top_n: int = 8,
) -> go.Figure:
    """Gráfico de dona o pastel para distribución de categorías."""
    if columna_cat not in df.columns:
        raise KeyError(f"Columna '{columna_cat}' no encontrada.")

    df_temp = df.copy()
    df_temp[columna_cat] = df_temp[columna_cat].fillna("Sin dato").astype(str)

    if columna_num and columna_num in df_temp.columns:
        df_temp[columna_num] = pd.to_numeric(df_temp[columna_num], errors="coerce").fillna(0)
        serie = df_temp.groupby(columna_cat, observed=True)[columna_num].sum().sort_values(ascending=False)
    else:
        serie = df_temp[columna_cat].value_counts()

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
            marker=dict(colors=PALETTE, line=dict(color="rgba(255,255,255,0.6)", width=1.5)),
            textinfo="percent+label",
            hovertemplate="%{label}: %{value:,.0f} (%{percent})<extra></extra>",
        )
    )
    return _aplicar_layout(fig, titulo=f"Distribución de {columna_cat}")


# ---------------------------------------------------------------------------
# 8. Gráfico comparativo Antes vs. Después
# ---------------------------------------------------------------------------

def grafico_antes_despues(
    metricas_antes: dict,
    metricas_despues: dict,
) -> go.Figure:
    """
    Gráfico de barras agrupadas que compara métricas de calidad
    antes y después de las operaciones de limpieza.
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
            marker_color=PALETTE[2],  # Rosa / Coral pastel
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
            marker_color=PALETTE[1],  # Menta / Esmeralda pastel
            marker_line=dict(width=0),
            text=valores_despues,
            textposition="outside",
        )
    )
    fig.update_layout(barmode="group")
    fig = _aplicar_layout(fig, titulo="Auditoría de Calidad: Estado Inicial vs. Estado Actual")
    return fig
