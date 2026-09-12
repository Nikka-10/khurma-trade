import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from . import services
from django.shortcuts import render, redirect
from config import settings
import stripe
from django.urls import reverse


stripe.api_key = settings.STRIPE_TEST_SECRET_KEY
login_url = '/login'


@login_required(login_url=login_url)
def subscription_view(request):
    plans = services.get_plans_from_stripe()
    sub = services.get_subscription(request.user)
    return render(request, 'subscriptions/plans.html', {
        'plans': plans,
        'sub': sub,
        'publishable_key': settings.STRIPE_TEST_PUBLISHABLE_KEY,
    })


@login_required(login_url=login_url)
def checkout_view(request, tier, period):
    plans = services.get_plans_from_stripe()
    if tier not in plans or period not in plans[tier]['prices']:
        return redirect('subscriptions:plans')

    plan = plans[tier]
    price = plan['prices'][period]

    return render(request, 'subscriptions/checkout.html', {
        'tier': tier,
        'period': period,
        'plan': plan,
        'price': price,
        'publishable_key': settings.STRIPE_TEST_PUBLISHABLE_KEY,
    })


@login_required(login_url=login_url)
def need_sub_page(request, tier):
    return render(request, 'subscriptions/need_sub.html', {'tier': tier})


@require_POST
@login_required(login_url=login_url)
def create_subscription(request):
    try:
        data = json.loads(request.body)
        tier = data['tier']
        period = data['period']

        plans = services.get_plans_from_stripe()

        if tier not in plans or period not in plans[tier]['prices']:
            return JsonResponse({'error': 'Invalid plan'}, status=400)

        price_data = plans[tier]['prices'][period]

        customer_id = request.user.stripe_customer_id

        if not customer_id:
            customer = services.create_stripe_customer(request.user)
            customer_id = customer.id

        existing_sub_id = (
            request.user.subscription.stripe_subscription_id
            if hasattr(request.user, 'subscription')
            else None
        )

        if existing_sub_id:
            subscription = services.upgrade_subscription(
                request,
                existing_sub_id,
                tier,
                price_data
            )
            return JsonResponse({
                'checkout_url': request.build_absolute_uri(
                    reverse('subscriptions:payment_success')
                ),
                'subscription_status': subscription.status,
            })

        session = services.create_checkout_session(
            user=request.user,
            customer_id=customer_id,
            price_id=price_data['id'],
            tier=tier,
            success_url=request.build_absolute_uri(
                reverse('subscriptions:payment_success')
            ),
            cancel_url=request.build_absolute_uri(
                reverse('subscriptions:plans')
            ),
        )

        return JsonResponse({
            'checkout_url': session.url,
        })

    except Exception as e:
        print("problem:", e)
        return JsonResponse(
            {'error': 'Something went wrong'},
            status=400
        )



@login_required(login_url=login_url)
def payment_success(request):
    return render(request, 'subscriptions/success.html')


@login_required(login_url=login_url)
@require_POST
def cancel_subscription(request):
    services.cancel_subscription(request.user)
    return redirect('subscriptions:plans')


@login_required(login_url=login_url)
@require_POST
def redeem_promo_code(request):
    code = request.POST.get('code', '').strip()
    success, message = services.redeem_promo_code(request.user, code)
    plans = services.get_plans_from_stripe()
    sub = services.get_subscription(request.user)

    return render(request, 'subscriptions/plans.html', {
        'plans': plans,
        'current_sub': sub,
        'publishable_key': settings.STRIPE_TEST_PUBLISHABLE_KEY,
        'promo_message': message,
        'promo_success': success,
    })



@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    signature = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            settings.DJSTRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return JsonResponse({'error': 'Invalid webhook'}, status=400)

    if not services.mark_webhook_processed(event['id']):
        return JsonResponse({'status': 'already processed'})

    if event['type'] in ('customer.subscription.created',
                         'customer.subscription.updated'):
        services.sync_from_stripe(event['data']['object'])

    elif event['type'] == 'customer.subscription.deleted':
        services.handle_subscription_cancelled(event['data']['object']['id'])

    return JsonResponse({'status': 'ok'})