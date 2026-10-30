
ha## 1. Visión General del Proyecto

### ¿Qué problema resuelve?
En ciencia de datos existe la máxima *"Garbage In, Garbage Out"* (Si entra basura, sale basura). Un modelo de Machine Learning o un reporte de Business Intelligence construido sobre datos duplicados, con valores nulos mal manejados o formatos inconsistentes, generará conclusiones erróneas.

### Filosofía Pedagógica
La aplicación sigue un flujo estricto y transparente:
$$\text{Cargar} \longrightarrow \text{Perfilar} \longrightarrow \text{Evidenciar} \longrightarrow \text{Corregir} \longrightarrow \text{Revalidar} \longrightarrow \text{Graficar} \longrightarrow \text{Exportar}$$

* **Diagnóstico con Evidencia:** Nunca dice solamente *"hay 10 errores"*; permite inspeccionar la tabla exacta de filas afectadas.
* **Limpieza Asistida:** Ningún cambio se ejecuta en segundo plano de manera automática; el usuario decide la estrategia y confirma.
* **Trazabilidad:** Cada cambio queda registrado cronológicamente para saber exactamente qué se modificó.

---

## 2. Arquitectura de Software: Capas Desacopladas

Aunque todo el sistema corre bajo el servidor de **Streamlit** en Python, el código está estrictamente dividido en dos capas:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CAPA DE PRESENTACIÓN (FRONTEND)                  │
│                                app.py                                  │
│  - Widgets interactivos (botones, sliders, selectores, file uploader)  │
│  - Gestión del estado en memoria (st.session_state)                    │
│  - Estilos visuales pasteles, glassmorphism y transiciones CSS         │
│  - Menú superior por pestañas (st.tabs)                                │
│  - Renderizado de tablas y gráficos interactivos                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Invoca funciones puras
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        CAPA DE SERVICIOS (BACKEND)                     │
│                                services/                               │
│                                                                        │
│   ├── data_loader.py      -> Ingesta segura, encodings y formatos      │
│   ├── quality_service.py  -> Auditoría pura y detección de anomalías   │
│   ├── cleaning_service.py -> Transformación inmutable de datos         │
│   └── chart_service.py    -> Construcción de gráficos con Plotly       │
└────────────────────────────────────────────────────────────────────────┘
```

### ¿Por qué esta separación?
1. **Mantenibilidad:** Si mañana cambias Streamlit por una API REST (FastAPI) o una app de escritorio, la carpeta `services/` no cambia ni una sola línea de código.
2. **Pruebas y Robustez:** Los servicios no dependen de la interfaz gráfica, por lo que se pueden probar de forma aislada con scripts o tests unitarios.
3. **Principio de Responsabilidad Única (SRP):** Cada archivo tiene un trabajo claro y delimitado.

---

## 3. Desglose del Backend Módulo por Módulo (`services/`)

### 3.1. `services/data_loader.py` (Ingesta Segura)
* **Objetivo:** Leer archivos de datos sin que la aplicación se caiga por problemas de formato o codificación.
* **Mecanismos clave:**
  * **Fallback de Codificación:** Prueba secuencialmente `utf-8`, `utf-8-sig`, `latin-1` y `cp1252`. Si un CSV viene de un Excel en español (con tildes o eñes codificadas en Latin-1), el módulo lo detecta y lo lee sin corromper caracteres.
  * **Inferencia de Separadores:** Usa la clase `csv.Sniffer` para detectar si el separador es coma (`,`), punto y coma (`;`), tabulador (`\t`) o pleca (`|`). Si el usuario sube un CSV europeo delimitado por `;`, lo interpreta correctamente.
  * **Soporte Excel:** Usa el motor `openpyxl` para leer hojas `.xlsx` y `.xls`.
  * **Lectura Polimórfica:** Acepta tanto rutas de archivo locales (`str`, `Path`) como buffers en memoria generados por `st.file_uploader` (`io.BytesIO`).

---

### 3.2. `services/quality_service.py` (Perfilado y Auditoría)
* **Objetivo:** Inspeccionar el dataset y emitir un diagnóstico completo. **Nunca modifica los datos (funciones de solo lectura).**
* **Funciones destacadas:**
  * `perfilar_dataset(df)`: Calcula métricas globales: dimensiones, porcentaje total de celdas vacías, conteo de nulos por columna, filas duplicadas, tipos de datos detectados y memoria RAM en MB.
  * `detectar_problemas(df)`: Retorna un diccionario donde cada clave es el tipo de problema y cada valor es un **DataFrame que contiene únicamente las filas problemáticas**:
    * **Faltantes:** Filas que tienen `NaN` en una columna concreta.
    * **Duplicados:** Filas exactamente idénticas o duplicadas por clave.
    * **Inconsistencias de texto:** Detecta espacios en blanco accidentales (`" Bogotá "`) y diferencias por mayúsculas/minúsculas (`"bogota"` vs `"BOGOTA"`).
  * **Detección de Outliers Estadísticos:**
    * **Método IQR (Rango Intercuartílico):**
      $$IQR = Q_3 - Q_1$$
      $$\text{Límite Inferior} = Q_1 - 1.5 \times IQR$$
      $$\text{Límite Superior} = Q_3 + 1.5 \times IQR$$
      Es un método robusto porque no se ve afectado por valores extremos (a diferencia de la media).
    * **Método Z-Score:** Mide a cuántas desviaciones estándar ($\sigma$) se encuentra un punto respecto a la media ($\mu$):
      $$z = \frac{x - \mu}{\sigma}$$
      Si $|z| > 3$, el registro se clasifica como outlier estadístico.

---

### 3.3. `services/cleaning_service.py` (Motor de Transformación)
* **Objetivo:** Aplicar las correcciones confirmadas por el usuario.
* **Principio de Inmutabilidad:** Toda función recibe un DataFrame y hace `df.copy()`. Nunca altera la variable original directamente en memoria.
* **Operaciones disponibles:**
  * `eliminar_duplicados()`: Permite eliminar duplicados exactos o definir columnas clave (ej. `anime_id`), eligiendo si conservar la primera ocurrencia (`first`) o la última (`last`).
  * `imputar_faltantes()`: Ofrece 5 estrategias de tratamiento de nulos:
    1. *Eliminar:* Borra las filas que tengan nulo en esa columna.
    2. *Media:* Rellena con el promedio aritmético (solo numéricas).
    3. *Mediana:* Rellena con el percentil 50 (recomendado si hay outliers).
    4. *Moda:* Rellena con el valor más repetido (ideal para categorías/texto).
    5. *Valor fijo:* Rellena con una constante personalizada (ej. `"Desconocido"` o `0`).
  * `normalizar_textos()`: Utiliza `unicodedata.normalize("NFD", texto)` para remover tildes y diacríticos, aplica `.str.strip()` para eliminar espacios sobrantes y `.str.lower()` para estandarizar a minúsculas.
  * `filtrar_o_recortar_outliers()`:
    * *Filtrar:* Descarta las filas fuera de los límites.
    * *Recortar (Winsorización):* Aplica `df[col].clip(lim_inf, lim_sup)` para comprimir los extremos sin perder la fila.
    * *Marcar:* Crea una nueva columna booleana (ej. `score__outlier = True/False`).
  * `exportar_csv()`: Codifica con `utf-8-sig` (UTF-8 con Byte Order Mark). Esto garantiza que Microsoft Excel en Windows abra el CSV reconociendo automáticamente tildes, caracteres especiales y eñes sin desconfigurarse.

---

### 3.4. `services/chart_service.py` (Visualización Interactiva)
* **Objetivo:** Construir objetos de visualización interactiva usando **Plotly Express** y **Plotly Graph Objects**.
* **Diseño Visual:** Emplea una paleta pastel coordinada:
  * Azul lavanda (`#B5C8E8`)
  * Menta suave (`#A8D8C8`)
  * Durazno (`#F2C9B0`)
  * Lavanda (`#D5B8E0`)
  * Rosa blush (`#F4A8B5`)
* **Gráficos disponibles:**
  * *Distribución:* Histograma con curva de densidad KDE calculada con `scipy.stats.gaussian_kde` y boxplot marginal.
  * *Barras Top N:* Rankings con agregaciones configurables (`sum`, `mean`, `count`).
  * *Dispersión (Scatter):* Cruce entre dos variables continuas con mapa de color por categoría.
  * *Boxplots:* Diagrama de cajas y bigotes para visualizar cuartiles, medianas y puntos atípicos.
  * *Matriz de Correlación:* Heatmap interactivo de coeficientes de Pearson.
  * *Gráfico Comparativo:* Gráfica de barras dobles (Antes vs. Después) para ver cómo bajaron los errores.

---

## 4. Desglose del Frontend (`app.py`)

### 4.1. Estilos y Microinteracciones (CSS Pastel)
En la parte superior de `app.py` se inyecta un bloque de CSS moderno mediante `st.markdown(PASTEL_CSS, unsafe_allow_html=True)`:
* **Glassmorphism:** Las tarjetas utilizan `background: rgba(255, 255, 255, 0.82)` con `backdrop-filter: blur(12px)`.
* **Transiciones fluidas:** Todos los botones y tarjetas responden con `transition: all 0.28s cubic-bezier(0.4, 0, 0.2, 1)`, logrando una elevación suave (*hover lift*) al pasar el cursor.
* **Menú Superior:** Se estilizan las pestañas nativas de Streamlit (`div[data-baseweb="tab-list"]`) como píldoras redondeadas horizontales, eliminando la necesidad de una barra lateral pesada.

### 4.2. Gestión del Estado (`st.session_state`)
Streamlit re-ejecuta todo el script de arriba a abajo cada vez que el usuario interactúa con un control. Para no perder los datos entre clics, se utiliza el estado de sesión:
* `st.session_state.df_original`: Fotografía intacta del dataset al momento de cargarse. Permite restaurar el archivo en cualquier momento.
* `st.session_state.df_actual`: El dataset activo que va recibiendo las transformaciones de limpieza.
* `st.session_state.historial`: Lista de cadenas de texto con la bitácora de cambios (ej. `["Eliminadas 10 filas duplicadas", "Imputados nulos en 'score'"]`).
* `st.session_state.snapshot_metricas_inicio`: Métricas de salud iniciales para calcular deltas de mejora en la pestaña de comparativa.

### 4.3. Las 7 Pestañas del Flujo de Trabajo
1. **📂 1. Ingesta:** Carga de CSV/Excel por drag & drop o mediante el botón de carga rápida para `top_15000_anime.csv`. Muestra vista previa (primeras 10, últimas 10 o muestra aleatoria).
2. **🔎 2. Diagnóstico:** 5 tarjetas KPI pasteles con totales, porcentaje global de nulos con semáforo de color y tabla detallada por columna.
3. **⚠️ 3. Evidencia:** Detección automática de anomalías y expanders (`st.expander`) donde el usuario puede desplegar y examinar las filas exactas que fallan.
4. **🧹 4. Limpieza:** 4 sub-paneles (Duplicados, Faltantes, Texto y Outliers) con botones de confirmación y opción para restaurar el dataset original.
5. **🔄 5. Comparativa:** Tarjetas con deltas numéricos (ej. `Faltantes: -45`), gráfica interactiva Antes vs. Después y línea de tiempo del historial.
6. **📊 6. Gráficos:** Módulo EDA interactivo para generar histogramas, barras, dispersión, boxplots y mapas de calor.
7. **💾 7. Exportar:** Auditoría final del dataset limpio y descarga directa en `.csv` (UTF-8 BOM) o `.xlsx`.

---

## 5. Conceptos Clave para Sustentar el Proyecto

| Concepto | ¿Por qué se implementó así? |
| :--- | :--- |
| **Arquitectura Desacoplada** | `app.py` solo dibuja; la lógica matemática y de datos está en `services/`. Esto evita el código espagueti. |
| **Inmutabilidad (`df.copy()`)** | Evita el error clásico de Pandas `SettingWithCopyWarning` y permite deshacer cambios fácilmente. |
| **IQR vs Desviación Estándar** | En distribuciones con sesgo o colas pesadas, la media y la desviación se distorsionan por los mismos valores extremos. El IQR se basa en cuartiles, haciéndolo mucho más confiable. |
| **Limpieza Asistida (Human-in-the-loop)** | No todos los outliers son errores: un anime con puntuación 9.3 o una venta de \$10,000,000 puede ser un caso real legítimo. Borrar automáticamente arruina el análisis. |
| **Codificación `utf-8-sig`** | Si descargas un CSV con tildes y lo abres en Excel en Windows, Excel asume ANSI/Windows-1252 a menos que detecte el BOM (`\xef\xbb\xbf`), lo que corrompería las palabras si se guardara con UTF-8 simple. |

---

## 6. Comandos de Operación

### Iniciar la aplicación
```powershell
python -m streamlit run app.py
```

### Probar importaciones del backend desde consola
```powershell
python -c "import services.data_loader, services.quality_service, services.cleaning_service, services.chart_service; print('Servicios OK')"
```

