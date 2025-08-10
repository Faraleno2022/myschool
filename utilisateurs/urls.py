from django.urls import path
from django.contrib.auth import views as auth_views

app_name = 'utilisateurs'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='utilisateurs/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
]
