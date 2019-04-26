from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('articles', views.ArticleListView.as_view(), name='articles'),
    path('article/<str:pk>', views.ArticleDetailView.as_view(), name='article-detail'),
    path('article-detail/<str:pk>/interest/', views.RecordInterest.as_view(), name='article-interest'),
    path('search/', views.SearchView.as_view(), name='articles-search'),
    path('interests', views.InterestView.as_view(), name='interests'),
    path('api/networkgraph/<str:pk>', views.network_json, name='network-json'),
    # Related to User Signup Form
    path('accounts/signup/', views.signup, name='signup'),
    # Author detail test
    path('author/<int:pk>', views.AuthorDetailView.as_view(), name='author-detail')
]