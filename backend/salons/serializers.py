from rest_framework import serializers

from .bunny import delete_image
from .models import CenikPolozka, Novinka, Salon, SalonObrazek


class CenikPolozkaSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = CenikPolozka
        fields = ['id', 'nazev', 'cena', 'obrazek', 'poradi', 'delka_minut', 'rezerva_minut', 'aktivni']
        extra_kwargs = {'obrazek': {'required': False, 'allow_blank': True}}


class NovinkaSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Novinka
        fields = ['id', 'nadpis', 'text', 'obrazek', 'datum']
        read_only_fields = ['datum']
        extra_kwargs = {'obrazek': {'required': False, 'allow_blank': True}}


class OteviraciDobaSerializer(serializers.Serializer):
    """Vypočtená otevírací doba (sjednocení rozvrhů aktivních zaměstnanců)."""
    den = serializers.IntegerField()
    den_nazev = serializers.CharField()
    od = serializers.TimeField(allow_null=True, required=False)
    do = serializers.TimeField(allow_null=True, required=False)
    zavreno = serializers.BooleanField()


class SalonObrazekSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalonObrazek
        fields = ['id', 'url', 'popis', 'poradi']
        extra_kwargs = {
            'url': {'required': False},
            'id': {'required': False},
        }


def _normalize_hex_color(value):
    if value is None:
        return ''
    raw = str(value).strip()
    if not raw:
        return ''
    if not raw.startswith('#'):
        raw = f'#{raw}'
    if len(raw) != 7 or any(c not in '0123456789abcdefABCDEF' for c in raw[1:]):
        raise serializers.ValidationError('Barva musí být ve formátu #RRGGBB.')
    return raw.upper()


class SalonSerializer(serializers.ModelSerializer):
    cenik = CenikPolozkaSerializer(many=True, required=False)
    novinky = NovinkaSerializer(many=True, required=False)
    oteviraci_doba = serializers.SerializerMethodField()
    obrazky = SalonObrazekSerializer(many=True, required=False)

    class Meta:
        model = Salon
        fields = [
            'id', 'name', 'description', 'address', 'phone', 'email',
            'hero_image', 'logo_url', 'favicon_url', 'primary_color', 'accent_color',
            'cenik', 'novinky', 'oteviraci_doba', 'obrazky',
        ]

    def get_oteviraci_doba(self, obj):
        from rezervace.services.oteviraci_doba import vypocti_oteviraci_dobu_tydne
        return OteviraciDobaSerializer(vypocti_oteviraci_dobu_tydne(obj), many=True).data

    def validate_primary_color(self, value):
        return _normalize_hex_color(value)

    def validate_accent_color(self, value):
        return _normalize_hex_color(value)

    def update(self, instance, validated_data):
        cenik_data = validated_data.pop('cenik', None)
        novinky_data = validated_data.pop('novinky', None)
        validated_data.pop('oteviraci_doba', None)
        obrazky_data = validated_data.pop('obrazky', None)

        old_email = instance.email

        # hero / logo / favicon URL jen přes /upload/; přes PUT lze jen vymazat
        validated_data.pop('hero_image', None)
        cleared_assets = []
        for field in ('logo_url', 'favicon_url'):
            if field not in validated_data:
                continue
            if validated_data[field]:
                validated_data.pop(field)
            else:
                old = getattr(instance, field) or ''
                if old:
                    cleared_assets.append(old)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        for old_url in cleared_assets:
            delete_image(old_url)

        self._sync_rezervacni_email(instance, old_email=old_email)

        if cenik_data is not None:
            self._sync_cenik(instance, cenik_data)
        if novinky_data is not None:
            self._sync_novinky(instance, novinky_data)
        if obrazky_data is not None:
            self._sync_obrazky(instance, obrazky_data)

        return instance

    def _sync_rezervacni_email(self, salon, old_email=None):
        """E-mail z administrace webu = odesílatel rezervačních e-mailů."""
        try:
            from rezervace.models import RezervacniNastaveni
            nast, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
            nast.email_odesilatel = salon.email
            nast.email_jmeno_odesilatele = salon.name
            if not nast.smtp_user or (old_email and nast.smtp_user == old_email):
                nast.smtp_user = salon.email
            nast.save(update_fields=['email_odesilatel', 'email_jmeno_odesilatele', 'smtp_user'])
        except Exception:
            pass

    def _sync_cenik(self, salon, items):
        existing_ids = []
        for item in items:
            item_id = item.get('id')
            if item_id:
                try:
                    obj = CenikPolozka.objects.get(id=item_id, salon=salon)
                    old_url = obj.obrazek
                    for key, val in item.items():
                        if key != 'id':
                            setattr(obj, key, val)
                    if 'obrazek' in item and old_url and old_url != (item.get('obrazek') or ''):
                        delete_image(old_url)
                    obj.save()
                    existing_ids.append(obj.id)
                except CenikPolozka.DoesNotExist:
                    pass
            else:
                obj = CenikPolozka.objects.create(salon=salon, **item)
                existing_ids.append(obj.id)
        to_delete = salon.cenik.exclude(id__in=existing_ids)
        for cenik in to_delete:
            if cenik.obrazek:
                delete_image(cenik.obrazek)
        to_delete.delete()

    def _sync_novinky(self, salon, items):
        existing_ids = []
        for item in items:
            item_id = item.get('id')
            if item_id:
                try:
                    obj = Novinka.objects.get(id=item_id, salon=salon)
                    obj.nadpis = item.get('nadpis', obj.nadpis)
                    obj.text = item.get('text', obj.text)
                    if 'obrazek' in item:
                        new_url = item['obrazek'] or ''
                        if obj.obrazek and obj.obrazek != new_url:
                            delete_image(obj.obrazek)
                        obj.obrazek = new_url
                    obj.save()
                    existing_ids.append(obj.id)
                except Novinka.DoesNotExist:
                    pass
            else:
                data = {k: v for k, v in item.items() if k != 'id'}
                obj = Novinka.objects.create(salon=salon, **data)
                existing_ids.append(obj.id)

        to_delete = salon.novinky.exclude(id__in=existing_ids)
        for novinka in to_delete:
            if novinka.obrazek:
                delete_image(novinka.obrazek)
        to_delete.delete()

    def _sync_obrazky(self, salon, items):
        """Aktualizuje jen popisy a pořadí. URL řeší upload/delete endpointy."""
        for item in items:
            item_id = item.get('id')
            if not item_id:
                continue
            try:
                obj = SalonObrazek.objects.get(id=item_id, salon=salon)
            except SalonObrazek.DoesNotExist:
                continue
            if 'popis' in item:
                obj.popis = item['popis']
            if 'poradi' in item:
                obj.poradi = item['poradi']
            obj.save()
