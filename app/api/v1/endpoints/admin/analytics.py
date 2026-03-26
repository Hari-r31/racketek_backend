"""
Admin analytics – revenue charts, sales reports, CSV export
"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta
import csv
import io

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.models.order import Order, OrderItem
from app.enums import OrderStatus
from app.models.product import Product
from app.models.category import Category

router = APIRouter()


@router.get("/revenue")
def revenue_analytics(
    days: int = Query(30, ge=7, le=365),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Daily revenue for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(
        func.date(Order.created_at).label("date"),
        func.sum(Order.total_amount).label("revenue"),
        func.count(Order.id).label("orders"),
    ).filter(
        Order.created_at >= since,
        Order.status.in_([
            OrderStatus.paid, OrderStatus.processing,
            OrderStatus.shipped, OrderStatus.delivered,
        ])
    ).group_by(func.date(Order.created_at)).order_by(func.date(Order.created_at)).all()

    return [{"date": str(r.date), "revenue": round(r.revenue or 0, 2), "orders": r.orders} for r in rows]


@router.get("/products")
def product_performance(
    limit: int = 10,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Top performing products by revenue and units sold."""
    rows = db.query(
        OrderItem.product_id,
        OrderItem.product_name,
        func.sum(OrderItem.total_price).label("revenue"),
        func.sum(OrderItem.quantity).label("units"),
    ).group_by(OrderItem.product_id, OrderItem.product_name).order_by(
        func.sum(OrderItem.total_price).desc()
    ).limit(limit).all()

    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "revenue": round(r.revenue or 0, 2),
            "units_sold": r.units or 0,
        }
        for r in rows
    ]


@router.get("/categories")
def category_performance(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Revenue per category."""
    rows = db.query(
        Category.name,
        func.sum(OrderItem.total_price).label("revenue"),
        func.sum(OrderItem.quantity).label("units"),
    ).join(Product, Product.category_id == Category.id
    ).join(OrderItem, OrderItem.product_id == Product.id
    ).group_by(Category.name).order_by(func.sum(OrderItem.total_price).desc()).all()

    return [
        {"category": r.name, "revenue": round(r.revenue or 0, 2), "units": r.units or 0}
        for r in rows
    ]


@router.get("/export/csv")
def export_orders_csv(
    days: int = Query(30, ge=1, le=365),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Export orders as CSV for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)
    orders = db.query(Order).filter(Order.created_at >= since).order_by(Order.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order Number", "Status", "Subtotal", "Discount",
        "Shipping", "Tax", "Total", "Created At"
    ])
    for o in orders:
        writer.writerow([
            o.order_number, o.status.value, o.subtotal, o.discount_amount,
            o.shipping_cost, o.tax_amount, o.total_amount,
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="orders_{days}days.csv"'},
    )


@router.get("/summary")
def analytics_summary(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """High-level stats for the analytics page."""
    total = db.query(func.sum(Order.total_amount)).filter(
        Order.status != OrderStatus.CANCELLED
    ).scalar() or 0
    count = db.query(func.count(Order.id)).scalar() or 0
    avg = total / count if count else 0

    status_breakdown = db.query(
        Order.status, func.count(Order.id)
    ).group_by(Order.status).all()

    return {
        "total_revenue": round(total, 2),
        "total_orders": count,
        "avg_order_value": round(avg, 2),
        "status_breakdown": {s.value: c for s, c in status_breakdown},
    }
