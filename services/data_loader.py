"""
services/data_loader.py
=======================
Módulo de ingesta segura de archivos.

Responsabilidad única:
  - Leer archivos CSV y Excel cargados desde cualquier fuente (ruta local o
    objeto de archivo compatible con file-like objects, como st.file_uploader).
  - Detectar y manejar codificaciones (utf-8, latin-1, utf-8-sig, cp1252).
  - Gestionar separadores de CSV de forma automática o manual.
  - Retornar un DataFrame limpio (sin mutar) o lanzar excepciones descriptivas.

NO depende de Streamlit. Puede usarse en scripts CLI, tests o notebooks.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Tipos aceptados como fuente de archivo
# ---------------------------------------------------------------------------
ArchivoEntrada = Union[str, Path, io.BytesIO, io.StringIO, object]

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
CODIFICACIONES_CANDIDATAS: list[str] = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
SEPARADORES_CANDIDATOS: list[str] = [",", ";", "\t", "|"]
EXTENSIONES_CSV: set[str] = {".csv", ".tsv", ".txt"}
EXTENSIONES_EXCEL: set[str] = {".xlsx", ".xls", ".xlsm"}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _detectar_nombre(archivo: ArchivoEntrada) -> str:
    """Intenta extraer el nombre del archivo de distintas fuentes."""
    if hasattr(archivo, "name"):
        return archivo.name
    if isinstance(archivo, (str, Path)):
        return str(Path(archivo).name)
    return "sin_nombre"


def _extension(nombre: str) -> str:
    return Path(nombre).suffix.lower()


def _leer_csv_con_fallback(
    contenido: bytes,
    separador: str | None,
) -> pd.DataFrame:
    """
    Intenta cargar un CSV probando codificaciones candidatas.
    Si `separador` es None, usa csv.Sniffer para inferirlo.
    Lanza ValueError si ninguna combinación funciona.
    """
    ultimo_error: Exception | None = None

    for enc in CODIFICACIONES_CANDIDATAS:
        try:
            texto = contenido.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

        sep = separador
        if sep is None:
            # Inferencia automática sobre las primeras 4096 bytes del texto
            try:
                import csv as _csv
                muestra = texto[:4096]
                dialectos = _csv.Sniffer().sniff(muestra, delimiters=",;\t|")
                sep = dialectos.delimiter
            except Exception:
                sep = ","  # fallback seguro

        try:
            df = pd.read_csv(
                io.StringIO(texto),
                sep=sep,
                low_memory=False,
                on_bad_lines="warn",
            )
            if df.shape[1] < 2:
                # Probablemente el separador no fue el correcto
                for sep_alt in SEPARADORES_CANDIDATOS:
                    if sep_alt == sep:
                        continue
                    try:
                        df_alt = pd.read_csv(
                            io.StringIO(texto),
                            sep=sep_alt,
                            low_memory=False,
                            on_bad_lines="warn",
                        )
                        if df_alt.shape[1] > df.shape[1]:
                            df = df_alt
                    except Exception:
                        pass
            return df
        except Exception as exc:
            ultimo_error = exc

    raise ValueError(
        f"No se pudo leer el CSV con ninguna codificación conocida. "
        f"Último error: {ultimo_error}"
    )


def _leer_excel(contenido: bytes, hoja: int | str = 0) -> pd.DataFrame:
    """Carga un archivo Excel desde bytes."""
    try:
        df = pd.read_excel(
            io.BytesIO(contenido),
            sheet_name=hoja,
            engine="openpyxl",
        )
        return df
    except Exception as exc:
        raise ValueError(f"No se pudo leer el archivo Excel: {exc}") from exc


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def cargar_archivo(
    archivo: ArchivoEntrada,
    separador: str | None = None,
    hoja_excel: int | str = 0,
) -> pd.DataFrame:
    """
    Carga un archivo CSV o Excel y retorna un DataFrame de Pandas.

    Parámetros
    ----------
    archivo : str | Path | file-like
        Ruta al archivo local, o un objeto con método .read() (ej. st.file_uploader).
    separador : str | None
        Separador de columnas para CSV. Si es None se intenta detectar automáticamente.
    hoja_excel : int | str
        Nombre o índice de la hoja Excel (por defecto la primera hoja).

    Retorna
    -------
    pd.DataFrame
        DataFrame con los datos cargados, sin ninguna modificación posterior.

    Lanza
    -----
    ValueError
        Si el formato no es reconocido, el archivo está vacío o no puede leerse.
    """
    nombre = _detectar_nombre(archivo)
    ext = _extension(nombre)

    # --- Leer bytes crudos ---
    if isinstance(archivo, (str, Path)):
        ruta = Path(archivo)
        if not ruta.exists():
            raise FileNotFoundError(f"El archivo no existe: {ruta}")
        contenido = ruta.read_bytes()
    elif hasattr(archivo, "read"):
        # st.file_uploader / BytesIO / etc.
        contenido = archivo.read()
        # Regresar el puntero al inicio para uso posterior
        if hasattr(archivo, "seek"):
            archivo.seek(0)
    else:
        raise TypeError(f"Tipo de archivo no soportado: {type(archivo)}")

    if len(contenido) == 0:
        raise ValueError("El archivo está vacío.")

    # --- Despachar según extensión ---
    if ext in EXTENSIONES_EXCEL:
        df = _leer_excel(contenido, hoja=hoja_excel)
    elif ext in EXTENSIONES_CSV or ext == "":
        df = _leer_csv_con_fallback(contenido, separador=separador)
    else:
        # Intento genérico como CSV
        try:
            df = _leer_csv_con_fallback(contenido, separador=separador)
        except ValueError:
            raise ValueError(
                f"Extensión '{ext}' no reconocida. "
                "Soportados: .csv, .tsv, .txt, .xlsx, .xls, .xlsm"
            )

    if df.empty:
        raise ValueError("El archivo fue leído pero no contiene datos.")

    return df


def obtener_resumen_fuente(df: pd.DataFrame) -> dict:
    """
    Genera un resumen técnico del DataFrame recién cargado.

    Retorna
    -------
    dict con claves:
        filas          - int: número de filas
        columnas       - int: número de columnas
        nombres_cols   - list[str]: lista de nombres de columnas
        memoria_mb     - float: uso de memoria en MB (deep=True)
        tipos          - dict[str, str]: {columna: dtype_str}
    """
    return {
        "filas": int(df.shape[0]),
        "columnas": int(df.shape[1]),
        "nombres_cols": df.columns.tolist(),
        "memoria_mb": round(df.memory_usage(deep=True).sum() / 1_048_576, 4),
        "tipos": {col: str(df[col].dtype) for col in df.columns},
    }

