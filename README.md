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

```bash
python -m venv .venv
