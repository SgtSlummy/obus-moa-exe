# Obus Setup Detail

## Docker
```bash
docker pull ghcr.io/ourorg/obus:latest
docker run -d --name obus -p 8081:8081 ghcr.io/ourorg/obus:latest
```

## Node/React
```bash
cd /c/Users/Hermes/Documents/obus-moa-exe
npm install
npm start
```

## Windows Start‑Menu link creation
The shortcut file `Obus.url` is placed in `%APPDATA%\Microsoft\Windows\Start Menu\Programs`.

```bash
echo "[InternetShortcut]\nURL=http://localhost:8081" > Obus.url
move /Y Obus.url "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Obus.url"
```
