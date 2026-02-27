"""
Admin Dashboard – KPIs and summary
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, timedelta

from app.core.dependencies import get_db, require_admin
from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.product import Product
from app.models.revenue_log import RevenueLog

router = APIRouter()


@router.get("")
def dashboard_summary(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return KPIs for the admin dashboard."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.status.in_([OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.SHIPPED,
                          OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED])
    ).scalar() or 0.0

    monthly_revenue = db.query(func.sum(Order.total_amount)).filter(
        Order.created_at >= month_start,
        Order.status.in_([OrderStatus.PAID, OrderStatus.PROCESSING, OrderStatus.SHIPPED,
                          OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED])
    ).scalar() or 0.0

    total_orders = db.query(func.count(Order.id)).scalar() or 0
    monthly_orders = db.query(func.count(Order.id)).filter(
        Order.created_at >= month_start
    ).scalar() or 0

    avg_order_value = (total_revenue / total_orders) if total_orders else 0

    total_users = db.query(func.count(User.id)).scalar() or 0
    total_products = db.query(func.count(Product.id)).scalar() or 0

    low_stock = db.query(Product).filter(
        Product.stock <= Product.low_stock_threshold,
        Product.stock > 0,
    ).count()

    out_of_stock = db.query(Product).filter(Product.stock == 0).count()

    # Monthly revenue chart (last 6 months)
    revenue_chart = []
    for i in range(5, -1, -1):
        d = now - timedelta(days=30 * i)
        m_start = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if d.month == 12:
            m_end = m_start.replace(year=m_start.year + 1, month=1)
        else:
            m_end = m_start.replace(month=m_start.month + 1)
        rev = db.query(func.sum(Order.total_amount)).filter(
            Order.created_at >= m_start,
            Order.created_at < m_end,
            Order.status != OrderStatus.CANCELLED,
        ).scalar() or 0.0
        revenue_chart.append({
            "month": m_start.strftime("%b %Y"),
            "revenue": round(rev, 2),
        })

    # Top 5 products by sold_count
    top_products = db.query(Product).order_by(Product.sold_count.desc()).limit(5).all()

    return {
        "total_revenue": round(total_revenue, 2),
        "monthly_revenue": round(monthly_revenue, 2),
        "total_orders": total_orders,
        "monthly_orders": monthly_orders,
        "avg_order_value": round(avg_order_value, 2),
        "total_users": total_users,
        "total_products": total_products,
        "low_stock_count": low_stock,
        "out_of_stock_count": out_of_stock,
        "revenue_chart": revenue_chart,
        "top_products": [
            {"id": p.id, "name": p.name, "sold_count": p.sold_count, "price": p.price}
            for p in top_products
        ],
    }
