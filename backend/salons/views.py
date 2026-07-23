from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings

from rezervace.services.audit import audit_actor, log_audit

from rezervace.throttles import PoptavkaRateThrottle

from .poptavka import odeslat_poptavku
from .bunny import BunnyUploadError, delete_image, is_bunny_configured, upload_image
from .models import CenikPolozka, Novinka, Salon, SalonObrazek
from .permissions import AdminPasswordPermission, MajitelPermission
from .serializers import NovinkaSerializer, SalonObrazekSerializer, SalonSerializer


def _form_param(request, name):
    """Čte parametr z query, DRF data nebo POST (multipart)."""
    value = request.query_params.get(name)
    if value not in (None, ''):
        return value
    if hasattr(request, 'data'):
        value = request.data.get(name)
        if value not in (None, ''):
            return value
    value = request.POST.get(name)
    if value not in (None, ''):
        return value
    return None


class SalonDetailView(APIView):
    permission_classes = [AdminPasswordPermission]

    def get_object(self, pk):
        return Salon.objects.prefetch_related(
            'cenik', 'novinky', 'oteviraci_doba', 'obrazky'
        ).get(pk=pk)

    def get(self, request, pk):
        try:
            salon = self.get_object(pk)
        except Salon.DoesNotExist:
            return Response({'detail': 'Salon nenalezen.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SalonSerializer(salon)
        return Response(serializer.data)

    def put(self, request, pk):
        try:
            salon = self.get_object(pk)
        except Salon.DoesNotExist:
            return Response({'detail': 'Salon nenalezen.'}, status=status.HTTP_404_NOT_FOUND)
        pred = SalonSerializer(salon).data
        serializer = SalonSerializer(salon, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            po = SalonSerializer(salon).data
            casti = []
            if 'cenik' in request.data:
                casti.append('ceník')
            if 'novinky' in request.data:
                casti.append('novinky')
            if 'obrazky' in request.data:
                casti.append('galerie')
            for pole in ('name', 'description', 'address', 'phone', 'email'):
                if pole in request.data:
                    casti.append('kontakty a texty')
                    break
            popis = f'změna {casti[0]}' if len(casti) == 1 else f'změna ({", ".join(dict.fromkeys(casti))})'
            if not casti:
                popis = 'změna údajů salonu'
            actor = audit_actor(request)
            log_audit(salon, actor, 'web', f'{actor}: {popis}', pred=pred, po=po)
            return Response(po)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, pk):
        return self.put(request, pk)


class ImageUploadView(APIView):
    permission_classes = [MajitelPermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        try:
            salon = Salon.objects.get(pk=pk)
        except Salon.DoesNotExist:
            return Response({'detail': 'Salon nenalezen.'}, status=status.HTTP_404_NOT_FOUND)

        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'Chybí soubor (pole file).'}, status=status.HTTP_400_BAD_REQUEST)

        typ = _form_param(request, 'typ') or 'galerie'
        if typ == 'hero':
            folder = 'hero'
        elif typ == 'logo':
            folder = 'logo'
        elif typ == 'favicon':
            folder = 'favicon'
        elif typ == 'cenik':
            folder = 'cenik'
        elif typ == 'novinka':
            folder = 'novinky'
        elif typ == 'personel':
            folder = 'personel'
        else:
            folder = 'galerie'

        try:
            url = upload_image(file_obj, salon.id, folder=folder)
        except BunnyUploadError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        if typ == 'hero':
            old_url = salon.hero_image
            salon.hero_image = url
            salon.save(update_fields=['hero_image'])
            if old_url and old_url != url:
                delete_image(old_url)
            log_audit(salon, audit_actor(request), 'web', f'{audit_actor(request)}: změna úvodního obrázku')
            return Response({'url': url, 'typ': 'hero'})

        if typ == 'logo':
            old_url = salon.logo_url
            salon.logo_url = url
            salon.save(update_fields=['logo_url'])
            if old_url and old_url != url:
                delete_image(old_url)
            log_audit(salon, audit_actor(request), 'web', f'{audit_actor(request)}: změna loga')
            return Response({'url': url, 'typ': 'logo'})

        if typ == 'favicon':
            old_url = salon.favicon_url
            salon.favicon_url = url
            salon.save(update_fields=['favicon_url'])
            if old_url and old_url != url:
                delete_image(old_url)
            log_audit(salon, audit_actor(request), 'web', f'{audit_actor(request)}: změna faviconu')
            return Response({'url': url, 'typ': 'favicon'})

        if typ == 'novinka':
            novinka_id = _form_param(request, 'novinka_id')
            try:
                novinka_id = int(novinka_id) if novinka_id else None
            except (TypeError, ValueError):
                novinka_id = None

            if not novinka_id:
                return Response(
                    {'detail': 'Chybí ID novinky. Nejdřív uložte novinku, pak nahrajte obrázek.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                novinka = Novinka.objects.get(id=novinka_id, salon=salon)
            except Novinka.DoesNotExist:
                return Response({'detail': 'Novinka nenalezena.'}, status=status.HTTP_404_NOT_FOUND)

            old_url = novinka.obrazek
            novinka.obrazek = url
            novinka.save(update_fields=['obrazek'])
            if old_url and old_url != url:
                delete_image(old_url)
            log_audit(salon, audit_actor(request), 'web', f'{audit_actor(request)}: nahrání obrázku novinky')
            return Response(NovinkaSerializer(novinka).data)

        if typ == 'cenik':
            cenik_id = _form_param(request, 'cenik_id')
            try:
                cenik_id = int(cenik_id) if cenik_id else None
            except (TypeError, ValueError):
                cenik_id = None

            if not cenik_id:
                return Response(
                    {'detail': 'Chybí ID služby. Nejdřív uložte ceník, pak nahrajte obrázek.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                cenik = CenikPolozka.objects.get(id=cenik_id, salon=salon)
            except CenikPolozka.DoesNotExist:
                return Response({'detail': 'Služba nenalezena.'}, status=status.HTTP_404_NOT_FOUND)

            old_url = cenik.obrazek
            cenik.obrazek = url
            cenik.save(update_fields=['obrazek'])
            if old_url and old_url != url:
                delete_image(old_url)
            log_audit(
                salon,
                audit_actor(request),
                'web',
                f'{audit_actor(request)}: nahrání obrázku služby ({cenik.nazev})',
            )
            return Response({'id': cenik.id, 'obrazek': cenik.obrazek, 'typ': 'cenik'})

        if typ == 'personel':
            zamestnanec_id = _form_param(request, 'zamestnanec_id')
            try:
                zamestnanec_id = int(zamestnanec_id) if zamestnanec_id else None
            except (TypeError, ValueError):
                zamestnanec_id = None
            if not zamestnanec_id:
                return Response(
                    {'detail': 'Chybí ID zaměstnance (zamestnanec_id).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            from rezervace.models import Zamestnanec
            try:
                zamestnanec = Zamestnanec.objects.get(id=zamestnanec_id, salon=salon)
            except Zamestnanec.DoesNotExist:
                return Response({'detail': 'Zaměstnanec nenalezen.'}, status=status.HTTP_404_NOT_FOUND)
            old_url = zamestnanec.fotka
            zamestnanec.fotka = url
            zamestnanec.save(update_fields=['fotka'])
            if old_url and old_url != url:
                delete_image(old_url)
            log_audit(salon, audit_actor(request), 'zamestnanec',
                      f'{audit_actor(request)}: nahrání fotky zaměstnance ({zamestnanec.jmeno})',
                      objekt_typ='zamestnanec', objekt_id=zamestnanec.id)
            return Response({'url': url, 'typ': 'personel', 'zamestnanec_id': zamestnanec.id})

        poradi = salon.obrazky.count()
        obrazek = SalonObrazek.objects.create(salon=salon, url=url, poradi=poradi)
        log_audit(salon, audit_actor(request), 'web', f'{audit_actor(request)}: přidání obrázku do galerie')
        return Response(SalonObrazekSerializer(obrazek).data, status=status.HTTP_201_CREATED)


class ImageDeleteView(APIView):
    permission_classes = [MajitelPermission]

    def delete(self, request, pk, image_id):
        try:
            obrazek = SalonObrazek.objects.get(id=image_id, salon_id=pk)
        except SalonObrazek.DoesNotExist:
            return Response({'detail': 'Obrázek nenalezen.'}, status=status.HTTP_404_NOT_FOUND)

        delete_image(obrazek.url)
        salon = obrazek.salon
        obrazek.delete()
        log_audit(salon, audit_actor(request), 'web', f'{audit_actor(request)}: smazání obrázku z galerie')
        return Response(status=status.HTTP_204_NO_CONTENT)


class BunnyStatusView(APIView):
    def get(self, request):
        return Response({
            'configured': is_bunny_configured(),
            'cdn_base': settings.BUNNY_CDN_BASE_URL if is_bunny_configured() else '',
        })


@method_decorator(csrf_exempt, name='dispatch')
class AuthLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        password = (request.data.get('password') or '').strip()
        if password == settings.SALON_ADMIN_PASSWORD:
            return Response({'ok': True, 'message': 'Přihlášení úspěšné.'})
        return Response(
            {'ok': False, 'message': 'Nesprávné heslo.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@method_decorator(csrf_exempt, name='dispatch')
class PoptavkaView(APIView):
    """Poptávka z prezentačního webu — bez rezervací."""
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PoptavkaRateThrottle]

    def post(self, request):
        jmeno = (request.data.get('jmeno') or '').strip()
        email = (request.data.get('email') or '').strip()
        telefon = (request.data.get('telefon') or '').strip()
        salon_nazev = (request.data.get('salon_nazev') or '').strip()
        zprava = (request.data.get('zprava') or '').strip()
        souhlas = request.data.get('souhlas')

        if not jmeno or not email:
            return Response({'detail': 'Vyplňte jméno a e-mail.'}, status=400)
        if not souhlas:
            return Response({'detail': 'Potvrďte souhlas se zpracováním údajů.'}, status=400)
        if len(zprava) > 5000:
            return Response({'detail': 'Zpráva je příliš dlouhá.'}, status=400)

        try:
            prijemce = odeslat_poptavku(jmeno, email, telefon, salon_nazev, zprava)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=503)
        except Exception:
            return Response(
                {'detail': 'Odeslání se nepodařilo. Zkuste to později nebo napište na info@ulovklienty.cz.'},
                status=500,
            )

        return Response({
            'ok': True,
            'message': 'Děkujeme — ozveme se vám co nejdříve.',
            'prijemce': prijemce,
        })
