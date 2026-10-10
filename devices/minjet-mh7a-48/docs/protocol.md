# Protokoll (Findings)

Quelle: Strings aus `libapp.so` der APK v2.0.2(19) (apktool-Export in `captures/`). Alles ungeprüft, nur statisch ermittelt.

## App
- Flutter (Dart AOT) → Logik in `lib/arm64-v8a/libapp.so`, kein Java/Smali-Code der App-Logik
- Dart-Package `minjet`: `utils/http_api.dart`, `utils/socket.dart`, `providers/device_provider.dart`
- Plugins: `flutter_blue_plus` (BLE), `wifi_scan`, `dio`, `web_socket_channel`, `crclib` (Crc16Modbus), Firebase Push
- Seiten: balcony_* (Balkonspeicher), stack_* (Stack), smart_meter, wifi_set / reset_wifi (WLAN-Provisionierung per BLE)

## Cloud
- REST: `https://app.minjet-energy.com/prod-api` (Bearer-Token, Header `Authorization`)
- WebSocket: `ws://app.minjet-energy.com/ws/device?token=<token>` (vermutlich Live-Daten)
- Endpunkte (Pfad relativ zu `/prod-api`):
  - `device/queryUserDeviceList`, `device/bindDevice`, `device/unBindDevice`, `device/productList`, `device/queryProductPictures`
  - `device/updateDeviceNickName/{id}`, `device/queryDeviceLastVersion/{id}`, `device/firmwareUpgrade/…`
  - `device/job/{list,add,edit,changeStatus/{id},zoneIdList}` (Zeitpläne)
  - `assist/queryInverterList`, `assist/querySmartMeterList`
  - `app/notice/{queryAppNoticeList,queryUnreadMessageCount,read}`
  - `system/user/profile/{updateNickName,updatePwd,updateUserTimeZone,avatar}`
- Login-/Datenpfade noch nicht gefunden (nur Teilstrings sichtbar)

## BLE (flutter_blue_plus)
- GATT-UUIDs im Binary: `0000A002-…`, `0000c304-…`, `0000c305-…` (jeweils `-0000-1000-8000-00805f9b34fb`), `00002902` (CCCD)
- Frame-Prüfsumme vermutlich CRC16-Modbus

## Nächste Schritte
1. Dart-AOT dekompilieren (blutter / reFlutter) → Request-/Frame-Strukturen, Login-Pfad
2. Live-Mitschnitt: mitmproxy (REST, WS) und HCI-Snoop (BLE); Zertifikats-Pinning prüfen
3. Entscheiden: lokal (BLE) vs. Cloud-Polling für HA
