import uuid

from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import serializers

from rezervace.notifikace_defaults import (
    MAX_NOTIFIKACE,
    NOTIFIKACE_TAGY,
    PLACEHOLDER_HINT,
    dopln_na_notifikace,
    normalizuj_notifikace,
)
from rezervace.models import (
    BlokaceCasu,
    NoShowZaznam,
    Rezervace,
    RezervaceHistorie,
    RezervacniNastaveni,
    RezervaceSluzba,
    SalonAuditLog,
    SalonVyjimka,
    Zakaznik,
    Zamestnanec,
    ZamestnanecAbsence,
    ZamestnanecRozvrh,
)
from salons.models import CenikPolozka


class SluzbaRezervaceSerializer(serializers.ModelSerializer):
    nazev = serializers.CharField(source='sluzba.nazev', read_only=True)
    cena = serializers.DecimalField(source='sluzba.cena', max_digits=10, decimal_places=0, read_only=True)
    delka_minut = serializers.IntegerField(source='sluzba.delka_minut', read_only=True)

    class Meta:
        model = RezervaceSluzba
        fields = ['sluzba', 'nazev', 'cena', 'delka_minut', 'poradi']


class RezervaceSerializer(serializers.ModelSerializer):
    polozky = SluzbaRezervaceSerializer(many=True, read_only=True)
    zamestnanec_jmeno = serializers.CharField(source='zamestnanec.jmeno', read_only=True, default=None)
    stav_label = serializers.CharField(source='get_stav_display', read_only=True)

    class Meta:
        model = Rezervace
        fields = [
            'id', 'zacatek', 'konec', 'stav', 'stav_label', 'zamestnanec', 'zamestnanec_jmeno',
            'poznamka_zakaznika', 'typ_vytvoreni', 'polozky', 'cancel_token', 'potvrzeni_token',
            'skutecna_delka_minut', 'dokonceno_at', 'vytvoreno',
        ]


class RezervaceCreateSerializer(serializers.Serializer):
    sluzby = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    datum = serializers.DateField()
    cas = serializers.RegexField(regex=r'^\d{2}:\d{2}$')
    zamestnanec_id = serializers.IntegerField(required=False, allow_null=True)
    poznamka = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    nick = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    ochrana_udaju_souhlas = serializers.BooleanField()
    zasady_verze = serializers.CharField(required=False, allow_blank=True, max_length=20)
    jazyk = serializers.CharField(required=False, allow_blank=True, max_length=10, default='cs')
    session_token = serializers.UUIDField(required=False, allow_null=True)

    def validate_ochrana_udaju_souhlas(self, value):
        if not value:
            raise serializers.ValidationError(
                'Musíte potvrdit seznámení se Zásadami ochrany osobních údajů.',
            )
        return value


class ZamestnanecSerializer(serializers.ModelSerializer):
    ma_prihlaseni = serializers.BooleanField(read_only=True)

    class Meta:
        model = Zamestnanec
        fields = [
            'id', 'jmeno', 'specializace', 'popis', 'fotka', 'zobrazit_na_webu', 'aktivni',
            'poradi', 'cislo_uctu', 'prihlasovaci_jmeno', 'role', 'ma_prihlaseni',
        ]


class ZamestnanecPublicSerializer(serializers.ModelSerializer):
    rozvrh = serializers.SerializerMethodField()

    class Meta:
        model = Zamestnanec
        fields = ['id', 'jmeno', 'specializace', 'popis', 'fotka', 'rozvrh']

    def get_rozvrh(self, obj):
        return dopln_rozvrh_7_dni(obj)


class ZamestnanecRozvrhSerializer(serializers.ModelSerializer):
    den_nazev = serializers.CharField(source='get_den_display', read_only=True)

    class Meta:
        model = ZamestnanecRozvrh
        fields = ['id', 'den', 'den_nazev', 'od', 'do', 'volno']


class ZamestnanecAbsenceSerializer(serializers.ModelSerializer):
    typ_label = serializers.CharField(source='get_typ_display', read_only=True)

    class Meta:
        model = ZamestnanecAbsence
        fields = ['id', 'datum_od', 'datum_do', 'typ', 'typ_label', 'poznamka']

    def validate(self, data):
        od = data.get('datum_od') or (self.instance.datum_od if self.instance else None)
        do = data.get('datum_do') or (self.instance.datum_do if self.instance else None)
        if od and do and do < od:
            raise serializers.ValidationError('Datum „do“ musí být stejné nebo pozdější než „od“.')
        return data


def dopln_rozvrh_7_dni(zamestnanec):
    from rezervace.models import DENY
    existing = {r.den: r for r in zamestnanec.rozvrh.all()}
    deny = dict(DENY)
    result = []
    for den in range(7):
        if den in existing:
            result.append(ZamestnanecRozvrhSerializer(existing[den]).data)
        else:
            result.append({
                'id': None,
                'den': den,
                'den_nazev': deny.get(den, str(den)),
                'od': None,
                'do': None,
                'volno': True,
            })
    return result


class ZamestnanecDetailSerializer(ZamestnanecSerializer):
    rozvrh = serializers.SerializerMethodField()
    absence = ZamestnanecAbsenceSerializer(many=True, read_only=True)

    class Meta(ZamestnanecSerializer.Meta):
        fields = ZamestnanecSerializer.Meta.fields + ['rozvrh', 'absence']

    def get_rozvrh(self, obj):
        return dopln_rozvrh_7_dni(obj)


class ZamestnanecWriteSerializer(serializers.ModelSerializer):
    rozvrh = ZamestnanecRozvrhSerializer(many=True, required=False)
    heslo = serializers.CharField(required=False, allow_blank=True, write_only=True, min_length=6)

    class Meta:
        model = Zamestnanec
        fields = [
            'id', 'jmeno', 'specializace', 'popis', 'fotka', 'zobrazit_na_webu', 'aktivni',
            'poradi', 'cislo_uctu', 'rozvrh', 'prihlasovaci_jmeno', 'role', 'heslo',
        ]

    def validate(self, data):
        instance = self.instance
        role = data.get('role', instance.role if instance else Zamestnanec.ROLE_ZAMESTNANEC)
        if role == Zamestnanec.ROLE_MAJITEL and (not instance or instance.role != Zamestnanec.ROLE_MAJITEL):
            raise serializers.ValidationError({
                'role': (
                    'Účet majitele nelze vytvořit ani přiřadit. Majitel má jen správcovský přístup. '
                    'Pokud také provádí služby, založte mu běžný zaměstnanecký účet.'
                ),
            })
        return data

    def create(self, validated_data):
        rozvrh_data = validated_data.pop('rozvrh', [])
        heslo = validated_data.pop('heslo', '')
        validated_data.pop('role', None)
        salon = self.context['salon']
        z = Zamestnanec.objects.create(salon=salon, role=Zamestnanec.ROLE_ZAMESTNANEC, **validated_data)
        if heslo:
            from rezervace.services.staff_auth import nastav_heslo_staff
            nastav_heslo_staff(z, heslo)
        if rozvrh_data:
            for r in rozvrh_data:
                ZamestnanecRozvrh.objects.create(zamestnanec=z, **r)
        else:
            for den in range(7):
                ZamestnanecRozvrh.objects.create(zamestnanec=z, den=den, volno=True)
        return z

    def update(self, instance, validated_data):
        if instance.role == Zamestnanec.ROLE_MAJITEL and validated_data.get('aktivni') is False:
            raise serializers.ValidationError({'aktivni': 'Účet majitelky nelze deaktivovat.'})
        if instance.role == Zamestnanec.ROLE_MAJITEL:
            validated_data.pop('role', None)
            validated_data['zobrazit_na_webu'] = False
            validated_data.pop('rozvrh', None)
        else:
            validated_data.pop('role', None)
        byl_aktivni = instance.aktivni
        rozvrh_data = validated_data.pop('rozvrh', None)
        heslo = validated_data.pop('heslo', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        if byl_aktivni and not instance.aktivni and instance.role != Zamestnanec.ROLE_MAJITEL:
            from rezervace.services.staff_auth import zrusit_vsechny_sessiony
            zrusit_vsechny_sessiony(instance)
        if heslo:
            from rezervace.services.staff_auth import nastav_heslo_staff
            nastav_heslo_staff(instance, heslo)
        if rozvrh_data is not None and instance.role != Zamestnanec.ROLE_MAJITEL:
            instance.rozvrh.all().delete()
            for r in rozvrh_data:
                ZamestnanecRozvrh.objects.create(zamestnanec=instance, **r)
        return instance


class EmailNastaveniSerializer(serializers.ModelSerializer):
    smtp_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    smtp_password_nastaveno = serializers.SerializerMethodField()

    class Meta:
        model = RezervacniNastaveni
        fields = [
            'smtp_host', 'smtp_port', 'smtp_use_ssl', 'smtp_user',
            'smtp_password', 'smtp_password_nastaveno',
            'email_odesilatel', 'email_jmeno_odesilatele',
            'web_rezervace_url',
        ]

    def get_smtp_password_nastaveno(self, obj):
        return bool(obj.smtp_password)

    def update(self, instance, validated_data):
        pwd = validated_data.pop('smtp_password', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if pwd:
            instance.smtp_password = pwd
        instance.save()
        return instance


class NotifikaceItemSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    offset = serializers.CharField(max_length=10, required=False, allow_blank=True)
    manual = serializers.BooleanField(default=False, required=False)
    manual_typ = serializers.CharField(max_length=20, required=False, allow_blank=True)
    aktivni = serializers.BooleanField(default=False)
    predmet = serializers.CharField(max_length=200)
    text = serializers.CharField(max_length=8000)

    def validate(self, attrs):
        manual = attrs.get('manual') or attrs.get('offset') == 'manual'
        if manual:
            attrs['manual'] = True
            attrs['offset'] = 'manual'
        elif not attrs.get('offset'):
            raise serializers.ValidationError({'offset': 'Offset je povinný u časované notifikace.'})
        return attrs

    def validate_offset(self, value):
        if value == 'manual' or not value:
            return 'manual'
        s = str(value).strip()
        import re
        if not re.match(r'^[+-]\d+$', s):
            raise serializers.ValidationError('Offset musí být ve formátu +24 nebo -2.')
        h = int(s[1:])
        if h <= 0:
            raise serializers.ValidationError('Počet hodin musí být kladné číslo.')
        return s


class RezervacniNastaveniSerializer(serializers.ModelSerializer):
    notifikace = NotifikaceItemSerializer(many=True, required=False)
    notifikace_placeholders = serializers.SerializerMethodField(read_only=True)
    notifikace_tagy = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RezervacniNastaveni
        fields = [
            'interval_minut', 'min_predstih_hodin', 'max_predstih_mesicu',
            'notifikace', 'notifikace_placeholders', 'notifikace_tagy',
            'storno_do_hodin', 'platba_qr_text', 'auto_potvrzeni', 'potvrzeni_platnost_hodin',
            'gdpr_zasady_verze',
            'email_odesilatel', 'email_jmeno_odesilatele', 'recenze_url',
        ]

    def get_notifikace_placeholders(self, obj):
        return PLACEHOLDER_HINT

    def get_notifikace_tagy(self, obj):
        return NOTIFIKACE_TAGY

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['notifikace'] = dopln_na_notifikace(instance.notifikace)
        return data

    def validate_notifikace(self, value):
        if len(value) > MAX_NOTIFIKACE:
            raise serializers.ValidationError(f'Maximálně {MAX_NOTIFIKACE} notifikace.')
        seen_ids = set()
        result = []
        for item in value:
            d = dict(item)
            nid = str(d.get('id') or uuid.uuid4())
            if nid in seen_ids:
                nid = str(uuid.uuid4())
            seen_ids.add(nid)
            d['id'] = nid
            result.append(d)
        return result

    def update(self, instance, validated_data):
        notifikace = validated_data.pop('notifikace', None)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if notifikace is not None:
            instance.notifikace = dopln_na_notifikace(notifikace)
        instance.save()
        return instance


class SluzbaPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = CenikPolozka
        fields = ['id', 'nazev', 'cena', 'delka_minut', 'rezerva_minut', 'poradi']


class SalonVyjimkaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalonVyjimka
        fields = ['id', 'datum_od', 'datum_do', 'duvod']


class BlokaceCasuSerializer(serializers.ModelSerializer):
    zamestnanec_jmeno = serializers.CharField(source='zamestnanec.jmeno', read_only=True, default=None)

    class Meta:
        model = BlokaceCasu
        fields = ['id', 'zamestnanec', 'zamestnanec_jmeno', 'zacatek', 'konec', 'popis']


class ZakaznikRegistraceSerializer(serializers.Serializer):
    nick = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, max_length=128, write_only=True)
    ochrana_udaju_souhlas = serializers.BooleanField()
    zasady_verze = serializers.CharField(required=False, allow_blank=True, max_length=20)
    jazyk = serializers.CharField(required=False, allow_blank=True, max_length=10, default='cs')

    def validate_ochrana_udaju_souhlas(self, value):
        if not value:
            raise serializers.ValidationError(
                'Musíte potvrdit seznámení se Zásadami ochrany osobních údajů.',
            )
        return value


class ZakaznikPrihlaseniSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128, write_only=True)


class AdminRezervaceSerializer(serializers.ModelSerializer):
    polozky = SluzbaRezervaceSerializer(many=True, read_only=True)
    zakaznik_nick = serializers.CharField(source='zakaznik.nick', read_only=True, default=None)
    zamestnanec_jmeno = serializers.CharField(source='zamestnanec.jmeno', read_only=True, default=None)
    zamestnanec_cislo_uctu = serializers.CharField(source='zamestnanec.cislo_uctu', read_only=True, default='')
    kontaktni_email = serializers.SerializerMethodField()
    kontaktni_jmeno = serializers.CharField(read_only=True)
    email_host = serializers.SerializerMethodField()
    anonymizovano = serializers.SerializerMethodField()

    class Meta:
        model = Rezervace
        fields = [
            'id', 'zacatek', 'konec', 'stav', 'zamestnanec', 'zamestnanec_jmeno', 'zamestnanec_cislo_uctu', 'zakaznik', 'zakaznik_nick',
            'jmeno_host', 'email_host', 'kontaktni_email', 'kontaktni_jmeno',
            'poznamka_zakaznika', 'poznamka_interni',
            'typ_vytvoreni', 'polozky', 'skutecna_delka_minut', 'dokonceno_at',
            'thank_you_sent_at', 'anonymized_at', 'deleted_at', 'anonymizovano',
        ]

    def get_anonymizovano(self, obj):
        return obj.anonymized_at is not None

    def get_kontaktni_email(self, obj):
        return '' if obj.anonymized_at else obj.kontaktni_email

    def get_email_host(self, obj):
        return '' if obj.anonymized_at else obj.email_host


class NoShowZaznamSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()

    class Meta:
        model = NoShowZaznam
        fields = [
            'id', 'jmeno', 'email', 'zacatek', 'zamestnanec_jmeno', 'sluzby',
            'email_upozorneni_odeslan', 'zakaznik_blokovan', 'vytvoreno', 'rezervace', 'zakaznik',
        ]

    def get_email(self, obj):
        return obj.email or ''


class AdminRezervaceCreateSerializer(serializers.Serializer):
    sluzby = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    datum = serializers.DateField()
    cas = serializers.RegexField(regex=r'^\d{2}:\d{2}$')
    zamestnanec_id = serializers.IntegerField(required=False, allow_null=True)
    nick = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    poznamka_zakaznika = serializers.CharField(required=False, allow_blank=True)
    poznamka_interni = serializers.CharField(required=False, allow_blank=True)
    typ_vytvoreni = serializers.ChoiceField(
        choices=['online', 'telefon', 'osobne', 'zamestnanec'], default='zamestnanec',
    )
    stav = serializers.ChoiceField(
        choices=['ceka', 'potvrzeno'], default='potvrzeno',
    )


class RezervaceHistorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = RezervaceHistorie
        fields = ['id', 'kdo', 'kdy', 'popis', 'data_pred', 'data_po']


class SalonAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalonAuditLog
        fields = ['id', 'kdo', 'kdy', 'kategorie', 'popis', 'objekt_typ', 'objekt_id']
