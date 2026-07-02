from .models import Cart


def cart_count(request):
    count = 0
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user).first()
        if cart:
            count = cart.items.count()
    else:
        session_id = request.session.session_key
        if session_id:
            cart = Cart.objects.filter(session_id=session_id).first()
            if cart:
                count = cart.items.count()
    return {"cart_count": count}
