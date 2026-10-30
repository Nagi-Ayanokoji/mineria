"""
services/cleaning_service.py
=============================
Motor de transformación y limpieza asistida de datasets.

Responsabilidad única:
  - Aplicar transformaciones confirmadas por el usuario sobre el DataFrame.
  - SIEMPRE retorna una COPIA del DataFrame (df.copy()); nunca muta el original.
  - Cada función es idempotente: aplicarla dos veces produce el mismo resultado.
  - Registra metadata de cada operación para facilitar la trazabilidad.

NO depende de Streamlit.
"""

from __future__ import annotations

import unicodedata
from typing import Any, Literal

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------
EstrategiaImputacion = Literal["eliminar", "media", "mediana", "moda", "valor_fijo"]
AccionOutlier = Literal["filtrar", "recortar", "marcar"]


# ---------------------------------------------------------------------------
# Helper: metadata de operación
# ---------------------------------------------------------------------------

def _log_op(nombre: str, **kwargs) -> dict:
    """Genera un registro estándar de operación para el historial."""
    return {"operacion": nombre, **kwargs}


# ---------------------------------------------------------------------------
# 1. Eliminación de duplicados
# ---------------------------------------------------------------------------

def eliminar_duplicados(
    df: pd.DataFrame,
    subset: list[str] | None = None,
    keep: Literal["first", "last", False] = "first",
) -> tuple[pd.DataFrame, dict]:
    """
    Elimina filas duplicadas del DataFrame.

    Parámetros
    ----------
    df     - DataFrame original (no se modifica).
    subset - Columnas a considerar para la comparación. None = todas las columnas.
    keep   - 'first': conservar la primera ocurrencia.
             'last': conservar la última ocurrencia.
             False: eliminar todas las instancias duplicadas.

    Retorna
    -------
    tuple[pd.DataFrame, dict]:
        - DataFrame sin duplicados.
        - Metadata de la operación: {operacion, filas_antes, filas_despues, eliminadas}.
    """
    filas_antes = len(df)
    df_limpio = df.drop_duplicates(subset=subset, keep=keep).copy()
    filas_despues = len(df_limpio)
    eliminadas = filas_antes - filas_despues

    meta = _log_op(
        "eliminar_duplicados",
        subset=subset,
        keep=keep,
        filas_antes=filas_antes,
        filas_despues=filas_despues,
        eliminadas=eliminadas,
    )
    return df_limpio, meta


# ---------------------------------------------------------------------------
# 2. Imputación de valores faltantes
# ---------------------------------------------------------------------------

def imputar_faltantes(
    df: pd.DataFrame,
    columna: str,
    estrategia: EstrategiaImputacion,
    valor_personalizado: Any = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Imputa o elimina filas con valores faltantes en una columna específica.

    Parámetros
    ----------
    df                  - DataFrame original.
    columna             - Nombre de la columna a tratar.
    estrategia          - Una de: 'eliminar', 'media', 'mediana', 'moda', 'valor_fijo'.
    valor_personalizado - Valor constante a usar cuando estrategia='valor_fijo'.

    Retorna
    -------
    tuple[pd.DataFrame, dict]:
        - DataFrame con la columna tratada.
        - Metadata de la operación.

    Lanza
    -----
    KeyError   - Si la columna no existe en el DataFrame.
    ValueError - Si la estrategia no es válida o requiere parámetros faltantes.
    """
    if columna not in df.columns:
        raise KeyError(f"Columna '{columna}' no encontrada en el DataFrame.")

    estrategias_validas = {"eliminar", "media", "mediana", "moda", "valor_fijo"}
    if estrategia not in estrategias_validas:
        raise ValueError(
            f"Estrategia '{estrategia}' no válida. Use una de: {estrategias_validas}"
        )

    df_c = df.copy()
    faltantes_antes = int(df_c[columna].isnull().sum())

    if estrategia == "eliminar":
        df_c = df_c.dropna(subset=[columna])
        valor_usado = "NaN → fila eliminada"

    elif estrategia == "media":
        if not pd.api.types.is_numeric_dtype(df_c[columna]):
            raise ValueError(f"La estrategia 'media' solo aplica a columnas numéricas.")
        valor = df_c[columna].mean()
        df_c[columna] = df_c[columna].fillna(valor)
        valor_usado = round(float(valor), 4)

    elif estrategia == "mediana":
        if not pd.api.types.is_numeric_dtype(df_c[columna]):
            raise ValueError(f"La estrategia 'mediana' solo aplica a columnas numéricas.")
        valor = df_c[columna].median()
        df_c[columna] = df_c[columna].fillna(valor)
        valor_usado = round(float(valor), 4)

    elif estrategia == "moda":
        modas = df_c[columna].mode()
        if modas.empty:
            raise ValueError(f"No se pudo calcular la moda para '{columna}'.")
        valor = modas.iloc[0]
        df_c[columna] = df_c[columna].fillna(valor)
        valor_usado = valor

    elif estrategia == "valor_fijo":
        if valor_personalizado is None:
            raise ValueError("Se requiere 'valor_personalizado' cuando estrategia='valor_fijo'.")
        df_c[columna] = df_c[columna].fillna(valor_personalizado)
        valor_usado = valor_personalizado

    faltantes_despues = int(df_c[columna].isnull().sum())

    meta = _log_op(
        "imputar_faltantes",
        columna=columna,
        estrategia=estrategia,
        valor_usado=valor_usado,
        faltantes_antes=faltantes_antes,
        faltantes_despues=faltantes_despues,
        resueltos=faltantes_antes - faltantes_despues,
    )
    return df_c, meta


# ---------------------------------------------------------------------------
# 3. Normalización de texto
# ---------------------------------------------------------------------------

def _quitar_tildes(texto: str) -> str:
    """Elimina diacríticos (tildes, acentos) de una cadena."""
    normalizado = unicodedata.normalize("NFD", texto)
    return "".join(c for c in normalizado if unicodedata.category(c) != "Mn")


def normalizar_textos(
    df: pd.DataFrame,
    columnas: list[str],
    minusculas: bool = True,
    quitar_espacios: bool = True,
    quitar_tildes: bool = False,
    mayusculas_primera: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """
    Estandariza columnas de texto aplicando las transformaciones seleccionadas.

    Parámetros
    ----------
    df                 - DataFrame original.
    columnas           - Lista de columnas de texto a normalizar.
    minusculas         - Convertir a minúsculas.
    quitar_espacios    - Eliminar espacios al inicio/final (strip).
    quitar_tildes      - Eliminar diacríticos (útil para comparaciones).
    mayusculas_primera - Capitalizar la primera letra de cada palabra (title case).
                         Solo aplica si minusculas=False.

    Retorna
    -------
    tuple[pd.DataFrame, dict]:
        - DataFrame con columnas normalizadas.
        - Metadata de la operación.
    """
    df_c = df.copy()
    cols_validas = [c for c in columnas if c in df_c.columns]
    cols_ignoradas = [c for c in columnas if c not in df_c.columns]

    cambios_totales = 0
    for col in cols_validas:
        original = df_c[col].astype(str)
        serie = original.copy()

        if quitar_espacios:
            serie = serie.str.strip()
        if minusculas:
            serie = serie.str.lower()
        elif mayusculas_primera:
            serie = serie.str.title()
        if quitar_tildes:
            serie = serie.apply(lambda x: _quitar_tildes(x) if isinstance(x, str) else x)

        # Restaurar NaN donde originalmente había NaN
        mask_nulos = df_c[col].isnull()
        serie[mask_nulos] = np.nan

        cambios = int((serie != original).sum())
        cambios_totales += cambios
        df_c[col] = serie

    meta = _log_op(
        "normalizar_textos",
        columnas=cols_validas,
        columnas_ignoradas=cols_ignoradas,
        opciones={
            "minusculas": minusculas,
            "quitar_espacios": quitar_espacios,
            "quitar_tildes": quitar_tildes,
            "mayusculas_primera": mayusculas_primera,
        },
        celdas_modificadas=cambios_totales,
    )
    return df_c, meta


# ---------------------------------------------------------------------------
# 4. Conversión de tipos de datos
# ---------------------------------------------------------------------------

TIPOS_SOPORTADOS = {"int", "float", "str", "datetime", "category", "bool"}


def convertir_tipos(
    df: pd.DataFrame,
    mapeo_tipos: dict[str, str],
) -> tuple[pd.DataFrame, dict]:
    """
    Castea columnas a los tipos especificados de forma segura.

    Parámetros
    ----------
    df           - DataFrame original.
    mapeo_tipos  - dict {columna: tipo_destino}
                   Tipos válidos: 'int', 'float', 'str', 'datetime', 'category', 'bool'.

    Retorna
    -------
    tuple[pd.DataFrame, dict]:
        - DataFrame con tipos convertidos (los errores de conversión quedan como NaN).
        - Metadata con columnas convertidas y las que fallaron.
    """
    df_c = df.copy()
    convertidas: list[str] = []
    errores: dict[str, str] = {}

    for col, tipo in mapeo_tipos.items():
        if col not in df_c.columns:
            errores[col] = "Columna no encontrada"
            continue

        if tipo not in TIPOS_SOPORTADOS:
            errores[col] = f"Tipo '{tipo}' no soportado. Use: {TIPOS_SOPORTADOS}"
            continue

        try:
            if tipo == "int":
                df_c[col] = pd.to_numeric(df_c[col], errors="coerce").astype("Int64")
            elif tipo == "float":
                df_c[col] = pd.to_numeric(df_c[col], errors="coerce")
            elif tipo == "str":
                df_c[col] = df_c[col].astype(str)
            elif tipo == "datetime":
                df_c[col] = pd.to_datetime(df_c[col], errors="coerce", infer_datetime_format=True)
            elif tipo == "category":
                df_c[col] = df_c[col].astype("category")
            elif tipo == "bool":
                df_c[col] = df_c[col].map(
                    {"True": True, "False": False, "1": True, "0": False,
                     True: True, False: False, 1: True, 0: False}
                )
            convertidas.append(col)
        except Exception as exc:
            errores[col] = str(exc)

    meta = _log_op(
        "convertir_tipos",
        convertidas=convertidas,
        errores=errores,
        mapeo=mapeo_tipos,
    )
    return df_c, meta


# ---------------------------------------------------------------------------
# 5. Tratamiento de outliers
# ---------------------------------------------------------------------------

def filtrar_o_recortar_outliers(
    df: pd.DataFrame,
    columna: str,
    lim_inf: float,
    lim_sup: float,
    accion: AccionOutlier = "filtrar",
    nombre_flag: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Trata outliers estadísticos en una columna numérica.

    Parámetros
    ----------
    df          - DataFrame original.
    columna     - Columna numérica a tratar.
    lim_inf     - Límite inferior; valores por debajo son outliers.
    lim_sup     - Límite superior; valores por encima son outliers.
    accion      - 'filtrar': eliminar filas outlier.
                  'recortar': clamp al límite (winsorización).
                  'marcar': agregar una columna booleana '<columna>__outlier'.
    nombre_flag - Nombre personalizado para la columna de marcado.
                  Por defecto: '<columna>__outlier'.

    Retorna
    -------
    tuple[pd.DataFrame, dict]:
        - DataFrame tratado.
        - Metadata de la operación.
    """
    if columna not in df.columns:
        raise KeyError(f"Columna '{columna}' no encontrada.")
    if not pd.api.types.is_numeric_dtype(df[columna]):
        raise ValueError(f"La columna '{columna}' no es numérica.")

    df_c = df.copy()
    mask_outlier = (df_c[columna] < lim_inf) | (df_c[columna] > lim_sup)
    n_outliers = int(mask_outlier.sum())

    if accion == "filtrar":
        df_c = df_c[~mask_outlier].copy()
        descripcion = f"Eliminadas {n_outliers} filas con outliers en '{columna}'"

    elif accion == "recortar":
        df_c[columna] = df_c[columna].clip(lower=lim_inf, upper=lim_sup)
        descripcion = f"Recortados {n_outliers} outliers en '{columna}' a [{lim_inf:.2f}, {lim_sup:.2f}]"

    elif accion == "marcar":
        flag_col = nombre_flag or f"{columna}__outlier"
        df_c[flag_col] = mask_outlier
        descripcion = f"Marcados {n_outliers} outliers en '{columna}' → columna '{flag_col}'"

    else:
        raise ValueError(f"Acción '{accion}' no válida. Use: 'filtrar', 'recortar' o 'marcar'.")

    meta = _log_op(
        "filtrar_o_recortar_outliers",
        columna=columna,
        accion=accion,
        lim_inf=lim_inf,
        lim_sup=lim_sup,
        n_outliers=n_outliers,
        descripcion=descripcion,
        filas_resultantes=len(df_c),
    )
    return df_c, meta


# ---------------------------------------------------------------------------
# 6. Exportación a bytes
# ---------------------------------------------------------------------------

def exportar_csv(df: pd.DataFrame) -> bytes:
    """
    Serializa el DataFrame a CSV con codificación utf-8-sig (compatible con Excel).

    Retorna
    -------
    bytes: contenido del CSV listo para st.download_button.
    """
    return df.to_csv(index=False).encode("utf-8-sig")


def exportar_excel(df: pd.DataFrame) -> bytes:
    """
    Serializa el DataFrame a Excel (.xlsx) usando openpyxl.

    Retorna
    -------
    bytes: contenido del archivo Excel listo para st.download_button.
    """
    import io
    import openpyxl  # noqa: F401 — verificar disponibilidad

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="datos_limpios")
    buffer.seek(0)
    return buffer.read()


# ---------------------------------------------------------------------------
# 7. Snapshot para comparativa Antes vs. Después
# ---------------------------------------------------------------------------

def tomar_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retorna una copia profunda del DataFrame para conservar el estado original.
    Usar antes de cualquier transformación para habilitar la comparativa.
    """
    return df.copy(deep=True)

