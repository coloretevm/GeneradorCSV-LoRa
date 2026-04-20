# GeneradorCSV-LoRa

Este repositorio contiene:

- `generador_csv.py`: codigo fuente principal de la aplicacion.
- `update_manifest.json`: manifiesto usado por la actualizacion automatica.
- `downloads/Device_Manager_v45.exe`: ejecutable oficial actual.
- `publish_update.bat`: script para publicar nuevas versiones.

## Version actual

- `1.45`

## Que corrige la 1.45

- Cambio de nombre a `Device Manager`.
- Nueva pestaña `Serial` despues de `FW Version`.
- Descarga de `Hyperterminal.zip` desde la pestaña `Serial`.
- Descarga de `APP_BLE_SERIAL__25_01_2026_wx.zip` desde la pestaña `Serial`.
- Comando de apagado para `X4S LTE` al inicio de la pestaña `GW`.
- Publicacion del nuevo ejecutable `Device_Manager_v45.exe`.

## Actualizacion automatica

El programa consulta este manifiesto:

- `https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json`

Y descarga la ultima version publicada desde la carpeta `downloads/`.
