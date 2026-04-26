"""
ticket_lagranmanzana.py
=======================
Genera un ticket de impresión térmica para "La Gran Manzana".
- ReportLab para el layout/PDF
- Pillow para procesar el logo BW
- qrcode para QR fiscal y redes
- Todo monocromático, apto para impresora térmica 80mm

DATOS DINÁMICOS: modificar el dict TICKET_DATA al final del archivo.
"""

import os, io
import math
import qrcode
from PIL import Image
import numpy as np

from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader

# ── Constantes ───────────────────────────────────────────────────────────────
TICKET_W_MM = 80
MARGIN_MM   = 4
BLACK = colors.black
WHITE = colors.white


# ════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _line(c, x1, y, x2, width=0.5, dashed=False):
    c.saveState()
    c.setStrokeColor(BLACK)
    c.setLineWidth(width)
    if dashed:
        c.setDash([2, 4])
    c.line(x1, y, x2, y)
    c.restoreState()

def _vline(c, x, y1, y2, width=0.4):
    c.saveState()
    c.setStrokeColor(BLACK)
    c.setLineWidth(width)
    c.line(x, y1, x, y2)
    c.restoreState()

def _rect_filled(c, x, y, w, h):
    c.setFillColor(BLACK)
    c.rect(x, y, w, h, fill=1, stroke=0)

def _text_c(c, cx, y, text, size, bold=False, fill=BLACK):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.setFillColor(fill)
    c.drawCentredString(cx, y, text)

def _text_l(c, x, y, text, size, bold=False, fill=BLACK):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.setFillColor(fill)
    c.drawString(x, y, text)

def _text_r(c, x, y, text, size, bold=False, fill=BLACK):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.setFillColor(fill)
    c.drawRightString(x, y, text)


# ════════════════════════════════════════════════════════════════════════════
#  LOGO
# ════════════════════════════════════════════════════════════════════════════

def prepare_logo(src_path: str):
    img = Image.open(src_path).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf), img.width, img.height


# ════════════════════════════════════════════════════════════════════════════
#  ASSET HELPER (ribbon, decorator)
# ════════════════════════════════════════════════════════════════════════════

def load_asset(path: str):
    """Carga PNG con alpha como ImageReader. Retorna (reader, w_px, h_px)."""
    img = Image.open(path).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf), img.width, img.height


# ════════════════════════════════════════════════════════════════════════════
#  QR
# ════════════════════════════════════════════════════════════════════════════

def make_qr(url: str, size_px: int = 100) -> ImageReader:
    qr = qrcode.QRCode(version=2,
                       error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=4, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white") \
            .convert("RGB").resize((size_px, size_px), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


# ════════════════════════════════════════════════════════════════════════════
#  RIBBON  (usa imagen PNG extraída del diseño original)
# ════════════════════════════════════════════════════════════════════════════

def draw_ribbon(c, cx, y_center, draw_w, ribbon_path, **kwargs):
    """Pega el ribbon PNG directo, centrado."""
    reader, rw, rh = load_asset(ribbon_path)
    draw_h = draw_w * rh / rw
    c.drawImage(reader, cx - draw_w/2, y_center - draw_h/2,
                width=draw_w, height=draw_h, mask="auto")


# ════════════════════════════════════════════════════════════════════════════
#  TABLA DE ITEMS
# ════════════════════════════════════════════════════════════════════════════

def draw_items_table(c, x0, y, w, items):
    ROW_H    = 5.5 * mm
    HEADER_H = 6.5 * mm

    cx_cant = x0 + 1*mm
    cx_desc = x0 + 10*mm
    cx_unit = x0 + w - 21*mm
    cx_imp  = x0 + w

    # Header
    _rect_filled(c, x0, y - HEADER_H, w, HEADER_H)
    for txt, x, align in [
        ("CANT.", cx_cant,          "L"),
        ("DESCRIPCIÓN", cx_desc,    "L"),
        ("P.UNIT.", cx_unit - 1*mm, "R"),
        ("IMP.",  cx_imp,           "R"),
    ]:
        c.setFont("Helvetica-Bold", 6); c.setFillColor(WHITE)
        if align == "L":
            c.drawString(x, y - HEADER_H + 1.8*mm, txt)
        else:
            c.drawRightString(x, y - HEADER_H + 1.8*mm, txt)
    y -= HEADER_H

    for i, item in enumerate(items):
        if i > 0:
            _line(c, x0, y, x0+w, 0.3, dashed=True)
        y -= ROW_H
        c.setFont("Helvetica", 6.5); c.setFillColor(BLACK)
        c.drawString(cx_cant, y + 1.3*mm, str(item["cant"]))
        c.drawString(cx_desc, y + 1.3*mm, item["desc"])
        c.drawRightString(cx_unit - 0.5*mm, y + 1.3*mm, item["unit"])
        c.drawRightString(cx_imp,  y + 1.3*mm, item["imp"])

    return y


# ════════════════════════════════════════════════════════════════════════════
#  GENERATE
# ════════════════════════════════════════════════════════════════════════════

def generate_ticket(data: dict, out_path: str, logo_path: str,
                    ribbon_path: str = None, footer_dec_path: str = None,
                    apple_path: str = None, stalk_path: str = None,
                    mono_left_path: str = None, mono_right_path: str = None):
    W  = TICKET_W_MM * mm
    MX = MARGIN_MM * mm
    CX = W / 2
    CW = W - 2*MX

    n = len(data["items"])
    H = (115 + n * 6.5 + 170) * mm

    c = rl_canvas.Canvas(out_path, pagesize=(W, H))
    c.setTitle("Ticket - La Gran Manzana")
    y = H - 2*mm

    # ── Perforación superior ──
    for xi in range(int(MX), int(W), int(4.5*mm)):
        c.setStrokeColor(colors.HexColor("#BBBBBB"))
        c.setLineWidth(0.3)
        c.circle(xi, y, 1.4*mm, fill=0, stroke=1)
    y -= 4*mm

    # ── LOGO ──
    logo_r, lw, lh = prepare_logo(logo_path)
    lw_draw = 40 * mm
    lh_draw = lw_draw * lh / lw
    c.drawImage(logo_r, CX - lw_draw/2, y - lh_draw,
                width=lw_draw, height=lh_draw, mask="auto")
    y -= lh_draw + 1*mm

    # ── Subtítulo ──
    _text_c(c, CX, y, "— VERDULERÍA & MERCADO —", 7, bold=True)
    y -= 5*mm

    # ── Ribbon ──
    rh = 9*mm
    if ribbon_path:
        r_reader, r_pw, r_ph = load_asset(ribbon_path)
        rh = CW * r_ph / r_pw
        draw_ribbon(c, CX, y - rh/2, CW, ribbon_path)
    else:
        rh = 7*mm
        _rect_filled(c, MX+3*mm, y-rh, CW-6*mm, rh)
        _text_c(c, CX, y - rh + 1.5*mm, "Gracias por elegirnos!", 7.5, bold=True, fill=WHITE)
    y -= rh + 3.5*mm

    # ── Datos empresa ──
    _text_c(c, CX, y, data["razon_social"], 7, bold=True);  y -= 4.5*mm
    for t in [
        f"Razón Social: {data['razon_social']}",
        f"CUIT: {data['cuit']}",
        f"Ing. Brutos: {data['ing_brutos']}",
        f"Inicio de Actividades: {data['inicio_act']}",
    ]:
        _text_c(c, CX, y, t, 6);  y -= 3.8*mm

    y -= 0.5*mm
    _text_c(c, CX, y, f"● {data['direccion']}", 6);  y -= 4*mm

    c.setFont("Helvetica", 6); c.setFillColor(BLACK)
    c.drawString(MX + 1*mm, y, f"⊙ {data['instagram']}")
    c.drawRightString(W - MX - 1*mm, y, f"⊕ {data['whatsapp']}")
    y -= 4*mm

    _text_c(c, CX, y, f"IVA: {data['iva_condicion']}", 6);  y -= 3*mm
    _line(c, MX, y, W-MX, dashed=True);  y -= 4*mm

    # ── Comprobante ──
    _text_c(c, CX, y, f"COMPROBANTE {data['tipo_comp']}", 8.5, bold=True);  y -= 5*mm
    c.setFont("Helvetica", 6.5); c.setFillColor(BLACK)
    c.drawString(MX, y, f"Punto de Venta: {data['pto_vta']}")
    c.drawRightString(W-MX, y, f"N°: {data['nro_comp']}")
    y -= 4*mm
    c.drawString(MX, y, f"Fecha: {data['fecha']}")
    c.drawRightString(W-MX, y, f"Hora: {data['hora']}")
    y -= 3*mm
    _line(c, MX, y, W-MX, dashed=True);  y -= 2*mm

    # ── Tabla ──
    y = draw_items_table(c, MX, y, CW, data["items"])
    y -= 2.5*mm
    _line(c, MX, y, W-MX, width=1.2);  y -= 5.5*mm

    # ── Total + pagos ──
    _text_l(c, MX, y, "TOTAL", 12, bold=True)
    _text_r(c, W-MX, y, data["total"], 12, bold=True)
    y -= 6*mm
    _text_l(c, MX+2*mm, y, "Efectivo", 7)
    _text_r(c, W-MX, y, data["efectivo"], 7)
    y -= 4.5*mm
    _text_l(c, MX+2*mm, y, "Vuelto", 7)
    _text_r(c, W-MX, y, data["vuelto"], 7)
    y -= 4*mm
    _line(c, MX, y, W-MX, width=0.8);  y -= 4*mm

    # ── Transparencia fiscal ──
    _text_c(c, CX, y, "——  TRANSPARENCIA FISCAL  ——", 6.5, bold=True);  y -= 4.5*mm
    c.setFont("Helvetica-Bold", 6); c.setFillColor(BLACK)
    c.drawString(MX, y, "Concepto")
    c.drawString(CX - 3*mm, y, "%")
    c.drawRightString(W-MX, y, "Importe")
    y -= 4*mm
    for label, pct, imp in data["fiscal_rows"]:
        fb = "Helvetica-Bold" if label.upper() == "TOTAL" else "Helvetica"
        c.setFont(fb, 6.5); c.setFillColor(BLACK)
        c.drawString(MX, y, label)
        if pct: c.drawString(CX - 3*mm, y, pct)
        c.drawRightString(W-MX, y, imp)
        y -= 4*mm

    y -= 1*mm
    _line(c, MX, y, W-MX, dashed=True);  y -= 4*mm

    # ── CAE + QR fiscal ──
    qr_sz = 20*mm
    qr_x  = W - MX - qr_sz
    y_cae = y

    for bl, rest in [
        ("CAE: ",               data["cae"]),
        ("Fecha Vto. CAE: ",    data["vto_cae"]),
        ("Cód. Autorización: ", data["cod_aut"]),
    ]:
        bw = c.stringWidth(bl, "Helvetica-Bold", 6)
        c.setFont("Helvetica-Bold", 6); c.setFillColor(BLACK)
        c.drawString(MX, y_cae, bl)
        c.setFont("Helvetica", 6)
        c.drawString(MX + bw, y_cae, rest)
        y_cae -= 3.8*mm

    for t in ["Esta Administración Federal no se",
              "responsabiliza por los datos.",
              "Verifique en:"]:
        c.setFont("Helvetica", 5.5); c.setFillColor(BLACK)
        c.drawString(MX, y_cae, t);  y_cae -= 3.3*mm
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(MX, y_cae, "www.arca.gob.ar/consulta");  y_cae -= 3.3*mm

    _text_c(c, qr_x + qr_sz/2, y + 1.5*mm, "DATOS FISCALES", 5, bold=True)
    c.drawImage(make_qr(data["qr_fiscal_url"]),
                qr_x, y - qr_sz, width=qr_sz, height=qr_sz)
    c.setFont("Helvetica", 4.5); c.setFillColor(BLACK)
    c.drawCentredString(qr_x + qr_sz/2, y - qr_sz - 2.5*mm, "ESCANEÁ PARA VER")
    c.drawCentredString(qr_x + qr_sz/2, y - qr_sz - 5*mm,   "EL COMPROBANTE")

    y = min(y_cae, y - qr_sz - 7*mm) - 2*mm
    _line(c, MX, y, W-MX, dashed=True);  y -= 4*mm

    # ── Promo + QR redes ──
    mid = W / 2
    y_promo = y
    _vline(c, mid, y_promo, y_promo - 32*mm)

    # Izquierda
    _text_l(c, MX, y_promo, "¡VOLVÉ POR MÁS!", 6.5, bold=True)
    y_promo -= 5.5*mm
    c.setFont("Helvetica-Bold", 18); c.setFillColor(BLACK)
    c.drawString(MX, y_promo, "10% OFF");  y_promo -= 6.5*mm
    _text_l(c, MX, y_promo, "EN TU PRÓXIMA COMPRA", 6, bold=True);  y_promo -= 4.5*mm
    _rect_filled(c, MX, y_promo, mid - MX - 2*mm, 5*mm)
    _text_c(c, MX + (mid-MX-2*mm)/2, y_promo + 0.5*mm,
            "PRESENTANDO ESTE TICKET", 4.8, bold=True, fill=WHITE)
    y_promo -= 5.5*mm
    c.setFont("Helvetica", 5); c.setFillColor(BLACK)
    c.drawString(MX, y_promo, f"Válido hasta: {data['promo_vto']}");  y_promo -= 3.5*mm
    c.drawString(MX, y_promo, "No acumulable c/otras promos.")

    # Derecha
    qr_r_sz = 18*mm
    qr_r_x  = mid + 2*mm
    y_redes = y
    c.setFont("Helvetica-Bold", 5.5); c.setFillColor(BLACK)
    c.drawString(qr_r_x, y_redes, "Escaneá y enterate")
    y_redes -= 3.5*mm
    c.setFont("Helvetica", 5.5)
    c.drawString(qr_r_x, y_redes, "de nuestras promos")
    y_redes -= 1*mm
    c.drawImage(make_qr(data["qr_redes_url"]),
                qr_r_x, y_redes - qr_r_sz, width=qr_r_sz, height=qr_r_sz)

    y = min(y_promo, y_redes - qr_r_sz) - 3*mm
    _line(c, MX, y, W-MX, dashed=True);  y -= 4*mm

    # ── Footer ──
    foot_h = 8*mm
    # Triguito izquierdo
    if stalk_path:
        sr, sw_px, sh_px = load_asset(stalk_path)
        sdh = foot_h * 1.1
        sdw = sdh * sw_px / sh_px
        c.drawImage(sr, MX, y - sdh + 2*mm, width=sdw, height=sdh, mask="auto")
        c.drawImage(sr, W - MX - sdw, y - sdh + 2*mm, width=sdw, height=sdh, mask="auto")
    # Texto central con rombos
    _text_c(c, CX, y - 3*mm, "♦  Gracias por su visita  ♦", 6)
    y -= foot_h

    # ── Perforación inferior ──
    for xi in range(int(MX), int(W), int(4.5*mm)):
        c.setStrokeColor(colors.HexColor("#BBBBBB"))
        c.setLineWidth(0.3)
        c.circle(xi, y, 1.4*mm, fill=0, stroke=1)

    c.save()
    print(f"✓ PDF guardado en: {out_path}")


# ════════════════════════════════════════════════════════════════════════════
#  DATOS  ← modificar para uso dinámico / conectar a base de datos
# ════════════════════════════════════════════════════════════════════════════

TICKET_DATA = {
    # ── Empresa ──
    "razon_social":  "LA GRAN MANZANA S.R.L.",
    "cuit":          "30-71685923-6",
    "ing_brutos":    "901-685923-6",
    "inicio_act":    "01/06/2025",
    "direccion":     "Calle 12 N° 3456, La Plata, Buenos Aires",
    "instagram":     "@lagranmanzana",
    "whatsapp":      "221 123 4567",
    "iva_condicion": "Responsable Inscripto",

    # ── Comprobante ──
    "tipo_comp":  "B",
    "pto_vta":    "0002",
    "nro_comp":   "0001-00012345",
    "fecha":      "24/05/2025",
    "hora":       "14:35:22",

    # ── Items ──
    "items": [
        {"cant": "1",     "desc": "Tomate Perita x kg",  "unit": "$1.650,00", "imp": "$1.650,00"},
        {"cant": "1,250", "desc": "Papa Negra x kg",     "unit": "$  950,00", "imp": "$1.187,50"},
        {"cant": "0,750", "desc": "Cebolla x kg",        "unit": "$  880,00", "imp": "$  660,00"},
        {"cant": "1",     "desc": "Zanahoria x kg",      "unit": "$  720,00", "imp": "$  720,00"},
        {"cant": "1",     "desc": "Lechuga Crespa",      "unit": "$1.200,00", "imp": "$1.200,00"},
        {"cant": "1",     "desc": "Banana x kg",         "unit": "$1.100,00", "imp": "$1.100,00"},
        {"cant": "0,500", "desc": "Manzana Roja x kg",   "unit": "$1.800,00", "imp": "$  900,00"},
    ],

    # ── Totales ──
    "total":    "$ 7.417,50",
    "efectivo": "$ 8.000,00",
    "vuelto":   "$   582,50",

    # ── Transparencia fiscal ──
    "fiscal_rows": [
        ("Subtotal Neto", "",      "$ 6.131,82"),
        ("IVA 21%",       "21,00", "$ 1.285,68"),
        ("TOTAL",         "",      "$ 7.417,50"),
    ],

    # ── CAE / AFIP ──
    "cae":            "75215012345678",
    "vto_cae":        "03/06/2025",
    "cod_aut":        "123456",
    "qr_fiscal_url":  "https://www.arca.gob.ar/fe/qr/?p=lagranmanzana",

    # ── Promo ──
    "promo_vto":      "31/07/2025",
    "qr_redes_url":   "https://instagram.com/lagranmanzana",
}

if __name__ == "__main__":
    # Rutas relativas al directorio del script
    HERE = os.path.dirname(os.path.abspath(__file__))

    generate_ticket(
        TICKET_DATA,
        out_path    = os.path.join(HERE, "ticket_lagranmanzana.pdf"),
        logo_path   = os.path.join(HERE, "logo_bw.png"),
        ribbon_path = os.path.join(HERE, "ribbon_clean.png"),
        apple_path  = os.path.join(HERE, "dec_apple.png"),
        stalk_path  = os.path.join(HERE, "dec_stalk.png"),
    )
