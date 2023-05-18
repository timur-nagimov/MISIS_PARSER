from flask import Flask, request, render_template, send_from_directory
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
		sci_list[ i['id'] ] = i
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

if __name__ == '__main__':
    app.run()
