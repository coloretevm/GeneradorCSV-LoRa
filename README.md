# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/Device_Manager_v54.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.54`

## Que corrige la 1.54

- `GW` entra tambien en el registro serial compartido de GitHub.
- La pestaña `Gateway` puede sugerir el siguiente serial GitHub al crear un nuevo gateway.
- Al generar el PDF `GW`, el programa valida duplicados y actualiza el ultimo serial usado.
- Publicacion del nuevo ejecutable `Device_Manager_v54.exe`.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
