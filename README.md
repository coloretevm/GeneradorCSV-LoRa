# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/Device_Manager_v58.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.58`

## Que corrige la 1.58

- Oculta los campos tecnicos de configuracion en la pestaña `Serial`.
- Si falta el token de GitHub, lo pide solo cuando realmente hace falta guardar.
- Corrige el titulo de ventana `Device Manager - TECNIDRO`.
- Limpia la vista previa de estructura del proyecto para que no salga texto roto.
- Publicacion del nuevo ejecutable `Device_Manager_v58.exe`.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
