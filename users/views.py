from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from .forms import UserSignUpForm, UserLoginForm
from django.contrib.auth.decorators import login_required


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
            login(request, user)
            return redirect("tradebook:tradebook")
        return render(request, "users/login.html", {"form":form})
    form = UserLoginForm()
    return render(request, "users/login.html", {"form":form})


@login_required(login_url=login_url)
def log_out(request):
    logout(request)
    return redirect("users:signup")