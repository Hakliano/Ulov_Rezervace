from datetime import timedelta


def generuj_ics(rezervace):
    salon = rezervace.salon
    sluzby = ', '.join(p.sluzba.nazev for p in rezervace.polozky.all())
    start = rezervace.zacatek.strftime('%Y%m%dT%H%M%S')
    end = rezervace.konec.strftime('%Y%m%dT%H%M%S')
    now = rezervace.vytvoreno.strftime('%Y%m%dT%H%M%S')
    uid = f'rezervace-{rezervace.id}@{salon.id}.ulovrezervaci'

    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Ulov Rezervaci//CS
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now}
DTSTART:{start}
DTEND:{end}
SUMMARY:{sluzby} – {salon.name}
DESCRIPTION:Rezervace u {salon.name}\\n{salon.address}
LOCATION:{salon.address}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR
"""
