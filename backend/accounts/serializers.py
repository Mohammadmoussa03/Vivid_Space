from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Public shape of a user, as consumed by the frontend AuthContext."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            'id', 'uuid', 'email', 'first_name', 'last_name', 'company',
            'role', 'is_approved', 'full_name', 'date_joined',
        )
        read_only_fields = ('id', 'uuid', 'role', 'is_approved', 'full_name', 'date_joined')


class RegisterSerializer(serializers.ModelSerializer):
    # Declared explicitly so DRF does NOT attach a UniqueValidator — duplicate
    # emails are handled generically in the view (anti-enumeration) and by the
    # DB unique constraint, not by a 400 that would reveal the email exists.
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'company')

    def validate_email(self, value):
        # Normalise only. Uniqueness/existence is handled in the view so the
        # response can't be used to enumerate registered accounts.
        return value.strip().lower()

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        # New accounts start unapproved and pending admin review.
        user = User.objects.create_user(
            password=password,
            is_approved=False,
            role=User.Role.MEMBER,
            **validated_data,
        )
        return user


class LoginSerializer(TokenObtainPairSerializer):
    """Email/password login that also enforces the approval gate and
    returns the serialized user alongside the JWT pair."""

    username_field = User.USERNAME_FIELD

    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_approved and not self.user.is_admin:
            raise serializers.ValidationError(
                {'detail': 'Your account is pending approval. We\'ll email you once it\'s active.'}
            )
        data['user'] = UserSerializer(self.user).data
        return data


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Editable profile fields from the Account page."""

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'company')

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('That email is already in use.')
        return value


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
