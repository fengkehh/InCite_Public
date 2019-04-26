from django.urls import include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

"""InCiteDev URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

urlpatterns = [
    #path('admin/', admin.site.urls),
    #path('', RedirectView.as_view(url = '/InCiteApp/')),
    path('InCiteApp/', include('InCiteApp.urls')),
    path('InCiteApp/accounts/', include('django.contrib.auth.urls')),
    path('InCiteApp/accounts/login', auth_views.login, name='login'),
    path('InCiteApp/accounts/logout', auth_views.logout, name='logout')
]

urlpatterns += static(settings.STATIC_URL, document_root = settings.STATIC_ROOT) # static content like images & css
