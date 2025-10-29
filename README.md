# 🤖 Bot de WhatsApp + Core API (FastAPI + Playwright)

Un sistema modular que combina un **bot de WhatsApp** con una **API en Python (FastAPI)** que automatiza consultas en sitios como AFIP, ANSES y NOSIS mediante **Playwright**. Está diseñado para correr en una **VPS Linux (probado en Debian)**, con ambos servicios aislados en entornos virtuales y ejecutándose en **pantallas `screen` separadas**.

---

## 📁 Estructura del Proyecto

```
~/pycore/             # Núcleo Python / API
  afip_core.py
  anses_core.py
  core_api.py

~/wabot/              # Bot de WhatsApp (Node.js)
  index.js
  package.json
  auth/                # Se crea al vincular el número por QR
```

---

## ⚙️ Requisitos del Servidor

- Debian o Ubuntu actualizado
- Python 3.10 o superior
- Node.js 18 o superior
- Git, curl, screen
- Dependencias gráficas para Playwright

Instalación rápida de dependencias base:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip screen git   libglib2.0-0 libnss3 libasound2 libatk1.0-0 libatk-bridge2.0-0   libx11-6 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3   libxrandr2 libxext6 libxshmfence1 libxcursor1 libxi6 libdrm2   libgbm1 libpango-1.0-0 libcairo2 fonts-liberation xvfb
```

---

## 🧠 Parte 1: Core API (Python + FastAPI)

### 🔹 Creación del entorno virtual

```bash
cd ~/pycore
python3 -m venv venv
source venv/bin/activate
```

### 🔹 Instalación de dependencias

```bash
pip install fastapi uvicorn[standard] playwright pillow beautifulsoup4 pypdf2
python -m playwright install chromium
python -m playwright install-deps
```

### 🔹 Ejecución del Core API

El servicio debe lanzarse dentro de un `screen` para mantenerlo activo:

```bash
screen -S core
cd pycore
source venv/bin/activate
xvfb-run -a uvicorn core_api:app --host 0.0.0.0 --port 9000
```

Luego presioná **Ctrl+A + D** para dejar el proceso corriendo en segundo plano.

Podés volver con:

```bash
screen -r core
```

### 🔹 Endpoints disponibles

- `/help` → Muestra información general.
- `/codem?doc=<DNI|CUIT>` → Consulta CODEM de ANSES.
- `/nosis?dni=<DNI>` → Consulta datos básicos en NOSIS.
- `/aportes?cuil=<CUIL>` → Devuelve capturas de los aportes en AFIP.

---

## 💬 Parte 2: Bot de WhatsApp (Node.js)

### 🔹 Crear entorno Node aislado

```bash
cd ~/wabot
python3 -m venv venv
source venv/bin/activate
```

### 🔹 Inicializar y configurar dependencias

```bash
npm init -y
npm install @whiskeysockets/baileys pino node-fetch qrcode-terminal
```

### 🔹 Ejecución del bot

Dentro de un nuevo `screen`:

```bash
screen -S wabot
cd ~/wabot
source venv/bin/activate
node index.js
```

En el primer arranque aparecerá un **QR en la consola**. Escanealo con el número de WhatsApp que funcionará como bot. Se creará una carpeta `auth/` que guarda las credenciales de sesión.

Podés desconectarte con **Ctrl+A + D** y volver con:

```bash
screen -r wabot
```

---

## 🧩 Cómo Funciona

1. El **Core API** maneja las automatizaciones (Playwright abre los portales de AFIP, ANSES o NOSIS y extrae la información).
2. El **bot de WhatsApp** escucha mensajes entrantes con comandos como `codem`, `nosis` o `aportes`.
3. Por cada consulta, el bot llama a los endpoints HTTP del Core y devuelve la respuesta al usuario en WhatsApp.

---

## 🕹️ Comandos del Bot

- `ping` → Responde con la latencia del servidor.
- `help` → Muestra la lista de comandos.
- `codem <DNI|CUIT>` → Consulta CODEM (ANSES).
- `nosis <DNI>` → Devuelve CUIL y nombre.
- `aportes <CUIL>` → Envía imágenes de aportes en AFIP.

---

## 🔒 Recomendaciones

- No ejecutar como `root`. Usar un usuario limitado.
- Mantener cada proceso en su propio entorno (`venv` y `nodeenv`).
- Si la VPS no tiene entorno gráfico, usar `xvfb-run` (ya incluido en el ejemplo).
- No exponer el puerto 9000 públicamente sin autenticación o proxy.

---

## 🚀 Arranque Rápido

### 1️⃣ Core API
```bash
screen -S core
cd pycore
source venv/bin/activate
xvfb-run -a uvicorn core_api:app --host 0.0.0.0 --port 9000
```
Luego CTRL+A, CTRL+D

### 2️⃣ Bot de WhatsApp
```bash
screen -S wabot
cd wabot
source venv/bin/activate
node index.js
```
Luego CTRL+A, CTRL+D

---

## 💾 Verificación Manual

Prueba los endpoints del Core:

```bash
curl http://127.0.0.1:9000/help
curl "http://127.0.0.1:9000/codem?doc=20123456789"
curl "http://127.0.0.1:9000/nosis?dni=12345678"
curl "http://127.0.0.1:9000/aportes?cuil=20-12345678-3"
```

Si las respuestas son correctas, el bot debería funcionar sin errores.

---

## 🧰 Detalles Técnicos

- **Backend**: FastAPI (Python 3.10+)
- **Automatización**: Playwright (Chromium)
- **Mensajería**: Baileys (Node.js)
- **Ejecución**: 2 screens independientes (`core` y `wabot`)
- **Compatibilidad**: Debian 12 / Ubuntu 22.04

---

## 👨‍💻 Autor
Proyecto creado y probado por **Agustín González**.
