# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/Device_Manager_v73.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.73`

## Que corrige la 1.73

- Tras `Salva valore ...` o `Salva tutti i valori` en `Serial`, las pestañas `RTU`, `GW`, `I-TIC` y `TIC12` refrescan enseguida el siguiente serial disponible de GitHub.
- El mismo refresco automatico ocurre despues de generar etiquetas o proyectos que actualizan el registro seriale.
- Publicacion del nuevo ejecutable `Device_Manager_v73.exe`.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
