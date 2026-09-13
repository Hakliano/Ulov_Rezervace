from rest_framework import serializers

from archivnik.models import (
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
    class Meta:
        model = ObjectType
        fields = ['uuid', 'nazev', 'poradi', 'aktivni']
        read_only_fields = ['uuid']


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

    class Meta:
        model = Object
        fields = [
            'uuid', 'nazev', 'popis', 'stav',
            'typ_uuid', 'typ_nazev', 'zakaznik_uuid', 'zakaznik_jmeno',
            'tagy', 'zapisy_pocet', 'posledni_zapis', 'pripominky_aktivni',
            'vytvoreno', 'upraveno',
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

    class Meta:
        model = Entry
        fields = [
            'uuid', 'zakaznik_uuid', 'zakaznik_jmeno', 'objekt_uuid', 'objekt_nazev',
            'nastalo', 'typ_zapisu', 'nadpis', 'text', 'autor',
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
