from functools import wraps
from django.shortcuts import redirect
from . import services


SUBSCRIPTION_PAGE = 'subscriptions:plans'


def need_base_access(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not services.has_base_access(request.user) and not services.has_advanced_access(request.user):
            return redirect(SUBSCRIPTION_PAGE)
        return func(request, *args, **kwargs)
    return wrapper


def need_advanced_access(func):
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not services.has_advanced_access(request.user):
            return redirect(SUBSCRIPTION_PAGE)
        return func(request, *args, **kwargs)
    return wrapper