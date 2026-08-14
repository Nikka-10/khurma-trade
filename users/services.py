from .email_sender import send_verification_code
from .models import OTPCode, User
from django.shortcuts import get_object_or_404
from django.contrib.auth.base_user import AbstractBaseUser


def send_otp_code(user: AbstractBaseUser, user_email: str):
    otp, plain_code = OTPCode.generate_for(user)
    send_verification_code(user.email, plain_code)


def get_user(user_id):
    return get_object_or_404(User, id=user_id)


def get_otp_obj(user: AbstractBaseUser, code: str):
    return (OTPCode.objects
               .filter(user=user, code=code, is_used=False)
               .order_by('-created_at')
               .first())


def verify_otp_code(user: AbstractBaseUser, code: str):
    import hashlib
    code_hash = hashlib.sha256(code.encode()).hexdigest()

    otp = (OTPCode.objects
           .filter(user=user, code_hash=code_hash, is_used=False)
           .order_by('-created_at')
           .first())

    if not otp:
        return False, 'Invalid code.'
    if otp.is_expired:
        return False, 'Code expired.'

    otp.is_used = True
    otp.save()
    return True, None


def toggle_2fa(user: AbstractBaseUser):
    enabled = True

    if user.two_fa_enabled:
        user.two_fa_enabled = False
        user.save()
    else:
        send_otp_code(user, user.email)
        enabled = False

    return enabled


def delete_expired_otp_codes():
    from django.utils import timezone
    from datetime import timedelta
    from .models import OTPCode

    expiry_time = timezone.now() - timedelta(minutes=10)
    deleted, _ = OTPCode.objects.filter(
        created_at__lt=expiry_time
    ).delete()
    return deleted

