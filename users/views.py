from django.contrib.auth import login, logout
from django.shortcuts import render, redirect, get_object_or_404

from .forms import UserSignUpForm, UserLoginForm
from django.contrib.auth.decorators import login_required
from . import services

login_url = '/login'


def signup_page(request):
    if request.method == 'POST':
        form = UserSignUpForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("users:login")
        return render(request, "users/signup.html", {"form":form})
    form = UserSignUpForm()
    return render(request, "users/signup.html", {'form':form})


def login_page(request):
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.two_fa_enabled:
                services.send_otp_code(user, user.email)
                request.session['pre_auth_user_id'] = user.id
                return redirect('users:verify_otp')
            login(request, user)
            return redirect('tradebook:tradebook')
        return render(request, 'users/login.html', {'form': form})
    return render(request, 'users/login.html', {'form': UserLoginForm()})


def verify_otp(request):
    user_id = request.session.get('pre_auth_user_id')
    if not user_id:
        return redirect('users:login')

    error = None
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        user = services.get_user(user_id)

        result, error = services.verify_otp_code(user, code)
        if result:
            del request.session['pre_auth_user_id']
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('tradebook:tradebook')

    return render(request, 'users/verify_otp.html', {'error': error})



@login_required(login_url=login_url)
def toggle_2fa(request):
    if request.method == 'POST':
        was_disabled = services.toggle_2fa(request.user)

        if was_disabled :       # already changed on false in services
            return redirect('tradebook:tradebook')
        else:                   # already sent verification code
            request.session['enable_2fa'] = True
            return redirect('users:verify_2fa_setup')


@login_required(login_url=login_url)
def verify_2fa_setup(request):
    if not request.session.get('enable_2fa'):
        return redirect('users:profile')

    error = None
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        result, error = services.verify_otp_code(request.user, code)

        if result:
            request.user.two_fa_enabled = True
            request.user.save()
            del request.session['enable_2fa']
            return redirect('tradebook:tradebook')

    return render(request, 'users/verify_otp.html', {
        'error': error,
        'title': 'Confirm 2FA activation',
    })


def reset_password(request):
    if request.method == 'POST':

        return redirect('users:login')

@login_required(login_url=login_url)
def log_out(request):
    logout(request)
    return redirect("users:signup")