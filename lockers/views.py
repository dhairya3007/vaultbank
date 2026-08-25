import logging
import ipaddress
import socket
import urllib.request
import urllib.error
import json
import os
from urllib.parse import urlparse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.core.mail import send_mail
from django.core.cache import cache
from django.http import JsonResponse, FileResponse, Http404
from django.conf import settings
from .models import Locker, Customer, LockerUser, AccessLog
from .forms import LockerForm, CustomerForm, LockerUserForm, ScanTokenForm

logger = logging.getLogger(__name__)


# ─── Security helpers ─────────────────────────────────────────────────────────

# Private / link-local / loopback networks — never allowed as API targets (SSRF)
_BLOCKED_NETWORKS = [
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('100.64.0.0/10'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),   # AWS/Azure metadata endpoint
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('198.18.0.0/15'),
    ipaddress.ip_network('198.51.100.0/24'),
    ipaddress.ip_network('203.0.113.0/24'),
    ipaddress.ip_network('224.0.0.0/4'),
    ipaddress.ip_network('240.0.0.0/4'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('fe80::/10'),
]


def _validate_ssrf(url: str) -> None:
    """
    Validate a user-supplied URL against SSRF attacks.
    Raises ValueError with a safe, generic message on any violation.
    Only http:// and https:// are allowed schemes.
    All resolved IP addresses are checked against _BLOCKED_NETWORKS.
    """
    parsed = urlparse(url)

    # 1. Scheme whitelist
    if parsed.scheme not in ('http', 'https'):
        raise ValueError("Only http:// and https:// endpoints are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: no hostname provided.")

    # 2. Block numeric IP literals immediately (before DNS)
    try:
        literal_ip = ipaddress.ip_address(hostname)
        for net in _BLOCKED_NETWORKS:
            if literal_ip in net:
                raise ValueError("Access to private or internal addresses is not permitted.")
    except ValueError as exc:
        if 'not permitted' in str(exc):
            raise
        # hostname is not an IP literal — resolve it below

    # 3. Resolve hostname → IPs and check each resolved address
    try:
        addr_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise ValueError("Could not resolve the hostname. Please check the URL.")

    for _, _, _, _, sockaddr in addr_infos:
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                raise ValueError("Access to private or internal addresses is not permitted.")


def _check_rate_limit(user_id: int, limit: int = 15, window: int = 60) -> bool:
    """
    Simple sliding-window rate limiter using Django's in-process cache.
    Returns True if the request is allowed, False if the user is over limit.
    """
    key = f'rl:api_explorer:{user_id}'
    count = cache.get(key, 0)
    if count >= limit:
        return False
    cache.set(key, count + 1, timeout=window)
    return True


def send_access_notification(customer, locker, log):
    """
    Dispatches automated SMS/WhatsApp and Email security access alerts.
    Message format: 'VaultBank Alert: Locker #A-101 was accessed by John Doe on 14 Aug at 14:15.'
    """
    timestamp = log.check_in_time.strftime('%d %b at %H:%M') if log.check_in_time else timezone.now().strftime('%d %b at %H:%M')
    msg = f"VaultBank Alert: Locker #{locker.locker_number} was accessed by {customer.name} on {timestamp}."
    
    # 1. Log simulated SMS/WhatsApp dispatch
    logger.info(f"[SMS/WhatsApp TO {customer.phone_number or 'Profile'}] {msg}")
    
    # 2. Email dispatch if customer has email configured
    if customer.email:
        try:
            send_mail(
                subject=f"VaultBank Security Alert — Locker #{locker.locker_number}",
                message=msg,
                from_email="security@vaultbank.local",
                recipient_list=[customer.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.warning(f"Could not send email alert: {e}")
            
    return msg


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    lockers = list(Locker.objects.all())
    total_lockers = len(lockers)
    active_lockers = sum(1 for l in lockers if l.is_active)
    total_customers = Customer.objects.count()
    active_sessions = AccessLog.objects.filter(check_out_time__isnull=True).count()
    recent_logs = AccessLog.objects.select_related('locker', 'customer')[:10]
    unassigned_lockers = Locker.objects.filter(locker_users__isnull=True, is_active=True).count()

    expiring_soon_count = sum(1 for l in lockers if l.lease_status == 'expiring_soon')
    overdue_count = sum(1 for l in lockers if l.lease_status == 'overdue')
    active_lease_count = sum(1 for l in lockers if l.lease_status == 'current')
    total_annual_revenue = sum(l.annual_fee for l in lockers)

    context = {
        'total_lockers': total_lockers,
        'active_lockers': active_lockers,
        'total_customers': total_customers,
        'active_sessions': active_sessions,
        'recent_logs': recent_logs,
        'unassigned_lockers': unassigned_lockers,
        'expiring_soon_count': expiring_soon_count,
        'overdue_count': overdue_count,
        'active_lease_count': active_lease_count,
        'total_annual_revenue': total_annual_revenue,
    }
    return render(request, 'lockers/dashboard.html', context)


# ─── Locker Views ─────────────────────────────────────────────────────────────

@login_required
def locker_list(request):
    query = request.GET.get('q', '')
    lockers = Locker.objects.prefetch_related('locker_users__customer')
    if query:
        lockers = lockers.filter(
            Q(locker_number__icontains=query) | Q(token__icontains=query)
        )
    return render(request, 'lockers/locker_list.html', {'lockers': lockers, 'query': query})


@login_required
def locker_detail(request, pk):
    locker = get_object_or_404(Locker, pk=pk)
    customers = locker.get_customers()
    active_log = AccessLog.objects.filter(locker=locker, check_out_time__isnull=True).first()
    logs = AccessLog.objects.filter(locker=locker).select_related('customer')[:20]
    add_form = LockerUserForm(locker=locker)

    context = {
        'locker': locker,
        'customers': customers,
        'active_log': active_log,
        'logs': logs,
        'add_form': add_form,
        'can_add': locker.customer_count < 3,
    }
    return render(request, 'lockers/locker_detail.html', context)


@login_required
def locker_add(request):
    form = LockerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            locker = form.save()
            messages.success(request, f"Locker #{locker.locker_number} created successfully.")
            return redirect('locker_detail', pk=locker.pk)
        except IntegrityError:
            messages.error(request, "A locker with this number already exists. Please use a unique locker number.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred while creating the locker: {e}")
    return render(request, 'lockers/locker_form.html', {'form': form, 'title': 'Add New Locker'})


@login_required
def locker_edit(request, pk):
    locker = get_object_or_404(Locker, pk=pk)
    form = LockerForm(request.POST or None, instance=locker)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, f"Locker #{locker.locker_number} updated.")
            return redirect('locker_detail', pk=locker.pk)
        except IntegrityError:
            messages.error(request, "A locker with this number already exists. Please use a unique locker number.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred while updating the locker: {e}")
    return render(request, 'lockers/locker_form.html', {'form': form, 'title': 'Edit Locker', 'locker': locker})


@login_required
def locker_delete(request, pk):
    locker = get_object_or_404(Locker, pk=pk)
    if request.method == 'POST':
        try:
            locker_number = locker.locker_number
            locker.delete()
            messages.success(request, f"Locker #{locker_number} deleted.")
            return redirect('locker_list')
        except Exception as e:
            messages.error(request, f"Could not delete locker: {e}")
            return redirect('locker_detail', pk=pk)
    return render(request, 'lockers/confirm_delete.html', {'obj': locker, 'type': 'Locker'})


# ─── Customer Views ───────────────────────────────────────────────────────────

@login_required
def customer_list(request):
    query = request.GET.get('q', '')
    customers = Customer.objects.prefetch_related('locker_users__locker')
    if query:
        customers = customers.filter(name__icontains=query)
    return render(request, 'lockers/customer_list.html', {'customers': customers, 'query': query})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    lockers = customer.get_lockers()
    logs = AccessLog.objects.filter(customer=customer).select_related('locker')[:20]
    return render(request, 'lockers/customer_detail.html', {
        'customer': customer,
        'lockers': lockers,
        'logs': logs,
    })


@login_required
def customer_add(request):
    form = CustomerForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            customer = form.save()
            messages.success(request, f"Customer '{customer.name}' added successfully.")
            return redirect('customer_detail', pk=customer.pk)
        except IntegrityError:
            messages.error(request, "A customer with this information already exists.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred while adding the customer: {e}")
    return render(request, 'lockers/customer_form.html', {'form': form, 'title': 'Add New Customer'})


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, request.FILES or None, instance=customer)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, f"Customer '{customer.name}' updated.")
            return redirect('customer_detail', pk=customer.pk)
        except Exception as e:
            messages.error(request, f"An unexpected error occurred while updating the customer: {e}")
    return render(request, 'lockers/customer_form.html', {'form': form, 'title': 'Edit Customer', 'customer': customer})


@login_required
def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        try:
            name = customer.name
            customer.delete()
            messages.success(request, f"Customer '{name}' deleted.")
            return redirect('customer_list')
        except Exception as e:
            messages.error(request, f"Could not delete customer: {e}")
            return redirect('customer_detail', pk=pk)
    return render(request, 'lockers/confirm_delete.html', {'obj': customer, 'type': 'Customer'})


# ─── LockerUser Assignment ─────────────────────────────────────────────────────

@login_required
def add_locker_user(request, pk):
    locker = get_object_or_404(Locker, pk=pk)
    if request.method == 'POST':
        form = LockerUserForm(locker=locker, data=request.POST)
        if form.is_valid():
            customer = form.cleaned_data['customer']
            try:
                # Use objects.create() so locker_id is set on the instance
                # BEFORE save() / full_clean() runs — avoids RelatedObjectDoesNotExist
                lu = LockerUser.objects.create(locker=locker, customer=customer)
                messages.success(request, f"{lu.customer.name} assigned to Locker #{locker.locker_number}.")
            except ValidationError as e:
                msg = e.message if hasattr(e, 'message') else ' '.join(e.messages)
                messages.error(request, msg)
            except IntegrityError:
                messages.error(request, f"{customer.name} is already assigned to this locker.")
            except Exception as e:
                messages.error(request, f"Could not assign customer to locker: {e}")
        else:
            for error in form.errors.values():
                messages.error(request, error.as_text())
    return redirect('locker_detail', pk=pk)


@login_required
def remove_locker_user(request, pk, customer_pk):
    locker = get_object_or_404(Locker, pk=pk)
    lu = get_object_or_404(LockerUser, locker=locker, customer_id=customer_pk)
    if request.method == 'POST':
        try:
            customer_name = lu.customer.name
            lu.delete()
            messages.success(request, f"{customer_name} removed from Locker #{locker.locker_number}.")
        except Exception as e:
            messages.error(request, f"Could not remove customer from locker: {e}")
    return redirect('locker_detail', pk=pk)


# ─── Token Scan & Check-In/Out ────────────────────────────────────────────────

@login_required
def scan_token(request):
    form = ScanTokenForm(request.POST or None)
    error = None

    if request.method == 'POST' and form.is_valid():
        token = form.cleaned_data['token'].strip()
        try:
            locker = Locker.objects.get(token=token)
            if not locker.is_active:
                error = f"Locker #{locker.locker_number} is currently inactive."
            elif locker.customer_count == 0:
                error = f"Locker #{locker.locker_number} has no registered customers."
            else:
                # Redirect to the step-2 check-in page
                return redirect('scan_checkin', pk=locker.pk)
        except Locker.DoesNotExist:
            error = "Invalid token. No locker found with this code."

    return render(request, 'lockers/scan_token.html', {'form': form, 'error': error})


@login_required
def scan_checkin(request, pk):
    """Step 2 of the scan flow: show locker customers with full details,
    allow manager to select 1+ customers and process entry."""
    locker = get_object_or_404(Locker, pk=pk, is_active=True)
    customers = locker.get_customers()

    # Fetch active session for this locker (if any)
    active_log = AccessLog.objects.filter(
        locker=locker, check_out_time__isnull=True
    ).select_related('customer').first()

    if request.method == 'POST':
        selected_ids = request.POST.getlist('customer_ids')   # multi-select
        if not selected_ids:
            messages.error(request, "Please select at least one customer to process entry.")
        else:
            checked_in = []
            for cid in selected_ids:
                customer = get_object_or_404(Customer, pk=cid)
                # Verify authorisation
                if not LockerUser.objects.filter(locker=locker, customer=customer).exists():
                    messages.error(request, f"{customer.name} is not authorised for this locker.")
                    continue
                # Check for existing active session for this customer on this locker
                already = AccessLog.objects.filter(
                    locker=locker, customer=customer, check_out_time__isnull=True
                ).first()
                if already:
                    messages.warning(request, f"{customer.name} is already checked in.")
                    continue
                log = AccessLog.objects.create(locker=locker, customer=customer)
                alert_msg = send_access_notification(customer, locker, log)
                checked_in.append((customer.name, customer.phone_number or customer.email or 'SMS/Profile'))

            if checked_in:
                names = ', '.join([c[0] for c in checked_in])
                messages.success(request, f"Entry processed for: {names} (Locker #{locker.locker_number}). Security alert dispatched.")
            return redirect('scan_checkin', pk=locker.pk)

    # Build set of customer IDs who are currently active in this locker
    active_customer_ids = set(
        AccessLog.objects.filter(locker=locker, check_out_time__isnull=True)
        .values_list('customer_id', flat=True)
    )

    # Enrich customers with display metadata
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    for c in customers:
        c.is_active_now = c.pk in active_customer_ids
        if c.id_proof_file:
            name_lower = c.id_proof_file.name.lower()
            ext = '.' + name_lower.rsplit('.', 1)[-1] if '.' in name_lower else ''
            c.proof_is_image = ext in IMAGE_EXTS
            c.proof_ext = ext.lstrip('.')
        else:
            c.proof_is_image = False
            c.proof_ext = ''

    context = {
        'locker': locker,
        'customers': customers,
        'active_log': active_log,
        'active_customer_ids': active_customer_ids,
    }
    return render(request, 'lockers/scan_checkin.html', context)



@login_required
def check_in(request):
    if request.method == 'POST':
        locker_id = request.POST.get('locker_id')
        customer_id = request.POST.get('customer_id')

        locker = get_object_or_404(Locker, pk=locker_id)
        customer = get_object_or_404(Customer, pk=customer_id)

        # Verify customer belongs to this locker
        if not LockerUser.objects.filter(locker=locker, customer=customer).exists():
            messages.error(request, f"{customer.name} is not authorized for Locker #{locker.locker_number}.")
            return redirect('locker_detail', pk=locker_id)

        # Check if already checked in
        existing = AccessLog.objects.filter(locker=locker, check_out_time__isnull=True).first()
        if existing:
            messages.warning(request, f"Locker #{locker.locker_number} is already occupied by {existing.customer.name}.")
            return redirect('locker_detail', pk=locker_id)

        try:
            log = AccessLog.objects.create(locker=locker, customer=customer)
            alert_msg = send_access_notification(customer, locker, log)
            messages.success(request, f"✅ {customer.name} checked into Locker #{locker.locker_number}. Security alert dispatched: \"{alert_msg}\"")
        except Exception as e:
            messages.error(request, f"Check-in failed: {e}")
        return redirect('locker_detail', pk=locker_id)

    return redirect('scan_token')


@login_required
def check_out(request, log_id):
    log = get_object_or_404(AccessLog, pk=log_id, check_out_time__isnull=True)
    if request.method == 'POST':
        try:
            log.check_out_time = timezone.now()
            log.save()
            messages.success(request, f"✅ {log.customer.name} checked out from Locker #{log.locker.locker_number}.")
        except Exception as e:
            messages.error(request, f"Check-out failed: {e}")
        return redirect('locker_detail', pk=log.locker.pk)
    return redirect('locker_detail', pk=log.locker.pk)


# ─── Access Log View ──────────────────────────────────────────────────────────

@login_required
def access_log(request):
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    logs = AccessLog.objects.select_related('locker', 'customer')

    if query:
        logs = logs.filter(
            Q(customer__name__icontains=query) | Q(locker__locker_number__icontains=query)
        )
    if status == 'active':
        logs = logs.filter(check_out_time__isnull=True)
    elif status == 'closed':
        logs = logs.filter(check_out_time__isnull=False)

    return render(request, 'lockers/access_log.html', {'logs': logs, 'query': query, 'status': status})

# ─── API Explorer (staff-only, SSRF-hardened) ─────────────────────────────────

@user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/login/')
def api_explorer(request):
    """
    Proxies GET requests to an external bank API and returns the JSON
    response as a table-renderable payload.

    Security controls:
      - Staff-only (@user_passes_test is_staff)
      - SSRF protection: blocks private/internal IP ranges & non-http(s) schemes
      - Rate limited: 15 requests per user per 60 seconds
      - Response size capped at 1 MB
      - Internal exception details are logged, never returned to the client
    """
    if request.method == 'POST':
        # --- Rate limiting ---
        if not _check_rate_limit(request.user.pk):
            return JsonResponse(
                {'error': 'Too many requests. Please wait a moment and try again.'},
                status=429
            )

        endpoint = request.POST.get('endpoint', '').strip()
        if not endpoint:
            return JsonResponse({'error': 'Endpoint URL is required.'}, status=400)

        # --- SSRF validation ---
        try:
            _validate_ssrf(endpoint)
        except ValueError as exc:
            logger.warning(
                'API Explorer SSRF attempt blocked | user=%s url=%s reason=%s',
                request.user.username, endpoint, exc
            )
            return JsonResponse({'error': str(exc)}, status=400)

        # --- Fetch with size cap ---
        try:
            req = urllib.request.Request(
                endpoint,
                headers={'Accept': 'application/json', 'User-Agent': 'VaultBank-Explorer/1.0'},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
                # Hard cap: read at most 1 MB; discard the rest
                raw_data = resp.read(1 * 1024 * 1024).decode('utf-8', errors='replace')

            data = json.loads(raw_data)

        except urllib.error.HTTPError as exc:
            logger.info('API Explorer upstream HTTP error | user=%s url=%s status=%s',
                        request.user.username, endpoint, exc.code)
            return JsonResponse(
                {'error': f'The remote API returned an error (HTTP {exc.code}).'},
                status=400
            )
        except urllib.error.URLError as exc:
            logger.info('API Explorer URL error | user=%s url=%s reason=%s',
                        request.user.username, endpoint, exc.reason)
            return JsonResponse(
                {'error': 'Could not reach the endpoint. Check the URL and try again.'},
                status=400
            )
        except json.JSONDecodeError:
            return JsonResponse(
                {'error': 'The remote API did not return valid JSON.'},
                status=400
            )
        except Exception as exc:  # pragma: no cover
            logger.exception('API Explorer unexpected error | user=%s url=%s', request.user.username, endpoint)
            return JsonResponse(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=500
            )

        # --- Normalise response to a list ---
        if not isinstance(data, list):
            if isinstance(data, dict):
                # Common pattern: { "data": [...], "results": [...] }
                for val in data.values():
                    if isinstance(val, list):
                        data = val
                        break
                else:
                    data = [data]
            else:
                data = [data]

        logger.info('API Explorer fetch | user=%s url=%s records=%d',
                    request.user.username, endpoint, len(data))
        return JsonResponse({'success': True, 'data': data})

    return render(request, 'lockers/api_explorer.html')


# ─── Protected Media Serving ──────────────────────────────────────────────────

@login_required
def serve_protected_media(request, path):
    """
    Stream media files (customer ID proofs etc.) only to authenticated users.
    Prevents unauthenticated access to sensitive PII documents.

    Path traversal is mitigated by asserting the resolved path stays within
    MEDIA_ROOT before opening the file.
    """
    media_root = os.path.abspath(str(settings.MEDIA_ROOT))
    # Resolve the full path and guard against traversal (e.g. '../../etc/passwd')
    requested = os.path.abspath(os.path.join(media_root, path))
    if not requested.startswith(media_root + os.sep) and requested != media_root:
        raise Http404
    if not os.path.isfile(requested):
        raise Http404
    return FileResponse(open(requested, 'rb'))  # noqa: WPS515


# ─── Custom Error Handlers ────────────────────────────────────────────────────

def error_404(request, exception=None):
    """Custom 404 Not Found handler."""
    return render(request, 'lockers/error_404.html', status=404)


def error_500(request):
    """Custom 500 Internal Server Error handler."""
    return render(request, 'lockers/error_500.html', status=500)
