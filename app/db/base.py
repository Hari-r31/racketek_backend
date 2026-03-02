"""
Import all models here so Alembic can detect them for migrations.
"""
from app.db.base_class import Base  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.product import Product, ProductVariant, ProductImage  # noqa: F401
from app.models.cart import Cart, CartItem  # noqa: F401
from app.models.wishlist import Wishlist  # noqa: F401
from app.models.order import Order, OrderItem  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.shipment import Shipment  # noqa: F401
from app.models.return_request import ReturnRequest  # noqa: F401
from app.models.coupon import Coupon  # noqa: F401
from app.models.review import Review  # noqa: F401
from app.models.support_ticket import SupportTicket  # noqa: F401
from app.models.revenue_log import RevenueLog  # noqa: F401
from app.models.address import Address  # noqa: F401
from app.models.homepage import HomepageContent  # noqa: F401
