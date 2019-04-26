import MySQLdb, json
from InCiteDev.settings import DATABASES
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem.porter import *
from math import log

# normalizer = WordNetLemmatizer()
normalizer = PorterStemmer()
stop_words = set(stopwords.words('english'))


# DB connection
import MySQLdb


class DB:
    conn = None

    def connect(self):
        self.conn = MySQLdb.connect(
            host=DATABASES['default']['HOST'],
            user=DATABASES['default']['USER'],
            passwd=DATABASES['default']['PASSWORD'],
            db=DATABASES['default']['NAME']
        )

    def query(self, sql):
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
        except (AttributeError, MySQLdb.OperationalError):
            self.connect()
            cursor = self.conn.cursor()
            cursor.execute(sql)
        return cursor


db_connection = DB()


# Function to tokenize, stem and perform stopword removal on the title.
# Produce standardized term counts as a dict() and doc length after stopword removal.
# Returns: (term_counts, doc_length)
def standardize_title(title: str):
    title = title.replace('-', ' ') # replace hyphens with space first
    tokens = word_tokenize(title)
    filtered = dict()
    doc_length = 0
    for w in tokens:
        if w.isalpha():
            # w_std = normalizer.lemmatize(w.lower())
            w_std = normalizer.stem(w.lower())
            if w_std not in stop_words:
                if w_std not in filtered.keys():
                    filtered[w_std] = 1
                else:
                    filtered[w_std] = filtered[w_std] + 1
                doc_length = doc_length + 1

    return filtered, doc_length


# Generate BM25 ranking score for a given query and a doc
# Arguments:
# query: a dict storing TF-IDF weights of the query
# doc: a dict storing TF-IDF weights of each doc.
# doc_length: number of non-stopwords in the doc.
# avdl: average doc length (get it from db)
# total_docs: total number of docs (get it from db)
def bm25(query: dict, doc: dict, doc_length: int, avdl: float, total_docs: int, k=1.2, b=0.75):
    score = 0
    for word in query.keys():
        if word in doc.keys():
            # DB query to retrieve document frequency for the term.
            cursor = db_connection.query(
                'SELECT total_count '
                'FROM InCiteApp_overalltermcounts '
                'WHERE term = "{}"'.format(word))
            rows = cursor.fetchall() # Should only return one row, but whatever
            df_word = 0
            for row in rows:
                df_word = max(1, row[0]) # hack to ensure df_word is at least 1 since not all documents were processed.
            # BM25/Okapi
            score += query[word]*(k+1)*doc[word]/(doc[word] + k*(1 - b + b*doc_length/avdl))*log((total_docs + 1)/df_word)
    return score



# Make an aggregated term count dictionary from a given list of term count dictionaries.
def aggregate_counts(term_count_list: list):
    aggregated = dict()
    for term_count in term_count_list:
        for term in term_count:
            if term in aggregated.keys():
                aggregated[term] += term_count[term]
            else:
                aggregated[term] = term_count[term]
    return aggregated


# Just in time update of DB in case user runs into a document that hasn't been processed before.
def update_term_counts(eid: str, title: str):
    # Start transaction and lock article row.
    cursor = db_connection.query('START TRANSACTION;') # Redundant as cursor defaults to transaction mode.
    cursor.execute('SELECT * '
                   'FROM InCiteApp_article '
                   "WHERE eid = '{}' "
                   'FOR UPDATE;'.format(eid))

    term_count, title_length = standardize_title(title)
    # Update per document term_count
    term_count_json = json.dumps(term_count)
    cursor.execute(
        'UPDATE InCiteApp_article '
        'SET term_count = %s, title_length = %s '
        'WHERE eid = %s;', (term_count_json, title_length, eid)
    )
    # Update overall document frequency.
    # prepare statement
    cursor.execute("PREPARE stmt "
                   "FROM 'SELECT COUNT(*) FROM InCiteApp_overalltermcounts WHERE term = ?';")
    for term in term_count.keys():
        cursor.execute('SET @a = "{}";'.format(term))
        cursor.execute('EXECUTE stmt USING @a;')
        term_df_entries = cursor.fetchall()
        for term_df_entry in term_df_entries:  # should be the only term_df entry
            if term_df_entry[0] > 0:
                # term already exists, increment.
                cursor.execute(
                    'UPDATE InCiteApp_overalltermcounts '
                    'SET total_count = total_count + 1 '
                    "WHERE term = '%s';" % term
                )
            else:
                # term doesn't exist. Create.
                cursor.execute(
                    'INSERT INTO InCiteApp_overalltermcounts(term, total_count) VALUES(%s, %s)', (term, 1)
                )
    cursor.execute('COMMIT;')
    return term_count
