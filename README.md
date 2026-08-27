# 🏦 VaultBank – Secure Locker Access System

A Django-based bank locker management system supporting multi-customer locker assignments, token-based check-in/check-out, and full access logging.

---

## 🚀 Features

- **Multi-Locker Support**: One customer can be linked to multiple lockers
- **Multi-Customer Lockers**: Each locker supports 1–3 authorized customers
- **Token Scan Check-In**: Managers scan a unique token to load the locker detail page
- **Customer Selection**: Manager must select which customer is accessing the locker
- **Access Logs**: Full audit trail with check-in/out timestamps and duration
- **Business Rule Enforcement**: Max 3 customers/locker; no duplicates (validated at model + form level)
- **Dark Glassmorphism UI**: Inter font, cyan/teal accent, smooth animations
- **Fully Responsive**: Dedicated `responsive.css` for mobile/tablet breakpoints

---

## 🗂️ Project Structure

```
banking managment/
├── bank/                      ← Virtual environment
├── locker_system/             ← Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── lockers/                   ← Main Django app
│   ├── models.py              ← Locker, Customer, LockerUser, AccessLog
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   └── admin.py
├── templates/lockers/         ← All HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── locker_list.html
│   ├── locker_detail.html
│   ├── locker_form.html
│   ├── customer_list.html
│   ├── customer_detail.html
│   ├── customer_form.html
│   ├── scan_token.html
│   ├── access_log.html
│   └── confirm_delete.html
├── static/
│   ├── css/
│   │   ├── style.css          ← Base styles (glassmorphism theme)
│   │   └── responsive.css     ← Media queries ONLY
│   └── js/
│       └── main.js
├── media/                     ← Uploaded ID proof files (auto-created)
├── db.sqlite3                 ← SQLite database (auto-created)
└── README.md
```

---

## 📦 Database Models

| Model | Fields |
|---|---|
| `Locker` | id, locker_number (unique), token (unique), is_active |
| `Customer` | id, name, id_proof_type, id_proof_file |
| `LockerUser` | locker (FK), customer (FK) — unique_together |
| `AccessLog` | id, locker (FK), customer (FK), check_in_time, check_out_time |

**Business Rules enforced at model level:**
- Max **3 customers** per locker (raises `ValidationError` on the 4th)
- **No duplicate** customer–locker pairs (unique_together constraint)
- Check-in blocked if **no customers** are assigned to the locker

---

## ⚙️ Setup & Development Commands

### 1. Create Virtual Environment

```bash
python -m venv bank
```

### 2. Activate Virtual Environment

```bash
# Windows (PowerShell)
bank\Scripts\Activate.ps1

# Windows (CMD)
bank\Scripts\activate.bat

# Linux/macOS
source bank/bin/activate
```

### 3. Install Dependencies

```bash
bank\Scripts\pip install django pillow
```

### 4. Create Django Project

```bash
bank\Scripts\django-admin startproject locker_system .
```

### 5. Create Django App

```bash
bank\Scripts\python manage.py startapp lockers
```

### 6. Apply Database Migrations

```bash
bank\Scripts\python manage.py makemigrations
bank\Scripts\python manage.py migrate
```

### 7. Create Superuser (Admin)

```bash
bank\Scripts\python manage.py createsuperuser
```

> **Default credentials created during setup:**
> - Username: `admin`
> - Password: `admin123`
> - ⚠️ Change these in production!

### 8. Collect Static Files (Production)

```bash
bank\Scripts\python manage.py collectstatic
```

### 9. Run Development Server

```bash
bank\Scripts\python manage.py runserver
```

Visit: **http://127.0.0.1:8000/**

---

## 🌐 URL Routes

| URL | View | Description |
|---|---|---|
| `/` | Dashboard | Stats overview |
| `/login/` | Login | Manager login |
| `/lockers/` | Locker List | All lockers |
| `/lockers/add/` | Add Locker | Create new locker |
| `/lockers/<id>/` | Locker Detail | View/manage locker |
| `/lockers/<id>/edit/` | Edit Locker | Modify locker |
| `/lockers/<id>/delete/` | Delete Locker | Confirm & delete |
| `/lockers/<id>/add-user/` | Assign Customer | Link customer to locker |
| `/lockers/<id>/remove-user/<cid>/` | Remove Customer | Unlink customer |
| `/customers/` | Customer List | All customers |
| `/customers/add/` | Add Customer | Register customer |
| `/customers/<id>/` | Customer Detail | View profile & lockers |
| `/customers/<id>/edit/` | Edit Customer | Modify customer |
| `/customers/<id>/delete/` | Delete Customer | Confirm & delete |
| `/scan/` | Scan Token | Token entry for check-in |
| `/checkin/` | Check-In | Process entry |
| `/checkout/<log_id>/` | Check-Out | Process exit |
| `/logs/` | Access Logs | Full history |
| `/admin/` | Django Admin | Full DB management |

---

## 🎨 Frontend

- **Font**: [Inter](https://fonts.google.com/specimen/Inter) via Google Fonts
- **Theme**: Dark glassmorphism with `#00d4ff` (cyan) accent
- **`static/css/style.css`**: All base styles, components, animations
- **`static/css/responsive.css`**: **Media queries only** (1200px → 360px)
- **`static/js/main.js`**: Sidebar toggle, check-in validation, scan debounce

### Responsive Breakpoints

| Breakpoint | Target |
|---|---|
| `≤ 1200px` | Large tablets, small laptops |
| `≤ 1024px` | Tablets landscape |
| `≤ 768px` | Tablets portrait (sidebar off-canvas) |
| `≤ 480px` | Mobile phones |
| `≤ 360px` | Very small phones |

---

## 🔒 Security Notes (for Production)

- Change `SECRET_KEY` in `settings.py`
- Set `DEBUG = False`
- Set `ALLOWED_HOSTS` to your domain
- Use PostgreSQL instead of SQLite
- Configure proper media file storage (e.g., AWS S3)
- Run `python manage.py collectstatic`

---

## 📝 License

MIT License – For educational/internal banking MVP use.


in this u can see the above nav bar how it looks also when i open sidebar still i can touch bihide that i can scroll it thats the problem 

# This will undo the latest pull and put your code exactly back to how it was before
git reset --hard HEAD@{1}
