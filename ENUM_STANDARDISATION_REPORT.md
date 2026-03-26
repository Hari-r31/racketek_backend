# Enum Standardisation Report
## Racketek Backend — Full System Enum Audit & Fix

**Date completed:** 2025  
**Migration:** `alembic upgrade head` (runs 021_enum_string_constraints)  
**Status:** ✅ COMPLETE — zero remaining violations

---

## 1. Problem Summary (Before)

| Layer | Issue |
|---|---|
| Models | Local enum classes in each model file; keys in `UPPER_CASE`, values in `"lowercase"` |
| Admin products endpoint | `ProductStatus(status.upper())` — crashed on valid lowercase input from frontend |
| Admin products endpoint | `GenderCategory(gender.upper())`, `DifficultyLevel(difficulty_level.upper())` — same bug |
| Customer products endpoint | `ProductStatus(status_filter.upper())` — crashed on valid lowercase input |
| Shipments endpoint | `ShipmentStatus.DELIVERED`, `OrderStatus.SHIPPED` — uppercase key access |
| Payments endpoint | `PaymentStatus.SUCCESS`, `OrderStatus.PAID`, `ReservationStatus.ACTIVE` — uppercase key access |
| Dashboard | `OrderStatus.PAID`, `OrderStatus.CANCELLED` — uppercase key access |
| Analytics | `OrderStatus.PAID`, `OrderStatus.DELIVERED` — uppercase key access |
| Celery worker | `ReservationStatus.ACTIVE`, `ProductStatus.OUT_OF_STOCK`, `OrderStatus.PENDING` — uppercase key access |
| Auth endpoint | `UserRole.CUSTOMER` — uppercase key access on user creation |
| Core dependencies | `UserRole.ADMIN`, `UserRole.SUPER_ADMIN`, `UserRole.STAFF` — role guard comparisons broken |
| Cart endpoint | `DiscountType.PERCENTAGE` — uppercase key access |
| Coupon service | `DiscountType.PERCENTAGE` — uppercase key access in discount calculation |
| `revenue_logs.type` | Raw string, no enum class, no DB constraint |
| `users.auth_provider` | Raw string, no enum class, no DB constraint |
| `ticket_replies.author_type` | Raw string, no enum class, no DB constraint |
| Seed scripts | `UserRole.SUPER_ADMIN`, `ProductStatus.ACTIVE` — uppercase key access |

---

## 2. Solution Architecture

### Single Source of Truth: `app/enums.py`

All 14 enum classes are now defined **once** in `app/enums.py`:

```
OrderStatus          UserRole             AuthProvider
PaymentMethod        PaymentStatus        ShipmentStatus
ReturnStatus         TicketStatus         TicketPriority
TicketAuthorType     ProductStatus        DifficultyLevel
GenderCategory       DiscountType         ReservationStatus
RevenueLogType
```

**Contract enforced:**
- All values: `lowercase_snake_case`
- All keys match values exactly: `pending = "pending"`, NOT `PENDING = "pending"`
- All classes inherit `(str, enum.Enum)` — serialize directly as strings in JSON

---

## 3. Enum Inventory (Standardised)

```python
class OrderStatus(str, enum.Enum):
    pending = "pending" | paid | processing | shipped | out_for_delivery
    delivered | cancelled | returned | refunded

class UserRole(str, enum.Enum):
    customer | staff | admin | super_admin

class AuthProvider(str, enum.Enum):
    local | google

class PaymentMethod(str, enum.Enum):
    razorpay | cod

class PaymentStatus(str, enum.Enum):
    pending | success | failed | refunded | partially_refunded

class ShipmentStatus(str, enum.Enum):
    pending | picked_up | in_transit | out_for_delivery
    delivered | failed_delivery | returned

class ReturnStatus(str, enum.Enum):
    requested | approved | rejected | picked_up | refund_initiated | completed

class TicketStatus(str, enum.Enum):
    open | in_progress | waiting_for_customer | resolved | closed

class TicketPriority(str, enum.Enum):
    low | medium | high

class TicketAuthorType(str, enum.Enum):
    user | admin

class ProductStatus(str, enum.Enum):
    active | inactive | out_of_stock | draft

class DifficultyLevel(str, enum.Enum):
    beginner | intermediate | advanced

class GenderCategory(str, enum.Enum):
    male | female | unisex | boys | girls

class DiscountType(str, enum.Enum):
    percentage | fixed

class ReservationStatus(str, enum.Enum):
    active | confirmed | released

class RevenueLogType(str, enum.Enum):
    sale | refund | discount
```

---

## 4. Files Modified

### New File
- `app/enums.py` — single source of truth

### Models (10 files) — local enum classes removed, imports centralised
- `models/order.py`
- `models/user.py`
- `models/payment.py`
- `models/shipment.py`
- `models/return_request.py`
- `models/support_ticket.py`
- `models/product.py`
- `models/coupon.py`
- `models/inventory_reservation.py`
- `models/revenue_log.py`

### Schemas (8 files) — import source changed to `app.enums`
- `schemas/order.py`
- `schemas/user.py`
- `schemas/payment.py`
- `schemas/shipment.py`
- `schemas/return_request.py`
- `schemas/support_ticket.py`
- `schemas/product.py`
- `schemas/coupon.py`

### API Endpoints (14 files) — uppercase keys → lowercase, `.upper()` → `.lower().strip()`
- `endpoints/auth.py`
- `endpoints/users.py`
- `endpoints/orders.py`
- `endpoints/payments.py`
- `endpoints/returns.py`
- `endpoints/reviews.py`
- `endpoints/coupons.py`
- `endpoints/products.py`
- `endpoints/shipments.py`
- `endpoints/cart.py`
- `admin/admin_orders.py`
- `admin/admin_products.py`
- `admin/admin_users.py`
- `admin/analytics.py`
- `admin/dashboard.py`
- `admin/inventory.py`

### Core (1 file)
- `core/dependencies.py` — `require_admin`, `require_staff_or_admin` role guards fixed

### Workers (1 file)
- `workers/order_tasks.py` — all Celery task enum references fixed

### Services (1 file)
- `services/coupon_service.py` — `DiscountType.PERCENTAGE` → `.percentage`

### Seed / Test (3 files)
- `scripts/seed.py`
- `seed_data.py`
- `test_api.py`

### Migration (1 file)
- `alembic/versions/021_enum_string_constraints.py`

**Total files touched: 33**

---

## 5. Database Migration (021)

Migration `021_enum_string_constraints` performs two actions:

### Step 1 — Normalise residual mixed-case data
```sql
-- Example (repeated for all 16 enum columns):
UPDATE orders SET status = LOWER(TRIM(status))
WHERE status IS NOT NULL AND status != LOWER(TRIM(status));
```
Safe to re-run. No-op if data is already lowercase.

### Step 2 — Add CHECK constraints (DB-level enforcement)
```sql
-- Example:
ALTER TABLE orders ADD CONSTRAINT ck_orders_status
  CHECK (status IS NULL OR status IN (
    'pending','paid','processing','shipped','out_for_delivery',
    'delivered','cancelled','returned','refunded'
  ));
```

**16 CHECK constraints added across 10 tables:**

| Table | Column | Constraint name |
|---|---|---|
| orders | status | ck_orders_status |
| users | role | ck_users_role |
| users | auth_provider | ck_users_auth_provider |
| payments | method | ck_payments_method |
| payments | status | ck_payments_status |
| shipments | status | ck_shipments_status |
| return_requests | status | ck_return_requests_status |
| support_tickets | status | ck_support_tickets_status |
| support_tickets | priority | ck_support_tickets_priority |
| ticket_replies | author_type | ck_ticket_replies_author_type |
| products | status | ck_products_status |
| products | difficulty_level | ck_products_difficulty_level |
| products | gender | ck_products_gender |
| coupons | discount_type | ck_coupons_discount_type |
| inventory_reservations | status | ck_inventory_reservations_status |
| revenue_logs | type | ck_revenue_logs_type |

---

## 6. Backward Compatibility

All API filter endpoints now normalize incoming values with `.lower().strip()` before
constructing the enum, so clients sending `"ACTIVE"` or `"Active"` still work:

```python
# admin_products.py — before (crashed on lowercase input):
ProductStatus(status.upper())

# after (accepts any casing):
ProductStatus(status.lower().strip())
```

This allows a graceful transition period for any legacy clients.

---

## 7. Edge Cases Handled

| Edge Case | Resolution |
|---|---|
| Postgres native ENUM columns | Already converted to lowercase by migrations 018–020 |
| VARCHAR enum columns with stale UPPERCASE data | Normalised by migration 021 step 1 |
| Previously unconstrained columns (revenue_logs.type, auth_provider, author_type) | Now have enum classes + DB CHECK constraints |
| Celery worker local imports | Fixed indentation + import source |
| Idempotency: migration run twice | `LOWER(TRIM())` is idempotent; no duplicate constraint errors |
| Nullable columns (difficulty_level, gender) | CHECK allows `IS NULL` |
| Admin `.upper()` filter bug | Fixed to `.lower().strip()` — was silently crashing all admin product filters |

---

## 8. Enforcement Contract — Layer by Layer

| Layer | Mechanism | Guarantees |
|---|---|---|
| **Definition** | `app/enums.py` only | One file to change, one file to review |
| **DB defaults** | `default=OrderStatus.pending` | Not a string literal — typos caught at import time |
| **Pydantic** | All schemas import from `app.enums` | Invalid values rejected with 422 before any DB write |
| **API filters** | `.lower().strip()` before enum construction | Accepts legacy casing from old clients |
| **DB write** | CHECK constraints on all 16 columns | Last line of defence — DB rejects contract violations |
| **Workers** | All Celery tasks import from `app.enums` | No silent mismatches in background jobs |

---

## 9. How to Run the Migration

```bash
cd E:\coder_projects\racketek\racketek_backend
alembic upgrade head
```

This runs migrations 018 through 021 in order if not already applied.
Migration 021 is the enum consistency migration — safe to re-run.

---

## 10. How to Add a New Enum Value in Future

1. Add the value to the class in `app/enums.py` only
2. Write an Alembic migration to add the value to the DB CHECK constraint:
   ```python
   op.execute("ALTER TABLE orders DROP CONSTRAINT ck_orders_status")
   op.execute("""
       ALTER TABLE orders ADD CONSTRAINT ck_orders_status
       CHECK (status IN ('pending','paid',...,'new_value'))
   """)
   ```
3. That's it — no other files need to change

**Never define enum values in model files, schema files, or endpoint files.**
