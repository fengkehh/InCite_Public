/* Importing data from XMLImport */
INSERT INTO InCiteDB.InCiteApp_article(eid, issn, title, journal, publish_date)
    SELECT RawArticle.eid, RawArticle.issn, RawArticle.title, RawSource.title, RawArticle.publishDate
    FROM XMLimport.Article AS RawArticle, XMLimport.Source AS RawSource
    WHERE RawArticle.publicationType = 'Article'
          AND
      RawArticle.sourceID = RawSource.sourceID;

/* Importing Authors */
INSERT INTO InCiteDB.InCiteApp_author(id, first_name, last_name, middle_name)
    SELECT RawAuthor.authorID, RawAuthor.givenName, RawAuthor.surname, RawAuthor.initials
    FROM XMLimport.Author AS RawAuthor;

/* Importing Institutes */
INSERT INTO InCiteDB.InCiteApp_institute(id, name, country)
    SELECT RawInst.affiliationID, RawInst.name, RawInst.country
    FROM XMLimport.Affiliation AS RawInst;

/* Importing Written */
/*Check duplicates first (remove them if found! Leave the entry with the lowest/most significant author order in. */
SELECT RawWritten.articleID, RawWritten.authorID, COUNT(*) AS count
FROM XMLimport.AuthorArticle AS RawWritten
GROUP BY RawWritten.articleID, RawWritten.authorID
HAVING COUNT(*) > 1;
/* Now insert after duplicates are removed. */
INSERT INTO InCiteDB.InCiteApp_written(article_id, author_id, author_order)
    SELECT RawArticle.eid, RawWritten.authorID, RawWritten.attributionSequence
    FROM XMLimport.AuthorArticle AS RawWritten, XMLimport.Article AS RawArticle
    WHERE RawWritten.articleID = RawArticle.articleID AND RawArticle.publicationType = 'Article';

/* Importing Affiliation */
INSERT INTO InCiteDB.InCiteApp_affiliation(article_id, author_id, institute_id)
    SELECT RawArticle.eid, RawAffiliation.authorID, RawAffiliation.affiliationID
    FROM XMLimport.ArticleAuthorAffiliation AS RawAffiliation, XMLimport.Article AS RawArticle
    WHERE RawArticle.articleID = RawAffiliation.articleID
    AND RawArticle.publicationType = 'Article';

/* Importing Citation */
INSERT INTO InCiteDB.InCiteApp_citation(cited_by_article_id, cites_article_id)
    SELECT RawArticle1.eid, RawArticle2.eid
    FROM XMLimport.Citation AS RawCitation, XMLimport.Article AS RawArticle1, XMLimport.Article AS RawArticle2
    WHERE RawCitation.citedByArticleID = RawArticle1.articleID
    AND RawCitation.articleID = RawArticle2.articleID
    AND RawArticle1.publicationType = 'Article'
    AND RawArticle2.publicationType = 'Article';

/* Create View */
CREATE VIEW InCiteApp_indexedarticle AS
  SELECT eid, title_length, term_count
  FROM InCiteApp_article
  WHERE term_count IS NOT NULL;