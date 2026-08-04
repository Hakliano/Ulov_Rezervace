from rest_framework import serializers

from flow.customer_card_models import CustomerCard, CustomerVisit


class CustomerVisitSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerVisit
        fields = ['id', 'datum', 'text', 'autor_jmeno', 'vytvoreno']
        read_only_fields = fields


class CustomerCardListSerializer(serializers.ModelSerializer):
    stav_label = serializers.CharField(source='get_stav_display', read_only=True)
    visits_count = serializers.SerializerMethodField()

    class Meta:
        model = CustomerCard
        fields = [
            'id', 'email', 'jmeno', 'telefon', 'stav', 'stav_label',
            'visits_count', 'vytvoreno', 'confirmed_at',
        ]

    def get_visits_count(self, obj):
        return obj.visits.count()


class CustomerCardDetailSerializer(serializers.ModelSerializer):
    stav_label = serializers.CharField(source='get_stav_display', read_only=True)
    visits = CustomerVisitSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerCard
        fields = [
            'id', 'email', 'jmeno', 'telefon', 'poznamka',
            'stav', 'stav_label',
            'confirmed_at', 'confirmed_ip',
            'vytvoreno', 'upraveno',
            'visits',
        ]


class CustomerCardCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    jmeno = serializers.CharField(required=False, allow_blank=True, default='', max_length=120)
    telefon = serializers.CharField(required=False, allow_blank=True, default='', max_length=40)
    poznamka = serializers.CharField(required=False, allow_blank=True, default='')
    visit_datum = serializers.DateField()
    visit_text = serializers.CharField()
    odeslat_potvrzeni = serializers.BooleanField(default=True)


class CustomerCardUpdateSerializer(serializers.Serializer):
    jmeno = serializers.CharField(required=False, allow_blank=True, max_length=120)
    telefon = serializers.CharField(required=False, allow_blank=True, max_length=40)
    poznamka = serializers.CharField(required=False, allow_blank=True)


class CustomerVisitCreateSerializer(serializers.Serializer):
    datum = serializers.DateField()
    text = serializers.CharField()
