# ✨ DataCleaner Studio

**Plataforma de Inspección, Limpieza Asistida y Visualización de Datasets** construida con Python, Streamlit, Pandas, NumPy y Plotly.

---

## 🚀 Características Principales

* **Arquitectura en Capas:** Estricta separación entre la interfaz de usuario ([`app.py`](app.py)) y la lógica de negocio desacoplada en [`services/`](services/).
* **Diagnóstico con Evidencia:** Detecta valores faltantes, duplicados exactos o por clave, inconsistencias de texto y outliers estadísticos (IQR y Z-Score) permitiendo inspeccionar exactamente las filas afectadas antes de modificarlas.
* **Limpieza Asistida y Controlada:** Deduplicación, imputación inteligente (media, mediana, moda, constante, eliminación), normalización de cadenas (minúsculas, trim, remoción de tildes) y tratamiento de outliers (filtrado, recorte/winsorización o marcado).
* **Trazabilidad e Inmutabilidad:** Historial cronológico de cambios con opción de restauración total del dataset original.
* **Exploración Visual (EDA):** Gráficos interactivos de distribución con curvas KDE, rankings de barras, diagramas de dispersión, boxplots y mapas de calor de correlación usando una paleta en colores pasteles.
* **Exportación Segura:** Descarga del dataset limpio en CSV (con codificación `utf-8-sig` compatible con Excel) o formato `.xlsx`.

---

## 📂 Estructura del Proyecto

```text
├── app.py                      # Capa Frontend: Interfaz Streamlit con diseño pastel y navegación superior
├── requirements.txt            # Dependencias del proyecto
├── GUIA_ESTUDIO.md             # Documento de estudio teórico y explicación técnica detallada
├── Infoapp.md                  # Especificación de requisitos y arquitectura
├── .gitignore                  # Exclusiones de Git (.venv, __pycache__, etc.)
├── services/                   # Capa Backend / Lógica de Negocio
│   ├── __init__.py
│   ├── data_loader.py          # Ingesta robusta de CSV y Excel con autodetección de encodings y separadores
│   ├── quality_service.py      # Diagnóstico puro, perfilado general y detección de anomalías
│   ├── cleaning_service.py     # Motor de transformación inmutable y serialización
│   └── chart_service.py        # Generación de visualizaciones interactivas con Plotly Express
└── top_15000_anime.csv         # Dataset de prueba / ejemplo
```

---

## 🛠️ Instalación y Uso

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/Nagi-Ayanokoji/mineria.git
   cd mineria
   ```

2. **Crear y activar un entorno virtual (recomendado):**
   ```bash
   python -m venv .venv
   # En Windows:
   .venv\Scripts\activate
   # En Linux / Mac:
   source .venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Ejecutar la aplicación:**
   ```bash
   streamlit run app.py
   ```
   Abre tu navegador en `http://localhost:8501`.
