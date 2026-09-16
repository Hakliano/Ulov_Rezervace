"""P5.6A testovací kartotéka s kompletním stromem a volitelnou rezervací."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO

from django.utils import timezone
from PIL import Image

from archivnik.models import (
    Asset,
    CustomFieldDef,
    CustomFieldValue,
    Customer,
    Entry,
    Object,
    ObjectType,
    Reminder,
)
from archivnik.storage import store_file
from rezervace.models import Rezervace, Zakaznik, Zamestnanec

DELETE_EMAIL = 'p56a.delete@p56a.ulov.local'
DELETE_PHONE = '777560001'
DELETE_NOTE = 'P5.6A delete target'


def jpeg_bytes(color=(40, 80, 120)) -> bytes:
    buf = BytesIO()
    Image.new('RGB', (24, 24), color).save(buf, format='JPEG')
    return buf.getvalue()


def _typ(salon, nazev='Pes'):
    typ = ObjectType.objects.filter(salon=salon, nazev=nazev).first()
    if typ:
        return typ
    return ObjectType.objects.create(salon=salon, nazev=nazev)


def _pole(salon, typ, nazev='Plemeno'):
    pole = CustomFieldDef.objects.filter(salon=salon, typ=typ, nazev=nazev).first()
    if pole:
        return pole
    return CustomFieldDef.objects.create(salon=salon, typ=typ, nazev=nazev, druh='text')


def pridej_asset(salon, zakaznik, *, nazev, druh='fotografie', objekt=None, zapis=None, color=(40, 80, 120)):
    raw = jpeg_bytes(color)
    asset_uuid, key, ctype, size = store_file(salon, raw, 'image/jpeg', nazev, druh)
    return Asset.objects.create(
        salon=salon,
        uuid=asset_uuid,
        zakaznik=zakaznik,
        objekt=objekt,
        zapis=zapis,
        druh=druh,
        nazev=nazev,
        content_type=ctype,
        velikost=size,
        storage_key=key,
    )


def vytvor_plnou_kartoteku(
    salon,
    *,
    jmeno='Jan',
    prijmeni='P56Amazany',
    email=DELETE_EMAIL,
    telefon=DELETE_PHONE,
    poznamka=DELETE_NOTE,
    asset_name='rentgen-max.jpg',
):
    customer = Customer.objects.create(
        salon=salon,
        jmeno=jmeno,
        prijmeni=prijmeni,
        email=email,
        telefon=telefon,
        poznamka=poznamka,
    )
    typ = _typ(salon)
    pole = _pole(salon, typ)
    objekt = Object.objects.create(salon=salon, zakaznik=customer, typ=typ, nazev='Max')
    CustomFieldValue.objects.create(objekt=objekt, pole=pole, hodnota='Labrador')
    Entry.objects.create(
        salon=salon, zakaznik=customer, text='Zápis bez objektu.', typ_zapisu='Poznámka',
    )
    zapis = Entry.objects.create(
        salon=salon, zakaznik=customer, objekt=objekt, text='Vyšetření a RTG.', typ_zapisu='Vyšetření',
    )
    Reminder.objects.create(
        salon=salon, zakaznik=customer, objekt=objekt, termin=date.today() + timedelta(days=14),
        text='Kontrola očkování',
    )
    asset = pridej_asset(
        salon, customer, nazev=asset_name, objekt=objekt, zapis=zapis, druh='dokument',
    )
    return {
        'customer': customer,
        'objekt': objekt,
        'asset': asset,
        'zapis': zapis,
    }


def zajisti_booking_se_stejnym_emailem(salon, email, nick='P56A Booking'):
    zak = Zakaznik.objects.filter(salon=salon, email=email).first()
    if zak is None:
        zak = Zakaznik.objects.create(salon=salon, nick=nick, email=email, gdpr_souhlas=True)
    owner = Zamestnanec.objects.filter(salon=salon, role=Zamestnanec.ROLE_MAJITEL).first()
    now = timezone.now()
    rez = Rezervace.objects.filter(salon=salon, zakaznik=zak).first()
    if rez is None:
        rez = Rezervace.objects.create(
            salon=salon,
            zakaznik=zak,
            zamestnanec=owner,
            zacatek=now + timedelta(days=3),
            konec=now + timedelta(days=3, hours=1),
            stav='potvrzeno',
        )
    return zak, rez
