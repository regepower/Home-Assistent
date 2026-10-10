# Protokoll (Findings)

Status: Login, Geräteliste und PV-Abfrage am 2026-10-10 live gegen die Cloud verifiziert (GitHub-Runner, eigener Account). Quelle der Pfade: blutter-Dekompilierung von `libapp.so` + `libflutter.so` (Minjet Android, Flutter/Dart 3.x, passende Paarung aus derselben APK-Version). Nur statisch ermittelt, noch nicht gegen die Cloud getestet.

## App
- Flutter (Dart AOT), Package `minjet`; relevante Dateien: `utils/http_api.dart`, `utils/socket.dart`, `providers/model/device_model.dart`, `page/{balcony,stack}_*_view.dart`
- Die App kennt zwei Gerätefamilien: **Balcony** (Balkonspeicher) und **Stack**. MH7A-48 steht als Produktname in `device_model.dart`.

## Cloud-REST
- Basis: `https://app.minjet-energy.com/prod-api` (RuoYi-Framework)
- Auth: Header `Authorization: Bearer <token>`
- Standardantwort: `{ "code": 200, "msg": "...", ... }` (`code`/`msg`/`rows`/`data`)

### Login
- `POST /login` mit Body `{ "username": "...", "password": "..." }` (Dart-Map, vermutlich JSON via dio; kein Captcha/uuid)
- Antwort: `code`, `token`
- Danach `getInfo` (User: `userName`, `nickName`, `email`, `avatar`, `timeZone`)

### Endpunkte (relativ zu `/prod-api`)
| Zweck | Pfad |
|---|---|
| Geräteliste | `device/queryUserDeviceList` |
| Binden / Lösen | `device/bindDevice`, `device/unBindDevice` |
| Produktliste/Bilder | `device/productList`, `device/queryProductPictures` |
| Umbenennen | `device/updateDeviceNickName/{id}` |
| Firmware | `device/queryDeviceLastVersion/{id}`, `device/firmwareUpgrade/{id}`, `device/firmwareUpgradeProgressBar/{id}` |
| Zeitpläne | `device/job/{list,add,edit,changeStatus/{id},zoneIdList}` |
| **Steuern** | `POST stacking/setProperty/{id}` mit Body `{ "key": <Property>, "value": <Wert> }` |
| PV / Balcony | `photovoltaic/queryPhotovoltaic/{id}`, `photovoltaic/setRatedPower/{id}`, `photovoltaic/closeRealTimeStatus/{id}` |
| Statistik | `deviceReport/queryDeviceStatistics`, `deviceReport/queryPhotovoltaicPowerStatistics` (Parameter u. a. `dateType`, `startDate`, `endDate`, `dateTime`, `serialNum`) |
| Wechselrichter / Zähler | `assist/queryInverterList`, `assist/querySmartMeterList`, `assist/setSmartMeterTypeAndAddress/{id}` |
| Benachrichtigungen | `app/notice/{queryAppNoticeList,queryUnreadMessageCount,read,queryDeviceDetailNoticeList/{id}}` |
| Profil | `system/user/profile/{updateNickName,updatePwd,updateUserTimeZone,avatar}` |

**Verifiziert:** `{id}` ist die `serialNum` (mit `deviceId` kommt `500 The device is not bound`).

## Geräteobjekt (`device_model.dart`)
- Stammdaten: `deviceId`, `deviceName`, `customName`, `serialNum`, `macAddress`, `productKey`, `productCode`, `productName`, `bindTime`, `activeTime`, `deviceCurrentVersion`, `deviceLatestVersion`
- Messwerte: `batteryPercentage`, `batteryPower`, `batteryStatus`, `ACInputPower`, `ACDCOutputPower`, `outputPower`, `PVInputPower`, `photovoltaicPower`, `onGridPower`, `chargePower`, `temperature`/`temperature1`/`temperature2`, `energyTotalUsed`, `photovoltaic{Today,Month,Total}{Generate,Used}`, `mpptInfo`
- Schalter/Einstellungen (setProperty-Keys): `ACSwitchStatus`, `DCSwitchStatus`, `USBSwitchStatus`, `BuzzerSwitchStatus`, `childLockStatus`, `onGridModeStatus`, `antiIslandingProtectionModeStatus`, `batteryPriorityModeStatus`, `maxOnGridPower`, `maxAntiIslandingProtectionPower`, `batteryChargeLimit`, `batteryDischargeLimit`, `standByTime`, `chargePower`, `customName`
- Weiteres: `parallelMachine`, `parallelFlagStatus`, `emType`/`emName`/`emCommStatus`/`emConfigStatus` (Energy Meter), `ratedPower`

## Verifizierte Antworten
- `POST /login` → `{"code":200,"msg":"success","token":"<JWT>"}`; Token ab dann als Bearer
- `GET getInfo` → `{user:{userId,userName,nickName,email,timeZone,language,...}}` (liefert u. a. den Passwort-Hash des Users zurück, nie loggen/teilen)
- `GET device/queryUserDeviceList` → `{"data":[{deviceId, productCode:"MH7A-48", productTypeCode:"MH7A", deviceName, customName, serialNum, deviceStatus ("1"=online), deviceCurrentVersion, deviceLatestVersion, properties:{...}}]}`
- Die Live-Messwerte stehen bereits in `properties` der Geräteliste (kein eigener Aufruf nötig). Upload-Zyklus des Geräts: `uploadCycle` = 60 s → Polling < 60 s bringt nichts.
- `GET photovoltaic/queryPhotovoltaic/{serialNum}` → Gerät + `properties` + `emName` (Energy Meter, z. B. Shelly) + `inverterName` (z. B. Deye) + Tages-/Monatswerte (`photovoltaicToday*`, `photovoltaicMonth*`)

### `properties` (MH7A-48), beobachtete Felder
| Feld | Bedeutung (Vermutung) |
|---|---|
| `batteryPercentage` | SOC in % |
| `batteryPower` | Batterieleistung in W (Vorzeichen/`batteryStatus` klären: 2 = entladen?) |
| `batteryStatus` | 0/1/2 (Lade-/Entladezustand) |
| `outputPower` | Ausgangsleistung W |
| `photovoltaicPower`, `photovoltaicStatus` | PV-Leistung W / Status |
| `photovoltaicTotalGenerate`, `photovoltaicMonthGenerate`, `photovoltaicTodayGenerate` | Erzeugung kWh |
| `energyTotalUsed`, `photovoltaicMonthUsed`, `photovoltaicTodayUsed` | Verbrauch kWh |
| `emType`, `emCommStatus`, `emConfigStatus`, `emFeedbackValue` | Energy Meter (Netzbezug W) |
| `ratedPower`, `batteryChargeLimit`, `batteryDischargeLimit`, `batteryPriorityModeStatus` | Einstellungen (Limits in %) |
| `mpptInfo`, `mpptPowerLmt1/2`, `dcdcInfo` | MPPT/DC-DC-Rohwerte (Spannung/Strom ×10?, noch zu entschlüsseln) |
| `temperature1`, `temperature2` | °C |
| `cellVoltMin`, `cellVoltMax` | mV |
| `chgCurrentLmt`, `dsgCurrentLmt` | Stromlimits |
| `WiFiRSSI`, `ip0`, `version`, `debugVer`, `inverterVer`, `mpptVer` | Diagnose |
| `warningStatus`, `mcuState` | Bitfelder (Warnungen/Status) |

## WebSocket
- `ws://app.minjet-energy.com/ws/device?token=<token>` antwortet auf Port 80 mit `301 Moved Permanently` → vermutlich `wss://…` (Probe nutzt jetzt TLS, Test steht aus)
- Wrapper `Socket` mit Reconnect (max. Versuche); Nachrichtenformat noch nicht ausgelesen → per Mitschnitt klären

## BLE (nur Erstinbetriebnahme/WLAN-Setup)
- UUIDs `…A002`, `…c304`, `…c305` (Basis `-0000-1000-8000-00805f9b34fb`), CCCD `2902`; Prüfsumme CRC16-Modbus
- Für HA nicht nötig, da Betrieb über Cloud/WLAN

## Offen
1. WebSocket über `wss://` mitschneiden (Nachrichtenformat, ob Push statt Polling möglich)
2. Schreibaufrufe (`setProperty`) einzeln testen, z. B. Buzzer oder Limit
3. Home-Assistant-Integration (Custom Component): Login, Polling/WS, Switches/Numbers per `setProperty`
4. Rate-Limits/ToS der Cloud beachten; Polling zurückhaltend wählen

## Tages-/Monatswerte und Benachrichtigungen (aus der App-Logik, noch ungetestet)
- Live-API liefert `photovoltaicTodayGenerate` = `photovoltaicMonthGenerate` = `photovoltaicTotalGenerate` (402.1) sowie `photovoltaicTodayUsed` = `energyTotalUsed` (353.8): die „heute"-Felder sind faktisch **Gesamtzähler** (App zeigt deshalb „Heute erzeugt" falsch).
- `GET deviceReport/queryDeviceStatistics?serialNum=<SN>&startDate=yyyy-MM-dd&endDate=yyyy-MM-dd&dateType=<1|2|3>` (1 = Monat, 2 = Jahr, 3 = Lebensdauer); Antwort `data.list`, `data.totalGenerate`, `data.totalUsed`
- `GET deviceReport/queryPhotovoltaicPowerStatistics?serialNum=<SN>&dateTime=yyyy-MM-dd` (Leistungsverlauf eines Tages)
- Benachrichtigungen: `GET app/notice/queryAppNoticeList`, `GET app/notice/queryUnreadMessageCount`, `GET app/notice/queryDeviceDetailNoticeList/{deviceId}`; `app/notice/read` markiert gelesen (schreibend, nicht getestet)
- HA-Plan für Tageswerte: Gesamtzähler als `total_increasing`-Sensoren und per `utility_meter` (daily/monthly) ableiten; optional zusätzlich die Cloud-Statistik
