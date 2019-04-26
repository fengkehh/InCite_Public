from django.urls import reverse
from django.db import models, transaction
from django_mysql.models import Model
from django_mysql.models import JSONField
from django.core.validators import MinValueValidator
from django.contrib.auth.models import AbstractUser
from app_process import process_nlp

# Create your models here.


# Articles
class Article(Model):
    eid = models.CharField(max_length=255, help_text="Internal SCOPUS key (EID)", primary_key= True)

    issn = models.CharField(max_length=255, help_text='<a href="http://www.issn.org/"'
                                                      '>International Standard Serial Number</a>',
                            null=True)

    title = models.CharField(max_length = 255, help_text="Enter the title of the article", null=False)

    journal = models.CharField(max_length=255, help_text="Enter the name of publishing journal", null=True)

    publish_date = models.DateField(null=True, help_text="Publishing date")

    authors = models.ManyToManyField("Author", through="Written")

    references = models.ManyToManyField("Article", through="Citation")

    # The following are GENERATED.
    citation_impact = models.PositiveIntegerField(null=True, default=0, help_text="Number of articles citing this article.", db_index=True)

    title_length = models.PositiveIntegerField(null=True)

    term_count = JSONField(null=True, help_text="Term count for each non-trivial title term.")

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """
        Returns the url to access a detailed record for this article.
        :return:
        """
        return reverse('article-detail', args = [str(self.eid)])

    # Return the indexed term count or update DB.
    @staticmethod
    def get_term_count(eid):
        # Do this to make sure the read is blocked if object is locked.
        with transaction.atomic():
            article = Article.objects.select_for_update().get(eid=eid)
            my_term_count = article.term_count
        if my_term_count is None:
            my_term_count = process_nlp.update_term_counts(eid, article.title)
        return my_term_count


    # default ordering using citation impact
    class Meta:
        ordering = ['-citation_impact']


# Fake model that is pointing to the indexed article view
class IndexedArticle(Model):
    eid = models.CharField(max_length=255, help_text="Internal SCOPUS key (EID)", primary_key=True)

    title_length = models.PositiveIntegerField(null=True)

    term_count = JSONField(null=True, help_text="Term count for each non-trivial title term.")

    class Meta:
        managed = False
        db_table = 'InCiteApp_indexedarticle'


class OverallTermCounts(Model):
    term = models.CharField(max_length=255, null=False)

    total_count = models.PositiveIntegerField(null=False)


class Author(Model):
    id = models.BigIntegerField(primary_key= True)

    last_name = models.CharField(max_length=255, null=False)

    first_name = models.CharField(max_length=255, null=False)

    middle_name = models.CharField(max_length=255, null=True)

    institutes = models.ManyToManyField("Institute", through = "Affiliation")

    fnDM1 = models.CharField(max_length=255, null=True)
    fnDM2 = models.CharField(max_length=255, null=True)

    lnDM1 = models.CharField(max_length=255, null=True)
    lnDM2 = models.CharField(max_length=255, null=True)

    def __str__(self):
        # midname_str = ''
        # if self.middle_name != "NULL":
        #     midname_str = self.middle_name
        return '{} {}'.format(self.first_name, self.last_name)


class Institute(Model):
    id = models.BigIntegerField(primary_key=True)

    name = models.CharField(max_length=255, null=False)

    country = models.CharField(max_length=255, null=False)

    def __str__(self):
        return '{} ({})'.format(self.name, self.country)


class Written(Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    article = models.ForeignKey(Article, on_delete=models.CASCADE)

    author_order = models.PositiveSmallIntegerField(null = False, validators=[MinValueValidator(1)])

    class Meta:
        unique_together = (("author", "article"),)
        ordering = ['author_order']


class Affiliation(Model):
    author = models.ForeignKey(Author, on_delete = models.CASCADE)

    article = models.ForeignKey(Article, on_delete = models.CASCADE)

    institute = models.ForeignKey(Institute, on_delete = models.CASCADE)

    class Meta:
        unique_together = (('author', 'article', 'institute'),)


class Citation(Model):
    cited_by_article = models.ForeignKey(Article, on_delete = models.CASCADE, null=False, related_name='cited_by_article', db_index=True)

    cites_article = models.ForeignKey(Article, on_delete = models.CASCADE, null=False, related_name='cites_article', db_index=True)

    class Meta:
        unique_together = (("cited_by_article", "cites_article"),)


class CustomUser(AbstractUser):
    interests = models.ManyToManyField(Article, through = "Interest")

    def __str__(self):
        return self.first_name


class Interest(Model):
    user = models.ForeignKey(CustomUser, null = False, on_delete=models.CASCADE)

    article = models.ForeignKey(Article, on_delete=models.CASCADE)