# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/Device_Manager_v55.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.55`

## Que corrige la 1.55

- El registro serial ya no depende de una carpeta local del repo en cada PC.
- La lectura del siguiente serial se hace directamente desde GitHub por internet.
- La escritura del nuevo serial se hace por la API de GitHub con token configurable en la pestaña `Serial`.
- Publicacion del nuevo ejecutable `Device_Manager_v55.exe`.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
