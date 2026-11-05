# Device Manager - TECNIDRO

Versione pubblicata: **1.127** (05/11/2026).

[Scarica Device_Manager_v127.exe](https://github.com/coloretevm/GeneradorCSV-LoRa/raw/refs/heads/main/downloads/Device_Manager_v127.exe)

## Aggiornamenti automatici

Dalla versione 1.125 il programma controlla gli aggiornamenti GitHub in background all'avvio. Dopo la conferma dell'utente scarica il nuovo exe nella stessa cartella, verifica il download e avvia la nuova versione. Il vecchio exe viene eliminato solo quando la nuova applicazione conferma di essere partita. In caso di errore il vecchio exe viene conservato.

Il manifest `update_manifest.json` contiene versione, URL del download, dimensione e checksum SHA-256. Ogni nuova pubblicazione deve aggiornare questo file insieme all'eseguibile. Non occorre un token per leggere il manifest o scaricare gli aggiornamenti pubblici.

Chi usa la v125 puo aggiornare alla v127 dal programma. Per una prima installazione si puo scaricare direttamente la v127.

## Novita v127

LORACONT ha ora una sezione dedicata subito sotto RTU, con Progetto, CSV, JSON ed Etichette. Non e piu una scelta dei moduli RTU. Per mantenere la numerazione esistente, RTU e LORACONT usano ancora il medesimo contatore RTU.

La sezione Istantaneo genera etichette 100L o 1000L, con un contatore unico condiviso. Il registro parte da ultimo usato 0: la prima etichetta e 0001. Il valore e sincronizzato su GitHub in `serial_registry_istantaneo.json`, separato dal registro storico per compatibilita con i vecchi client. Si puo correggere con la password amministrativa nella scheda Serial.

## Etichette e adesivi

- Istantaneo: 36 dispositivi per A4, etichetta da 50 mm con Versione 100L/1000L e un adesivo batteria separato da 15 x 15 mm per dispositivo.
- Gateway: quattro celle nell'intestazione con logo Tecnidro, LoRaWAN/HYDRONET, Gateway LTE e simbolo batteria integrato.
- I-TIC: 21 dispositivi per A4, QR del manuale sotto ogni etichetta e altrettanti adesivi batteria separati in fondo al foglio.
- TIC12: 27 dispositivi per A4, con QR manuali separati da 15 mm (riquadro 18 x 20 mm) e altrettanti adesivi batteria.
- RTU Bluetooth, senza Bluetooth, in tubo e LoraCont: dimensioni delle etichette invariate e un adesivo batteria da 15 x 15 mm per dispositivo.
- Ogni pagina contiene solo gli adesivi corrispondenti ai dispositivi stampati, anche quando incompleta.
- Manuali > Fogli adesivi permette di salvare i tre PDF originali integrati. Le nuove voci sono disponibili in IT/ES/EN.

## Contenuti

- `generador_csv.py`: applicazione desktop, etichette, CSV, JSON, firmware e manuali.
- `device_manager_updater.py`: download verificato e sostituzione del programma su Windows.
- `device_manager_labels.py`: layout etichette e conteggio degli adesivi per pagina.
- `device_manager_serials.py`: sincronizzazione del contatore Istantaneo isolato dai client precedenti.
- `label_assets/`: QR originali e simbolo batteria vettoriale alle dimensioni originali.
- `test_device_manager_updater.py`: test del manifest e dei download, compresi i casi di errore.
- `fw/` e `manuali/`: file firmware e manuali.
- `downloads/Device_Manager_v127.exe`: eseguibile pubblicato.
- `CHANGELOG.md`: modifiche pubblicate.

La v125 include i firmware LoraCont 1.0.6 INFO/TRACE, il manuale TIC12 aggiornato, le sei varianti RST per Instantaneo Nuovo e Terminal Antonio del 22/06/2026.

## Sorgenti e credenziali

Dipendenze principali: Python, CustomTkinter, Pillow, ReportLab e qrcode. Per generare un exe si usa PyInstaller, includendo le risorse firmware, manuali, ZIP e immagini. I file `serial_token.txt` e le configurazioni locali delle credenziali sono esclusi dal versionamento dei sorgenti.

Eseguire i test con `python -m unittest test_device_manager_updater test_device_manager_labels test_device_manager_serials test_device_manager_ui -v`. Per i test PDF serve anche `pypdf`.
