import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Address


def _validate_address_data(data):
    """Validate address form fields. Returns a dict of field -> error message."""
    errors = {}

    name = data.get("name", "").strip()
    if not name:
        errors["name"] = "Full name is required."
    elif not re.match(r"^[A-Za-z\s]{2,100}$", name):
        errors["name"] = "Name must be 2–100 letters and spaces only."

    phone = data.get("phone_number", "").strip()
    if not phone:
        errors["phone_number"] = "Phone number is required."
    elif not re.match(r"^\d{10}$", phone):
        errors["phone_number"] = "Enter a valid 10-digit phone number."

    addr1 = data.get("address_line_1", "").strip()
    if not addr1:
        errors["address_line_1"] = "Address line 1 is required."
    elif len(addr1) < 5:
        errors["address_line_1"] = "Address line 1 must be at least 5 characters."
    elif not re.match(r"^[A-Za-z0-9\s,.\/\-#&'()]{5,255}$", addr1):
        errors["address_line_1"] = "Address contains invalid characters."

    city = data.get("city", "").strip()
    if not city:
        errors["city"] = "City is required."
    elif not re.match(r"^[A-Za-z\s]{2,100}$", city):
        errors["city"] = "City must contain letters and spaces only."

    state = data.get("state", "").strip()
    if not state:
        errors["state"] = "State is required."
    elif not re.match(r"^[A-Za-z\s]{2,100}$", state):
        errors["state"] = "State must contain letters and spaces only."

    pincode = data.get("pincode", "").strip()
    if not pincode:
        errors["pincode"] = "Pincode is required."
    elif not re.match(r"^\d{6}$", pincode):
        errors["pincode"] = "Enter a valid 6-digit pincode."

    country = data.get("country", "").strip()
    if not country:
        errors["country"] = "Country is required."
    elif not re.match(r"^[A-Za-z\s]{2,100}$", country):
        errors["country"] = "Country must contain letters and spaces only."

    return errors


def _form_context(address=None, post_data=None, errors=None, next_url=None):
    """
    Build template context with pre-resolved field values.
    Helper to prepare template variables for create/edit.
    """
    d = post_data or {}
    a = address

    return {
        "address": address,
        "errors": errors or {},
        "next_url": next_url,
        # Pre-resolved values — no attribute access on None in template
        "val_name": d.get("name", a.name if a else ""),
        "val_phone": d.get("phone_number", a.phone_number if a else ""),
        "val_addr1": d.get("address_line_1", a.address_line_1 if a else ""),
        "val_addr2": d.get("address_line_2", a.address_line_2 if a else ""),
        "val_city": d.get("city", a.city if a else ""),
        "val_state": d.get("state", a.state if a else ""),
        "val_pincode": d.get("pincode", a.pincode if a else ""),
        "val_country": d.get("country", a.country if a else "India"),
        "val_type": d.get("address_type", a.address_type if a else "Home"),
        "val_default": d.get("is_default") == "on" if post_data else (a.is_default if a else False),
    }


@login_required(login_url="login")
def address_list(request):
    addresses = Address.objects.filter(user=request.user).order_by(
        "-is_default", "-created_at"
    )
    return render(request, "address/address_list.html", {"addresses": addresses})


@login_required(login_url="login")
def add_address(request):
    next_url = request.GET.get("next") or request.POST.get("next")
    if request.method == "POST":
        data = request.POST
        errors = _validate_address_data(data)

        if errors:
            return render(request, "address/address_form.html",
                          _form_context(address=None, post_data=data, errors=errors, next_url=next_url))

        address = Address(
            user=request.user,
            name=data.get("name", "").strip(),
            phone_number=data.get("phone_number", "").strip(),
            address_line_1=data.get("address_line_1", "").strip(),
            address_line_2=data.get("address_line_2", "").strip(),
            city=data.get("city", "").strip(),
            state=data.get("state", "").strip(),
            pincode=data.get("pincode", "").strip(),
            country=data.get("country", "India").strip(),
            address_type=data.get("address_type", "Home"),
            is_default=data.get("is_default") == "on",
        )
        address.save()
        messages.success(request, "Address added successfully!")
        if next_url:
            return redirect(next_url)
        return redirect("address_list")

    return render(request, "address/address_form.html", _form_context(next_url=next_url))


@login_required(login_url="login")
def edit_address(request, id):
    address = get_object_or_404(Address, id=id, user=request.user)
    next_url = request.GET.get("next") or request.POST.get("next")
    if request.method == "POST":
        data = request.POST
        errors = _validate_address_data(data)

        if errors:
            return render(request, "address/address_form.html",
                          _form_context(address=address, post_data=data, errors=errors, next_url=next_url))

        address.name = data.get("name", "").strip()
        address.phone_number = data.get("phone_number", "").strip()
        address.address_line_1 = data.get("address_line_1", "").strip()
        address.address_line_2 = data.get("address_line_2", "").strip()
        address.city = data.get("city", "").strip()
        address.state = data.get("state", "").strip()
        address.pincode = data.get("pincode", "").strip()
        address.country = data.get("country", "India").strip()
        address.address_type = data.get("address_type", "Home")
        address.is_default = data.get("is_default") == "on"

        address.save()
        messages.success(request, "Address updated successfully!")
        if next_url:
            return redirect(next_url)
        return redirect("address_list")

    return render(request, "address/address_form.html", _form_context(address=address, next_url=next_url))


@login_required(login_url="login")
def delete_address(request, id):
    if request.method == "POST":
        address = get_object_or_404(Address, id=id, user=request.user)
        address.delete()
        messages.success(request, "Address deleted successfully!")
    return redirect("address_list")


@login_required(login_url="login")
def set_default_address(request, id):
    if request.method == "POST":
        address = get_object_or_404(Address, id=id, user=request.user)
        Address.objects.filter(user=request.user, is_default=True).exclude(
            pk=id
        ).update(is_default=False)
        address.is_default = True
        address.save()
        messages.success(request, "Default address updated!")
    return redirect("address_list")
