# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/Device_Manager_v57.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.57`

## Que corrige la 1.57

- Carga automaticamente el siguiente serial disponible desde GitHub en `RTU`, `GW`, `I-TIC` y `TIC12`.
- Quita los botones manuales de “usar siguiente serial GitHub” en las secciones operativas.
- La pestaña `Serial` deja solo botones para guardar un valor por familia o todos los valores.
- Los guardados manuales en GitHub ahora piden contraseña.
- Publicacion del nuevo ejecutable `Device_Manager_v57.exe`.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
