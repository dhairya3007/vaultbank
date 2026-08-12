# Secure Locker Access System – Django MVP (Multi-Locker Support)

## Overview
A bank-grade Django web application that manages secure lockers with multi-customer support.
A single customer can be assigned to multiple lockers; each locker supports 1–3 customers.
Managers scan QR/token codes, select the customer, and process check-in/check-out.

---

## Proposed Changes

### Project Structure
```
banking managment/
├── venv/bank/                    ← virtual environment
├── locker_system/                ← Django project root
│   ├── manage.py
│   ├── locker_system/            ← project config package
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── lockers/                  ← main Django app
│       ├── models.py             ← Locker, Customer, LockerUser, AccessLog
│       ├── views.py              ← all view logic
│       ├── urls.py
│       ├── admin.py
│       ├── forms.py
│       └── templates/lockers/
│           ├── base.html
│           ├── dashboard.html
│           ├── locker_detail.html
│           ├── locker_list.html
│           ├── customer_list.html
│           ├── customer_detail.html
│           ├── access_log.html
│           └── scan_token.html
├── static/
│   ├── css/
│   │   ├── style.css             ← main styles (dark glassmorphism theme)
│   │   └── responsive.css        ← media queries ONLY
│   └── js/
│       └── main.js               ← QR scan / UI interactions
├── media/                        ← uploaded ID proof files
└── README.md
```

---

### Models (`lockers/models.py`)
| Model | Fields | Notes |
|---|---|---|
| `Locker` | id, locker_number (unique), token (unique), is_active | Token used for QR/scan |
| `Customer` | id, name, id_proof_type, id_proof_file | FileField for ID upload |
| `LockerUser` | locker (FK), customer (FK), unique_together | Join table; max 3 per locker |
| `AccessLog` | id, locker (FK), customer (FK), check_in_time, check_out_time (null) | Tracks sessions |

### Business Rules
- `LockerUser.save()` → reject if locker already has ≥ 3 customers
- `LockerUser` has `unique_together = ('locker', 'customer')`
- Check-in requires selecting one customer from the locker's linked users
- If no users linked → block check-in

### Views
| View | URL | Function |
|---|---|---|
| Dashboard | `/` | Stats overview |
| Locker List | `/lockers/` | All lockers with status |
| Locker Detail | `/lockers/<id>/` | Customers, check-in panel |
| Scan Token | `/scan/` | POST token → redirect to locker detail |
| Customer List | `/customers/` | All customers |
| Customer Detail | `/customers/<id>/` | Lockers assigned, logs |
| Access Log | `/logs/` | All check-in/out history |
| Check-In | `/checkin/` | POST: locker + customer |
| Check-Out | `/checkout/<log_id>/` | POST: close log entry |
| Add Customer to Locker | `/lockers/<id>/add-user/` | POST with validation |

### Frontend Theme
- Dark glassmorphism design with cyan/teal accent colors
- Google Font: **Inter**
- `style.css` → layout, components, typography, animations
- `responsive.css` → **only** `@media` queries for mobile/tablet breakpoints

---

## Verification Plan
1. Run migrations and check DB schema
2. Create test data via admin
3. Test check-in flow with valid token
4. Test rejection of 4th customer assignment
5. Test duplicate customer-locker assignment rejection
6. Verify responsive layout on mobile viewport
