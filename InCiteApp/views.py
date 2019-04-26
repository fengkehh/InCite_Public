from django.core.paginator import Paginator
import pickle
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic.detail import SingleObjectMixin
from django.db.models import Sum, Avg, Case, When
from app_process import process_nlp
from InCiteDev import settings

# Related to User Signup Form
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django.shortcuts import render, redirect
from django.views import generic

from django.contrib.auth import get_user_model

from .forms import ArticleSearchForm
from .models import Article, Author, Affiliation, Institute, Citation, Interest, IndexedArticle, Written

class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=False, help_text='Optional.')
    last_name = forms.CharField(max_length=30, required=False, help_text='Optional.')
    email = forms.EmailField(max_length=254, help_text='Required. Inform a valid email address.')

    class Meta:
        # model = User
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2', )

def signup(request):
    if request.method == 'POST':
        # form = UserCreationForm(request.POST)
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('index')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})    


# Helper function to get BM25 parameters.
def get_bm25_params():
    corpus = IndexedArticle.objects.all()  # search all articles with non-null term counts.
    total_num_docs = corpus.count()

    total_title_length = corpus.aggregate(Sum('title_length'))['title_length__sum']
    avdl = total_title_length / total_num_docs

    return corpus, avdl, total_num_docs


# Create your views here.
# Overview (homepage)
def index(request):
    """
    View for overview/homepage.
    :param request:
    :return:
    """

    return render(
        request,
        'index.html'
    )


class ArticleListView(generic.ListView):
    model = Article
    paginate_by = settings.NUM_PER_PAGE


class QueryArticleListView(ArticleListView):
    template_name = 'InCiteApp/article_list.html'

    def get_query_from_session(self, request):
        qs = self.model.objects.all()
        query_str = request.session['queryset']
        if query_str is not None:
            qs.query = pickle.loads(query_str.encode())
        self.queryset = qs
        self.object_list = self.get_queryset()

    # This view should ONLY get a GET response when user switches page on an article list.
    def get(self, request, *args, **kwargs):
        self.get_query_from_session(request)
        return self.render_to_response(context=self.get_context_data())

    # This view should ONLY get a POST response when user clicks on the form submit button.
    def post(self, request):
        # Serialize and save queryset into session
        request.session['queryset'] = pickle.dumps(self.get_queryset().query, 0).decode()
        return self.render_to_response(self.get_context_data())


class ArticleDetailView(generic.DetailView):
    model = Article

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Find authors and order them by author order.
        authors = Author.objects.raw('SELECT Author.id, last_name, first_name, middle_name, fnDM1, fnDM2, lnDM1, lnDM2 '
                           'FROM InCiteApp_author AS Author, '
                           '(SELECT * '
                           'FROM InCiteApp_written '
                           "WHERE article_id = %s) AS Written "
                           'WHERE Author.id = Written.author_id '
                           'ORDER BY '
                           ' Written.author_order ASC;', [self.object.pk])
        author_institutes = dict()
        for author in authors:
            his_affiliations = Affiliation.objects.filter(article_id=self.object.pk, author_id=author.id)
            his_institutes = Institute.objects.filter(id__in=his_affiliations.values('institute_id'))
            author_institutes[author.id] = his_institutes

        context['authors'] = authors
        context['author_institutes'] = author_institutes
        return context


class AuthorDetailView(generic.DetailView):
    model = Author

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add in all articles by this Author.
        articles = Article.objects.filter(eid__in=Written.objects.filter(author=self.object.pk) \
                                                     .values('article')).order_by('-publish_date')
        context['articles'] = articles
        context['total_citation'] = articles.aggregate(Sum('citation_impact'))
        context['avg_citation'] = articles.aggregate(Avg('citation_impact'))
        context['num_articles'] = articles.count()
        # Find all institutes associated with the Author
        context['institutes'] = Institute.objects.filter(id__in=Affiliation.objects.filter(author=self.object.pk).values('institute'))
        return context


class RecordInterest(SingleObjectMixin, View):
    """
    Records the current user's interest in an article.
    """
    model = Article

    def post(self, request, *args, **kwargs):
        curr_user = request.user
        if not curr_user.is_authenticated:
            return redirect('login')

        # The article the user is interested in.
        self.object = self.get_object()
        # Record interest.
        obj, created = Interest.objects.get_or_create(user=curr_user, article=self.object)

        return HttpResponseRedirect(reverse('article-detail', kwargs={'pk': self.object.pk}))


class SearchView(QueryArticleListView):
    template_name = 'InCiteApp/article_list.html'

    @staticmethod
    def perform_search(request):
        # Create a form instance and populate it with data from the request
        form = ArticleSearchForm(request.POST)
        # Check if the form is valid:
        if form.is_valid():
            # Dealing with author name search
            first_name = form.cleaned_data['search_author_first_name'].strip()
            # middle_name = form.cleaned_data['search_author_middle_name'].strip()
            last_name = form.cleaned_data['search_author_last_name'].strip()
            searched_author = False
            matched_articles = Article.objects.all()
            if first_name and last_name:
                searched_author = True # searched for full author
                matched_articles = matched_articles.filter(authors__first_name=first_name, authors__last_name=last_name)
            elif first_name: # only searched first name
                matched_articles = matched_articles.filter(authors__first_name=first_name)
            else: # only searched last name
                matched_articles = matched_articles.filter(authors__last_name=last_name)


            # Dealing with title search
            user_search_query = form.cleaned_data['search_title']
            if user_search_query:
                q_dict = process_nlp.standardize_title(user_search_query)[0]  # only need the dict
                rank_scores = list()  # going to hold tuples of the form (rank_score, eid)
                corpus, avdl, total_num_docs = get_bm25_params()  # Statistics of the indexed
                # corpus.
                # Iterate through articles and compute rank score
                if not searched_author:
                    # Didn't search for author. Use the indexed documents as corpus
                    article_scope = corpus  # obviously all articles in the scope would be indexed.
                else:
                    # Use author subsetted documents.
                    article_scope = matched_articles  # articles in the scope might not be
                    # indexed. Double check.
                    update_flag = False  # indicate if any new documents are indexed
                    for article in article_scope.exclude(term_count__isnull=False):
                        update_flag = True
                        process_nlp.update_term_counts(article.eid, article.title)
                    if update_flag:
                        # Update indexed corpus parameters again.
                        corpus, avdl, total_num_docs = get_bm25_params()
                for article in article_scope:
                    # retrieve document dict
                    doc_dict = article.term_count  # no need to use get_term_count() because by
                    # now all articles in scope are indexed.
                    rank_score = process_nlp.bm25(q_dict, doc_dict, article.title_length, avdl,
                                                  total_num_docs)
                    if rank_score > 0:
                        rank_scores.append((rank_score, article.eid))
                # Sort tuples by rank_score in descending order
                rank_scores.sort(key=lambda tup: tup[0], reverse=True)
                eid_list = [x[1] for x in rank_scores]
                # Construct an ordered article queryset based on the position of eid in eid_list
                preserved = Case(*[When(pk=eid, then=pos) for pos, eid in enumerate(eid_list)])
                matched_articles = Article.objects.filter(eid__in=eid_list).order_by(preserved)
            return matched_articles

    def get(self, request, *args, **kwargs):
        pagenum = request.GET.get('page')
        if pagenum is None:
            # Create blank form.
            form = ArticleSearchForm()
            return render(
                request,
                'InCiteApp/search.html',
                context={'form': form}
            )
        else:
            # Search result display on page switch.
            # Read cached query from session to subset queryset.
            return QueryArticleListView.get(self, request, *args, **kwargs)

    def post(self, request):
        matched_articles = SearchView.perform_search(request)
        # Cache queryset by pickling it.
        self.queryset = matched_articles.all()
        self.object_list = self.get_queryset()
        return QueryArticleListView.post(self, request)


class InterestView(QueryArticleListView):

    @staticmethod
    def find_recommendations(selected_eids, curr_user):
        full_user_interests = Interest.objects.filter(user=curr_user)
        # Recommender mode.
        if len(selected_eids) > 0:
            selected_interests = full_user_interests.filter(article__in=selected_eids)
        else:
            # Nothing selected. Use the full interest list.
            selected_interests = full_user_interests

        if selected_interests.count() == 0:
            # Can't push! Shouldn't happen because the button should be hidden.
            print('How did you get here?')
        # Find the articles.
        selected_articles = Article.objects.filter(eid__in=selected_interests.values('article'))

        # Construct aggregated term count as query
        term_count_list = list()
        for article in selected_articles:
            term_count = article.get_term_count(
                str(article.eid))  # Need to use get_term_count in case article
            # is not indexed.
            term_count_list.append(term_count)
        q_dict = process_nlp.aggregate_counts(term_count_list)

        # Iterate through indexed articles and compute rank score
        corpus, avdl, total_num_docs = get_bm25_params()
        # Don't rank articles that are already interested by the user.
        article_scope = corpus.exclude(eid__in=full_user_interests.values('article'))
        rank_scores = list()
        for article in article_scope:
            # retrieve document dict
            doc_dict = article.term_count  # don't need to use get_term_count because
            # articles in
            # scope are guaranteed to be indexed
            rank_score = process_nlp.bm25(q_dict, doc_dict, article.title_length, avdl,
                                          total_num_docs)
            if rank_score > 0:
                rank_scores.append((rank_score, article.eid))

        # Sort tuples by rank_score in descending order
        rank_scores.sort(key=lambda tup: tup[0], reverse=True)
        eid_list = [x[1] for x in rank_scores]
        # Construct an ordered article queryset based on the position of eid in eid_list
        preserved = Case(*[When(pk=eid, then=pos) for pos, eid in enumerate(eid_list)])
        matched_articles = Article.objects.filter(eid__in=eid_list).order_by(preserved)
        return matched_articles

    def get(self, request, *args, **kwargs):
        curr_user = request.user
        if not curr_user.is_authenticated:
            return redirect('login')

        pagenum = request.GET.get('page')
        if pagenum is None:
            interested_articles = curr_user.interests.all()
            # TODO: paginate this?
            return render(
                request,
                'InCiteApp/interest_list.html',
                context={'article_list': interested_articles}
            )
        else:
            # Recommender result display on page switch.
            # Read cached query from session to subset queryset.
            return QueryArticleListView.get(self, request, *args, **kwargs)

    def post(self, request):
        curr_user = request.user
        selected_eids = request.POST.getlist('selected')
        if request.POST.get("delete"):
            # Delete interests.
            Interest.objects.filter(user=curr_user, article__in=selected_eids).delete()
            return redirect('interests')
        elif request.POST.get("recommend"):
            matched_articles = InterestView.find_recommendations(selected_eids, curr_user)
            self.queryset = matched_articles.all()
            self.object_list = self.get_queryset()
        return QueryArticleListView.post(self, request)


def network_json(request, pk):
    # referenced: boolean to indicate if we want articles reference by the start article
    # (ie: left side) or referencing articles (right side)
    def GetTopNodes(start: Article, referenced: bool):
        if referenced:
            # Returns top 3 referenced articles by start
            citation_entries = Citation.objects.filter(cited_by_article=start.eid)
            top = Article.objects.filter(
                eid__in=citation_entries.values('cites_article')).order_by('-citation_impact')[
                   0:settings.MAX_CHILD]
        else:
            # Top 3 articles referencing start
            citation_entries = Citation.objects.filter(cites_article=start.eid)
            top = Article.objects.filter(
                eid__in=citation_entries.values('cited_by_article')).order_by('-citation_impact')[
                   0:settings.MAX_CHILD]

        return top

    # source_article: the article that is being referenced ("source" of knowledge)
    # target_article: the article that is referencing ("target" of knowledge)
    def MakeEdge(source_article: Article, target_article: Article):
        return {"source": source_article.eid, "target": target_article.eid, "strength": 0.5}

    def format_node_strs(node: Article, group: int, level: int):
        string = {"id": node.eid, "group": group, "label": node.title, "value": node.citation_impact, "level": level}
        return string

    # left: include articles referenced by start node in the network
    # right: include articles referencing start node in the network
    def GenNetwork(start_node: Article,
                   curr_nodes: set,
                   curr_edges: list,
                   curr_node_strs: list,
                   level: int,
                   include_left: bool,
                   include_right: bool):
        if level == 0:  # Start node is the original, current article (blue node)
            group = 0
        else:
            if include_left:  # Start node is on the left side of the blue node.
                group = -1
            else:  # right side
                group = 1
        if start_node in curr_nodes:
            # Cyclic reference! Discard node. Do not process.
            return curr_nodes, curr_node_strs, curr_edges
        else:
            curr_nodes.add(start_node)
            curr_node_strs.append(format_node_strs(node=start_node,
                                                   group=group,
                                                   level=level))

            if level < settings.MAX_LV:
                if include_left:
                    top3_cited = GetTopNodes(start_node, referenced=True)
                    # Processing new nodes on the left of current node
                    for node in top3_cited:
                        curr_edges.append(MakeEdge(source_article=node,
                                                   target_article=start_node))
                        curr_nodes, curr_node_strs, curr_edges = GenNetwork(start_node=node,
                                                                            curr_nodes=curr_nodes,
                                                                            curr_edges=curr_edges,
                                                                            curr_node_strs=curr_node_strs,
                                                                            level=level + 1,
                                                                            include_left=True,
                                                                            include_right=False)

                if include_right:
                    top3_citing = GetTopNodes(start_node, referenced=False)
                    # Processing new nodes on the right of current node
                    for node in top3_citing:
                        curr_edges.append(MakeEdge(source_article=start_node,
                                                   target_article=node))
                        curr_nodes, curr_node_strs, curr_edges = GenNetwork(start_node=node,
                                                                            curr_nodes=curr_nodes,
                                                                            curr_edges=curr_edges,
                                                                            curr_node_strs=curr_node_strs,
                                                                            level=level + 1,
                                                                            include_left=False,
                                                                            include_right=True)
                return curr_nodes, curr_node_strs, curr_edges
            else:
                return curr_nodes, curr_node_strs, curr_edges

    # Construct network graph
    target_article = Article.objects.get(eid=pk)
    articles, node_strs, edges = GenNetwork(start_node=target_article,
                                         curr_nodes=set(),
                                         curr_edges=list(),
                                         curr_node_strs=list(),
                                         level=0,
                                         include_left=True,
                                         include_right=True)

    graph = {"nodes": node_strs, "links": edges}
    resp = JsonResponse(graph, safe=False)
    return resp
