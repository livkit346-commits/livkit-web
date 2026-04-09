from rest_framework import serializers
from .models import User, UserProfile
from django.contrib.auth import authenticate

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ResetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def validate_username(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Username too short")

        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already taken")

        return value

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            username=validated_data['username'],
        )


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(
            email=data["email"],
            password=data["password"]
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if user.role not in ["ADMIN_MAIN", "ADMIN_LIMITED"]:
            raise serializers.ValidationError("Not an admin")

        if user.is_banned:
            raise serializers.ValidationError("Admin account banned")

        return user




class UserProfileNestedSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = (
            'display_name',
            'bio',
            'phone',
            'avatar',
        )

    def get_avatar(self, obj):
        if obj.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None



# 🔹 ADJUST ONLY THIS SERIALIZER
class MeSerializer(serializers.ModelSerializer):
    is_premium = serializers.SerializerMethodField()
    profile = UserProfileNestedSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'role',
            'is_banned',
            'is_premium',
            'date_joined',
            'profile',
        )

    def get_is_premium(self, obj):
        return hasattr(obj, "entitlement") and obj.entitlement.is_active

    def get_is_premium(self, obj):
        return hasattr(obj, "entitlement") and obj.entitlement.is_active


class UserSerializer(serializers.ModelSerializer):
    is_premium = serializers.SerializerMethodField()

    def get_is_premium(self, obj):
        return hasattr(obj, "entitlement") and obj.entitlement.is_active



