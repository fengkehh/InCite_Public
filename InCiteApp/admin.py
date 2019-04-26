from django.contrib import admin
from .models import CustomUser, Article, Institute, Interest, Author, Citation

# Register your models here.
admin.site.register(CustomUser)
admin.site.register(Interest)
admin.site.register(Article)
admin.site.register(Author)
admin.site.register(Institute)
admin.site.register(Citation)
