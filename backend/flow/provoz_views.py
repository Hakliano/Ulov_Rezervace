from datetime import datetime

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from flow.auth import flow_absence_zam, flow_je_owner, flow_ucet_je_majitel, flow_zam, get_flow_user_from_request
from flow.permissions import FlowPermission
from rezervace.models import NoShowZaznam, Rezervace, RezervaceHistorie, Zamestnanec, ZamestnanecAbsence, ZamestnanecRozvrh
from rezervace.notifikace_defaults import (
    MANUAL_TYP_NOSHOW,
    MANUAL_TYP_PLATBA,
    MANUAL_TYP_ZALOHA,
    get_manual_notifikace,
)
from rezervace.serializers import (
    AdminRezervaceSerializer,
    NoShowZaznamSerializer,
    ZamestnanecAbsenceSerializer,
    ZamestnanecRozvrhSerializer,
    dopln_rozvrh_7_dni,
)
from rezervace.services.audit import log_audit, log_rezervace_audit
from rezervace.services.availability import volni_zamestnanci
from rezervace.services.emails import email_storno, email_zmena_obsluhy, ma_kontaktni_email


def _flow_user(request):
    return get_flow_user_from_request(request)


def _log_flow(user, rezervace, popis, pred=None, po=None):
    actor = f'FLOW:{flow_zam(user).jmeno}'
    RezervaceHistorie.objects.create(
        rezervace=rezervace, kdo=actor, popis=popis,
        data_pred=pred, data_po=po,
    )
    log_rezervace_audit(rezervace, actor, popis, pred=pred, po=po)


def _own_rezervace_or_403(user, rezervace):
    if rezervace.salon_id != user.salon_id:
        return Response({'detail': 'Rezervace nepatří k vašemu salonu.'}, status=403)
    # Majitel řeší kolize absencí za celý tým
    if flow_je_owner(user):
        return None
    if rezervace.zamestnanec_id != flow_zam(user).id:
        return Response({'detail': 'Můžete spravovat jen vlastní rezervace.'}, status=403)
    return None


def _email_override(request):
    """Volitelný předmět/text z FLOW preview sheetu."""
    data = getattr(request, 'data', None) or {}
    predmet = data.get('email_predmet')
    text = data.get('email_text')
    if predmet is not None:
        predmet = str(predmet)
    if text is not None:
        text = str(text)
    return predmet, text


def _dostupni_kolegove(salon, rezervace, exclude_zamestnanec_id=None):
    """Kolegové volní ve stejném termínu (bez majitelky / bez sebe)."""
    if not rezervace.zacatek or not rezervace.konec:
        return []
    datum = timezone.localtime(rezervace.zacatek).date()
    sluzby_ids = list(rezervace.polozky.values_list('sluzba_id', flat=True))
    volni = volni_zamestnanci(
        salon,
        datum,
        rezervace.zacatek,
        rezervace.konec,
        exclude_id=rezervace.id,
        sluzby_ids=sluzby_ids or None,
    )
    out = []
    for z in volni:
        if exclude_zamestnanec_id and z.id == exclude_zamestnanec_id:
            continue
        out.append({'id': z.id, 'jmeno': z.jmeno})
    return out


def _konflikt_payload(rezervace, exclude_zamestnanec_id=None):
    data = AdminRezervaceSerializer(rezervace).data
    data['dostupni_kolegove'] = _dostupni_kolegove(
        rezervace.salon, rezervace, exclude_zamestnanec_id=exclude_zamestnanec_id,
    )
    return data


def _parse_range(request):
    od = request.query_params.get('od')
    do = request.query_params.get('do')
    return od, do


def _filter_rezervace_qs(qs, od, do):
    if od:
        if len(od) <= 10:
            qs = qs.filter(zacatek__date__gte=datetime.strptime(od, '%Y-%m-%d').date())
        else:
            qs = qs.filter(zacatek__gte=od)
    if do:
        if len(do) <= 10:
            qs = qs.filter(zacatek__date__lte=datetime.strptime(do, '%Y-%m-%d').date())
        else:
            qs = qs.filter(zacatek__lte=do)
    return qs


def _filter_absence_qs(qs, od, do):
    if od:
        qs = qs.filter(datum_do__gte=od[:10])
    if do:
        qs = qs.filter(datum_od__lte=do[:10])
    return qs


class FlowKalendarView(APIView):
    """Můj kalendář + moje absence. ?od=&do=&overview=1 pro Visible Overview (jen čtení)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        od, do = _parse_range(request)
        overview = str(request.query_params.get('overview', '')).lower() in ('1', 'true', 'yes')
        je_majitel = flow_je_owner(user)
        if overview and not user.visible_overview and not je_majitel:
            return Response({'detail': 'Nemáte zapnuté Visible Overview.'}, status=403)

        salon = user.salon
        qs = Rezervace.objects.filter(salon=salon).prefetch_related('polozky__sluzba', 'zamestnanec')
        if overview:
            mode = 'overview'
        elif je_majitel:
            # Majitel zadává rezervace na personál — kalendář musí vidět celý salon.
            mode = 'salon'
        else:
            mode = 'mine'
            qs = qs.filter(zamestnanec_id=flow_zam(user).id)
        qs = _filter_rezervace_qs(qs, od, do)

        if overview or je_majitel:
            abs_qs = ZamestnanecAbsence.objects.filter(
                zamestnanec__salon=salon,
            ).exclude(
                stav=ZamestnanecAbsence.STAV_ZAMITNUTO,
            ).select_related('zamestnanec')
        else:
            abs_qs = ZamestnanecAbsence.objects.filter(
                zamestnanec_id=flow_zam(user).id,
            ).exclude(stav=ZamestnanecAbsence.STAV_ZAMITNUTO)
        abs_qs = _filter_absence_qs(abs_qs, od, do)

        absence_data = []
        for a in abs_qs.order_by('datum_od'):
            item = ZamestnanecAbsenceSerializer(a).data
            item['zamestnanec_id'] = a.zamestnanec_id
            item['zamestnanec_jmeno'] = a.zamestnanec.jmeno
            absence_data.append(item)

        rezervace_data = list(AdminRezervaceSerializer(qs.order_by('zacatek'), many=True).data)
        # feature/flow-customer-card — runtime odkaz, bez FK na rezervace
        from flow.customer_card_services import attach_customer_card_links
        attach_customer_card_links(salon.id, rezervace_data)

        return Response({
            'mode': mode,
            'visible_overview': user.visible_overview,
            'rezervace': rezervace_data,
            'absence': absence_data,
        })


class FlowRezervaceDokoncenoView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        from rezervace.services.dokonceni import NelzeDokoncit, oznacit_dokonceno

        try:
            _, po = oznacit_dokonceno(
                rezervace,
                log_fn=lambda r, pred, po: _log_flow(user, r, 'rezervace proběhla', pred, po),
            )
        except NelzeDokoncit as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(po)


class FlowRezervaceNoShowView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        if rezervace.stav in ('zakaznik_storno', 'salon_storno', 'dokonceno', 'no_show'):
            return Response({'detail': 'Tuto rezervaci nelze označit jako Hříšníci.'}, status=400)

        # FLOW: žádná blokace e-mailu — to zůstává majitelce v rezervacích
        odeslat_upozorneni = bool(request.data.get('odeslat_upozorneni'))

        pred = AdminRezervaceSerializer(rezervace).data
        rezervace.stav = 'no_show'
        rezervace.save(update_fields=['stav', 'aktualizovano'])

        sluzby = ', '.join(p.sluzba.nazev for p in rezervace.polozky.all())
        from rezervace.services.gdpr import email_hash

        email_val = rezervace.kontaktni_email or ''
        zaznam = NoShowZaznam.objects.create(
            salon=user.salon,
            rezervace=rezervace,
            zakaznik=rezervace.zakaznik,
            jmeno=rezervace.kontaktni_jmeno,
            email=email_val,
            email_hash=email_hash(email_val) if email_val else '',
            zacatek=rezervace.zacatek,
            zamestnanec_jmeno=rezervace.zamestnanec.jmeno if rezervace.zamestnanec else '',
            sluzby=sluzby,
            zakaznik_blokovan=False,
        )
        if rezervace.zakaznik:
            rezervace.zakaznik.no_show_pocet += 1
            rezervace.zakaznik.save(update_fields=['no_show_pocet'])

        from rezervace.services.email_reputace import aktualizuj_po_noshow

        reputace = aktualizuj_po_noshow(rezervace.kontaktni_email or '', user.salon_id)

        email_odeslan = False
        if odeslat_upozorneni and rezervace.kontaktni_email:
            try:
                nastaveni = user.salon.rezervacni_nastaveni
                manual = get_manual_notifikace(nastaveni.notifikace, MANUAL_TYP_NOSHOW)
                if manual:
                    from rezervace.services.notifikace_email import email_notifikace

                    ep, et = _email_override(request)
                    email_notifikace(rezervace, manual, predmet=ep, text=et)
                    odeslane = list(rezervace.notifikace_odeslane or [])
                    nid = str(manual['id'])
                    if nid not in odeslane:
                        odeslane.append(nid)
                        rezervace.notifikace_odeslane = odeslane
                        rezervace.save(update_fields=['notifikace_odeslane'])
                    email_odeslan = True
                    zaznam.email_upozorneni_odeslan = True
                    zaznam.save(update_fields=['email_upozorneni_odeslan'])
            except Exception as exc:
                return Response({
                    'detail': f'Hříšníci uloženi, ale e-mail se nepodařilo odeslat: {exc}',
                    'rezervace': AdminRezervaceSerializer(rezervace).data,
                    'zaznam': NoShowZaznamSerializer(zaznam).data,
                }, status=502)

        po = AdminRezervaceSerializer(rezervace).data
        _log_flow(user, rezervace, 'Hříšníci', pred, po)
        return Response({
            'rezervace': po,
            'zaznam': NoShowZaznamSerializer(zaznam).data,
            'email_odeslan': email_odeslan,
            'reputace': reputace,
        })


class FlowRezervaceStornoView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def delete(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        if rezervace.stav in ('zakaznik_storno', 'salon_storno', 'dokonceno', 'no_show'):
            return Response({'detail': 'Tuto rezervaci nelze stornovat.'}, status=400)
        pred = AdminRezervaceSerializer(rezervace).data
        rezervace.stav = 'salon_storno'
        rezervace.save(update_fields=['stav', 'aktualizovano'])
        po = AdminRezervaceSerializer(rezervace).data
        _log_flow(user, rezervace, 'storno salonu', pred, po)
        email_odeslan = False
        try:
            duvod = (request.data.get('duvod') or request.headers.get('X-Absence-Duvod') or '').strip()[:100]
            ep, et = _email_override(request)
            email_odeslan = bool(email_storno(
                rezervace,
                kdo='salon',
                duvod=duvod,
                predmet=ep,
                text=et,
            ))
        except Exception:
            email_odeslan = False
        from rezervace.services.zaloha_storno import storno_zaloha_payload, zaloha_je_zaplacena
        payload = {
            'ok': True,
            'rezervace': po,
            'email_odeslan': email_odeslan,
            'zaloha_zaplacena': zaloha_je_zaplacena(rezervace),
        }
        # lze_stornovat=True → text pro „po stornu volejte“ (ne propadnutí)
        payload.update(storno_zaloha_payload(rezervace, lze_stornovat=True))
        return Response(payload)


class FlowRezervacePrevestView(APIView):
    """Převod vlastní rezervace na volného kolegu (typicky při absenci)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(
            Rezervace.objects.select_related('salon', 'zamestnanec'),
            pk=rezervace_id,
            salon_id=user.salon_id,
        )
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        if rezervace.stav not in ('ceka', 'potvrzeno'):
            return Response({'detail': 'Tuto rezervaci nelze převést.'}, status=400)

        try:
            cil_id = int(request.data.get('zamestnanec_id'))
        except (TypeError, ValueError):
            return Response({'detail': 'Vyberte kolegu.'}, status=400)

        if cil_id == rezervace.zamestnanec_id:
            return Response({'detail': 'Nelze převést na stejného pracovníka.'}, status=400)

        exclude_id = rezervace.zamestnanec_id
        kolegove = _dostupni_kolegove(
            user.salon, rezervace, exclude_zamestnanec_id=exclude_id,
        )
        if not any(k['id'] == cil_id for k in kolegove):
            return Response(
                {'detail': 'Vybraný kolega v tomto termínu není volný.'},
                status=400,
            )

        cil = get_object_or_404(
            Zamestnanec, pk=cil_id, salon_id=user.salon_id, aktivni=True,
        )
        pred = AdminRezervaceSerializer(rezervace).data
        puvodni_jmeno = rezervace.zamestnanec.jmeno if rezervace.zamestnanec_id else ''
        rezervace.zamestnanec = cil
        rezervace.save(update_fields=['zamestnanec', 'aktualizovano'])
        po = AdminRezervaceSerializer(rezervace).data
        _log_flow(
            user,
            rezervace,
            f'převod na {cil.jmeno} (absence)',
            pred,
            po,
        )
        try:
            email_zmena_obsluhy(rezervace, puvodni_jmeno, cil.jmeno)
        except Exception:
            pass
        return Response({'ok': True, 'rezervace': po})


class FlowRezervacePlatbaView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied
        castka = request.data.get('castka')
        ucet = (request.data.get('ucet') or request.data.get('cislo_uctu') or '').strip()
        vs = request.data.get('variabilni_symbol') or request.data.get('vs')
        je_zaloha = bool(request.data.get('zaloha') or request.data.get('is_zaloha'))
        if not castka or not ucet or vs is None or str(vs).strip() == '':
            return Response({'detail': 'Vyplňte částku, číslo účtu a variabilní symbol.'}, status=400)

        from rezervace.services.platba_qr import generuj_platbu_qr
        import base64

        try:
            platba_data = generuj_platbu_qr(ucet, castka, vs, zprava=user.salon.name)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        email_odeslan = False
        if ma_kontaktni_email(rezervace):
            try:
                nastaveni = user.salon.rezervacni_nastaveni
                typ_mailu = MANUAL_TYP_ZALOHA if je_zaloha else MANUAL_TYP_PLATBA
                platba = get_manual_notifikace(nastaveni.notifikace, typ_mailu)
                if not platba:
                    return Response({
                        'detail': 'Chybí nastavení e-mailu (záloha QR).' if je_zaloha else 'Chybí nastavení e-mailu (platba QR).',
                    }, status=400)
                from rezervace.services.notifikace_email import email_platba_qr

                ep, et = _email_override(request)
                email_platba_qr(
                    rezervace, platba, castka, ucet, vs,
                    platba_data=platba_data, predmet=ep, text=et,
                )
                email_odeslan = True
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=400)
            except Exception as exc:
                return Response({'detail': f'E-mail se nepodařilo odeslat: {exc}'}, status=502)

        if je_zaloha:
            rezervace.zaloha_vyzadana_at = timezone.now()
            rezervace.zaloha_nepozadovana_at = None
            try:
                rezervace.zaloha_castka = float(str(castka).replace(',', '.').replace(' ', ''))
            except (TypeError, ValueError):
                rezervace.zaloha_castka = None
            rezervace.save(update_fields=[
                'zaloha_vyzadana_at', 'zaloha_nepozadovana_at', 'zaloha_castka', 'aktualizovano',
            ])
            _log_flow(
                user, rezervace,
                f'žádost o zálohu {castka} Kč' if email_odeslan else f'QR záloha zobrazena {castka} Kč',
            )
            msg = (
                'E-mail s QR zálohou odeslán.'
                if email_odeslan
                else 'QR kód je připraven — ukažte ho zákazníkovi.'
            )
        else:
            _log_flow(
                user, rezervace,
                f'odeslání žádosti o platbu {castka} Kč' if email_odeslan else f'QR platba zobrazena {castka} Kč',
            )
            msg = (
                'E-mail s QR platbou odeslán.'
                if email_odeslan
                else 'QR kód je připraven — ukažte ho zákazníkovi.'
            )

        return Response({
            'ok': True,
            'message': msg,
            'email_odeslan': email_odeslan,
            'qr_png_base64': base64.b64encode(platba_data['qr_png']).decode('ascii'),
            'castka': platba_data['castka_display'],
            'ucet': platba_data['ucet'],
            'variabilni_symbol': platba_data['variabilni_symbol'],
            'rezervace': AdminRezervaceSerializer(rezervace).data,
        })


class FlowRezervaceZalohaOkView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied

        from rezervace.notifikace_defaults import MANUAL_TYP_ZALOHA_OK, get_manual_notifikace
        from rezervace.services.notifikace_email import email_notifikace

        rezervace.zaloha_ok_at = timezone.now()
        if rezervace.stav == 'ceka':
            rezervace.stav = 'potvrzeno'
            rezervace.save(update_fields=['zaloha_ok_at', 'stav', 'aktualizovano'])
        else:
            rezervace.save(update_fields=['zaloha_ok_at', 'aktualizovano'])

        try:
            nastaveni = user.salon.rezervacni_nastaveni
            notif = get_manual_notifikace(nastaveni.notifikace, MANUAL_TYP_ZALOHA_OK)
            if notif and notif.get('aktivni', True):
                extra = {}
                if rezervace.zaloha_castka is not None:
                    extra['castka'] = str(rezervace.zaloha_castka)
                ep, et = _email_override(request)
                email_notifikace(rezervace, notif, extra_ctx=extra, predmet=ep, text=et)
        except Exception:
            pass

        _log_flow(user, rezervace, 'záloha OK – potvrzeno personálem')
        return Response({
            'ok': True,
            'message': 'Záloha potvrzena.',
            'rezervace': AdminRezervaceSerializer(rezervace).data,
        })


class FlowRezervaceZalohaNepozadovatView(APIView):
    """Personál / Manager: riziková služba, ale zálohu nechceme (stabilní host, rodina…)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied

        rezervace.zaloha_nepozadovana_at = timezone.now()
        rezervace.save(update_fields=['zaloha_nepozadovana_at', 'aktualizovano'])
        _log_flow(user, rezervace, 'záloha nepožadována – důvěryhodný host / výjimka')
        return Response({
            'ok': True,
            'message': 'Záloha se nepožaduje — rezervace zmizí z rizikových.',
            'rezervace': AdminRezervaceSerializer(rezervace).data,
        })


class FlowEmailPreviewView(APIView):
    """Náhled textu e-mailu zákazníkovi před odesláním z FLOW."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request, rezervace_id):
        from flow.email_drafts import (
            render_noshow_draft,
            render_platba_draft,
            render_storno_draft,
            render_zaloha_ok_draft,
        )

        user = _flow_user(request)
        rezervace = get_object_or_404(Rezervace, pk=rezervace_id, salon_id=user.salon_id)
        denied = _own_rezervace_or_403(user, rezervace)
        if denied:
            return denied

        typ = (request.data.get('typ') or '').strip().lower()
        try:
            if typ == 'storno':
                duvod = (request.data.get('duvod') or '').strip()[:100]
                draft = render_storno_draft(rezervace, kdo='salon', duvod=duvod)
            elif typ == 'noshow':
                draft = render_noshow_draft(rezervace)
            elif typ == 'zaloha_ok':
                draft = render_zaloha_ok_draft(rezervace)
            elif typ in ('platba', 'zaloha'):
                castka = request.data.get('castka')
                ucet = (request.data.get('ucet') or request.data.get('cislo_uctu') or '').strip()
                vs = request.data.get('variabilni_symbol') or request.data.get('vs')
                if not castka or not ucet or vs is None or str(vs).strip() == '':
                    return Response(
                        {'detail': 'Vyplňte částku, číslo účtu a variabilní symbol.'},
                        status=400,
                    )
                draft = render_platba_draft(
                    rezervace,
                    castka=castka,
                    ucet=ucet,
                    variabilni_symbol=vs,
                    je_zaloha=(typ == 'zaloha'),
                )
            else:
                return Response(
                    {'detail': 'Neznámý typ e-mailu. Použijte storno / noshow / platba / zaloha / zaloha_ok.'},
                    status=400,
                )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        except Exception as exc:
            return Response({'detail': f'Náhled e-mailu selhal: {exc}'}, status=400)

        return Response({
            'ok': True,
            'rezervace_id': rezervace.id,
            'title': {
                'storno': 'E-mail storna',
                'noshow': 'E-mail Hříšníci',
                'platba': 'E-mail platby QR',
                'zaloha': 'E-mail zálohy QR',
                'zaloha_ok': 'E-mail — záloha přijata',
            }.get(draft.get('typ') or typ, 'Náhled e-mailu'),
            **draft,
        })


class FlowAbsenceView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        zam = flow_absence_zam(user)
        if zam is None:
            return Response([])
        qs = ZamestnanecAbsence.objects.filter(zamestnanec_id=zam.id)
        od, do = _parse_range(request)
        qs = _filter_absence_qs(qs, od, do)
        return Response(ZamestnanecAbsenceSerializer(qs.order_by('-vytvoreno', 'datum_od'), many=True).data)

    def post(self, request):
        user = _flow_user(request)
        ser = ZamestnanecAbsenceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        zam = flow_absence_zam(user)
        if zam is None:
            return Response(
                {
                    'detail': (
                        'Účet Manager nepracuje — dovolená dává smysl jen u pracovní persony. '
                        'Zapněte „Manager také pracuje“, nebo zadejte absenci Staff ve Správě.'
                    ),
                },
                status=400,
            )
        # Manager (včetně pracovní persony majitele) = hned schváleno.
        # Ostatní Staff = žádost ke schválení.
        auto_schvalit = flow_ucet_je_majitel(user) or flow_je_owner(user)
        stav = (
            ZamestnanecAbsence.STAV_SCHVALENO
            if auto_schvalit
            else ZamestnanecAbsence.STAV_CEKA
        )
        absence = ZamestnanecAbsence.objects.create(
            zamestnanec_id=zam.id,
            stav=stav,
            **ser.validated_data,
        )
        od = ser.validated_data['datum_od']
        do = ser.validated_data['datum_do']
        konflikty = Rezervace.objects.filter(
            salon_id=user.salon_id,
            zamestnanec_id=zam.id,
            stav__in=('ceka', 'potvrzeno'),
            zacatek__date__gte=od,
            zacatek__date__lte=do,
        ).select_related('salon', 'zamestnanec').prefetch_related('polozky__sluzba').order_by('zacatek')
        konflikt_data = [
            _konflikt_payload(r, exclude_zamestnanec_id=zam.id)
            for r in konflikty
        ]
        if auto_schvalit:
            detail = (
                'Absence schválena na pracovním profilu.'
                if flow_ucet_je_majitel(user)
                else 'Absence schválena.'
            )
        else:
            detail = (
                'Žádost odeslána majitelce ke schválení. '
                'Kalendář se zablokuje až po schválení.'
            )
            if konflikt_data:
                detail += f' Kolize rezervací ({len(konflikt_data)}) vyřeší Manager při schválení.'
        return Response({
            'absence': ZamestnanecAbsenceSerializer(absence).data,
            'konfliktni_rezervace': konflikt_data if auto_schvalit else [],
            'pocet_konfliktu': len(konflikt_data),
            'detail': detail,
            'ceka_na_schvaleni': not auto_schvalit,
        }, status=status.HTTP_201_CREATED)


class FlowAbsenceDetailView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def delete(self, request, absence_id):
        user = _flow_user(request)
        zam = flow_absence_zam(user)
        if zam is None:
            return Response({'detail': 'Nelze smazat absenci účtu Manager bez pracovní persony.'}, status=400)
        absence = get_object_or_404(
            ZamestnanecAbsence, pk=absence_id, zamestnanec_id=zam.id
        )
        # Staff může stáhnout jen čekající žádost; schválené maže majitel (nebo sám u vlastní pracovní persony)
        if (
            not flow_ucet_je_majitel(user)
            and not flow_je_owner(user)
            and absence.stav == ZamestnanecAbsence.STAV_SCHVALENO
        ):
            return Response(
                {'detail': 'Schválenou absenci může zrušit jen Manager.'},
                status=400,
            )
        absence.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FlowSluzbyView(APIView):
    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        from rezervace.serializers import SluzbaPublicSerializer
        from salons.models import CenikPolozka

        sluzby = CenikPolozka.objects.filter(
            salon_id=user.salon_id, aktivni=True,
        ).order_by('poradi', 'id')
        return Response(SluzbaPublicSerializer(sluzby, many=True).data)


class FlowVolneTerminyView(APIView):
    """Volné termíny pro přihlášeného pracovníka (majitel může vybrat staff)."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        from rezervace.services.availability import generuj_terminy, salon_je_zavreny
        from salons.models import CenikPolozka

        datum_str = request.query_params.get('datum')
        sluzby_str = request.query_params.get('sluzby', '')
        if not datum_str or not sluzby_str:
            return Response({'detail': 'Parametry datum a sluzby jsou povinné.'}, status=400)

        zam_id = flow_zam(user).id
        if flow_je_owner(user):
            raw = request.query_params.get('zamestnanec_id')
            if not raw:
                return Response({'detail': 'Vyberte pracovníka.'}, status=400)
            try:
                zam_id = int(raw)
            except (TypeError, ValueError):
                return Response({'detail': 'Neplatný pracovník.'}, status=400)
            zam = get_object_or_404(Zamestnanec, pk=zam_id, salon_id=user.salon_id)
            if zam.role == Zamestnanec.ROLE_MAJITEL:
                return Response({'detail': 'Rezervaci nelze zadat na účet majitele.'}, status=400)
            if not zam.aktivni:
                return Response({'detail': 'Pracovník je neaktivní.'}, status=400)

        datum = datetime.strptime(datum_str, '%Y-%m-%d').date()
        if salon_je_zavreny(user.salon, datum):
            return Response({
                'datum': datum_str, 'zavreno': True, 'terminy': [],
                'duvod': 'Salon je tento den zavřený.',
            })

        sluzby_ids = [int(x) for x in sluzby_str.split(',') if x.strip()]
        if not sluzby_ids:
            return Response({'detail': 'Vyberte alespoň jednu službu.'}, status=400)

        terminy = generuj_terminy(user.salon, datum, sluzby_ids, zam_id)
        duvod = ''
        if not terminy:
            aktivni = CenikPolozka.objects.filter(
                salon_id=user.salon_id, pk__in=sluzby_ids, aktivni=True,
            ).count()
            if aktivni != len(sluzby_ids):
                duvod = 'Vybraná služba není dostupná.'
            else:
                duvod = 'Pro tento den u vybraného pracovníka není volný žádný termín.'

        return Response({
            'datum': datum_str,
            'zavreno': False,
            'terminy': terminy,
            'duvod': duvod,
            'zamestnanec_id': zam_id,
        })


class FlowRezervaceCreateView(APIView):
    """Zadat rezervaci na sebe (telefon / osobně). Majitel může vybrat staff."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def post(self, request):
        user = _flow_user(request)
        from rezervace.serializers import AdminRezervaceCreateSerializer
        from rezervace.views import vytvor_rezervaci

        payload = dict(request.data)
        zam_id = flow_zam(user).id
        if flow_je_owner(user):
            try:
                zam_id = int(payload.get('zamestnanec_id'))
            except (TypeError, ValueError):
                return Response({'detail': 'Vyberte pracovníka.'}, status=400)
            zam = get_object_or_404(Zamestnanec, pk=zam_id, salon_id=user.salon_id)
            if zam.role == Zamestnanec.ROLE_MAJITEL:
                return Response({'detail': 'Rezervaci nelze zadat na účet majitele.'}, status=400)
            if not zam.aktivni:
                return Response({'detail': 'Pracovník je neaktivní.'}, status=400)
        payload['zamestnanec_id'] = zam_id
        if not payload.get('typ_vytvoreni'):
            payload['typ_vytvoreni'] = 'telefon'
        if not payload.get('stav'):
            payload['stav'] = 'potvrzeno'

        ser = AdminRezervaceCreateSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        d['zamestnanec_id'] = zam_id

        try:
            rezervace = vytvor_rezervaci(
                user.salon,
                d,
                typ_vytvoreni=d.get('typ_vytvoreni', 'telefon'),
                stav=d.get('stav', 'potvrzeno'),
                kdo=f'FLOW:{flow_zam(user).jmeno}',
                request=request,
            )
            if d.get('poznamka_interni'):
                rezervace.poznamka_interni = d['poznamka_interni']
                rezervace.save(update_fields=['poznamka_interni'])
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)

        return Response(AdminRezervaceSerializer(rezervace).data, status=status.HTTP_201_CREATED)


class FlowRozvrhView(APIView):
    """Týdenní pracovní doba přihlášeného zaměstnance — stejná data jako web a rezervace."""

    authentication_classes = []
    permission_classes = [FlowPermission]

    def get(self, request):
        user = _flow_user(request)
        z = get_object_or_404(
            Zamestnanec.objects.prefetch_related('rozvrh'),
            pk=flow_zam(user).id,
            salon_id=user.salon_id,
        )
        return Response({'rozvrh': dopln_rozvrh_7_dni(z)})

    def put(self, request):
        user = _flow_user(request)
        z = get_object_or_404(
            Zamestnanec.objects.prefetch_related('rozvrh'),
            pk=flow_zam(user).id,
            salon_id=user.salon_id,
        )
        if z.role == Zamestnanec.ROLE_MAJITEL:
            return Response(
                {'detail': 'Účet majitelky nemá pracovní rozvrh pro rezervace.'},
                status=400,
            )
        # I4: pracovní dobu mění jen Manager ve Správě → Staff
        return Response(
            {'detail': 'Pracovní dobu může měnit jen Manager ve Správě.'},
            status=403,
        )
