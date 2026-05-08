# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/Device_Manager_v56.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.56`

## Que corrige la 1.56

- Corrige los textos rotos de la pestaña `Language`.
- Usa etiquetas simples para los idiomas y deja estable el nombre de la pestaña.
- Mantiene el soporte del registro serial por internet desde GitHub.
- Publicacion del nuevo ejecutable `Device_Manager_v56.exe`.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
