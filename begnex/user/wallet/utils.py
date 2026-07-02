from decimal import Decimal

from django.db import transaction

from .models import Wallet, WalletTransaction


def get_user_wallet(user):
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def refund_to_wallet(user, amount, description):
    amount = Decimal(str(amount))
    if amount <= 0:
        return None
    wallet = get_user_wallet(user)
    wallet.balance += amount
    wallet.save()

    return WalletTransaction.objects.create(
        wallet=wallet, amount=amount, transaction_type="credit", description=description
    )


@transaction.atomic
def pay_using_wallet(user, amount, description):
    amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    wallet = get_user_wallet(user)
    if wallet.balance < amount:
        raise ValueError("Insufficient wallet balance.")

    wallet.balance -= amount
    wallet.save()

    return WalletTransaction.objects.create(
        wallet=wallet, amount=amount, transaction_type="debit", description=description
    )
