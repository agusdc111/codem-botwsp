import baileys from "@whiskeysockets/baileys"
import pino from "pino"
import fetch from "node-fetch"
import qrcode from "qrcode-terminal"
import { webcrypto } from "crypto"
globalThis.crypto = webcrypto

const { default: makeWASocket, useMultiFileAuthState, fetchLatestBaileysVersion, DisconnectReason } = baileys
const CORE = "http://127.0.0.1:9000"
const logger = pino({ level: "info" })

const HELP = `Comandos:
- ping -> pong <Latencia en ms>
- codem <DNI|CUIT> -> Situacion Codem de una persona
- nosis <DNI> -> Devuelve CUIL y nombre
- aportes <CUIL> -> Consulta aportes de todos los empleadores de una persona, envia imagenes`

async function start() {
  const { state, saveCreds } = await useMultiFileAuthState("./auth")
  const { version } = await fetchLatestBaileysVersion()
  const sock = makeWASocket({ version, logger, auth: state })

  sock.ev.on("creds.update", saveCreds)
  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) qrcode.generate(qr, { small: true })
    if (connection === "close") {
      const shouldReconnect = (lastDisconnect?.error)?.output?.statusCode !== DisconnectReason.loggedOut
      if (shouldReconnect) start()
    }
  })

  sock.ev.on("messages.upsert", async ({ messages }) => {
    const msg = messages?.[0]
    if (!msg?.message || msg.key.fromMe) return
    const jid = msg.key.remoteJid
    const text = msg.message?.conversation || msg.message?.extendedTextMessage?.text || ""
    const t = text.trim()
    if (!t) { await sock.sendMessage(jid, { text: HELP }); return }

    const [cmd, ...rest] = t.split(/\s+/)
    const arg = rest.join(" ").trim()
    const low = cmd.toLowerCase()

    // PING con medicion de latencia de respuesta (procesamiento + envio)
    if (low === "ping") {
      const t0 = Date.now()
      // Puedes hacer un ping "real" al CORE si quieres incluir red local:
      // await fetch(CORE + "/help").catch(()=>{})
      await sock.sendMessage(jid, { text: "pong" })
      const ms = Date.now() - t0
      await sock.sendMessage(jid, { text: `latencia: ${ms} ms` })
      return
    }

    if (low === "help" || low === "ayuda") {
      await sock.sendMessage(jid, { text: HELP })
      return
    }

    if (low === "codem") {
      if (!arg) { await sock.sendMessage(jid, { text: `Uso: codem <DNI|CUIT>\n\n${HELP}` }); return }
      await sock.sendMessage(jid, { text: "Consultando CODEM..." })
      try {
        const r = await fetch(`${CORE}/codem?doc=${encodeURIComponent(arg)}`)
        const body = await r.text()
        if (!r.ok) { await sock.sendMessage(jid, { text: `Error del nucleo: ${body}\n\n${HELP}` }); return }
        await sock.sendMessage(jid, { text: body.slice(0, 4000) })
      } catch (e) {
        await sock.sendMessage(jid, { text: `Error de conexion al nucleo: ${e}\n\n${HELP}` })
      }
      return
    }

    if (low === "nosis") {
      if (!arg) { await sock.sendMessage(jid, { text: `Uso: nosis <DNI>\n\n${HELP}` }); return }
      await sock.sendMessage(jid, { text: "Buscando en Nosis..." })
      try {
        const r = await fetch(`${CORE}/nosis?dni=${encodeURIComponent(arg)}`)
        const data = await r.json()
        if (!data.ok) { await sock.sendMessage(jid, { text: `No se pudo obtener informacion.\n\n${HELP}` }); return }
        await sock.sendMessage(jid, { text: `CUIL: ${data.cuil}\nNombre: ${data.nombre}` })
      } catch (e) {
        await sock.sendMessage(jid, { text: `Error de conexion al nucleo: ${e}\n\n${HELP}` })
      }
      return
    }

    if (low === "aportes") {
      if (!arg) { await sock.sendMessage(jid, { text: `Uso: aportes <CUIL>\n\n${HELP}` }); return }
      await sock.sendMessage(jid, { text: "Consultando AFIP..." })
      try {
        const r = await fetch(`${CORE}/aportes?cuil=${encodeURIComponent(arg)}`)
        const data = await r.json()
        if (!data.ok) { await sock.sendMessage(jid, { text: `Error: ${data.error}\n\n${HELP}` }); return }
        for (const img of data.images) {
          const buf = Buffer.from(img.png_base64, "base64")
          await sock.sendMessage(jid, { image: buf, caption: img.caption })
        }
      } catch (e) {
        await sock.sendMessage(jid, { text: `Error de conexion al nucleo: ${e}\n\n${HELP}` })
      }
      return
    }

    await sock.sendMessage(jid, { text: HELP })
  })
}

start()
