from rest_framework import serializers

from flow.models import FlowUser, heslo_je_platne


class FlowUserPublicSerializer(serializers.ModelSerializer):
    zamestnanec_jmeno = serializers.CharField(source='zamestnanec.jmeno', read_only=True)

    class Meta:
        model = FlowUser
        fields = [
            'id',
            'email',
            'visible_overview',
            'aktivni',
            'zamestnanec_id',
            'zamestnanec_jmeno',
            'vytvoreno',
        ]


class FlowCreateSerializer(serializers.Serializer):
    zamestnanec_id = serializers.IntegerField()
    email = serializers.EmailField()
    visible_overview = serializers.BooleanField(required=False, default=False)


class FlowPatchSerializer(serializers.Serializer):
    visible_overview = serializers.BooleanField(required=False)
    aktivni = serializers.BooleanField(required=False)


class FlowLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()


class FlowChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField()

    def validate_new_password(self, value):
        if not heslo_je_platne(value):
            raise serializers.ValidationError(
                'Heslo musí mít alespoň 8 znaků, jedno písmeno a jedno číslo.'
            )
        return value
