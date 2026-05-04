# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/Device_Manager_v51.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.51`

## Que corrige la 1.51

- Updater de Windows reforzado para reintentar el reemplazo del EXE actual.
- Si el reemplazo falla, se abre igualmente el EXE descargado.
- Publicacion del nuevo ejecutable `Device_Manager_v51.exe`.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
