/* Create temporary table that contains citation impacts. */
CREATE TABLE InCiteDB.times_cited (
  SELECT InCiteDB.InCiteApp_citation.cites_article_id AS cited_article, COUNT(*) AS times_cited
  FROM InCiteDB.InCiteApp_citation
  GROUP BY InCiteDB.InCiteApp_citation.cites_article_id
);

/* Add foreign key constraint to the temp table to speed up lookup. */
ALTER TABLE InCiteDB.times_cited ADD CONSTRAINT FOREIGN KEY (cited_article) REFERENCES InCiteDB.InCiteApp_article(eid);

/* Update the citation impact field in article table using the temp table. */
UPDATE InCiteDB.InCiteApp_article
    SET InCiteDB.InCiteApp_article.citation_impact =
    (
    SELECT times_cited
    FROM InCiteDB.times_cited
    WHERE times_cited.cited_article = InCiteDB.InCiteApp_article.eid
    );

/* Set all null citation impacts to 0. */
UPDATE InCiteDB.InCiteApp_article
    SET citation_impact = 0
    WHERE citation_impact IS NULL;

/* Add an index to the citation impact field in article to speed up sorting. */
/* ALTER TABLE InCiteDB.InCiteApp_article ADD INDEX (citation_impact); */

/* Drop the temp table. */
DROP TABLE InCiteDB.times_cited;