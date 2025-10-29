# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from anses_core import process_input, scrape_anses
from afip_core import nosis_lookup, aportes_lookup

app = FastAPI()

HELP_TEXT = (
    "Comandos:\n"
    "- ping -> pong <ms>\n"
    "- codem <DNI|CUIT> -> Situacion CODEM\n"
    "- nosis <DNI> -> Devuelve CUIL y nombre\n"
    "- aportes <CUIL> -> Devuelve aportes de todos los empleadores (AFIP), envia imagenes\n"
)

@app.get("/help", response_class=PlainTextResponse)
def help_text():
    return HELP_TEXT

@app.get("/codem", response_class=PlainTextResponse)
async def codem(doc: str):
    kind, num = process_input(doc)
    if not num:
        raise HTTPException(status_code=400, detail="Uso: /codem?doc=<DNI|CUIT>")
    return await scrape_anses(num, lambda _: None)

@app.get("/nosis")
async def nosis(dni: str):
    cuil, nombre = await nosis_lookup(dni)
    if not cuil or not nombre:
        return JSONResponse({"ok": False, "error": "No se pudo obtener informacion para ese DNI."})
    return {"ok": True, "cuil": cuil, "nombre": nombre}

@app.get("/aportes")
async def aportes(cuil: str):
    return JSONResponse(await aportes_lookup(cuil))
