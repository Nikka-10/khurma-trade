import json
import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from . import services, stripe_services
from .models import SubscriptionTier
from .webhook import dispatch

login_url = '/login'


@login_required(login_url=login_url)
def subscription_view(request):
    return render(request, 'subscriptions/plans.html', {
        'plans': stripe_services.get_plans(),
        'current_sub': services.get_subscription(request.user),
        'publishable_key': settings.STRIPE_TEST_PUBLISHABLE_KEY,
    })


@login_required(login_url=login_url)
def need_sub_page(request, tier):
    return render(request, 'subscriptions/need_sub.html', {'tier': tier})


@login_required(login_url=login_url)
@require_POST
def create_subscription(request):
    try:
        data = json.loads(request.body)
        tier_key, period = data['tier'], data['period']

        plans = stripe_services.get_plans()
        if tier_key not in plans or period not in plans[tier_key]['prices']:
            return JsonResponse({'error': 'Invalid plan'}, status=400)

        tier = SubscriptionTier(tier_key)
        current_sub = services.get_subscription(request.user)

        if services.is_downgrade(current_sub, tier, period):
            return JsonResponse(
                {'error': 'Downgrading is not supported. Cancel your current subscription first if you want a lower plan.'},
                status=400,
            )

        price_data = plans[tier_key]['prices'][period]

        if current_sub and current_sub.stripe_subscription_id and current_sub.is_active:
            stripe_services.upgrade_subscription(
                request.user, current_sub.stripe_subscription_id, price_data['id'], tier_key
            )
            return JsonResponse({
                'checkout_url': request.build_absolute_uri(reverse('subscriptions:payment_success')),
            })

        session = stripe_services.start_checkout(
            user=request.user,
            price_id=price_data['id'],
            tier=tier_key,
            success_url=request.build_absolute_uri(reverse('subscriptions:payment_success')),
            cancel_url=request.build_absolute_uri(reverse('subscriptions:plans')),
        )
        return JsonResponse({'checkout_url': session.url})

    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception:
        return JsonResponse({'error': 'Something went wrong'}, status=400)


@login_required(login_url=login_url)
def payment_success(request):
    return render(request, 'subscriptions/success.html')


@login_required(login_url=login_url)
@require_POST
def cancel_subscription(request):
    sub = services.get_subscription(request.user)
    if sub and sub.stripe_subscription_id:
        stripe_services.request_cancellation(sub.stripe_subscription_id)

    return redirect('subscriptions:plans')


@login_required(login_url=login_url)
@require_POST
def redeem_promo_code(request):
    code = request.POST.get('code', '').strip()
    success, message = services.redeem_promo_code(request.user, code)
    return render(request, 'subscriptions/plans.html', {
        'plans': stripe_services.get_plans(),
        'current_sub': services.get_subscription(request.user),
        'publishable_key': settings.STRIPE_TEST_PUBLISHABLE_KEY,
        'promo_message': message,
        'promo_success': success,
    })


@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        event = stripe_services.verify_webhook_event(
            request.body, request.META.get('HTTP_STRIPE_SIGNATURE')
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return JsonResponse({'error': 'Invalid webhook'}, status=400)

    if not services.mark_webhook_processed(event['id']):
        return JsonResponse({'status': 'already processed'})

    try:
        dispatch(event)
    except Exception:
        return JsonResponse(
            {'error': 'Webhook processing failed'},
            status=500,
        )
    return JsonResponse({'status': 'ok'})