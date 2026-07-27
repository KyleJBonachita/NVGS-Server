from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "display_name",
            "department",
            "role",
        ]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        trim_whitespace=False,
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        request = self.context.get("request")
        email = attrs["email"].strip().lower()
        user = authenticate(request=request, email=email, password=attrs["password"])
        if user is None or not user.is_active:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=150, allow_blank=False)
    last_name = serializers.CharField(max_length=150, allow_blank=False)
    department = serializers.CharField(
        max_length=120,
        allow_blank=True,
        required=False,
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "department"]

    def validate(self, attrs):
        user = self.instance
        for field_name, value in attrs.items():
            setattr(user, field_name, value.strip())
        user.full_clean()
        return attrs

    def update(self, instance, validated_data):
        for field_name, value in validated_data.items():
            setattr(instance, field_name, value.strip())
        instance.save(update_fields=list(validated_data))
        return instance
