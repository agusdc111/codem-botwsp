# -*- coding: utf-8 -*-
import asyncio, io, base64, tempfile, os, unicodedata
from typing import Optional, Tuple, Dict
from bs4 import BeautifulSoup
from PIL import Image
from playwright.async_api import async_playwright

NOSIS_URL = "https://informes.nosis.com"
AFIP_URL = "https://serviciosweb.afip.gob.ar/TRAMITES_CON_CLAVE_FISCAL/MISAPORTES/app/basica.aspx"

def _crop_file_to_b64(path_in: str, box):
    with Image.open(path_in) as img:
        cropped = img.crop(box)
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")

def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.lower().split())

async def nosis_lookup(dni: str) -> Tuple[Optional[str], Optional[str]]:
    dni = (dni or '').strip()
    if not dni.isdigit() or not (7 <= len(dni) <= 9):
        return None, None
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(NOSIS_URL, timeout=60000)
            await page.fill("#Busqueda_Texto", dni)
            await page.press("#Busqueda_Texto", "Enter")
            await page.wait_for_selector("#wrap-resultados .cuit", timeout=30000)
            cuil = await page.text_content("#wrap-resultados .cuit")
            nombre = await page.text_content("#wrap-resultados .rz")
            return (cuil.strip() if cuil else None, nombre.strip() if nombre else None)
        except Exception:
            return (None, None)
        finally:
            await browser.close()

async def aportes_lookup(cuil_input: str) -> Dict:
    cuil_original = (cuil_input or '').strip()
    cuil_clean = cuil_original.replace("-", "")
    if not (cuil_clean.isdigit() and len(cuil_clean) == 11):
        return {"ok": False, "error": "CUIL invalido. Debe tener 11 digitos (con o sin guiones)."}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.set_viewport_size({"width": 1920, "height": 1080})
            await page.goto(AFIP_URL, timeout=60000)
            await asyncio.sleep(2)

            variantes = []
            if "-" in cuil_original:
                variantes.append(cuil_original.replace("-", ""))
                variantes.append(cuil_original)
            else:
                variantes.append(cuil_original)
                if cuil_original.startswith("0"):
                    variantes.append(cuil_original[1:])
                if len(cuil_original) == 11:
                    variantes.append(f"{cuil_original[:2]}-{cuil_original[2:10]}-{cuil_original[10]}")
            if len(cuil_clean) == 11:
                variantes += [cuil_clean, cuil_clean[1:], f"{cuil_clean[:2]}-{cuil_clean[2:10]}-{cuil_clean[10]}", f"{cuil_clean[10]}{cuil_clean[:10]}"]

            seen = set()
            variantes = [x for x in variantes if not (x in seen or seen.add(x))]

            cuil_valido = None
            for cuil_var in variantes:
                await page.fill('#ctl00_ContentPlaceHolder2_txtCuil_txtSufijo', '')
                await page.click('#ctl00_ContentPlaceHolder2_txtCuil_txtSufijo', click_count=3)
                await page.keyboard.press("Backspace")
                await asyncio.sleep(0.05)
                for d in cuil_var:
                    await page.keyboard.type(d)
                await page.keyboard.press("Enter")
                await page.wait_for_selector('#ctl00_ContentPlaceHolder2_btnContinuar', timeout=8000)
                await page.click('#ctl00_ContentPlaceHolder2_btnContinuar')
                await asyncio.sleep(1.5)

                err = await page.query_selector('#ctl00_ContentPlaceHolder2_vldSumaryCuil')
                err_text = (await err.inner_text()) if err else ""
                nerr = _norm(err_text)

                # Caso solicitado: CUIL no declarado en el sistema -> cortar y avisar
                if "su cuil no se encuentra declarado en nuestro sistema" in nerr:
                    await browser.close()
                    return {"ok": False, "error": "Esta persona no tiene aportes, verifica CODEM"}

                # Si NO dice "invalido", entonces AFIP acepto el CUIL y seguimos
                if "el cuil ingresado es invalido" not in nerr:
                    cuil_valido = cuil_var
                    break
                # Caso invalido: probar siguiente variante
                # (continua el loop)

            if not cuil_valido:
                return {"ok": False, "error": "El CUIL ingresado es invalido en todos los formatos probados."}

            with tempfile.TemporaryDirectory(prefix="aportes_") as tmpdir:
                first_full = os.path.join(tmpdir, "full_0.png")
                await page.screenshot(path=first_full, full_page=True)
                siguiente = await page.query_selector('#ctl00_ContentPlaceHolder2_btnEmpleSiguiente')

                images = []
                if not siguiente:
                    b64 = _crop_file_to_b64(first_full, (651, 295, 1273, 751))
                    images.append({"caption": "UNICO EMPLEADOR", "png_base64": b64})
                else:
                    idx, prev = 1, first_full
                    while True:
                        b64 = _crop_file_to_b64(prev, (654, 439, 1273, 891))
                        images.append({"caption": f"EMPLEADOR {idx}", "png_base64": b64})
                        next_btn = await page.query_selector('#ctl00_ContentPlaceHolder2_btnEmpleSiguiente')
                        if not next_btn:
                            break
                        await next_btn.click()
                        await asyncio.sleep(1.5)
                        new_full = os.path.join(tmpdir, f"full_{idx}.png")
                        await page.screenshot(path=new_full, full_page=True)
                        prev, idx = new_full, idx + 1

            return {"ok": True, "images": images}
        except Exception as e:
            return {"ok": False, "error": f"Error procesando AFIP: {e}"}
        finally:
            await browser.close()
