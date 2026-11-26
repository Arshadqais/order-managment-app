from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from .forms import ComplaintForm, CompletionForm, HistoryFilter, ModeForm
from .models import ComplaintPhoto, RateBucket, Ticket


def rate_limited(request, scope, limit, minutes):
    now = timezone.now()
    interval = minutes * 60
    window = int(now.timestamp()) // interval
    address = request.META.get("REMOTE_ADDR", "unknown")
    key = salted_hmac("support.rate", f"{scope}:{address}:{window}").hexdigest()
    with transaction.atomic():
        RateBucket.objects.filter(expires_at__lte=now).delete()
        RateBucket.objects.get_or_create(
            key=key, defaults={"expires_at": now + timedelta(seconds=interval)}
        )
        RateBucket.objects.filter(key=key).update(hits=F("hits") + 1)
        return RateBucket.objects.get(key=key).hits > limit


@never_cache
@require_http_methods(["GET", "POST"])
def complaint(request):
    form = ComplaintForm()
    if request.method == "POST":
        if rate_limited(request, "complaint", 20, 10):
            return HttpResponse("Too many requests. Please try again in a few minutes.", status=429)
        form = ComplaintForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                ticket = form.save()
                if photo := form.cleaned_data["photo"]:
                    ComplaintPhoto.objects.create(ticket=ticket, image=photo)
            messages.success(request, f"Complaint submitted. Your reference is #{ticket.pk}.")
            return redirect("complaint")
    return render(request, "complaint.html", {"form": form})


class PortalLogin(LoginView):
    template_name = "login.html"
    admin_portal = False

    def post(self, request, *args, **kwargs):
        if rate_limited(request, "login", 15, 10):
            return HttpResponse("Too many sign-in attempts. Please try again later.", status=429)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        if form.get_user().is_staff != self.admin_portal:
            form.add_error(None, "These credentials are invalid for this portal.")
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("queue")


@never_cache
@login_required(login_url="employee-login")
def queue(request):
    history = request.GET.get("view") == "history"
    tickets = Ticket.objects.select_related("completed_by")
    filters = HistoryFilter(request.GET if history and request.user.is_staff else None)
    if history:
        tickets = tickets.filter(completed_at__isnull=False).order_by("-completed_at")
        if not request.user.is_staff:
            tickets = tickets.filter(completed_by=request.user)
        elif filters.is_valid():
            data = filters.cleaned_data
            if data["employee"]:
                tickets = tickets.filter(completed_by__username__icontains=data["employee"])
            if data["start"]:
                tickets = tickets.filter(completed_at__date__gte=data["start"])
            if data["end"]:
                tickets = tickets.filter(completed_at__date__lte=data["end"])
    else:
        tickets = tickets.filter(completed_at__isnull=True)
    page = Paginator(tickets, 20).get_page(request.GET.get("page"))
    return render(request, "queue.html", {"page": page, "history": history, "filters": filters})


def visible_tickets(user):
    tickets = Ticket.objects.all()
    if not user.is_staff:
        tickets = tickets.filter(Q(completed_at__isnull=True) | Q(completed_by=user))
    return tickets


@never_cache
@login_required(login_url="employee-login")
@require_safe
def complaint_photo(request, pk):
    photo = get_object_or_404(
        ComplaintPhoto, ticket_id=pk, ticket__in=visible_tickets(request.user)
    )
    return HttpResponse(photo.image, content_type="image/jpeg")


@never_cache
@login_required(login_url="employee-login")
@require_http_methods(["GET", "POST"])
def ticket_detail(request, pk):
    ticket = get_object_or_404(visible_tickets(request.user).select_related("completed_by"), pk=pk)
    open_ticket = Ticket.objects.filter(pk=pk, completed_at__isnull=True)
    mode_form = ModeForm(initial={"mode": ticket.mode})
    completion_form = CompletionForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "route" and request.user.is_staff:
            mode_form = ModeForm(request.POST)
            if mode_form.is_valid():
                updated = open_ticket.update(mode=mode_form.cleaned_data["mode"])
                return action_result(request, pk, updated, "Service type updated.")
        elif action == "complete" and not request.user.is_staff:
            completion_form = CompletionForm(request.POST)
            if completion_form.is_valid():
                updated = open_ticket.exclude(mode="").update(
                    completed_at=timezone.now(), completed_by=request.user,
                    resolution=completion_form.cleaned_data["resolution"],
                    sms_status=Ticket.SmsStatus.QUEUED,
                )
                return action_result(request, pk, updated, "Work recorded.")
        else:
            return HttpResponse(status=403)
    return render(request, "detail.html", {
        "ticket": ticket, "mode_form": mode_form, "completion_form": completion_form,
        "has_photo": ComplaintPhoto.objects.filter(ticket=ticket).exists(),
    })


def action_result(request, pk, updated, success):
    if updated:
        messages.success(request, success)
        return redirect("ticket", pk=pk)
    messages.error(request, "This ticket changed or still needs a service type. Check the queue.")
    return redirect("queue")
