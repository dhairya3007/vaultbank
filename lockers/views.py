from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from .models import Locker, Customer, LockerUser, AccessLog
from .forms import LockerForm, CustomerForm, LockerUserForm, ScanTokenForm


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    total_lockers = Locker.objects.count()
    active_lockers = Locker.objects.filter(is_active=True).count()
    total_customers = Customer.objects.count()
    active_sessions = AccessLog.objects.filter(check_out_time__isnull=True).count()
    recent_logs = AccessLog.objects.select_related('locker', 'customer')[:10]
    unassigned_lockers = Locker.objects.filter(locker_users__isnull=True, is_active=True).count()

    context = {
        'total_lockers': total_lockers,
        'active_lockers': active_lockers,
        'total_customers': total_customers,
        'active_sessions': active_sessions,
        'recent_logs': recent_logs,
        'unassigned_lockers': unassigned_lockers,
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
                AccessLog.objects.create(locker=locker, customer=customer)
                checked_in.append(customer.name)

            if checked_in:
                names = ', '.join(checked_in)
                messages.success(request, f"Entry processed for: {names} — Locker #{locker.locker_number}.")
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
            AccessLog.objects.create(locker=locker, customer=customer)
            messages.success(request, f"✅ {customer.name} checked into Locker #{locker.locker_number}.")
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


# ─── Custom Error Handlers ────────────────────────────────────────────────────

def error_404(request, exception=None):
    """Custom 404 Not Found handler."""
    return render(request, 'lockers/error_404.html', status=404)


def error_500(request):
    """Custom 500 Internal Server Error handler."""
    return render(request, 'lockers/error_500.html', status=500)
