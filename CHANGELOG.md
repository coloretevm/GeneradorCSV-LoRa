# Changelog

## 1.128 - 05/11/2026

- Nuova interfaccia guidata con foto dei sei prodotti e scelta Dispositivo, Operazione, Dati e Riepilogo.
- Pulsante Menu precedente sempre visibile, ritorno ai menu senza perdere i dati e pulsanti Apri dispositivo nelle schede prodotto.
- Ripristinate le icone Firmware, Manuali, Terminali e Impostazioni. Temi chiaro/scuro e testi italiano, spagnolo e inglese.
- RTU: varianti Bluetooth, senza Bluetooth, in tubo e NBIoT. RTU e LORACONT mantengono progetto completo oppure CSV Nodi, JSON ed etichette separati, senza Strumenti avanzati.
- NBIoT: disponibile soltanto Prepara firmware, PIC24FJ128GL306, file pic24_Radio_NBIOT_2CH.Xver_1.6_02.11.2026.production.hex integrato e verificato.
- Gateway: solo etichette e comando di spegnimento X4S LTE da copiare; nessuna esecuzione automatica del comando.
- I-TIC: scelta REV6/REV4, etichette, firmware della revisione selezionata e manuali utente.
- TIC12: scelta AC/DC, etichette, firmware filtrati AC/DC e manuale utente.
- Istantaneo: scelta Nuovo/Vecchio, etichette 100L/1000L e relativi firmware; nessuna voce manuale.
- LORACONT: documentazione denominata Guida di installazione, con le due guide di collegamento esistenti.
- Firmware riorganizzati per dispositivo in righe compatte con nome, versione e PIC. La biblioteca usa due colonne quando lo spazio lo permette; verde soltanto il pulsante PIC cliccato.
- Anteprima PDF integrata prima della generazione, senza consumare seriali; finestra dedicata per aprire i documenti e salvare una copia. Visualizzatore PDF incluso nell'exe.
- Conservati i generatori e i formati CSV/JSON/PDF, gli adesivi batteria e QR, i contatori GitHub e l'aggiornamento automatico. I registri esistenti non vengono modificati dalla pubblicazione.
- Lettura iniziale dei seriali in background, apertura dei moduli solo al bisogno e dimensioni finestra adattate alla scala DPI dello schermo.
- Nuove prove automatiche su percorsi, varianti, firmware, ritorno ai menu, mantenimento dei dati, icone, traduzioni e anteprime senza prenotazione dei seriali.
- Nuovo eseguibile: Device_Manager_v128.exe.

## 1.127 - 05/11/2026

- Nuova sezione Istantaneo: selezione 100L / 1000L e modello approvato con Misuratore di Portata su due righe e campo Versione. Fino a 36 etichette da 50 mm per A4.
- Un adesivo batteria separato da 15 x 15 mm per ogni Istantaneo stampato, anche nei fogli incompleti.
- Istantaneo 100L e 1000L condividono lo stesso contatore: ultimo usato iniziale 0, primo seriale disponibile 0001. Aggiornamento automatico dopo la generazione e correzione con password nella scheda Serial.
- Registro Istantaneo in serial_registry_istantaneo.json, separato per evitare che i client precedenti cancellino il nuovo contatore. I contatori esistenti non vengono azzerati.
- LORACONT ha una sezione dedicata subito sotto RTU con Progetto, CSV, JSON ed Etichette. Rimosse le scelte LORACONT dai moduli RTU.
- LORACONT mantiene modello 297, nessuna valvola, numvalves 0, ADC 0/1 e contatori 0/1. RTU mantiene modello 210 e le varianti senza Bluetooth, Bluetooth e tubo.
- RTU e LORACONT conservano il contatore seriale RTU gia in uso e la serie indirizzi progetto condivisa. La separazione della navigazione non duplica i seriali esistenti.
- Gateway: intestazione approvata con quattro celle separate da linee per logo Tecnidro, LoRaWAN / HYDRONET, Gateway LTE e simbolo batteria integrato alle dimensioni originali.
- Caricamento dei moduli al primo utilizzo invece di costruire tutti i formulari all'avvio. Menu laterale scorrevole per raggiungere tutte le sezioni.
- Nuove voci tradotte in italiano, inglese e spagnolo; italiano predefinito. Conservati firmware, manuali e fogli adesivi della v126.
- Superati 27 test su interfaccia, generazione CSV/JSON/progetti, PDF completi e parziali, contatori e aggiornamenti.
- Nuovo eseguibile: Device_Manager_v127.exe.

## 1.126 - 05/11/2026

- I-TIC: etichette orientate tutte nello stesso verso, QR del manuale centrato sotto l'etichetta e adesivi batteria separati alla fine di ogni pagina. Fino a 21 dispositivi per A4.
- TIC12: etichetta dispositivo, QR manuale e adesivo batteria tutti separati. QR da 15 mm in un riquadro da 18 x 20 mm con testo Manual ITA-ENG. Fino a 27 dispositivi per A4.
- RTU Bluetooth, RTU senza Bluetooth, RTU in tubo e LoraCont: un adesivo batteria indipendente da 15 x 15 mm per ogni dispositivo presente nella pagina, mantenendo le dimensioni originali delle etichette.
- Quantita esatte anche per fogli incompleti: 5 dispositivi producono 5 adesivi. Gli adesivi e i QR non consumano numeri seriali.
- Nuova sezione Manuali > Fogli adesivi con i PDF originali QR Manuale TIC12, QR Manuale I-TIC e Sticker batteria, tutti inclusi nell'eseguibile.
- Calcolo delle pagine aggiornato e nuove voci tradotte in italiano, inglese e spagnolo.
- Verificati i modelli con fogli completi, singole etichette e pagine finali parziali. Preparato il manifest con dimensione e SHA-256 per aggiornare dalla v125.
- Nuovo eseguibile: Device_Manager_v126.exe.

## 1.125 - 29/10/2026

- Controllo aggiornamenti GitHub in background, senza bloccare la finestra.
- Dopo la conferma, download del nuovo exe nella stessa cartella con indicatore di avanzamento.
- Verifica dimensione, checksum SHA-256 quando presente nel manifest e formato del file Windows prima dell'installazione.
- Avvio automatico del nuovo programma ed eliminazione del vecchio exe solo dopo la conferma di avvio della nuova versione. In caso di errore, il vecchio exe viene conservato.
- Corretta la lettura dei manifest JSON con codifica UTF-8 BOM.
- Inclusi i contenuti delle versioni locali precedenti: ValveStatus e Motor Duration in JSON/Progetto, indirizzo RTU disponibile, Terminal Antonio del 22/06/2026, firmware LoraCont 1.0.6 INFO e TRACE, nuovo manuale TIC12 e sei firmware RST per Instantaneo Nuovo (10/100/1000 L e 10/100/1000 Gal AF Med).
- Pubblicati il codice Python aggiornato, il modulo di aggiornamento e i test. I file di credenziali esterni restano esclusi dai sorgenti.
- Nuovo eseguibile: Device_Manager_v125.exe.

## 1.114

- Aggiunto nella sezione I-TIC il promemoria di collegamento del solenoide bistabile 12v DC con Cavo Rosso - V1_C e Cavo Nero - V1_O.
- Allineati nel repository i contenuti fw e manuali usati per la build distribuita.
- Nuova build ufficiale pubblicata come Device_Manager_v114.exe.

## 1.109

- Corretta la scheda `FW Version`: i pulsanti PIC della colonna destra tornano blu scuro per default e diventano verdi solo quando vengono cliccati.
- I pulsanti firmware restano celesti senza piu essere sovrascritti dal tema globale dell applicazione.
- Aggiornato il firmware `RTU LORACONT` al file `CONTATORE_REL.1.0.2_REV2.18.05.2026.production.hex`.
- Nuova build ufficiale pubblicata come `Device_Manager_v109.exe`.
## 1.73

- Dopo `Salva valore ...` o `Salva tutti i valori` nella scheda `Serial`, le sezioni `RTU`, `GW`, `I-TIC` e `TIC12` aggiornano subito il prossimo seriale disponibile da GitHub senza riavviare l app.
- Lo stesso refresh automatico avviene anche dopo la generazione di PDF o progetti che aggiornano il registro seriali.
- Nuova build ufficiale pubblicata come `Device_Manager_v73.exe`.

## 1.58

- Nascosti i campi tecnici della scheda `Serial` che non servono all uso quotidiano.
- Il salvataggio manuale continua a funzionare e, se manca il token, lo chiede solo al momento del salvataggio.
- Corretto il titolo finestra `Device Manager - TECNIDRO`.
- Ripulita la vista struttura del progetto con testo ASCII semplice.
- Nuova build ufficiale pubblicata come `Device_Manager_v58.exe`.

## 1.57

- Le sezioni `RTU`, `GW`, `I-TIC` e `TIC12` caricano automaticamente il prossimo seriale disponibile da GitHub all apertura del programma.
- Rimossi i pulsanti manuali `Usa il prossimo seriale GitHub` dalle sezioni operative.
- Nella scheda `Serial` ci sono ora solo i pulsanti `Salva valore` per ogni famiglia e `Salva tutti i valori`.
- Ogni salvataggio manuale su GitHub richiede la password amministrativa.
- Nuova build ufficiale pubblicata come `Device_Manager_v57.exe`.

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
- AÃ±adido respaldo automatico entre `logo.png` y `gw_logo_tecnidro.png`.
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
- Nueva pestaÃ±a `Serial` aÃ±adida despues de `FW Version`.
- `Serial` incluye descarga/exportacion de `Hyperterminal.zip`.
- `Serial` incluye descarga/exportacion de `APP_BLE_SERIAL__25_01_2026_wx.zip` para `Terminal Antonio (RTU Bluetooth e LORACONT)`.
- `Gateway` aÃ±ade al inicio el comando de apagado de `X4S LTE` con boton para copiarlo.
- El ejecutable oficial publicado pasa a ser `Device_Manager_v45.exe`.

## 1.43

- RTU con Bluetooth: eliminada una fila de etiquetas por pagina y rejilla centrada en A4.
- RTU sin Bluetooth: eliminada una fila de etiquetas por pagina y rejilla centrada en A4.
- RTU LORACONT: eliminada una fila de etiquetas por pagina y rejilla centrada en A4.
- RTU LORACONT: logo corregido para imprimirse en negro.
- RTU en tubo: eliminada una fila de etiquetas por pagina y rejilla centrada en A4.
