# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/GeneradorCSV_LoRa_v43.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.43`

## Que corrige la 1.43

- Ajuste de etiquetas RTU con Bluetooth: una fila menos y centrado en A4.
- Ajuste de etiquetas RTU sin Bluetooth: una fila menos y centrado en A4.
- Ajuste de etiquetas RTU LORACONT: una fila menos y centrado en A4.
- Correccion del logo de LORACONT para que salga en negro.
- Ajuste de etiquetas RTU en tubo: una fila menos y centrado en A4.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
