"""Faktura PDF s Unicode fontem (čeština: ř, ě, š…)."""

from calendar import monthrange
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import PartnerNastaveni, PlatbaPartnera
from .services import primarni_ulov_ucet

# § 435 OZ: na obchodní listině jméno, sídlo, IČO a zápis v evidenci.
# RES (statistika) nestačí — OSVČ s živností uvádí živnostenský rejstřík.
DODAVATEL = {
    'jmeno': 'Jiří Hakl',
    'znacka': 'ULOV KLIENTY',
    'ico': '24552488',
    'sidlo': 'Praha - Záběhlice, Aubrechtové 3110/8, 106 00',
    'evidence': 'Fyzická osoba zapsaná v živnostenském rejstříku',
}

_FONTY_NACTENY = False
FONT = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'


def _kandidati(bold=False):
    zde = Path(__file__).resolve().parent / 'fonts'
    if bold:
        return [
            zde / 'DejaVuSans-Bold.ttf',
            Path(r'C:\Windows\Fonts\arialbd.ttf'),
            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
            Path('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'),
        ]
    return [
        zde / 'DejaVuSans.ttf',
        Path(r'C:\Windows\Fonts\arial.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'),
    ]


def _prvni_existujici(cesty):
    for cesta in cesty:
        if cesta.is_file():
            return cesta
    return None


def nacti_fonty():
    global _FONTY_NACTENY, FONT, FONT_BOLD
    if _FONTY_NACTENY:
        return FONT, FONT_BOLD
    regular = _prvni_existujici(_kandidati(False))
    bold = _prvni_existujici(_kandidati(True)) or regular
    if regular:
        pdfmetrics.registerFont(TTFont('UlovSans', str(regular)))
        pdfmetrics.registerFont(TTFont('UlovSans-Bold', str(bold)))
        FONT = 'UlovSans'
        FONT_BOLD = 'UlovSans-Bold'
    _FONTY_NACTENY = True
    return FONT, FONT_BOLD


def _max_poradi_faktur(rok):
    from .models import ExtraFaktura, PlatbaPartnera

    prefix = f'{rok}-'
    max_n = 0
    for model in (PlatbaPartnera, ExtraFaktura):
        for cislo in model.objects.filter(cislo_faktury__startswith=prefix).values_list(
            'cislo_faktury', flat=True,
        ):
            konec = (cislo or '')[len(prefix):]
            if konec.isdigit():
                max_n = max(max_n, int(konec))
    return max_n


def dalsi_cislo_faktury(rok=None):
    rok = rok or timezone.localdate().year
    return f'{rok}-{_max_poradi_faktur(rok) + 1:04d}'


def vs_extra_z_cisla(cislo):
    """Faktura 2026-0042 → VS 620260042."""
    text = (cislo or '').strip()
    if '-' not in text:
        return ''
    rok, poradi = text.split('-', 1)
    if not (rok.isdigit() and poradi.isdigit()):
        return ''
    return f'6{rok}{poradi}'[:10]


def _datum_z_date(den):
    return f'{den.day}. {den.month}. {den.year}'


def _predchozi_konec(konec, periodicita):
    if periodicita == PartnerNastaveni.PERIODA_ROK:
        try:
            return konec.replace(year=konec.year - 1)
        except ValueError:
            return konec.replace(year=konec.year - 1, day=28)
    mesic = konec.month - 1
    rok = konec.year
    if mesic == 0:
        mesic = 12
        rok -= 1
    den = min(konec.day, monthrange(rok, mesic)[1])
    return date(rok, mesic, den)


def _nazev_polozky(partner):
    tarif = (partner.tarif or '').strip()
    if not tarif:
        return 'Partnerství'
    if 'partnerst' in tarif.lower():
        return tarif
    return f'{tarif} – Partnerství'


def _obdobi_sluzby(platba, partner):
    konec = platba.splatnost
    zacatek = _predchozi_konec(konec, partner.periodicita) + timedelta(days=1)
    return f'{_datum_z_date(zacatek)} – {_datum_z_date(konec)}'


def vychozi_data_faktury(platba):
    salon = platba.salon
    partner = salon.partner_nastaveni
    castka = platba.prijata_castka if platba.prijata_castka is not None else platba.ocekavana_castka
    uhrada = platba.zaplaceno_dne
    vystaveni = timezone.localdate()
    polozka = _nazev_polozky(partner)
    obdobi = _obdobi_sluzby(platba, partner)
    return {
        'cislo': platba.cislo_faktury or dalsi_cislo_faktury(vystaveni.year),
        'datum_vystaveni': vystaveni.isoformat(),
        'datum_uhrady': uhrada.isoformat(),
        'zpusob_uhrady': 'převodem',
        'stav': 'UHRAZENO',
        'dodavatel_jmeno': DODAVATEL['jmeno'],
        'dodavatel_znacka': DODAVATEL['znacka'],
        'dodavatel_ico': DODAVATEL['ico'],
        'dodavatel_sidlo': DODAVATEL['sidlo'],
        'dodavatel_evidence': DODAVATEL['evidence'],
        'odberatel_nazev': salon.name,
        'odberatel_ico': partner.ico or '',
        'odberatel_adresa': salon.address or '',
        'odberatel_email': partner.fakturacni_email or salon.email or '',
        'polozka': polozka,
        'obdobi': obdobi,
        'popis': f'{polozka} | období {obdobi}',
        'castka': f'{castka:.2f}'.replace('.', ','),
        'vs': platba.variabilni_symbol or partner.variabilni_symbol or '',
        'ucet': primarni_ulov_ucet() or partner.ulov_cislo_uctu or '',
        'poznamka': platba.poznamka or '',
        'je_k_uhrade': False,
        'datum_splatnosti': '',
    }


def vychozi_data_extra_faktury(faktura):
    salon = faktura.salon
    try:
        partner = salon.partner_nastaveni
    except PartnerNastaveni.DoesNotExist:
        partner = None
    k_uhrade = faktura.stav == faktura.STAV_K_UHRADE
    return {
        'cislo': faktura.cislo_faktury,
        'datum_vystaveni': faktura.datum_vystaveni.isoformat(),
        'datum_uhrady': faktura.datum_uhrady.isoformat() if faktura.datum_uhrady else '',
        'datum_splatnosti': (
            faktura.datum_splatnosti.isoformat() if faktura.datum_splatnosti else ''
        ),
        'zpusob_uhrady': 'převodem',
        'stav': 'K úhradě' if k_uhrade else 'UHRAZENO',
        'je_k_uhrade': k_uhrade,
        'dodavatel_jmeno': DODAVATEL['jmeno'],
        'dodavatel_znacka': DODAVATEL['znacka'],
        'dodavatel_ico': DODAVATEL['ico'],
        'dodavatel_sidlo': DODAVATEL['sidlo'],
        'dodavatel_evidence': DODAVATEL['evidence'],
        'odberatel_nazev': salon.name,
        'odberatel_ico': (partner.ico if partner else '') or '',
        'odberatel_adresa': salon.address or '',
        'odberatel_email': (
            (partner.fakturacni_email if partner else '') or salon.email or ''
        ),
        'polozka': faktura.popis,
        'obdobi': '',
        'popis': faktura.popis,
        'castka': f'{faktura.castka:.2f}'.replace('.', ','),
        'vs': faktura.variabilni_symbol or '',
        'ucet': primarni_ulov_ucet() or ((partner.ulov_cislo_uctu if partner else '') or ''),
        'poznamka': faktura.poznamka or '',
    }


def _esc(text):
    return (
        (text or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _datum_cs(raw):
    text = (raw or '').strip()
    if len(text) >= 10 and text[4] == '-' and text[7] == '-':
        return f'{int(text[8:10])}. {int(text[5:7])}. {text[:4]}'
    return text


def vygeneruj_fakturu_pdf(data):
    """Vrátí bytes PDF. Font musí umět české znaky."""
    regular, bold = nacti_fonty()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Faktura {data.get('cislo') or ''}",
        author=data.get('dodavatel_jmeno') or 'ULOV KLIENTY',
    )
    styly = getSampleStyleSheet()
    znacka = ParagraphStyle('znacka', parent=styly['Normal'], fontName=regular, fontSize=9, textColor=colors.HexColor('#5c6b7a'), spaceAfter=4, leading=12)
    nadpis = ParagraphStyle('nadpis', parent=styly['Normal'], fontName=bold, fontSize=18, textColor=colors.HexColor('#1e3a5f'), spaceAfter=8, leading=22)
    telo = ParagraphStyle('telo', parent=styly['Normal'], fontName=regular, fontSize=10, leading=14, textColor=colors.HexColor('#1a1a1a'))
    tucne = ParagraphStyle('tucne', parent=telo, fontName=bold)
    hlavicka = ParagraphStyle('hlavicka', parent=tucne, textColor=colors.white)
    male = ParagraphStyle('male', parent=telo, fontSize=8, textColor=colors.HexColor('#5c6b7a'))

    castka = (data.get('castka') or '0').replace(' ', '')
    prvky = [
        Paragraph('ULOV KLIENTY', znacka),
        Paragraph('Faktura', nadpis),
        Paragraph(f"Číslo: <b>{_esc(data.get('cislo') or '—')}</b>", telo),
        Spacer(1, 8 * mm),
    ]
    stranky = [
        [
            Paragraph('<b>Dodavatel</b>', tucne),
            Paragraph('<b>Odběratel</b>', tucne),
        ],
        [
            Paragraph(
                f"{_esc(data.get('dodavatel_jmeno'))}<br/>"
                f"{_esc(data.get('dodavatel_znacka') or DODAVATEL['znacka'])}<br/>"
                f"IČO: {_esc(data.get('dodavatel_ico'))}<br/>"
                f"{_esc(data.get('dodavatel_sidlo'))}<br/>"
                f"{_esc(data.get('dodavatel_evidence'))}",
                telo,
            ),
            Paragraph(
                f"{_esc(data.get('odberatel_nazev'))}<br/>"
                + (f"IČO: {_esc(data.get('odberatel_ico'))}<br/>" if data.get('odberatel_ico') else '')
                + f"{_esc(data.get('odberatel_adresa'))}<br/>"
                + f"{_esc(data.get('odberatel_email'))}",
                telo,
            ),
        ],
    ]
    tabulka_osob = Table(stranky, colWidths=[85 * mm, 85 * mm])
    tabulka_osob.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f4f7fa')),
        ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#1e3a5f')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d0d7de')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    prvky += [tabulka_osob, Spacer(1, 8 * mm)]
    k_uhrade = bool(data.get('je_k_uhrade')) or (data.get('stav') or '').lower().startswith('k úhrad')
    druha_popis = 'Datum splatnosti' if k_uhrade else 'Datum úhrady'
    druha_hodnota = data.get('datum_splatnosti') if k_uhrade else (
        data.get('datum_uhrady') or data.get('datum_splatnosti')
    )
    meta = Table(
        [[
            Paragraph(f"Datum vystavení<br/><b>{_esc(_datum_cs(data.get('datum_vystaveni')))}</b>", telo),
            Paragraph(f"{druha_popis}<br/><b>{_esc(_datum_cs(druha_hodnota))}</b>", telo),
            Paragraph(f"Variabilní symbol<br/><b>{_esc(data.get('vs') or '—')}</b>", telo),
        ]],
        colWidths=[57 * mm, 57 * mm, 56 * mm],
    )
    meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f4f7fa')),
        ('BOX', (0, 0), (-1, -1), 0.3, colors.HexColor('#d0d7de')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    prvky += [meta, Spacer(1, 4 * mm)]
    prvky.append(Paragraph(
        f"Způsob úhrady: <b>{_esc(data.get('zpusob_uhrady') or 'převodem')}</b>"
        f" &nbsp;·&nbsp; Stav: <b>{_esc(data.get('stav') or 'UHRAZENO')}</b>",
        telo,
    ))
    prvky.append(Spacer(1, 8 * mm))
    polozka = data.get('polozka') or data.get('popis') or 'Partnerství'
    obdobi = data.get('obdobi') or ''
    polozky = Table(
        [
            [
                Paragraph('<b>Položka</b>', hlavicka),
                Paragraph('<b>Období služby</b>', hlavicka),
                Paragraph('<b>Částka</b>', hlavicka),
            ],
            [
                Paragraph(_esc(polozka), telo),
                Paragraph(_esc(obdobi or '—'), telo),
                Paragraph(f"<b>{_esc(castka)} Kč</b>", tucne),
            ],
        ],
        colWidths=[70 * mm, 60 * mm, 40 * mm],
    )
    polozky.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#1e3a5f')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#d0d7de')),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 1), (-1, 1), colors.white),
    ]))
    prvky += [polozky, Spacer(1, 8 * mm)]
    celkem_label = 'Celkem k úhradě' if k_uhrade else 'Celkem uhrazeno'
    prvky.append(Paragraph(f"{celkem_label}: <b>{_esc(castka)} Kč</b>", nadpis))
    prvky.append(Paragraph(f"Stav: <b>{_esc(data.get('stav') or 'UHRAZENO')}</b>", tucne))
    if data.get('ucet'):
        prvky.append(Paragraph(f"Číslo účtu: <b>{_esc(data.get('ucet'))}</b>", telo))
    if data.get('poznamka'):
        prvky += [Spacer(1, 4 * mm), Paragraph(_esc(data.get('poznamka')), telo)]
    prvky += [
        Spacer(1, 14 * mm),
        Paragraph('Dodavatel není plátcem DPH.', male),
        Paragraph('Doklad je vystaven elektronicky.', male),
    ]
    doc.build(prvky)
    return buffer.getvalue()


def uloz_fakturu_k_platbe(platba, data):
    pdf = vygeneruj_fakturu_pdf(data)
    cislo = (data.get('cislo') or dalsi_cislo_faktury()).strip()
    if platba.faktura_pdf:
        platba.faktura_pdf.close()
        platba.faktura_pdf.delete(save=False)
    platba.cislo_faktury = cislo
    platba.faktura_pdf.save(f'faktura-{cislo}.pdf', ContentFile(pdf), save=False)
    platba.save(update_fields=['faktura_pdf', 'cislo_faktury'])
    return platba


def zajisti_fakturu(platba, *, prepsat=False):
    """Jedna faktura na platbu. Opakované volání nic nepřidá, pokud PDF už existuje."""
    if platba.faktura_pdf and not prepsat:
        return platba, False
    return uloz_fakturu_k_platbe(platba, vychozi_data_faktury(platba)), True


def odesli_fakturu_partnerovi(platba):
    """Pošle PDF na fakturační e-mail. Nehází výjimku — vrací (ok, zprava)."""
    from django.conf import settings
    from django.core.mail import EmailMessage

    partner = platba.salon.partner_nastaveni
    prijemce = (partner.fakturacni_email or platba.salon.email or '').strip()
    if not prijemce:
        return False, 'chybí fakturační e-mail'
    if not platba.faktura_pdf:
        return False, 'chybí PDF'
    cislo = platba.cislo_faktury or 'faktura'
    try:
        with platba.faktura_pdf.open('rb') as handle:
            obsah = handle.read()
        zprava = EmailMessage(
            subject=f'Faktura {cislo} – ULOV KLIENTY',
            body=(
                f'Dobrý den,\n\n'
                f'přijali jsme platbu a vystavili fakturu {cislo}.\n'
                f'Stav: UHRAZENO. PDF je v příloze.\n\n'
                f'ULOV KLIENTY\n'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[prijemce],
        )
        zprava.attach(f'faktura-{cislo}.pdf', obsah, 'application/pdf')
        zprava.send(fail_silently=False)
    except Exception as exc:
        return False, str(exc)[:300]
    return True, prijemce


def uloz_fakturu_extra(faktura, data=None):
    data = data or vychozi_data_extra_faktury(faktura)
    pdf = vygeneruj_fakturu_pdf(data)
    cislo = (data.get('cislo') or faktura.cislo_faktury or dalsi_cislo_faktury()).strip()
    if faktura.faktura_pdf:
        faktura.faktura_pdf.close()
        faktura.faktura_pdf.delete(save=False)
    faktura.cislo_faktury = cislo
    faktura.faktura_pdf.save(f'faktura-{cislo}.pdf', ContentFile(pdf), save=False)
    faktura.save(update_fields=['faktura_pdf', 'cislo_faktury'])
    return faktura


def odesli_extra_fakturu_partnerovi(faktura):
    from django.conf import settings
    from django.core.mail import EmailMessage

    try:
        partner = faktura.salon.partner_nastaveni
        prijemce = (partner.fakturacni_email or faktura.salon.email or '').strip()
    except PartnerNastaveni.DoesNotExist:
        prijemce = (faktura.salon.email or '').strip()
    if not prijemce:
        return False, 'chybí fakturační e-mail'
    if not faktura.faktura_pdf:
        return False, 'chybí PDF'
    cislo = faktura.cislo_faktury or 'faktura'
    k_uhrade = faktura.stav == faktura.STAV_K_UHRADE
    splatnost = (
        f'{faktura.datum_splatnosti.day}. {faktura.datum_splatnosti.month}. {faktura.datum_splatnosti.year}'
        if faktura.datum_splatnosti else '—'
    )
    if k_uhrade:
        telo = (
            f'Dobrý den,\n\n'
            f'vystavili jsme fakturu {cislo} k úhradě.\n'
            f'Položka: {faktura.popis}\n'
            f'Částka: {faktura.castka:.2f} Kč\n'
            f'VS: {faktura.variabilni_symbol or "—"}\n'
            f'Splatnost: {splatnost}\n\n'
            f'PDF je v příloze.\n\n'
            f'ULOV KLIENTY\n'
        )
    else:
        telo = (
            f'Dobrý den,\n\n'
            f'vystavili jsme fakturu {cislo}.\n'
            f'Stav: UHRAZENO. PDF je v příloze.\n\n'
            f'ULOV KLIENTY\n'
        )
    try:
        with faktura.faktura_pdf.open('rb') as handle:
            obsah = handle.read()
        zprava = EmailMessage(
            subject=f'Faktura {cislo} – ULOV KLIENTY',
            body=telo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[prijemce],
        )
        zprava.attach(f'faktura-{cislo}.pdf', obsah, 'application/pdf')
        zprava.send(fail_silently=False)
    except Exception as exc:
        return False, str(exc)[:300]
    return True, prijemce


def vygeneruj_souhrn_pdf(data):
    """Souhrn za období: součty nahoře, pod nimi výpis všech faktur."""
    regular, bold = nacti_fonty()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=data.get('nadpis') or 'Souhrn',
        author='ULOV KLIENTY',
    )
    styly = getSampleStyleSheet()
    nadpis = ParagraphStyle('nadpis', parent=styly['Normal'], fontName=bold, fontSize=16, textColor=colors.HexColor('#1e3a5f'), spaceAfter=6, leading=20)
    telo = ParagraphStyle('telo', parent=styly['Normal'], fontName=regular, fontSize=10, leading=14, textColor=colors.HexColor('#1a1a1a'))
    tucne = ParagraphStyle('tucne', parent=telo, fontName=bold)
    male = ParagraphStyle('male', parent=telo, fontSize=8, textColor=colors.HexColor('#5c6b7a'))
    bunka = ParagraphStyle('bunka', parent=telo, fontSize=7, leading=9)
    hlavicka = ParagraphStyle('hlavicka', parent=bunka, fontName=bold, textColor=colors.white)
    prvky = [
        Paragraph('ULOV KLIENTY', telo),
        Paragraph(_esc(data.get('nadpis') or 'Souhrn'), nadpis),
        Paragraph(_esc(data.get('odstavec') or ''), telo),
        Spacer(1, 6 * mm),
        Paragraph(f"Vystaveno faktur: <b>{_esc(str(data.get('pocet_faktur') or 0))}</b>", telo),
        Paragraph(f"Tržby (uhrazeno): <b>{_esc(data.get('trzby') or '0,00')} Kč</b>", tucne),
        Paragraph(f"K úhradě: <b>{_esc(data.get('k_uhrade') or '0,00')} Kč</b>", telo),
        Paragraph(f"Výdaje: <b>{_esc(data.get('vydaje') or '0,00')} Kč</b>", telo),
        Spacer(1, 5 * mm),
        Paragraph('KAM', tucne),
    ]
    for radek in data.get('kam') or []:
        prvky.append(Paragraph(
            f"{_esc(radek.get('jmeno') or '—')}: {_esc(radek.get('castka') or '0,00')} Kč",
            telo,
        ))
    if not data.get('kam'):
        prvky.append(Paragraph('V období žádné uvolněné provize.', telo))
    prvky.append(Spacer(1, 7 * mm))
    prvky.append(Paragraph('Výpis faktur', tucne))
    vypis = data.get('vypis') or []
    if vypis:
        hlavicky = ['Číslo', 'Partner', 'Položka', 'Vystaveno', 'Úhrada', 'Stav', 'Částka', 'VS']
        tabulka = [[Paragraph(f'<b>{_esc(h)}</b>', hlavicka) for h in hlavicky]]
        for radek in vypis:
            tabulka.append([
                Paragraph(_esc(radek.get('cislo')), bunka),
                Paragraph(_esc(radek.get('partner')), bunka),
                Paragraph(_esc(radek.get('polozka')), bunka),
                Paragraph(_esc(radek.get('vystaveno')), bunka),
                Paragraph(_esc(radek.get('uhrada')), bunka),
                Paragraph(_esc(radek.get('stav')), bunka),
                Paragraph(_esc(radek.get('castka')), bunka),
                Paragraph(_esc(radek.get('vs')), bunka),
            ])
        sirky = [28 * mm, 48 * mm, 55 * mm, 24 * mm, 24 * mm, 24 * mm, 28 * mm, 28 * mm]
        grid = Table(tabulka, colWidths=sirky, repeatRows=1)
        grid.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('BOX', (0, 0), (-1, -1), 0.3, colors.HexColor('#1e3a5f')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#d0d7de')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ALIGN', (6, 1), (6, -1), 'RIGHT'),
        ]))
        prvky.append(grid)
    else:
        prvky.append(Paragraph('V období žádná faktura.', telo))
    prvky += [
        Spacer(1, 10 * mm),
        Paragraph(_esc(data.get('obdobi_label') or ''), male),
        Paragraph('Dodavatel není plátcem DPH. Interní souhrn, ne daňový doklad.', male),
    ]
    doc.build(prvky)
    return buffer.getvalue()
