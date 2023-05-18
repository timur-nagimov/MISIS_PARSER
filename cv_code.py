import sqlite3
from threading import Thread
import hashlib
import time
import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup

# Early launch check
class RunControl:
    t = None    # thread
    run = False # thread state
    con = None  # connection db
    cur = None  # cursor

    def start():
        if RunControl.t != None: return 
        RunControl.con = sqlite3.connect("data.db", check_same_thread=False)
        RunControl.cur = RunControl.con.cursor()
        rez = RunControl.cur.execute("SELECT value FROM config WHERE param = 'scan_time'")
        scan_time = int(rez.fetchone()[0])
        if abs(time.time() - scan_time) < 15: return False # anti second starter
        RunControl.t = Thread(target=RunControl.tick)
        RunControl.run = True
        RunControl.t.start()
        return True
    def stop():
        if RunControl.t == None: return
        RunControl.run = False
    def tick():
        while RunControl.run:
            RunControl.cur.execute("UPDATE config SET value = ? WHERE param = 'scan_time'", (int(time.time()),))
            RunControl.con.commit()
            time.sleep(2)

# ВКЛЮЧИТЬ!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#if not RunControl.start(): 
#    exit() # if < 15 sec before last update -> exit


# DataBase operations

def md5(t):
    return hashlib.sha256(t.encode()).hexdigest()

def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def load_data():
    con = sqlite3.connect("data.db")
    con.row_factory = dict_factory
    cur = con.cursor()
    _sci = cur.execute("SELECT * FROM scientists").fetchall()
    sci = ({'id': s['id'], 'scopus_id': s['scopus_id'], 'full_name': s['full_name']} for s in _sci)
    _cfg = cur.execute("SELECT * FROM config").fetchall()
    cfg = {c['param']:c['value'] for c in _cfg}
    return (sci, cfg)

def check_conference(data): # check conf in db by title, pubname and year
    con = sqlite3.connect('data.db')
    cur = con.cursor()
    cur.execute("SELECT id FROM conference WHERE title = :title AND pubname = :pubname AND year = :year", data)
    cid = cur.fetchone()
    return cid[0] if cid != None else None # conference [id] or [None]

def add_conference(data): # add conference to db if it not exists
    cid = check_conference(data)
    if cid != None: return cid
    con = sqlite3.connect('data.db')
    cur = con.cursor()
    cur.execute("INSERT INTO conference (scientist, title, pubname, pages, number, year, doi, cites) VALUES (:scientist, :title, :pubname, :pages, :number, :year, :doi, :cites)", data)
    con.commit()
    cid = cur.lastrowid
    con.close()
    return cid

def add_scimago_if_no_exists(data):
    con = sqlite3.connect('data.db')
    cur = con.cursor()
    cur.execute("SELECT * FROM scimago WHERE conference = :conference AND indx = :index  AND link = :link", data)
    if not cur.fetchone(): 
        cur.execute("INSERT INTO scimago (conference, indx, link) VALUES (:conference, :index, :link)", data)
    con.commit()
    con.close()
    return True

def add_journal_if_no_exists(conf_id, params):
    con = sqlite3.connect('data.db')
    cur = con.cursor()
    cur.execute("DELETE FROM journal WHERE conference = :conf_id", {'conf_id': conf_id})
    for key, value in params.items():
        cur.execute("INSERT INTO journal (conference, key, value) VALUES (:conf_id, :key, :value)", {'conf_id': conf_id, 'key': str(key).strip(), 'value': str(value).strip()})
    con.commit()
    con.close()
    return True

#add_or_update_conference(123, {})
scientists_of_scopus, config = load_data()

# parser coding

class Elsevier(object):
    ___base_uri = "https://api.elsevier.com/content/search/scopus"

    def __init__(self, author_id, api_key, uri=''):
        """Initializes an author given a Scopus author URI or author ID"""
        if uri:
            self.___base_uri = uri
        if not uri and not author_id:
            raise ValueError('No URI or author ID specified')
        if api_key:
            self.___api_key = api_key
        self.author_id = author_id
        resp = requests.get(
            url="{0}?query=AU-ID({1})&field=dc:identifier".format(self.___base_uri, author_id),
            headers={'Accept': 'application/json', 'X-ELS-APIKey': self.___api_key}
        )
        data = resp.json()
        self.article_count = data['search-results']['opensearch:totalResults']
        # print("Получено публикаций в результате поиска: {0}".format(self.___article_count))

        self.articles = []  # init
        for item in data['search-results']['entry']:
            d = {'url': item['prism:url'], 'scopus_id': item['dc:identifier']}
            self.articles.append(d)

    def get_article_info(self, article_url):
        url = (article_url
               + "?field=authors,title,publicationName,volume,issueIdentifier,"
               + "prism:pageRange,coverDate,article-number,prism:doi,citedby-count,prism:aggregationType")
        resp = requests.get(url, headers={'Accept': 'application/json', 'X-ELS-APIKey': self.___api_key})
        if resp.text:
            results = json.loads(resp.text.encode('utf-8'))
            coredata = results['abstracts-retrieval-response']['coredata']

            return {
                # 'authors':', '.join([au['ce:indexed-name'] for au in results['abstracts-retrieval-response']['authors']['author']]),
                'title': coredata['dc:title'],
                'pubname': coredata['prism:publicationName'],
                # 'volume': coredata['prism:volume'],
                'pages': coredata.get('prism:pageRange'),
                'number': coredata.get('article-number'),
                'year': datetime.strptime(coredata['prism:coverDate'], "%Y-%m-%d").year,
                'doi': coredata['prism:doi'] if 'prism:doi' in coredata.keys() else None,
                'cites': int(coredata['citedby-count'])
            }
        else:
            raise ValueError("Request return empty result")

    def print_article_list(self):
        res = []
        for item in self.articles:
            res.append(self.get_article_info(article_url=item['url']))
        # print("Распознано публикаций: {0}".format(len(res)))
        return res


# **************************************************************************
#
#                               EXAMPLE
#
# **************************************************************************

# штучки для инфы о конфе
def convert_to_url(conference_name):
    url_list = conference_name.split()
    correct_name = ""
    for i in url_list:
        correct_name += i + '+'
    return correct_name[:-1]


def scimago_parser(conference_name):
    try:
        link = 'https://www.scimagojr.com/journalsearch.php?q=' + convert_to_url(conference_name)

        r = requests.get(link)
        soup = BeautifulSoup(r.text, 'lxml')
        # ссылка на саму конференцию
        journal_link = 'https://www.scimagojr.com/' + soup.find('div', class_='search_results').find('a').get('href')

        # страничка конференции
        r_j = requests.get(journal_link)
        soup_jr = BeautifulSoup(r_j.text, 'lxml')
        h_index = soup_jr.find('p', class_='hindexnumber').text
        quantile_link = soup_jr.find('img', class_='imgwidget').get('src')
        return { 'index': h_index, 'link': quantile_link }
    except:
        pass
    return None


def journal_searches_parser(conference_name):
    try:
        link_searches = 'https://journalsearches.com/journal.php?title=' + convert_to_url(conference_name)
        r_searches = requests.get(link_searches)
        soup_searches = BeautifulSoup(r_searches.text, 'lxml')
        info_objects = soup_searches.find('div', class_='row row-cols-4').findAll('div', class_='col')
        response = {}
        for info in info_objects:
            key, value = info.text.split(": ")
            response[key] = value
        return response
    except:
        return None

# with dict
for scientist in scientists_of_scopus:
    idx = scientist['id']
    key = scientist['scopus_id']
    value = scientist['full_name']
    print(key, "->", value, "[[ id:", idx, "]]") # scopus_id, full_name, db_id

    e = Elsevier(author_id=key, api_key=config['X-ELS-APIKey'])
    print("/ Объект создан / => ", e.article_count, "шт. <=")

    res = e.print_article_list()
    for item in res: # info about conferences ...
        item['scientist'] = idx # add scientist id to create fullset
        conf_id = add_conference(item) # select or create conference & get id
        print("[ Новый ресурс ]:")
        print("- item = ", item)

        print("- Scimago:")
        scimago = scimago_parser((item['pubname']))
        if scimago:
            scimago['conference'] = conf_id
            add_scimago_if_no_exists(scimago)
        print("! Not found." if not scimago else scimago)

        print("- Journal:")
        journal = journal_searches_parser(item['pubname'])
        if journal:
            add_journal_if_no_exists(conf_id, journal)
        print("! Not found." if not journal else journal)

    print('------------------------------')
