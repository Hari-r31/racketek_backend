"""
AI Support Assistant – powered by OpenAI
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import openai

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.order import Order
from app.models.product import Product
from app.core.config import settings

router = APIRouter()


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


SYSTEM_PROMPT = """You are a helpful customer support assistant for Racketek Outlet, 
a sports equipment eCommerce store selling badminton, cricket, running gear, accessories, 
sportswear, and equipment. 

You can help customers with:
- Product recommendations and size guides
- Order status and tracking
- Return and refund policies
- Shipping information
- General product questions

Return Policy: 7-day returns for unused products in original packaging.
Shipping: Free shipping on orders above ₹999. Standard delivery in 5-7 business days.
Payment: Razorpay (cards, UPI, netbanking) and Cash on Delivery available.

Be friendly, concise, and helpful. If you don't know something specific, 
ask the customer to contact support at support@racketek.com."""


@router.post("/chat")
def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not settings.OPENAI_API_KEY:
        return {"reply": "AI assistant is not configured. Please contact support@racketek.com"}

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    # Build context – inject user's recent orders if mentioned
    context = ""
    if any(kw in payload.message.lower() for kw in ["order", "status", "track", "shipment"]):
        recent_orders = db.query(Order).filter(
            Order.user_id == current_user.id
        ).order_by(Order.created_at.desc()).limit(3).all()
        if recent_orders:
            order_info = "\n".join(
                [f"- Order {o.order_number}: {o.status.value}, ₹{o.total_amount}" for o in recent_orders]
            )
            context = f"\n\nCustomer's recent orders:\n{order_info}"

    messages = [{"role": "system", "content": SYSTEM_PROMPT + context}]
    for h in payload.history[-8:]:   # last 8 messages for context window
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": payload.message})

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = "I'm having trouble right now. Please email support@racketek.com for help."

    return {"reply": reply}


@router.get("/recommend/{product_id}")
def ai_recommendations(
    product_id: int,
    db: Session = Depends(get_db),
):
    """Return similar products based on category and tags."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    similar = db.query(Product).filter(
        Product.category_id == product.category_id,
        Product.id != product_id,
        Product.status == "active",
    ).order_by(Product.avg_rating.desc()).limit(6).all()

    return {"recommendations": [{"id": p.id, "name": p.name, "price": p.price, "slug": p.slug} for p in similar]}
