from django.urls import path
from . import views
from .views import upload_image, analysis_page, update_profile, record, main

app_name = "user"

urlpatterns = [
    path('upload/', upload_image, name='upload_image'),
    path('analysis/', analysis_page, name='analysis_page'),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("signup/", views.signup_view, name="signup"),
    path('update_profile/', update_profile, name='update_profile'),
    path('record/', record, name='record'),
    path('main/', main, name='main')
]