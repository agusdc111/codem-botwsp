# -*- coding: utf-8 -*-
import re, asyncio, unicodedata, inspect
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import PyPDF2

def process_input(input_str: str):
    numbers = re.sub(r'\D', '', input_str or '')
    if len(numbers) == 8:
        return 'DNI', numbers
    if len(numbers) == 11:
        return 'CUIT', numbers
    return None, None

def extract_birthdate_from_pdf(pdf_path: str):
    try:
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ''.join((p.extract_text() or '') for p in reader.pages)
        m = re.search(r'Fecha de Nacimiento:\s*(\d{2}/\d{2}/\d{4})', text)
        return m.group(1) if m else None
    except Exception:
        return None

def _strip_accents(s: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFKD', s) if not unicodedata.combining(ch))

async def _notify(progress, msg: str):
    """Llama al callback de progreso si existe (soporta sync y async)."""
    try:
        if progress is None:
            return
        if inspect.iscoroutinefunction(progress):
            await progress(msg)
        else:
            progress(msg)
    except Exception:
        # Nunca rompas el flujo por errores de notificación
        pass

async def scrape_anses(doc_number: str, progress=lambda _: None):
    async with async_playwright() as p:
        # Si te funciona headless=True, cambialo y evitarás xvfb-run.
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-AR,es;q=0.9"
        })
        try:
            await page.goto("https://servicioswww.anses.gob.ar/ooss2/", timeout=60000)

            # CAPTCHA: abortar inmediatamente
            if await page.query_selector('div.g-recaptcha'):
                await browser.close()
                return "La página requiere resolver un CAPTCHA manual."

            # Ingresar documento
            await page.fill('input[name="ctl00$ContentPlaceHolder1$txtDoc"]', doc_number)

            # Bucle de intentos
            max_attempts = 10
            attempt = 1
            while attempt <= max_attempts:
                # Click consultar
                await page.click('input[name="ctl00$ContentPlaceHolder1$Button1"]')
                await page.wait_for_load_state('networkidle', timeout=60000)

                # ¿Mensaje de error?
                err = await page.query_selector('span#ContentPlaceHolder1_MessageLabel')
                if err:
                    raw_txt = (await err.inner_text() or "").strip()
                    # Comparación robusta sin tildes para no depender del encoding
                    norm = _strip_accents(raw_txt).lower()
                    no_result = _strip_accents("La consulta no arrojó resultados.").lower()
                    if norm == no_result:
                        # Corta inmediatamente con el texto EXACTO que espera el usuario
                        await browser.close()
                        return "La consulta no arrojó resultados."
                    # Otro error: reintenta hasta agotar
                    if attempt >= max_attempts:
                        await browser.close()
                        return f"Error: No se pudieron obtener datos tras {max_attempts} intentos. Último error: {raw_txt}"
                    # Avisar progreso y reintentar
                    await _notify(progress, "Reintentando...")
                    attempt += 1
                    await asyncio.sleep(2)
                    continue

                # Parsear contenido
                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')

                table = soup.find('table', id='ContentPlaceHolder1_DGOOSS')
                if not table:
                    if attempt >= max_attempts:
                        await browser.close()
                        return f"Error: No se encontraron datos tras {max_attempts} intentos."
                    await _notify(progress, "Reintentando...")
                    attempt += 1
                    await asyncio.sleep(2)
                    continue

                cuil_el = soup.find('span', id='ContentPlaceHolder1_lblCuil')
                nombre_el = soup.find('span', id='ContentPlaceHolder1_lblNombre')
                if not cuil_el or not nombre_el:
                    if attempt >= max_attempts:
                        await browser.close()
                        return f"Error: No se pudo extraer CUIL/Nombre tras {max_attempts} intentos."
                    await _notify(progress, "Reintentando...")
                    attempt += 1
                    await asyncio.sleep(2)
                    continue

                cuil = cuil_el.text.strip()
                nombre = nombre_el.text.strip()

                rows = table.find_all('tr')
                obrasocial = condicion = situacion = None
                for row in rows[1:]:
                    cells = row.find_all('td')
                    if len(cells) >= 4:
                        obrasocial = cells[1].text.strip()
                        condicion = cells[2].text.strip()
                        situacion = cells[3].text.strip()
                        break

                if not all([obrasocial, condicion, situacion]):
                    if attempt >= max_attempts:
                        await browser.close()
                        return f"Error: No se pudieron extraer campos tras {max_attempts} intentos."
                    await _notify(progress, "Reintentando...")
                    attempt += 1
                    await asyncio.sleep(2)
                    continue

                # Éxito: salir del bucle
                break

            # Descargar PDF y extraer fecha de nacimiento
            async with page.expect_download(timeout=30000) as dl:
                await page.click('a[href*="__doPostBack"]')
            download = await dl.value
            pdf_path = await download.path()
            birthdate = extract_birthdate_from_pdf(pdf_path)
            await browser.close()

            return (
                f"Nombre: {nombre}\n"
                f"CUIL: {cuil}\n"
                f"Obra Social: {obrasocial}\n"
                f"Condición: {condicion}\n"
                f"Situación: {situacion}\n"
                f"Fecha de Nacimiento: {birthdate or 'No disponible'}"
            )

        except PlaywrightTimeoutError:
            await browser.close()
            return "Error: Timeout cargando la página."
        except Exception as e:
            await browser.close()
            return f"Error inesperado: {e}"
