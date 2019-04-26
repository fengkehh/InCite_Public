import MySQLdb, json
from InCiteDev.settings import *
from app_process import process_nlp

db_connection = process_nlp.DB()


# Compute and store citation impact
def cache_citation_impact():
    db_connection.query('CREATE TABLE times_cited ( '
                        'SELECT InCiteApp_citation.cites_article_id AS cited_article, COUNT(*) AS '
                        'times_cited '
                        'FROM InCiteApp_citation '
                        'GROUP BY InCiteApp_citation.cites_article_id '
                        '); '
                        'COMMIT;')

    # Add foreign key constraint to the temp table to speed up lookup.
    db_connection.query(
        'ALTER TABLE times_cited ADD CONSTRAINT FOREIGN KEY (cited_article) REFERENCES '
        'InCiteApp_article(eid); '
        'COMMIT;')

    # Update the citation impact field in article table using the temp table.
    db_connection.query('UPDATE InCiteApp_article '
                        'SET InCiteApp_article.citation_impact = '
                        '( '
                        'SELECT times_cited '
                        'FROM times_cited '
                        'WHERE times_cited.cited_article = InCiteApp_article.eid '
                        '); '
                        'COMMIT;')

    # Set all null citation impacts to 0.
    db_connection.query('UPDATE InCiteApp_article '
                        'SET citation_impact = 0 '
                        'WHERE citation_impact IS NULL; '
                        'COMMIT;')

    # Add an index to the citation impact field in article to speed up sorting.
    db_connection.query('ALTER TABLE InCiteApp_article ADD INDEX (citation_impact);')
    # Drop the temp table.
    db_connection.query('DROP TABLE times_cited;')
    db_connection.query('COMMIT;')


# Execute after article table is fully populated.
def gen_doc_term_counts():
    print('Caching term counts...')
    db_connection.query('SET NAMES utf8mb4')
    db_connection.query("SET CHARACTER SET utf8mb4")
    db_connection.query("SET character_set_connection=utf8mb4")

    counter = 0
    # Iterate through the current article list and generate term count.
    # Only do it for the first TOP_N documents in terms of citation impact!
    cursor = db_connection.query(
        'SELECT eid, title '
        'FROM InCiteApp_article '
        'ORDER BY citation_impact DESC '
        'LIMIT {}'.format(TOP_N))

    rows = cursor.fetchall()
    for row in rows:
        print('Processing {} out of {} total docs'.format(counter + 1, TOP_N))

        # compute processed term counts
        eid, title = row
        # Update overall counts for document frequency
        process_nlp.update_term_counts(eid, title)
        counter += 1


cache_citation_impact()
gen_doc_term_counts()
