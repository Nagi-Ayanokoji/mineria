"""
services/quality_service.py
===========================
Módulo de auditoría y perfilado de calidad de datos.

Responsabilidad única:
  - Inspeccionar el DataFrame y devolver métricas y evidencias de problemas.
  - NUNCA modifica el DataFrame; todas las funciones son de solo lectura.
  - Los problemas se agrupan en dos niveles:
      · Universales  → aplican a cualquier dataset (nulos, duplicados, tipos).
      · Estadísticos → outliers detectados por IQR o Z-score.

NO depende de Streamlit.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------
ProblemDict = dict[str, pd.DataFrame]


# ---------------------------------------------------------------------------
# 1. Perfilado general
# ---------------------------------------------------------------------------

def perfilar_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """
    Genera un perfil técnico completo del DataFrame.

    Retorna
    -------
    dict con claves:
        filas               - int
        columnas            - int
        nombres_cols        - list[str]
        tipos               - dict[str, str]
        faltantes_por_col   - dict[str, int]   # conteo de NaN por columna
        faltantes_pct       - dict[str, float] # porcentaje NaN por columna
        total_faltantes     - int
        pct_faltantes_global- float            # % celdas vacías sobre total
        duplicados_exactos  - int
        estadisticas_num    - dict             # describe() columnas numéricas
        estadisticas_cat    - dict             # describe() columnas object/category
        memoria_mb          - float
        cols_numericas      - list[str]
        cols_categoricas    - list[str]
        cols_fecha          - list[str]
    """
    filas, cols = df.shape
    total_celdas = filas * cols if cols > 0 else 1

    faltantes_por_col = df.isnull().sum().to_dict()
    total_faltantes = int(sum(faltantes_por_col.values()))
    faltantes_pct = {
        col: round(v / filas * 100, 2) if filas > 0 else 0.0
        for col, v in faltantes_por_col.items()
    }

    cols_num = df.select_dtypes(include="number").columns.tolist()
    cols_cat = df.select_dtypes(include=["object", "category", "string"]).columns.tolist()
    cols_fecha = df.select_dtypes(include=["datetime", "datetimetz"]).columns.tolist()

    # Estadísticas descriptivas — convertimos a dict para facilitar serialización
    est_num = (
        df[cols_num].describe().to_dict() if cols_num else {}
    )
    est_cat = (
        df[cols_cat].describe().to_dict() if cols_cat else {}
    )

    return {
        "filas": int(filas),
        "columnas": int(cols),
        "nombres_cols": df.columns.tolist(),
        "tipos": {col: str(df[col].dtype) for col in df.columns},
        "faltantes_por_col": {k: int(v) for k, v in faltantes_por_col.items()},
        "faltantes_pct": faltantes_pct,
        "total_faltantes": total_faltantes,
        "pct_faltantes_global": round(total_faltantes / total_celdas * 100, 2),
        "duplicados_exactos": int(df.duplicated().sum()),
        "estadisticas_num": est_num,
        "estadisticas_cat": est_cat,
        "memoria_mb": round(df.memory_usage(deep=True).sum() / 1_048_576, 4),
        "cols_numericas": cols_num,
        "cols_categoricas": cols_cat,
        "cols_fecha": cols_fecha,
    }


# ---------------------------------------------------------------------------
# 2. Detección de problemas universales
# ---------------------------------------------------------------------------

def _detectar_faltantes(df: pd.DataFrame) -> ProblemDict:
    """Retorna un sub-DataFrame por cada columna que tenga valores nulos."""
    resultado: ProblemDict = {}
    for col in df.columns:
        mascara = df[col].isnull()
        if mascara.any():
            resultado[f"faltantes__{col}"] = df[mascara].copy()
    return resultado


def _detectar_duplicados(
    df: pd.DataFrame,
    columnas_clave: list[str] | None,
) -> ProblemDict:
    """
    Detecta:
      - Filas completamente duplicadas (todas las columnas iguales).
      - Filas con clave candidata repetida (si se proveen columnas_clave).
    """
    resultado: ProblemDict = {}

    mask_dup_exacto = df.duplicated(keep=False)
    if mask_dup_exacto.any():
        resultado["duplicados__exactos"] = df[mask_dup_exacto].copy()

    if columnas_clave:
        cols_validas = [c for c in columnas_clave if c in df.columns]
        if cols_validas:
            mask_clave = df.duplicated(subset=cols_validas, keep=False)
            if mask_clave.any():
                resultado["duplicados__clave"] = df[mask_clave].copy()

    return resultado


def _detectar_inconsistencias_texto(df: pd.DataFrame) -> ProblemDict:
    """
    Detecta columnas de texto donde existan:
      - Cadenas con espacios al inicio o final.
      - Valores que difieren solo por capitalización (ej. 'Bogotá' vs 'BOGOTA').
    """
    resultado: ProblemDict = {}
    cols_texto = df.select_dtypes(include=["object", "string"]).columns

    for col in cols_texto:
        serie = df[col].dropna().astype(str)

        # Espacios sobrantes
        mask_espacios = serie != serie.str.strip()
        if mask_espacios.any():
            idx = serie[mask_espacios].index
            resultado[f"texto_espacios__{col}"] = df.loc[idx].copy()

        # Variantes de capitalización: si la versión normalizada tiene menos
        # valores únicos que la original, hay inconsistencias
        unicos_orig = serie.nunique()
        unicos_norm = serie.str.strip().str.lower().nunique()
        if unicos_norm < unicos_orig:
            # Identificar grupos con múltiples representaciones
            mapa = serie.str.strip().str.lower()
            grupos = serie.groupby(mapa).filter(lambda g: g.nunique() > 1)
            if not grupos.empty:
                resultado[f"texto_capitalizacion__{col}"] = df.loc[grupos.index].copy()

    return resultado


def _detectar_fuera_de_rango(
    df: pd.DataFrame,
    reglas_negocio: dict[str, dict] | None,
) -> ProblemDict:
    """
    Aplica reglas de negocio parametrizables.

    Formato de reglas_negocio:
    {
        "columna": {
            "min": valor_minimo,   # opcional
            "max": valor_maximo,   # opcional
            "unico": True/False,   # opcional, verifica unicidad
        }
    }
    """
    resultado: ProblemDict = {}
    if not reglas_negocio:
        return resultado

    for col, regla in reglas_negocio.items():
        if col not in df.columns:
            continue

        serie = df[col]
        mask_total = pd.Series([False] * len(df), index=df.index)

        if "min" in regla:
            try:
                mask_total = mask_total | (pd.to_numeric(serie, errors="coerce") < regla["min"])
            except Exception:
                pass

        if "max" in regla:
            try:
                mask_total = mask_total | (pd.to_numeric(serie, errors="coerce") > regla["max"])
            except Exception:
                pass

        if mask_total.any():
            resultado[f"fuera_rango__{col}"] = df[mask_total].copy()

    return resultado


# ---------------------------------------------------------------------------
# 3. Detección de outliers estadísticos
# ---------------------------------------------------------------------------

def _calcular_outliers_iqr(
    df: pd.DataFrame,
    columnas: list[str] | None = None,
    factor: float = 1.5,
) -> ProblemDict:
    """
    Detecta outliers usando el método del Rango Intercuartílico (IQR).
    
    Límite inferior: Q1 - factor * IQR
    Límite superior: Q3 + factor * IQR

    Solo procesa columnas numéricas. Si `columnas` es None, usa todas las numéricas.
    """
    resultado: ProblemDict = {}
    cols_num = (
        df.select_dtypes(include="number").columns.tolist()
        if columnas is None
        else [c for c in columnas if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    )

    for col in cols_num:
        serie = df[col].dropna()
        if serie.empty:
            continue

        q1 = serie.quantile(0.25)
        q3 = serie.quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            continue  # Sin dispersión, no hay outliers significativos

        lim_inf = q1 - factor * iqr
        lim_sup = q3 + factor * iqr

        mask = (df[col] < lim_inf) | (df[col] > lim_sup)
        if mask.any():
            subset = df[mask].copy()
            subset[f"__lim_inf_{col}"] = lim_inf
            subset[f"__lim_sup_{col}"] = lim_sup
            resultado[f"outlier_iqr__{col}"] = subset

    return resultado


def _calcular_outliers_zscore(
    df: pd.DataFrame,
    columnas: list[str] | None = None,
    umbral: float = 3.0,
) -> ProblemDict:
    """
    Detecta outliers usando Puntuación Z (Z-Score).
    Un valor es outlier si |z| > umbral (por defecto 3 desviaciones estándar).
    """
    resultado: ProblemDict = {}
    cols_num = (
        df.select_dtypes(include="number").columns.tolist()
        if columnas is None
        else [c for c in columnas if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    )

    for col in cols_num:
        serie = df[col].dropna()
        if serie.empty or serie.std() == 0:
            continue

        media = serie.mean()
        std = serie.std()
        z_scores = (df[col] - media) / std
        mask = z_scores.abs() > umbral
        if mask.any():
            subset = df[mask].copy()
            subset[f"__zscore_{col}"] = z_scores[mask].round(3)
            resultado[f"outlier_zscore__{col}"] = subset

    return resultado


def calcular_limites_iqr(df: pd.DataFrame, columna: str, factor: float = 1.5) -> dict:
    """
    Retorna los límites IQR para una columna numérica.
    Útil para que el frontend construya sliders interactivos.

    Retorna
    -------
    dict: {q1, q3, iqr, lim_inf, lim_sup, minimo, maximo}
    """
    if columna not in df.columns:
        raise KeyError(f"Columna '{columna}' no encontrada.")

    serie = df[columna].dropna()
    q1 = float(serie.quantile(0.25))
    q3 = float(serie.quantile(0.75))
    iqr = q3 - q1

    return {
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lim_inf": q1 - factor * iqr,
        "lim_sup": q3 + factor * iqr,
        "minimo": float(serie.min()),
        "maximo": float(serie.max()),
    }


# ---------------------------------------------------------------------------
# 4. Función unificadora principal
# ---------------------------------------------------------------------------

def detectar_problemas(
    df: pd.DataFrame,
    reglas_negocio: dict[str, dict] | None = None,
    columnas_clave: list[str] | None = None,
    columnas_outlier: list[str] | None = None,
    metodo_outlier: str = "iqr",
    factor_iqr: float = 1.5,
    umbral_zscore: float = 3.0,
) -> dict[str, pd.DataFrame]:
    """
    Función principal de auditoría. Ejecuta todos los detectores en secuencia
    y retorna un diccionario unificado donde:

      - Clave: nombre descriptivo del problema (prefijo__columna).
      - Valor: DataFrame con ÚNICAMENTE los registros afectados.

    Parámetros
    ----------
    df               - DataFrame a auditar (no se modifica).
    reglas_negocio   - dict de reglas de rango por columna (ver _detectar_fuera_de_rango).
    columnas_clave   - Columnas que deben ser únicas (ej. ['id_venta']).
    columnas_outlier - Columnas numéricas a analizar para outliers. None = todas.
    metodo_outlier   - 'iqr' (por defecto) o 'zscore'.
    factor_iqr       - Multiplicador IQR (por defecto 1.5).
    umbral_zscore    - Umbral de desviaciones estándar (por defecto 3.0).

    Retorna
    -------
    dict[str, pd.DataFrame]: diccionario vacío si no se detectaron problemas.
    """
    problemas: ProblemDict = {}

    # --- 1. Valores faltantes ---
    problemas.update(_detectar_faltantes(df))

    # --- 2. Duplicados ---
    problemas.update(_detectar_duplicados(df, columnas_clave))

    # --- 3. Inconsistencias de texto ---
    problemas.update(_detectar_inconsistencias_texto(df))

    # --- 4. Reglas de negocio / fuera de rango ---
    if reglas_negocio:
        problemas.update(_detectar_fuera_de_rango(df, reglas_negocio))

    # --- 5. Outliers estadísticos ---
    if metodo_outlier == "zscore":
        problemas.update(
            _calcular_outliers_zscore(df, columnas=columnas_outlier, umbral=umbral_zscore)
        )
    else:
        problemas.update(
            _calcular_outliers_iqr(df, columnas=columnas_outlier, factor=factor_iqr)
        )

    return problemas


def resumen_problemas(problemas: ProblemDict) -> list[dict]:
    """
    Convierte el dict de problemas en una lista de resúmenes tabulares,
    ordenada de mayor a menor cantidad de casos. Útil para construir
    la tabla de incidencias en el frontend.

    Retorna
    -------
    list[dict]: cada dict tiene {tipo, descripcion, cantidad}
    """
    descripciones = {
        "faltantes__": "Valores faltantes en",
        "duplicados__exactos": "Filas completamente duplicadas",
        "duplicados__clave": "Duplicados por columna clave",
        "texto_espacios__": "Espacios sobrantes en",
        "texto_capitalizacion__": "Variantes de capitalización en",
        "fuera_rango__": "Valores fuera de rango en",
        "outlier_iqr__": "Outlier estadístico (IQR) en",
        "outlier_zscore__": "Outlier estadístico (Z-Score) en",
    }

    resumen = []
    for clave, subdf in problemas.items():
        # Determinar descripción legible
        descripcion = clave
        for prefijo, desc in descripciones.items():
            if clave.startswith(prefijo):
                columna = clave.replace(prefijo, "").replace("__", " → ")
                descripcion = f"{desc} '{columna}'" if columna else desc
                break

        resumen.append({
            "tipo": clave,
            "descripcion": descripcion,
            "cantidad": len(subdf),
        })

    return sorted(resumen, key=lambda x: x["cantidad"], reverse=True)

