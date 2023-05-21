from flask import Flask, request, render_template, send_from_directory, redirect
import sqlite3


def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


con = sqlite3.connect('data.db', check_same_thread=False)
con.row_factory = dict_factory
cur = con.cursor()


def get_scientists():
    cur.execute("SELECT * FROM scientists")
    sci_list = {}
    for i in cur.fetchall():
        sci_list[i['id']] = i
    return sci_list


def get_scidata(scientist_id):
    con = sqlite3.connect('data.db', check_same_thread=False)
    con.row_factory = dict_factory
    cur = con.cursor()

    cur.execute("SELECT * FROM conference WHERE scientist = ?", (scientist_id,))
    conf_list = cur.fetchall()

    for conf in conf_list:
        conf['scimago'] = []
        cur.execute("SELECT * FROM scimago WHERE conference = ?", (conf['id'],))
        for scimago in cur.fetchall():
            conf['scimago'].append(scimago)

        conf['journal'] = []
        cur.execute("SELECT * FROM journal WHERE conference = ?", (conf['id'],))
        for journal in cur.fetchall():
            conf['journal'].append(journal)

    con.close()
    return conf_list


def add_scientist(sciid, sciname):
    con = sqlite3.connect('data.db', check_same_thread=False)
    con.row_factory = dict_factory
    cur = con.cursor()
    cur.execute("INSERT INTO scientists (scopus_id, full_name) VALUES (?, ?)", (sciid, sciname,))
    con.commit()
    return True


def del_scientist(sciid, sciname):
    con = sqlite3.connect('data.db', check_same_thread=False)
    con.row_factory = dict_factory
    cur = con.cursor()
    cur.execute("DELETE FROM scientists WHERE scopus_id = ? AND full_name = ?", (sciid, sciname,))
    con.commit()
    return True


app = Flask(__name__)


@app.route('/')
def index():
    selected = request.args.get('sci-info', type=int)
    scientists = get_scientists()
    scidata = None

    if selected in scientists:
        scientists[selected]['selected'] = True
        scidata = get_scidata(selected)

    return render_template('index.html', sci=scientists, scidata=scidata)


@app.route('/add')
def add_sci():
    idsci = request.args.get('idsci')
    namesci = request.args.get('namesci')
    if idsci != None and namesci != None:
        add_scientist(idsci, namesci)
    return f'<h1>idsci: {idsci}</h1><h1>idname: {namesci}</h1>'


@app.route('/del')
def del_sci():
    referer = request.headers.get('Referer')
    idsci = request.args.get('idsci')
    namesci = request.args.get('namesci')
    if idsci != None and namesci != None:
        del_scientist(idsci, namesci)
    return redirect(referer)


if __name__ == '__main__':
    app.run()
