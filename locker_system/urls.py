"""
URL configuration for locker_system project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

# Redirect the Django admin login page to our custom app login
# This prevents the double-login issue where /admin/ shows its own login
def _admin_login_redirect(request, **kwargs):
    if request.user.is_authenticated and not request.user.is_staff:
        # Authenticated but not staff — show a clear error on the login page
        from django.contrib import messages as _msg
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden(
            "<h2 style='font-family:sans-serif;padding:2rem;color:#EF4444'>"
            "⛔ Access Denied: Your account does not have admin privileges.</h2>"
        )
    # Not authenticated yet — send to our custom login with ?next pointing at admin
    return redirect(f"/login/?next={request.get_full_path()}")

admin.site.login = _admin_login_redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='lockers/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('lockers.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler404 = 'lockers.views.error_404'
handler500 = 'lockers.views.error_500'
