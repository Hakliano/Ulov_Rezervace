from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from archivnik.auth import (
    authenticate_zamestnanec,
    create_session,
    get_actor_from_request,
    get_session_from_request,
)
from archivnik.kartoteka_delete import KartotekaDeleteError, smaz_kartoteku_zakaznika
from archivnik.models import (
    Asset,
    AssetKind,
    Customer,
    Entry,
    Object,
    Obor,
    ObjectType,
    Reminder,
    ReminderStav,
    Stav,
    Tag,
)
from archivnik.permissions import ArchivnikPermission
from archivnik.serializers import (
    CustomerListSerializer,
    CustomerWriteSerializer,
    EntrySerializer,
    EntryWriteSerializer,
    ObjectSerializer,
    ObjectTypeSerializer,
    ObjectTypeWriteSerializer,
    OborSerializer,
    ObjectWriteSerializer,
    ReminderSerializer,
    ReminderWriteSerializer,
    TagSerializer,
)


def _user_payload(zam):
    from archivnik.services import salon_config_status
    payload = {
        'jmeno': zam.jmeno,
        'email': zam.prihlasovaci_jmeno,
        'role': zam.role,
        'provozovna': zam.salon.name,
        'je_spravce': zam.role == zam.ROLE_MAJITEL,
    }
    payload.update(salon_config_status(zam.salon))
    return payload


def _actor(request):
    return get_actor_from_request(request)


def _salon(request):
    return _actor(request).salon


def _validation_detail(exc):
    if getattr(exc, 'messages', None):
        return '; '.join(str(m) for m in exc.messages)
    return str(exc)


def _objects_qs(salon):
    return (
        Object.objects.filter(salon=salon)
        .select_related('typ', 'zakaznik', 'cover')
        .prefetch_related('tagy')
        .annotate(
            zapisy_pocet=Count('zapisy', distinct=True),
            posledni_zapis=Max('zapisy__nastalo'),
            pripominky_aktivni=Count(
                'pripominky',
                filter=Q(pripominky__stav=ReminderStav.AKTIVNI),
                distinct=True,
            ),
        )
    )


def _tags(salon, uuids, *, for_zakaznik=False, for_objekt=False):
    if not uuids:
        return Tag.objects.none()
    qs = Tag.objects.filter(salon=salon, uuid__in=uuids)
    if for_zakaznik:
        qs = qs.exclude(rozsah='objekt')
    if for_objekt:
        qs = qs.exclude(rozsah='zakaznik')
    return qs


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email') or ''
        password = request.data.get('password') or ''
        zam, err = authenticate_zamestnanec(email, password)
        if err == 'module_off':
            return Response(
                {'detail': 'Archivník není pro tuto provozovnu zapnutý.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not zam:
            return Response({'detail': 'Neplatné přihlašovací údaje.'}, status=status.HTTP_401_UNAUTHORIZED)
        session = create_session(zam)
        payload = _user_payload(zam)
        payload['token'] = str(session.token)
        return Response(payload)


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def post(self, request):
        session = get_session_from_request(request)
        if session:
            session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        return Response(_user_payload(_actor(request)))


_MONTHS_CS = ('led', 'úno', 'bře', 'dub', 'kvě', 'čvn', 'čvc', 'srp', 'zář', 'říj', 'lis', 'pro')


def _add_months(dt, months):
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    return dt.replace(year=y, month=m, day=1, hour=0, minute=0, second=0, microsecond=0)


def _overview_aktivita(salon, month_start):
    rows = []
    for offset in range(5, -1, -1):
        start = _add_months(month_start, -offset)
        end = _add_months(start, 1)
        rows.append({
            'mesic': f'{start.year:04d}-{start.month:02d}',
            'label': _MONTHS_CS[start.month - 1],
            'zakaznici': Customer.objects.filter(salon=salon, vytvoreno__gte=start, vytvoreno__lt=end).count(),
            'zapisy': Entry.objects.filter(salon=salon, vytvoreno__gte=start, vytvoreno__lt=end).count(),
        })
    return rows


def _overview_feed(salon):
    events = []
    for row in Entry.objects.filter(salon=salon).select_related('zakaznik', 'objekt', 'objekt__typ').order_by('-vytvoreno')[:12]:
        events.append({
            'druh': 'zapis',
            'cas': row.vytvoreno.isoformat(),
            'titulek': row.nadpis or row.typ_zapisu or 'Zápis',
            'subjekt': row.objekt.display_name if row.objekt_id else row.zakaznik.display_name,
            'zakaznik_uuid': str(row.zakaznik.uuid),
            'objekt_uuid': str(row.objekt.uuid) if row.objekt_id else None,
        })
    for row in Asset.objects.filter(salon=salon).select_related('zakaznik', 'objekt', 'objekt__typ').order_by('-vytvoreno')[:12]:
        events.append({
            'druh': 'fotografie' if row.druh == AssetKind.FOTOGRAFIE else 'dokument',
            'cas': row.vytvoreno.isoformat(),
            'titulek': row.nazev,
            'subjekt': row.objekt.display_name if row.objekt_id else row.zakaznik.display_name,
            'zakaznik_uuid': str(row.zakaznik.uuid),
            'objekt_uuid': str(row.objekt.uuid) if row.objekt_id else None,
        })
    for row in Object.objects.filter(salon=salon).select_related('zakaznik', 'typ').order_by('-vytvoreno')[:8]:
        events.append({
            'druh': 'objekt',
            'cas': row.vytvoreno.isoformat(),
            'titulek': f'Nový objekt {row.display_name}',
            'subjekt': row.zakaznik.display_name,
            'zakaznik_uuid': str(row.zakaznik.uuid),
            'objekt_uuid': str(row.uuid),
        })
    for row in Reminder.objects.filter(salon=salon).select_related('zakaznik', 'objekt', 'objekt__typ').order_by('-vytvoreno')[:8]:
        events.append({
            'druh': 'pripominka',
            'cas': row.vytvoreno.isoformat(),
            'titulek': row.text,
            'subjekt': row.objekt.display_name if row.objekt_id else row.zakaznik.display_name,
            'zakaznik_uuid': str(row.zakaznik.uuid),
            'objekt_uuid': str(row.objekt.uuid) if row.objekt_id else None,
        })
    events.sort(key=lambda item: item['cas'], reverse=True)
    return events[:12]


def _overview_hlaseni(salon, month_start, zapisy_mesic, pripominky_aktivni, zakaznici, objekty):
    last_start = _add_months(month_start, -1)
    zapisy_minuly = Entry.objects.filter(
        salon=salon, vytvoreno__gte=last_start, vytvoreno__lt=month_start,
    ).count()
    bez_zapisu = (
        Object.objects.filter(salon=salon, stav=Stav.AKTIVNI)
        .annotate(n=Count('zapisy'))
        .filter(n=0)
        .count()
    )
    items = []
    if zakaznici == 0 and objekty == 0:
        items.append('Kartotéka je prázdná. Začněte prvním zákazníkem — typy objektů si nastavíte v Nastavení.')
        return items
    if pripominky_aktivni:
        if pripominky_aktivni == 1:
            items.append('Čeká 1 aktivní připomínka.')
        else:
            items.append(f'Čeká {pripominky_aktivni} aktivních připomínek.')
    if zapisy_mesic > zapisy_minuly:
        items.append(
            f'Tento měsíc máte {zapisy_mesic} zápisů, o {zapisy_mesic - zapisy_minuly} víc než minulý měsíc.'
        )
    elif zapisy_mesic < zapisy_minuly:
        items.append(
            f'Tento měsíc máte {zapisy_mesic} zápisů, o {zapisy_minuly - zapisy_mesic} méně než minulý měsíc.'
        )
    elif zapisy_mesic:
        items.append(f'Tento měsíc máte stejně zápisů jako minulý měsíc ({zapisy_mesic}).')
    else:
        items.append('Tento měsíc zatím nemáte žádný zápis.')
    if bez_zapisu:
        if bez_zapisu == 1:
            items.append('1 objekt zatím nemá žádný zápis.')
        else:
            items.append(f'{bez_zapisu} objektů zatím nemá žádný zápis.')
    if not items:
        items.append('V kartotéce je klid. Nic zásadního teď nevyžaduje pozornost.')
    return items[:3]


class OverviewView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        by_type = list(
            Object.objects.filter(salon=salon, stav=Stav.AKTIVNI)
            .values('typ__nazev')
            .annotate(pocet=Count('id'))
            .order_by('-pocet')
        )
        upcoming = Reminder.objects.filter(
            salon=salon, stav=ReminderStav.AKTIVNI,
        ).select_related('zakaznik', 'objekt', 'objekt__typ', 'prirazeny').order_by('termin', 'id')[:8]
        zakaznici = Customer.objects.filter(salon=salon, stav=Stav.AKTIVNI).count()
        objekty = Object.objects.filter(salon=salon, stav=Stav.AKTIVNI).count()
        zapisy_mesic = Entry.objects.filter(salon=salon, vytvoreno__gte=month_start).count()
        pripominky_aktivni = Reminder.objects.filter(salon=salon, stav=ReminderStav.AKTIVNI).count()
        return Response({
            'provozovna': salon.name,
            'zakaznici': zakaznici,
            'objekty': objekty,
            'zapisy_mesic': zapisy_mesic,
            'pripominky_aktivni': pripominky_aktivni,
            'podle_typu': [{'typ': r['typ__nazev'], 'pocet': r['pocet']} for r in by_type],
            'nejblizsi_pripominky': ReminderSerializer(upcoming, many=True).data,
            'aktivita': _overview_aktivita(salon, month_start),
            'posledni_aktivita': _overview_feed(salon),
            'hlaseni': _overview_hlaseni(
                salon, month_start, zapisy_mesic, pripominky_aktivni, zakaznici, objekty,
            ),
        })


class SearchView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'zakaznici': [], 'objekty': []})
        customers = Customer.objects.filter(salon=salon).filter(
            Q(jmeno__icontains=q) | Q(prijmeni__icontains=q) | Q(telefon__icontains=q) | Q(email__icontains=q)
        )[:20]
        objects = Object.objects.filter(salon=salon).select_related('typ', 'zakaznik').filter(
            Q(nazev__icontains=q) | Q(typ__nazev__icontains=q)
        )[:20]
        return Response({
            'zakaznici': CustomerListSerializer(customers, many=True).data,
            'objekty': ObjectSerializer(objects, many=True).data,
        })


class CustomerListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        qs = Customer.objects.filter(salon=salon).annotate(objekty_pocet=Count('objekty')).prefetch_related('tagy')
        stav = request.query_params.get('stav')
        if stav in (Stav.AKTIVNI, Stav.ARCHIVOVANY):
            qs = qs.filter(stav=stav)
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(jmeno__icontains=q) | Q(prijmeni__icontains=q) | Q(telefon__icontains=q) | Q(email__icontains=q)
            )
        return Response(CustomerListSerializer(qs[:200], many=True).data)

    def post(self, request):
        ser = CustomerWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        actor = _actor(request)
        customer = Customer(
            salon=actor.salon,
            jmeno=(data.get('jmeno') or '').strip(),
            prijmeni=data['prijmeni'].strip(),
            telefon=(data.get('telefon') or '').strip(),
            email=(data.get('email') or '').strip().lower(),
            adresa=(data.get('adresa') or '').strip(),
            poznamka=(data.get('poznamka') or '').strip(),
            stav=data.get('stav') or Stav.AKTIVNI,
            vytvoril=actor,
            zmenil=actor,
        )
        try:
            customer.save()
        except IntegrityError:
            return Response(
                {'detail': 'Zákazník s tímto e-mailem už v provozovně existuje.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tags = _tags(actor.salon, data.get('tagy') or [], for_zakaznik=True)
        if tags.exists():
            customer.tagy.set(tags)
        customer.objekty_pocet = 0
        return Response(CustomerListSerializer(customer).data, status=status.HTTP_201_CREATED)


class CustomerDetailView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def _get(self, request, customer_uuid):
        return Customer.objects.filter(salon=_salon(request), uuid=customer_uuid).prefetch_related('tagy').first()

    def get(self, request, customer_uuid):
        c = self._get(request, customer_uuid)
        if not c:
            return Response({'detail': 'Zákazník nenalezen.'}, status=404)
        c.objekty_pocet = c.objekty.count()
        return Response(CustomerListSerializer(c).data)

    def patch(self, request, customer_uuid):
        c = self._get(request, customer_uuid)
        if not c:
            return Response({'detail': 'Zákazník nenalezen.'}, status=404)
        ser = CustomerWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        for field in ('jmeno', 'prijmeni', 'telefon', 'adresa', 'poznamka', 'stav'):
            if field in data:
                setattr(c, field, (data[field] or '').strip() if field != 'stav' else data[field])
        if 'email' in data:
            c.email = (data['email'] or '').strip().lower()
        c.zmenil = _actor(request)
        try:
            c.save()
        except IntegrityError:
            return Response(
                {'detail': 'Zákazník s tímto e-mailem už v provozovně existuje.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if 'tagy' in data:
            c.tagy.set(_tags(_salon(request), data.get('tagy') or [], for_zakaznik=True))
        c.objekty_pocet = c.objekty.count()
        return Response(CustomerListSerializer(c).data)

    def delete(self, request, customer_uuid):
        actor = _actor(request)
        if actor.role != actor.ROLE_MAJITEL:
            return Response(
                {'detail': 'Odstranit zákazníka smí jen majitel provozovny.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        c = self._get(request, customer_uuid)
        if not c:
            return Response({'detail': 'Zákazník nenalezen.'}, status=404)
        potvrzeni = (request.data.get('potvrzeni') or '').strip()
        if potvrzeni != c.display_name:
            return Response(
                {'detail': 'Pro potvrzení napište přesné jméno zákazníka.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            smaz_kartoteku_zakaznika(actor.salon, c.uuid)
        except KartotekaDeleteError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OborListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        qs = Obor.objects.filter(salon=salon).annotate(typy_pocet=Count('typy', distinct=True))
        return Response(OborSerializer(qs, many=True).data)

    def post(self, request):
        ser = OborSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            from archivnik.services import create_obor
            obor = create_obor(
                salon=_salon(request),
                nazev=ser.validated_data['nazev'],
                objekt_jednotne=ser.validated_data.get('objekt_jednotne') or 'Objekt',
                objekt_mnozne=ser.validated_data.get('objekt_mnozne') or 'Objekty',
            )
        except IntegrityError:
            return Response({'detail': 'Obor s tímto názvem už existuje.'}, status=400)
        except Exception as exc:
            return Response({'detail': _validation_detail(exc)}, status=400)
        return Response(OborSerializer(obor).data, status=201)


class PresetListView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        from archivnik.presets import list_presets
        return Response(list_presets())


class PresetApplyView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def post(self, request):
        salon = _salon(request)
        from archivnik.presets import get_preset
        from archivnik.services import apply_preset, salon_is_onboarded
        if salon_is_onboarded(salon):
            return Response(
                {
                    'detail': (
                        'Obor už je nastavený. Další systémový preset může přidat '
                        'jen správa Archivníka.'
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        kod = (request.data.get('kod') or '').strip()
        try:
            get_preset(kod)
        except KeyError:
            return Response({'detail': 'Neznámý preset.'}, status=400)
        result = apply_preset(salon, kod)
        obor = result['obor']
        payload = OborSerializer(obor).data
        payload.update({
            'created': result['created'],
            'skipped': result['skipped'],
            'created_types': result['created_types'],
            'created_fields': result['created_fields'],
        })
        return Response(payload, status=201 if result['created'] else 200)


class ObjectTypeListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        qs = ObjectType.objects.filter(salon=salon).select_related('obor').prefetch_related('pole')
        ou = request.query_params.get('obor')
        if ou == 'bez':
            qs = qs.filter(obor__isnull=True)
        elif ou:
            qs = qs.filter(obor__uuid=ou)
        return Response(ObjectTypeSerializer(qs, many=True).data)

    def post(self, request):
        ser = ObjectTypeWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        salon = _salon(request)
        obor = Obor.objects.filter(salon=salon, uuid=data['obor_uuid']).first()
        if not obor:
            return Response({'detail': 'Obor nenalezen.'}, status=400)
        try:
            obj = ObjectType(
                salon=salon,
                obor=obor,
                nazev=data['nazev'].strip(),
                poradi=data.get('poradi') or (obor.typy.count() + 1),
                vyzaduje_nazev=data.get('vyzaduje_nazev', True),
            )
            obj.save()
        except IntegrityError:
            return Response({'detail': 'Typ s tímto názvem už v provozovně existuje.'}, status=400)
        except Exception as extra:
            return Response({'detail': _validation_detail(extra)}, status=400)
        return Response(ObjectTypeSerializer(obj).data, status=201)


class ObjectListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        qs = _objects_qs(salon)
        cu = request.query_params.get('zakaznik')
        if cu:
            qs = qs.filter(zakaznik__uuid=cu)
        q = (request.query_params.get('q') or '').strip()
        if q:
            qs = qs.filter(Q(nazev__icontains=q) | Q(typ__nazev__icontains=q))
        return Response(ObjectSerializer(qs[:200], many=True, context={'request': request}).data)

    def post(self, request):
        ser = ObjectWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        salon = _salon(request)
        actor = _actor(request)
        if not data.get('zakaznik_uuid') or not data.get('typ_uuid'):
            return Response({'detail': 'Zadejte zákazníka a typ objektu.'}, status=400)
        zakaznik = Customer.objects.filter(salon=salon, uuid=data['zakaznik_uuid']).first()
        typ = ObjectType.objects.filter(salon=salon, uuid=data['typ_uuid']).first()
        if not zakaznik:
            return Response({'detail': 'Zákazník nenalezen.'}, status=400)
        if not typ:
            return Response({'detail': 'Typ objektu nenalezen.'}, status=400)
        from archivnik.services import object_type_allowed_for_assign
        if not object_type_allowed_for_assign(salon, typ):
            return Response(
                {'detail': 'Tento typ nepatří k oboru kartotéky.'},
                status=400,
            )
        nazev = (data.get('nazev') or '').strip()
        if typ.vyzaduje_nazev and not nazev:
            return Response({'detail': 'Zadejte název.'}, status=400)
        obj = Object(
            salon=salon,
            zakaznik=zakaznik,
            typ=typ,
            nazev=nazev,
            popis=(data.get('popis') or '').strip(),
            stav=data.get('stav') or Stav.AKTIVNI,
            vytvoril=actor,
            zmenil=actor,
        )
        try:
            obj.save()
        except ValidationError as exc:
            return Response({'detail': _validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        tags = _tags(salon, data.get('tagy') or [], for_objekt=True)
        if tags.exists():
            obj.tagy.set(tags)
        return Response(ObjectSerializer(obj, context={'request': request}).data, status=201)


class ObjectDetailView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def _get(self, request, object_uuid):
        return _objects_qs(_salon(request)).filter(uuid=object_uuid).first()

    def get(self, request, object_uuid):
        obj = self._get(request, object_uuid)
        if not obj:
            return Response({'detail': 'Objekt nenalezen.'}, status=404)
        return Response(ObjectSerializer(obj, context={'request': request}).data)

    def patch(self, request, object_uuid):
        obj = self._get(request, object_uuid)
        if not obj:
            return Response({'detail': 'Objekt nenalezen.'}, status=404)
        ser = ObjectWriteSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        salon = _salon(request)
        if 'nazev' in data:
            obj.nazev = data['nazev'].strip()
        if 'popis' in data:
            obj.popis = (data.get('popis') or '').strip()
        if 'stav' in data:
            obj.stav = data['stav']
        if 'typ_uuid' in data:
            typ = ObjectType.objects.filter(salon=salon, uuid=data['typ_uuid']).first()
            if not typ:
                return Response({'detail': 'Typ objektu nenalezen.'}, status=400)
            from archivnik.services import object_type_allowed_for_assign
            if not object_type_allowed_for_assign(salon, typ, current_typ=obj.typ):
                return Response(
                    {'detail': 'Tento typ nepatří k oboru kartotéky.'},
                    status=400,
                )
            obj.typ = typ
        obj.zmenil = _actor(request)
        try:
            obj.save()
        except ValidationError as exc:
            return Response({'detail': _validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if 'tagy' in data:
            obj.tagy.set(_tags(salon, data.get('tagy') or [], for_objekt=True))
        return Response(ObjectSerializer(obj, context={'request': request}).data)


class EntryListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        qs = Entry.objects.filter(salon=salon).select_related('zakaznik', 'objekt', 'objekt__typ', 'vytvoril').prefetch_related('prilohy')
        cu = request.query_params.get('zakaznik')
        ou = request.query_params.get('objekt')
        if ou:
            qs = qs.filter(objekt__uuid=ou)
        elif cu:
            if request.query_params.get('vcetne_objektu') == '1':
                qs = qs.filter(zakaznik__uuid=cu)
            else:
                qs = qs.filter(zakaznik__uuid=cu, objekt__isnull=True)
        return Response(EntrySerializer(qs.order_by('-nastalo', '-id')[:200], many=True, context={'request': request}).data)

    def post(self, request):
        ser = EntryWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        salon = _salon(request)
        actor = _actor(request)
        objekt = None
        zakaznik = None
        if data.get('objekt_uuid'):
            objekt = Object.objects.filter(salon=salon, uuid=data['objekt_uuid']).select_related('zakaznik').first()
            if not objekt:
                return Response({'detail': 'Objekt nenalezen.'}, status=400)
            zakaznik = objekt.zakaznik
            if data.get('zakaznik_uuid') and zakaznik.uuid != data['zakaznik_uuid']:
                return Response(
                    {'detail': 'Objekt zápisu musí patřit stejnému zákazníkovi.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif data.get('zakaznik_uuid'):
            zakaznik = Customer.objects.filter(salon=salon, uuid=data['zakaznik_uuid']).first()
            if not zakaznik:
                return Response({'detail': 'Zákazník nenalezen.'}, status=400)
        else:
            return Response({'detail': 'Zadejte zákazníka nebo objekt.'}, status=400)
        entry = Entry(
            salon=salon,
            zakaznik=zakaznik,
            objekt=objekt,
            nastalo=data.get('nastalo') or timezone.now(),
            typ_zapisu=(data.get('typ_zapisu') or 'Poznámka').strip() or 'Poznámka',
            nadpis=(data.get('nadpis') or '').strip(),
            text=data['text'].strip(),
            vytvoril=actor,
            zmenil=actor,
        )
        try:
            entry.save()
        except ValidationError as exc:
            return Response({'detail': _validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EntrySerializer(entry, context={'request': request}).data, status=201)


class TagListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        return Response(TagSerializer(Tag.objects.filter(salon=_salon(request)), many=True).data)

    def post(self, request):
        ser = TagSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tag = Tag.objects.create(salon=_salon(request), **ser.validated_data)
        return Response(TagSerializer(tag).data, status=201)


class ReminderListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        qs = Reminder.objects.filter(salon=salon).select_related('zakaznik', 'objekt', 'objekt__typ', 'prirazeny')
        stav = request.query_params.get('stav')
        if stav in (ReminderStav.AKTIVNI, ReminderStav.HOTOVO):
            qs = qs.filter(stav=stav)
        cu = request.query_params.get('zakaznik')
        if cu:
            qs = qs.filter(zakaznik__uuid=cu)
        ou = request.query_params.get('objekt')
        if ou:
            qs = qs.filter(objekt__uuid=ou)
        return Response(ReminderSerializer(qs.order_by('termin', 'id')[:200], many=True).data)

    def post(self, request):
        ser = ReminderWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        salon = _salon(request)
        actor = _actor(request)
        zakaznik = Customer.objects.filter(salon=salon, uuid=data['zakaznik_uuid']).first()
        if not zakaznik:
            return Response({'detail': 'Zákazník nenalezen.'}, status=400)
        objekt = None
        if data.get('objekt_uuid'):
            objekt = Object.objects.filter(salon=salon, uuid=data['objekt_uuid'], zakaznik=zakaznik).first()
            if not objekt:
                return Response({'detail': 'Objekt nenalezen u tohoto zákazníka.'}, status=400)
        rem = Reminder(
            salon=salon,
            zakaznik=zakaznik,
            objekt=objekt,
            termin=data['termin'],
            text=data['text'].strip(),
            prirazeny=actor,
            vytvoril=actor,
        )
        try:
            rem.save()
        except ValidationError as exc:
            return Response({'detail': _validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ReminderSerializer(rem).data, status=201)


class ReminderDoneView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def post(self, request, reminder_uuid):
        rem = Reminder.objects.filter(salon=_salon(request), uuid=reminder_uuid).first()
        if not rem:
            return Response({'detail': 'Připomínka nenalezena.'}, status=404)
        rem.stav = ReminderStav.HOTOVO
        rem.save(update_fields=['stav', 'upraveno'])
        return Response(ReminderSerializer(rem).data)
