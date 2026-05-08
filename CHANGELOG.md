# Changelog

## 1.56

- Corretti i testi corrotti nella scheda `Language`.
- Le opzioni lingua usano etichette semplici e stabili: `ES Espanol`, `EN English`, `IT Italiano`.
- Sistemato anche il nome della scheda `Language` nella barra principale.
- Nuova build ufficiale pubblicata come `Device_Manager_v56.exe`.

## 1.55

- Il registro seriale non dipende piu dalla cartella locale del repository.
- Lettura dei seriali via URL RAW GitHub, quindi `Usa il prossimo seriale GitHub` funziona anche sugli altri PC.
- Scrittura dei nuovi seriali via API GitHub con token configurabile nella scheda `Serial`.
- Nuova build ufficiale pubblicata come `Device_Manager_v55.exe`.

## 1.54

- Aggiunto `GW` al registro seriali condiviso su GitHub.
- Nella scheda `Gateway` c e ora il pulsante per usare il prossimo seriale GitHub quando aggiungi un nuovo gateway.
- Alla generazione del PDF Gateway il programma controlla seriali numerici, evita duplicati e aggiorna l ultimo seriale `GW` nel registro.
- Nuova build ufficiale pubblicata come `Device_Manager_v54.exe`.

## 1.53

- URL del manifest GitHub integrata di default dentro l applicazione.
- Se manca `update_settings.json`, il programma sa comunque dove controllare gli aggiornamenti.
- Nuova build ufficiale pubblicata come `Device_Manager_v53.exe`.

## 1.52

- L aggiornamento ora chiede dove salvare il nuovo EXE.
- Dopo il download, il programma attuale si chiude e apre automaticamente il nuovo EXE scelto.
- Nuova build ufficiale pubblicata come `Device_Manager_v52.exe`.

## 1.51

- Corregido el updater de Windows para reintentar el reemplazo del EXE actual varias veces.
- Si el reemplazo falla, ahora se abre igualmente el EXE descargado para que la actualizacion no quede bloqueada.
- Nueva build oficial publicada como `Device_Manager_v51.exe`.

## 1.50

- Corregida la carga del logo Tecnidro en las etiquetas `TIC12` e `I-TIC`.
- Añadido respaldo automatico entre `logo.png` y `gw_logo_tecnidro.png`.
- Nueva build oficial preparada como `Device_Manager_v50.exe`.

## 1.49

- La actualizacion ahora descarga la nueva version con ventana `Guardar como...` en lugar de intentar reemplazar el exe en uso.
- Nueva build oficial preparada como `Device_Manager_v49.exe`.

## 1.48

- URL del manifest de actualizacion precargada por defecto en la aplicacion.
- Ajuste del sistema de updates para evitar que vuelva a abrir la v47 al buscar actualizaciones.
- Nueva build oficial publicada como `Device_Manager_v48.exe`.

## 1.47

- Nueva pestana `Manuali` con secciones `RTU`, `Gateway`, `I-TIC` y `TIC12`.
- Manuales, `fw`, `Hyperterminal.zip` y `APP_BLE_SERIAL__25_01_2026_wx.zip` integrados en la build oficial.
- Interfaz de `Manuali` simplificada, dejando solo los botones de descarga.
- Nueva build oficial publicada como `Device_Manager_v47.exe`.

## 1.46

- Idioma por defecto cambiado de espanol a italiano al abrir el programa.
- Nueva build oficial publicada como `Device_Manager_v46.exe`.
- Codigo Python y manifiesto de actualizacion sincronizados con la version 1.46.

## 1.45

- Cambio de nombre visual y de build a `Device Manager`.
- Nueva pestaña `Serial` añadida despues de `FW Version`.
- `Serial` incluye descarga/exportacion de `Hyperterminal.zip`.
- `Serial` incluye descarga/exportacion de `APP_BLE_SERIAL__25_01_2026_wx.zip` para `Terminal Antonio (RTU Bluetooth e LORACONT)`.
- `Gateway` añade al inicio el comando de apagado de `X4S LTE` con boton para copiarlo.
- El ejecutable oficial publicado pasa a ser `Device_Manager_v45.exe`.

## 1.43

- RTU con Bluetooth: eliminada una fila de etiquetas por pagina y rejilla centrada en A4.
- RTU sin Bluetooth: eliminada una fila de etiquetas por pagina y rejilla centrada en A4.
- RTU LORACONT: eliminada una fila de etiquetas por pagina y rejilla centrada en A4.
- RTU LORACONT: logo corregido para imprimirse en negro.
- RTU en tubo: eliminada una fila de etiquetas por pagina y rejilla centrada en A4.
