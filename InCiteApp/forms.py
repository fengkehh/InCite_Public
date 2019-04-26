from django import forms


class ArticleSearchForm(forms.Form):
    search_title = forms.CharField(max_length=255,
                                   label="Article Title",
                                   required=False)

    search_author_first_name = forms.CharField(max_length=255,
                                         label="Author First Name",
                                         initial="",
                                         required=False)

    # search_author_middle_name = forms.CharField(max_length=255,
    #                                            label="Middle Name (optional)",
    #                                            initial="",
    #                                            required=False)

    search_author_last_name = forms.CharField(max_length=255,
                                               label="Last Name",
                                               initial="",
                                               required=False)
