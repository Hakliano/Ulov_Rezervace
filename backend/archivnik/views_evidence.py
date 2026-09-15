from __future__ import annotations

import uuid

from django.db import IntegrityError
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from archivnik.models import (
    Asset,
    AssetKind,
    CustomFieldDef,
    CustomFieldValue,
    Customer,
    Entry,
    FieldKind,
    Object,
    ObjectType,
)
from archivnik.permissions import ArchivnikPermission
from archivnik.serializers import (
    AssetSerializer,
    CustomFieldDefSerializer,
    CustomFieldDefWriteSerializer,
    ObjectSerializer,
)
from archivnik.storage import BunnyUploadError, delete_bytes, get_bytes, guess_kind, store_file
from archivnik.views import _actor, _salon, _validation_detail


def _set_cover(obj, asset=None, exclude_id=None):
    if asset and asset.druh == AssetKind.FOTOGRAFIE and asset.objekt_id == obj.id:
        Object.objects.filter(pk=obj.id).update(cover=asset)
        return
    nxt = (
        Asset.objects.filter(objekt=obj, druh=AssetKind.FOTOGRAFIE)
        .exclude(pk=exclude_id or 0)
        .order_by('-vytvoreno')
        .first()
    )
    Object.objects.filter(pk=obj.id).update(cover=nxt)


class FieldListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request):
        salon = _salon(request)
        qs = CustomFieldDef.objects.filter(salon=salon).select_related('typ')
        tu = request.query_params.get('typ')
        if tu:
            qs = qs.filter(typ__uuid=tu)
        return Response(CustomFieldDefSerializer(qs, many=True).data)

    def post(self, request):
        ser = CustomFieldDefWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        salon = _salon(request)
        typ = ObjectType.objects.filter(salon=salon, uuid=data['typ_uuid']).first()
        if not typ:
            return Response({'detail': 'Typ objektu nenalezen.'}, status=400)
        obj = CustomFieldDef(
            salon=salon,
            typ=typ,
            nazev=data['nazev'].strip(),
            druh=data.get('druh') or FieldKind.TEXT,
            volby=list(data.get('volby') or []),
            poradi=data.get('poradi') or (typ.pole.count() + 1),
        )
        try:
            obj.save()
        except IntegrityError:
            return Response({'detail': 'Pole s tímto názvem u typu už existuje.'}, status=400)
        except Exception as exc:
            return Response({'detail': _validation_detail(exc)}, status=400)
        return Response(CustomFieldDefSerializer(obj).data, status=201)


class ObjectFieldValuesView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def _objekt(self, request, object_uuid):
        return Object.objects.filter(salon=_salon(request), uuid=object_uuid).select_related('typ').first()

    def get(self, request, object_uuid):
        obj = self._objekt(request, object_uuid)
        if not obj:
            return Response({'detail': 'Objekt nenalezen.'}, status=404)
        defs = list(CustomFieldDef.objects.filter(salon=obj.salon, typ=obj.typ, aktivni=True))
        values = {row.pole_id: row.hodnota for row in CustomFieldValue.objects.filter(objekt=obj)}
        payload = []
        for d in defs:
            payload.append({
                'pole_uuid': str(d.uuid),
                'nazev': d.nazev,
                'druh': d.druh,
                'volby': list(d.volby or []),
                'hodnota': values.get(d.id, ''),
            })
        return Response(payload)

    def put(self, request, object_uuid):
        obj = self._objekt(request, object_uuid)
        if not obj:
            return Response({'detail': 'Objekt nenalezen.'}, status=404)
        rows = request.data.get('hodnoty') or []
        if isinstance(rows, dict):
            rows = [{'pole_uuid': k, 'hodnota': v} for k, v in rows.items()]
        defs = {
            str(d.uuid): d
            for d in CustomFieldDef.objects.filter(salon=obj.salon, typ=obj.typ)
        }
        for row in rows:
            pole = defs.get(str(row.get('pole_uuid') or ''))
            if not pole:
                return Response({'detail': 'Neznámé vlastní pole.'}, status=400)
            CustomFieldValue.objects.update_or_create(
                objekt=obj, pole=pole,
                defaults={'hodnota': str(row.get('hodnota') or '').strip()},
            )
        return self.get(request, object_uuid)


class AssetListCreateView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        salon = _salon(request)
        qs = Asset.objects.filter(salon=salon).select_related('zakaznik', 'objekt', 'objekt__typ', 'zapis')
        cu = request.query_params.get('zakaznik')
        ou = request.query_params.get('objekt')
        eu = request.query_params.get('zapis')
        druh = request.query_params.get('druh')
        if ou:
            qs = qs.filter(objekt__uuid=ou)
        elif cu:
            qs = qs.filter(zakaznik__uuid=cu, objekt__isnull=True) if request.query_params.get('jen_zakaznik') == '1' else qs.filter(zakaznik__uuid=cu)
        if eu:
            qs = qs.filter(zapis__uuid=eu)
        if druh in (AssetKind.FOTOGRAFIE, AssetKind.DOKUMENT):
            qs = qs.filter(druh=druh)
        return Response(AssetSerializer(qs[:200], many=True, context={'request': request}).data)

    def post(self, request):
        upload = request.FILES.get('soubor') or request.FILES.get('file')
        if not upload:
            return Response({'detail': 'Vyberte soubor.'}, status=400)
        salon = _salon(request)
        actor = _actor(request)
        druh = guess_kind(upload.content_type or '', request.data.get('druh'))
        zakaznik = None
        objekt = None
        zapis = None
        if request.data.get('zapis_uuid'):
            zapis = Entry.objects.filter(salon=salon, uuid=request.data.get('zapis_uuid')).select_related('zakaznik', 'objekt').first()
            if not zapis:
                return Response({'detail': 'Zápis nenalezen.'}, status=400)
            zakaznik = zapis.zakaznik
            objekt = zapis.objekt
        elif request.data.get('objekt_uuid'):
            objekt = Object.objects.filter(salon=salon, uuid=request.data.get('objekt_uuid')).select_related('zakaznik').first()
            if not objekt:
                return Response({'detail': 'Objekt nenalezen.'}, status=400)
            zakaznik = objekt.zakaznik
        elif request.data.get('zakaznik_uuid'):
            zakaznik = Customer.objects.filter(salon=salon, uuid=request.data.get('zakaznik_uuid')).first()
            if not zakaznik:
                return Response({'detail': 'Zákazník nenalezen.'}, status=400)
        else:
            return Response({'detail': 'Zadejte zákazníka, objekt nebo zápis.'}, status=400)
        if request.data.get('objekt_uuid') and zapis and not objekt:
            objekt = Object.objects.filter(salon=salon, uuid=request.data.get('objekt_uuid'), zakaznik=zakaznik).first()
        raw = upload.read()
        nazev = (request.data.get('nazev') or getattr(upload, 'name', '') or 'soubor').strip()[:200]
        asset_uuid = uuid.uuid4()
        try:
            _, key, ctype, size = store_file(
                salon, raw, upload.content_type or '', getattr(upload, 'name', ''), druh,
                asset_uuid=asset_uuid,
            )
        except BunnyUploadError as exc:
            return Response({'detail': str(exc)}, status=400)
        asset = Asset(
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
            vytvoril=actor,
        )
        try:
            asset.save()
        except Exception as exc:
            return Response({'detail': _validation_detail(exc)}, status=400)
        if druh == AssetKind.FOTOGRAFIE and objekt and not objekt.cover_id:
            _set_cover(objekt, asset)
        return Response(AssetSerializer(asset, context={'request': request}).data, status=201)


class AssetContentView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def get(self, request, asset_uuid):
        asset = Asset.objects.filter(salon=_salon(request), uuid=asset_uuid).first()
        if not asset:
            return Response({'detail': 'Soubor nenalezen.'}, status=404)
        try:
            data, ctype = get_bytes(asset.storage_key)
        except BunnyUploadError as exc:
            return Response({'detail': str(exc)}, status=404)
        resp = HttpResponse(data, content_type=asset.content_type or ctype)
        inline = (asset.content_type or '').startswith('image/') or asset.content_type == 'application/pdf'
        disp = 'inline' if inline else 'attachment'
        resp['Content-Disposition'] = f'{disp}; filename="{asset.nazev}"'
        resp['Cache-Control'] = 'private, max-age=300'
        return resp


class AssetDetailView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def delete(self, request, asset_uuid):
        asset = Asset.objects.filter(salon=_salon(request), uuid=asset_uuid).select_related('objekt', 'zapis').first()
        if not asset:
            return Response({'detail': 'Soubor nenalezen.'}, status=404)
        objekt = asset.objekt
        was_cover = bool(objekt and objekt.cover_id == asset.id)
        key = asset.storage_key
        asset_id = asset.id
        asset.delete()
        delete_bytes(key)
        if objekt and was_cover:
            _set_cover(objekt, exclude_id=asset_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ObjectCoverView(APIView):
    authentication_classes = []
    permission_classes = [ArchivnikPermission]

    def post(self, request, object_uuid):
        obj = Object.objects.filter(salon=_salon(request), uuid=object_uuid).first()
        if not obj:
            return Response({'detail': 'Objekt nenalezen.'}, status=404)
        asset = Asset.objects.filter(
            salon=obj.salon, uuid=request.data.get('asset_uuid'), objekt=obj, druh=AssetKind.FOTOGRAFIE,
        ).first()
        if not asset:
            return Response({'detail': 'Vyberte fotografii tohoto objektu.'}, status=400)
        _set_cover(obj, asset)
        obj = Object.objects.select_related('typ', 'zakaznik', 'cover').filter(pk=obj.pk).first()
        return Response(ObjectSerializer(obj, context={'request': request}).data)
