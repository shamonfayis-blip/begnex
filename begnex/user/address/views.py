from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Address

@login_required(login_url='login')
def address_list(request):
    addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created_at')
    return render(request, 'address/address_list.html', {'addresses': addresses})

@login_required(login_url='login')
def add_address(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone_number = request.POST.get('phone_number')
        address_line_1 = request.POST.get('address_line_1')
        address_line_2 = request.POST.get('address_line_2')
        city = request.POST.get('city')
        state = request.POST.get('state')
        pincode = request.POST.get('pincode')
        country = request.POST.get('country')
        address_type = request.POST.get('address_type')
        is_default = request.POST.get('is_default') == 'on'
        
        address = Address(
            user=request.user,
            name=name,
            phone_number=phone_number,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            pincode=pincode,
            country=country,
            address_type=address_type,
            is_default=is_default
        )
        address.save()
        messages.success(request, 'Address added successfully!')
        return redirect('address_list')
        
    return render(request, 'address/address_form.html')

@login_required(login_url='login')
def edit_address(request, id):
    address = get_object_or_404(Address, id=id, user=request.user)
    if request.method == 'POST':
        address.name = request.POST.get('name')
        address.phone_number = request.POST.get('phone_number')
        address.address_line_1 = request.POST.get('address_line_1')
        address.address_line_2 = request.POST.get('address_line_2')
        address.city = request.POST.get('city')
        address.state = request.POST.get('state')
        address.pincode = request.POST.get('pincode')
        address.country = request.POST.get('country')
        address.address_type = request.POST.get('address_type')
        address.is_default = request.POST.get('is_default') == 'on'
        
        address.save()
        messages.success(request, 'Address updated successfully!')
        return redirect('address_list')
        
    return render(request, 'address/address_form.html', {'address': address})

@login_required(login_url='login')
def delete_address(request, id):
    if request.method == 'POST':
        address = get_object_or_404(Address, id=id, user=request.user)
        address.delete()
        messages.success(request, 'Address deleted successfully!')
    return redirect('address_list')

@login_required(login_url='login')
def set_default_address(request, id):
    if request.method == 'POST':
        address = get_object_or_404(Address, id=id, user=request.user)
        Address.objects.filter(user=request.user, is_default=True).exclude(pk=id).update(is_default=False)
        address.is_default = True
        address.save()
        messages.success(request, 'Default address updated!')
    return redirect('address_list')
