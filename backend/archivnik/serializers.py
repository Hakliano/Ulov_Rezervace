from rest_framework import serializers

from archivnik.models import (
    Asset,
    CustomFieldDef,
    Customer,
    Entry,
    Object,
    ObjectType,
    Reminder,
    Tag,
)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['uuid', 'nazev', 'rozsah']
        read_only_fields = ['uuid']


class ObjectTypeSerializer(serializers.ModelSerializer):
    pole = serializers.SerializerMethodField()

    class Meta:
        model = ObjectType
        fields = ['uuid', 'nazev', 'poradi', 'aktivni', 'pole']
        read_only_fields = ['uuid']

    def get_pole(self, obj):
        qs = obj.pole.all() if hasattr(obj, '_prefetched_objects_cache') and 'pole' in obj._prefetched_objects_cache else obj.pole.filter(aktivni=True)
        return CustomFieldDefSerializer(qs, many=True).data


class CustomFieldDefSerializer(serializers.ModelSerializer):
    typ_uuid = serializers.UUIDField(source='typ.uuid', read_only=True)

    class Meta:
        model = CustomFieldDef
        fields = ['uuid', 'typ_uuid', 'nazev', 'druh', 'poradi', 'aktivni']
        read_only_fields = ['uuid']


class CustomFieldDefWriteSerializer(serializers.Serializer):
    typ_uuid = serializers.UUIDField()
    nazev = serializers.CharField(max_length=80)
    druh = serializers.ChoiceField(choices=['text', 'cislo', 'datum', 'ano_ne'], required=False, default='text')
    poradi = serializers.IntegerField(required=False, default=0)


class CustomFieldValueSerializer(serializers.Serializer):
    pole_uuid = serializers.UUIDField()
    nazev = serializers.CharField(read_only=True)
    druh = serializers.CharField(read_only=True)
    hodnota = serializers.CharField(allow_blank=True, max_length=300)


class AssetSerializer(serializers.ModelSerializer):
    zakaznik_uuid = serializers.UUIDField(source='zakaznik.uuid', read_only=True)
    zakaznik_jmeno = serializers.CharField(source='zakaznik.display_name', read_only=True)
    objekt_uuid = serializers.UUIDField(source='objekt.uuid', read_only=True, allow_null=True)
    objekt_nazev = serializers.CharField(source='objekt.nazev', read_only=True, allow_null=True)
    zapis_uuid = serializers.UUIDField(source='zapis.uuid', read_only=True, allow_null=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = [
            'uuid', 'druh', 'nazev', 'content_type', 'velikost',
            'zakaznik_uuid', 'zakaznik_jmeno', 'objekt_uuid', 'objekt_nazev',
            'zapis_uuid', 'url', 'vytvoreno',
        ]

    def get_url(self, obj):
        request = self.context.get('request')
        if not request:
            return f'/api/archivnik/assets/{obj.uuid}/content/'
        token = (
            request.headers.get('X-Archivnik-Token')
            or request.GET.get('token')
            or ''
        )
        url = request.build_absolute_uri(f'/api/archivnik/assets/{obj.uuid}/content/')
        if token:
            sep = '&' if '?' in url else '?'
            return f'{url}{sep}token={token}'
        return url


class CustomerListSerializer(serializers.ModelSerializer):
    tagy = TagSerializer(many=True, read_only=True)
    objekty_pocet = serializers.IntegerField(read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            'uuid', 'jmeno', 'prijmeni', 'display_name', 'telefon', 'email',
            'adresa', 'poznamka', 'stav', 'tagy', 'objekty_pocet',
            'vytvoreno', 'upraveno',
        ]


class CustomerWriteSerializer(serializers.Serializer):
    jmeno = serializers.CharField(required=False, allow_blank=True, default='', max_length=120)
    prijmeni = serializers.CharField(max_length=160)
    telefon = serializers.CharField(required=False, allow_blank=True, default='', max_length=40)
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    adresa = serializers.CharField(required=False, allow_blank=True, default='', max_length=300)
    poznamka = serializers.CharField(required=False, allow_blank=True, default='')
    stav = serializers.ChoiceField(required=False, choices=['aktivni', 'archivovany'])
    tagy = serializers.ListField(child=serializers.UUIDField(), required=False)


class ObjectSerializer(serializers.ModelSerializer):
    typ_uuid = serializers.UUIDField(source='typ.uuid', read_only=True)
    typ_nazev = serializers.CharField(source='typ.nazev', read_only=True)
    zakaznik_uuid = serializers.UUIDField(source='zakaznik.uuid', read_only=True)
    zakaznik_jmeno = serializers.CharField(source='zakaznik.display_name', read_only=True)
    tagy = TagSerializer(many=True, read_only=True)
    zapisy_pocet = serializers.SerializerMethodField()
    posledni_zapis = serializers.SerializerMethodField()
    pripominky_aktivni = serializers.SerializerMethodField()
    cover_uuid = serializers.SerializerMethodField()

    class Meta:
        model = Object
        fields = [
            'uuid', 'nazev', 'popis', 'stav',
            'typ_uuid', 'typ_nazev', 'zakaznik_uuid', 'zakaznik_jmeno',
            'tagy', 'zapisy_pocet', 'posledni_zapis', 'pripominky_aktivni',
            'cover_uuid', 'vytvoreno', 'upraveno',
        ]

    def get_zapisy_pocet(self, obj):
        if 'zapisy_pocet' in obj.__dict__:
            return obj.zapisy_pocet
        return obj.zapisy.count()

    def get_posledni_zapis(self, obj):
        if 'posledni_zapis' in obj.__dict__:
            val = obj.posledni_zapis
            return val.isoformat() if val else None
        last = obj.zapisy.order_by('-nastalo').values_list('nastalo', flat=True).first()
        return last.isoformat() if last else None

    def get_pripominky_aktivni(self, obj):
        if 'pripominky_aktivni' in obj.__dict__:
            return obj.pripominky_aktivni
        return obj.pripominky.filter(stav='aktivni').count()

    def get_cover_uuid(self, obj):
        if obj.cover_id:
            return str(obj.cover.uuid)
        photo = obj.soubory.filter(druh='fotografie').order_by('-vytvoreno').values_list('uuid', flat=True).first()
        return str(photo) if photo else None


class ObjectWriteSerializer(serializers.Serializer):
    zakaznik_uuid = serializers.UUIDField(required=False)
    typ_uuid = serializers.UUIDField(required=False)
    nazev = serializers.CharField(max_length=160, required=False)
    popis = serializers.CharField(required=False, allow_blank=True)
    stav = serializers.ChoiceField(required=False, choices=['aktivni', 'archivovany'])
    tagy = serializers.ListField(child=serializers.UUIDField(), required=False)


class EntrySerializer(serializers.ModelSerializer):
    zakaznik_uuid = serializers.UUIDField(source='zakaznik.uuid', read_only=True)
    zakaznik_jmeno = serializers.CharField(source='zakaznik.display_name', read_only=True)
    objekt_uuid = serializers.UUIDField(source='objekt.uuid', read_only=True, allow_null=True)
    objekt_nazev = serializers.CharField(source='objekt.nazev', read_only=True, allow_null=True)
    autor = serializers.CharField(source='vytvoril.jmeno', read_only=True, allow_null=True)
    prilohy = AssetSerializer(many=True, read_only=True)

    class Meta:
        model = Entry
        fields = [
            'uuid', 'zakaznik_uuid', 'zakaznik_jmeno', 'objekt_uuid', 'objekt_nazev',
            'nastalo', 'typ_zapisu', 'nadpis', 'text', 'autor', 'prilohy',
            'vytvoreno', 'upraveno',
        ]


class EntryWriteSerializer(serializers.Serializer):
    zakaznik_uuid = serializers.UUIDField(required=False)
    objekt_uuid = serializers.UUIDField(required=False, allow_null=True)
    nastalo = serializers.DateTimeField(required=False)
    typ_zapisu = serializers.CharField(required=False, allow_blank=True, default='Poznámka', max_length=80)
    nadpis = serializers.CharField(required=False, allow_blank=True, default='', max_length=200)
    text = serializers.CharField()


class ReminderSerializer(serializers.ModelSerializer):
    zakaznik_uuid = serializers.UUIDField(source='zakaznik.uuid', read_only=True)
    zakaznik_jmeno = serializers.CharField(source='zakaznik.display_name', read_only=True)
    objekt_uuid = serializers.UUIDField(source='objekt.uuid', read_only=True, allow_null=True)
    objekt_nazev = serializers.CharField(source='objekt.nazev', read_only=True, allow_null=True)
    prirazeny_jmeno = serializers.CharField(source='prirazeny.jmeno', read_only=True, allow_null=True)

    class Meta:
        model = Reminder
        fields = [
            'uuid', 'zakaznik_uuid', 'zakaznik_jmeno', 'objekt_uuid', 'objekt_nazev',
            'termin', 'text', 'stav', 'prirazeny_jmeno', 'vytvoreno',
        ]


class ReminderWriteSerializer(serializers.Serializer):
    zakaznik_uuid = serializers.UUIDField()
    objekt_uuid = serializers.UUIDField(required=False, allow_null=True)
    termin = serializers.DateField()
    text = serializers.CharField(max_length=300)
    prirazeny_uuid = serializers.UUIDField(required=False, allow_null=True)
