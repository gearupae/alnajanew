# Safety Point Scan (Flutter SDK)

Small Dart library + example app for **stock take scanning** against **Safety Point ERP**, using the **same username and password** as the web login (Django session cookie).

## Django API (already wired in the ERP repo)

Base path: **`/api/scan/v1/`**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login/` | JSON `{"username","password"}` — creates session |
| `POST` | `/auth/logout/` | Ends session |
| `GET` | `/auth/me/` | Current user + `can_inventory_scan` |
| `GET` | `/stock-take/sessions/` | In-progress sessions (inventory **view**) |
| `GET` | `/stock-take/sessions/<id>/` | Session + lines (inventory **view**) |
| `POST` | `/stock-take/sessions/<id>/scan/` | Same JSON body as the web scan API (inventory **edit**) |

These routes are **CSRF-exempt** so native clients can use cookies without a CSRF token.

## Flutter usage

```yaml
dependencies:
  safetypoint_scan:
    path: ../safetypoint_scan   # adjust path
```

```dart
final client = AlnajahScanClient(baseUrl: 'http://sp.telldb.com');
await client.login(username: 'u', password: 'p');
final sessions = await client.listStockTakeSessions();
final detail = await client.getStockTakeSession(sessions.first.id);
final result = await client.submitScan(sessions.first.id, barcode: decoded);
```

## Installable APK (for phone testing)

**Option A — GitHub Actions (no Flutter on your PC)**  
1. Push this repository to GitHub.  
2. Open **Actions** → workflow **“Build Safety Point Scan APK”** → **Run workflow**.  
3. When it finishes, open the run → **Artifacts** → download **`safetypoint-scan-apk`** (contains `app-release.apk`).  
4. Copy the APK to your phone and install (allow “install unknown apps” if prompted).  
5. In the app, set **Base URL** to your ERP, e.g. `http://sp.telldb.com` (Django must list that host in `ALLOWED_HOSTS`). Cleartext HTTP is enabled in the built APK for dev testing only.

**Option B — Docker** (from repo root):

```bash
docker build -f safetypoint_scan/Dockerfile.apk -t safetypoint-scan-apk .
cid=$(docker create safetypoint-scan-apk)
docker cp "$cid:/src/safetypoint_scan/example/build/app/outputs/flutter-apk/app-release.apk" ./safetypoint-scan.apk
docker rm "$cid"
```

**Option C — Local Flutter**

```bash
./safetypoint_scan/scripts/build_apk.sh
# APK: safetypoint_scan/example/build/app/outputs/flutter-apk/app-release.apk
```

## Example app

See **`example/`** — first run `flutter create .` inside `example/` to generate `android/` / `ios/`, then `flutter run`.

Camera scanning uses **`mobile_scanner`** (device-native decoders where available).

## Security

- Use **HTTPS** in production.
- Session cookies behave like the web app (8h session in current Django settings).
- Protect devices like you would an open ERP browser tab.
