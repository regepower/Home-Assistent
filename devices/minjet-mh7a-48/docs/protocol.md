# Protokoll (Findings)

Quelle: blutter-Dekompilierung von `libapp.so` + `libflutter.so` (Minjet Android, Flutter/Dart 3.x, passende Paarung aus derselben APK-Version). Nur statisch ermittelt, noch nicht gegen die Cloud getestet.

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

Ob `{id}` die `deviceId` oder `serialNum` ist, ist noch offen (Call-Site baut den Pfad per String-Interpolation).

## Geräteobjekt (`device_model.dart`)
- Stammdaten: `deviceId`, `deviceName`, `customName`, `serialNum`, `macAddress`, `productKey`, `productCode`, `productName`, `bindTime`, `activeTime`, `deviceCurrentVersion`, `deviceLatestVersion`
- Messwerte: `batteryPercentage`, `batteryPower`, `batteryStatus`, `ACInputPower`, `ACDCOutputPower`, `outputPower`, `PVInputPower`, `photovoltaicPower`, `onGridPower`, `chargePower`, `temperature`/`temperature1`/`temperature2`, `energyTotalUsed`, `photovoltaic{Today,Month,Total}{Generate,Used}`, `mpptInfo`
- Schalter/Einstellungen (setProperty-Keys): `ACSwitchStatus`, `DCSwitchStatus`, `USBSwitchStatus`, `BuzzerSwitchStatus`, `childLockStatus`, `onGridModeStatus`, `antiIslandingProtectionModeStatus`, `batteryPriorityModeStatus`, `maxOnGridPower`, `maxAntiIslandingProtectionPower`, `batteryChargeLimit`, `batteryDischargeLimit`, `standByTime`, `chargePower`, `customName`
- Weiteres: `parallelMachine`, `parallelFlagStatus`, `emType`/`emName`/`emCommStatus`/`emConfigStatus` (Energy Meter), `ratedPower`

## WebSocket
- `ws://app.minjet-energy.com/ws/device?token=<token>` (unverschlüsselt!)
- Wrapper `Socket` mit Reconnect (max. Versuche); Nachrichtenformat noch nicht ausgelesen → per Mitschnitt klären

## BLE (nur Erstinbetriebnahme/WLAN-Setup)
- UUIDs `…A002`, `…c304`, `…c305` (Basis `-0000-1000-8000-00805f9b34fb`), CCCD `2902`; Prüfsumme CRC16-Modbus
- Für HA nicht nötig, da Betrieb über Cloud/WLAN

## Offen
1. Pfad-Parameter `{id}` (deviceId vs. serialNum) und Antwortformat von `queryUserDeviceList` per Live-Test mit eigenem Account prüfen
2. WebSocket-Nachrichten mitschneiden
3. Home-Assistant-Integration (Custom Component): Login, Polling/WS, Switches/Numbers per `setProperty`
4. Rate-Limits/ToS der Cloud beachten; Polling zurückhaltend wählen
