"""
Cart endpoints
BUG 2 FIX — Enforce min_order_value when applying coupon to cart
BUG 3 FIX — Re-validate min_order_value when building cart response
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.coupon import Coupon, DiscountType
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartResponse, ApplyCouponRequest
from app.utils.helpers import calculate_shipping, calculate_tax

router = APIRouter()


def _compute_subtotal(cart: Cart) -> float:
    """Compute the subtotal of all active (non-saved) cart items."""
    subtotal = 0.0
    for item in cart.items:
        if item.save_for_later:
            continue
        price = item.product.price
        if item.variant:
            price += item.variant.price_modifier
        subtotal += price * item.quantity
    return subtotal


def _build_cart_response(cart: Cart, db: Session) -> CartResponse:
    """
    Compute cart totals and return CartResponse.
    BUG 3 FIX: Re-validate coupon min_order_value every time the cart is built.
    If the cart drops below the coupon's minimum (e.g. items removed), the coupon
    is automatically detached and discount zeroed.
    """
    subtotal = _compute_subtotal(cart)

    discount_amount = 0.0
    coupon_code = None

    if cart.coupon:
        # BUG 3 FIX: enforce min_order_value dynamically
        if subtotal >= cart.coupon.min_order_value:
            coupon_code = cart.coupon.code
            if cart.coupon.discount_type == DiscountType.PERCENTAGE:
                discount_amount = subtotal * (cart.coupon.discount_value / 100)
                if cart.coupon.max_discount_amount:
                    discount_amount = min(discount_amount, cart.coupon.max_discount_amount)
            else:
                discount_amount = min(cart.coupon.discount_value, subtotal)
            discount_amount = round(discount_amount, 2)
        else:
            # Cart subtotal fell below minimum — silently detach coupon
            cart.coupon_id = None
            db.commit()

    discounted = subtotal - discount_amount
    shipping_cost = calculate_shipping(discounted)
    tax_amount = calculate_tax(discounted)
    total_amount = round(discounted + shipping_cost + tax_amount, 2)

    return CartResponse(
        id=cart.id,
        items=cart.items,
        coupon_code=coupon_code,
        subtotal=subtotal,
        discount_amount=discount_amount,
        shipping_cost=shipping_cost,
        tax_amount=tax_amount,
        total_amount=total_amount,
    )


@router.get("", response_model=CartResponse)
def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return _build_cart_response(cart, db)


@router.post("/items", status_code=201)
def add_to_cart(
    payload: CartItemAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        db.flush()

    existing = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == payload.product_id,
        CartItem.variant_id == payload.variant_id,
    ).first()

    if existing:
        existing.quantity += payload.quantity
        db.commit()
        db.refresh(existing)
        return {"message": "Item added to cart", "item_id": existing.id, "quantity": existing.quantity}
    else:
        item = CartItem(
            cart_id=cart.id,
            product_id=payload.product_id,
            variant_id=payload.variant_id,
            quantity=payload.quantity,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"message": "Item added to cart", "item_id": item.id, "quantity": item.quantity}


@router.put("/items/{item_id}")
def update_cart_item(
    item_id: int,
    payload: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.cart_id == cart.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    if payload.quantity <= 0:
        db.delete(item)
    else:
        item.quantity = payload.quantity
    db.commit()
    return {"message": "Cart updated"}


@router.delete("/items/{item_id}", status_code=204)
def remove_cart_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.cart_id == cart.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()


@router.post("/items/{item_id}/save-for-later")
def save_for_later(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    item = db.query(CartItem).filter(
        CartItem.id == item_id, CartItem.cart_id == cart.id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    item.save_for_later = not item.save_for_later
    db.commit()
    return {"message": "Saved for later" if item.save_for_later else "Moved to cart"}


@router.post("/coupon")
def apply_coupon(
    payload: ApplyCouponRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    BUG 2 FIX: Apply coupon with full validation including min_order_value.
    Previously this endpoint only checked existence/active/expiry/usage_limit
    but SKIPPED the min_order_value check.
    """
    coupon = db.query(Coupon).filter(
        Coupon.code == payload.coupon_code.upper(),
        Coupon.is_active == True,
    ).first()
    if not coupon:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon")
    if coupon.expires_at and coupon.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Coupon has expired")
    if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        raise HTTPException(status_code=400, detail="Coupon usage limit reached")

    # BUG 2 FIX: compute current cart subtotal and validate minimum order value
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")

    subtotal = _compute_subtotal(cart)

    if coupon.min_order_value and subtotal < coupon.min_order_value:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This coupon requires a minimum order value of "
                f"₹{coupon.min_order_value:.2f}. "
                f"Your cart total is ₹{subtotal:.2f}."
            ),
        )

    cart.coupon_id = coupon.id
    db.commit()
    return {"message": "Coupon applied", "code": coupon.code}


@router.delete("/coupon", status_code=204)
def remove_coupon(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if cart:
        cart.coupon_id = None
        db.commit()


@router.delete("", status_code=204)
def clear_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if cart:
        db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()
        cart.coupon_id = None
        db.commit()
