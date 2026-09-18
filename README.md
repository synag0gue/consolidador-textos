# Consolidador de Textos

Aplicación MVP para Windows que permite consolidar textos desde múltiples archivos en un único archivo final.

## Características

- Selección múltiple de archivos.
- Procesamiento de carpetas completas.
- Soporte inicial para:
  - `.txt`
  - `.docx`
  - `.pdf`
- Arquitectura extensible para agregar nuevos formatos.
- Reordenamiento de archivos:
  - botones ↑ / ↓
  - drag & drop en la lista
- Separadores configurables:
  - línea en blanco simple
  - línea de guiones `---`
  - nombre del archivo como encabezado
  - separador personalizado
- Vista previa en tiempo real.
- Eliminación de archivos individuales antes de guardar.
- Los archivos originales nunca se modifican.
- Historial de carpetas recientes.
- Modo claro y oscuro.
- Log/reporte de archivos omitidos o corruptos.
- Guardado final en:
  - `.txt`
  - `.docx`

## Requisitos

- Windows 10/11
- Python 3.10 o superior

## Instalación

1. Abrir una terminal en la carpeta del proyecto.
2. Crear un entorno virtual:

##  Uso
Pasos
Desde la carpeta del proyecto:
bash
1  python -m venv .venv
Activar el entorno virtual:
bash
1  .venv\Scripts\activate
Instalar dependencias:
bash
1  pip install -r requirements.txt
Ejecutar la aplicación:
bash
1  python run.py

```bash
python -m venv .venv
```

## Ejecutable de Windows

Para usuarios sin Python, el proyecto incluye `consolidador.spec`:

```bash
pip install pyinstaller
pyinstaller consolidador.spec --noconfirm
```

El resultado es `dist/ConsolidadorTextos.exe` (~70 MB, un solo archivo,
sin consola). Las funciones opcionales que requieren programas externos
(Tesseract) u opcionales pesados (EasyOCR) no van incluidas: se detectan
en ejecución si están disponibles.

## Automatización (CLI)

Sin interfaz gráfica:

```bash
python -m src.cli merge ./docs -o out.docx --separator filename --recursive
python -m src.cli run receta.yaml --overwrite
python -m src.cli handoff ./docs -o ./paquete-ia
```

Ver `docs/PLAN.md` (arquitectura) y `docs/RECIPES.md` (recetas por rol).
