from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import date, datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'andravohangy_secret_2026'
DB = 'andravohangy.db'
MOT_DE_PASSE = 'christina2026'  # ← CHANGE ICI

LIVREURS = ['À assigner','Mbola','Patrick','Sarobidy Nomena','Toky','Solo','Daniel','Andry','Ando']
CATEGORIES = {
    'Charme & Douceur': [str(i) for i in range(1,12)],
    'Slip & Boxer': ['S'+str(i) for i in range(1,21)],
    'Chaussette': ['C1','C2','C4']
}
MOTIFS = [
    'Tsy mandray telephone','Maty telephone','Tsy antonona',
    'Tsy mety amilay client','Diso numero ny commercial',
    'Diso ny entana commercial','Tara lera ny livreur','Autre'
]
PRIX_DEF = {'Charme & Douceur':5000,'Slip & Boxer':3000,'Chaussette':2500}

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS commandes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT DEFAULT CURRENT_DATE,
        heure TEXT DEFAULT '',
        client TEXT DEFAULT '',
        contact TEXT DEFAULT '',
        adresse TEXT DEFAULT '',
        facebook TEXT DEFAULT '',
        livreur TEXT DEFAULT '',
        frais INTEGER DEFAULT 0,
        paiement TEXT DEFAULT 'espece',
        paiement_timing TEXT DEFAULT 'apres',
        coordonne TEXT DEFAULT 'non_recu',
        statut TEXT DEFAULT 'att',
        motif TEXT DEFAULT '',
        motif_autre TEXT DEFAULT '',
        retour_anja INTEGER DEFAULT 0,
        retour_christina INTEGER DEFAULT 0,
        montant_retour INTEGER DEFAULT 0,
        notes TEXT DEFAULT '',
        envoye_anja INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        commande_id INTEGER,
        categorie TEXT DEFAULT '',
        ref TEXT DEFAULT '',
        nom TEXT DEFAULT '',
        qte INTEGER DEFAULT 1,
        prix_unitaire INTEGER DEFAULT 0,
        FOREIGN KEY(commande_id) REFERENCES commandes(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock (
        ref TEXT PRIMARY KEY,
        categorie TEXT,
        nom TEXT DEFAULT '',
        qte_init INTEGER DEFAULT 50,
        qte INTEGER DEFAULT 50,
        prix_vente INTEGER DEFAULT 5000,
        prix_achat INTEGER DEFAULT 3000
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS ventes_directes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT DEFAULT CURRENT_DATE,
        client TEXT DEFAULT '',
        contact TEXT DEFAULT '',
        ref TEXT DEFAULT '',
        categorie TEXT DEFAULT '',
        qte INTEGER DEFAULT 1,
        prix_unitaire INTEGER DEFAULT 0,
        paiement TEXT DEFAULT 'espece',
        notes TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS achats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT DEFAULT CURRENT_DATE,
        description TEXT DEFAULT '',
        montant INTEGER DEFAULT 0,
        frais_port INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS versements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT DEFAULT CURRENT_DATE,
        montant INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS avances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT DEFAULT CURRENT_DATE,
        montant INTEGER DEFAULT 0,
        rembourse INTEGER DEFAULT 0,
        description TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS excedents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT DEFAULT CURRENT_DATE,
        montant INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS depenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT DEFAULT CURRENT_DATE,
        categorie TEXT DEFAULT '',
        montant INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock_mouvements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT DEFAULT CURRENT_DATE,
        ref TEXT DEFAULT '',
        type TEXT DEFAULT '',
        qte INTEGER DEFAULT 0,
        prix_achat INTEGER DEFAULT 0,
        remise INTEGER DEFAULT 0,
        notes TEXT DEFAULT ''
    )''')
    # Add photo column if not exists
    try:
        c.execute('ALTER TABLE stock ADD COLUMN photo TEXT DEFAULT ""')
    except:
        pass
    if c.execute('SELECT COUNT(*) FROM stock').fetchone()[0] == 0:
        for cat, refs in CATEGORIES.items():
            pv = PRIX_DEF[cat]
            for ref in refs:
                c.execute('INSERT INTO stock (ref,categorie,qte_init,qte,prix_vente) VALUES (?,?,50,50,?)',(ref,cat,pv))
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return dec

def get_articles(conn, cid):
    return conn.execute('SELECT * FROM articles WHERE commande_id=?',(cid,)).fetchall()

def calc_total(arts):
    return sum(a['qte']*a['prix_unitaire'] for a in arts)

def calc_types(arts):
    t = set()
    for a in arts:
        if 'Charme' in a['categorie']: t.add('Soutiens')
        elif 'Slip' in a['categorie']: t.add('Slip')
        elif 'Chaussette' in a['categorie']: t.add('Chaussette')
    return ' + '.join(sorted(t)) if t else '—'

# AUTH
@app.route('/login', methods=['GET','POST'])
def login():
    err = ''
    if request.method == 'POST':
        if request.form['password'] == MOT_DE_PASSE:
            session['logged_in'] = True
            return redirect(url_for('moi'))
        err = 'Mot de passe incorrect'
    return render_template('login.html', error=err)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ANJA
@app.route('/')
def index():
    return redirect(url_for('anja'))

@app.route('/anja')
def anja():
    conn = get_db()
    today = date.today().strftime('%Y-%m-%d')
    rows = conn.execute('SELECT * FROM commandes WHERE envoye_anja=1 ORDER BY date DESC,id DESC').fetchall()
    commandes = []
    for r in rows:
        arts = get_articles(conn, r['id'])
        commandes.append({**dict(r),'total':calc_total(arts),'types':calc_types(arts),'articles':[dict(a) for a in arts]})
    frais_jour = conn.execute('''SELECT livreur,COUNT(*) nb,SUM(frais) tf
        FROM commandes WHERE date=? AND envoye_anja=1
        GROUP BY livreur ORDER BY livreur''',(today,)).fetchall()
    ca_esp = conn.execute('''SELECT COALESCE(SUM(a.qte*a.prix_unitaire),0)
        FROM articles a JOIN commandes c ON a.commande_id=c.id
        WHERE c.date=? AND c.statut='liv' AND c.envoye_anja=1''',(today,)).fetchone()[0]
    ca_mm = conn.execute('''SELECT COALESCE(SUM(a.qte*a.prix_unitaire),0)
        FROM articles a JOIN commandes c ON a.commande_id=c.id
        WHERE c.date=? AND c.statut IN ('mvola','orange','airtel') AND c.envoye_anja=1''',(today,)).fetchone()[0]
    frais_mm = conn.execute('''SELECT COALESCE(SUM(frais),0) FROM commandes
        WHERE date=? AND statut IN ('mvola','orange','airtel') AND envoye_anja=1''',(today,)).fetchone()[0]
    conn.close()
    return render_template('anja.html', commandes=commandes, livreurs=LIVREURS,
        today=today, frais_jour=frais_jour, motifs=MOTIFS,
        ca_esp=ca_esp, ca_mm=ca_mm, frais_mm=frais_mm)

@app.route('/anja/modifier_livreur/<int:cid>', methods=['POST'])
def anja_modifier_livreur(cid):
    conn = get_db()
    conn.execute('UPDATE commandes SET livreur=? WHERE id=?',(request.form['livreur'],cid))
    conn.commit()
    conn.close()
    return redirect(url_for('anja'))

@app.route('/anja/statut/<int:cid>', methods=['POST'])
def anja_statut(cid):
    conn = get_db()
    statut = request.form['statut']
    motif = request.form.get('motif','')
    motif_autre = request.form.get('motif_autre','')
    retour = 1 if statut in ('ann','ret','chg') else 0
    conn.execute('''UPDATE commandes SET statut=?,motif=?,motif_autre=?,
        retour_anja=CASE WHEN ?=1 THEN 1 ELSE retour_anja END WHERE id=?''',
        (statut,motif,motif_autre,retour,cid))
    conn.commit()
    conn.close()
    return redirect(url_for('anja'))

@app.route('/anja/confirmer_retour/<int:cid>', methods=['POST'])
def anja_confirmer_retour(cid):
    conn = get_db()
    conn.execute('UPDATE commandes SET retour_anja=1 WHERE id=?',(cid,))
    conn.commit()
    conn.close()
    return redirect(url_for('anja'))

@app.route('/anja/qr_groupe', methods=['POST'])
def anja_qr_groupe():
    ids = request.form.getlist('ids')
    conn = get_db()
    for cid in ids:
        conn.execute("UPDATE commandes SET statut='liv' WHERE id=? AND statut IN ('att','chg')",(cid,))
    conn.commit()
    conn.close()
    return redirect(url_for('anja'))

@app.route('/anja/supprimer/<int:cid>', methods=['POST'])
def anja_supprimer(cid):
    conn = get_db()
    conn.execute('DELETE FROM articles WHERE commande_id=?',(cid,))
    conn.execute('DELETE FROM commandes WHERE id=?',(cid,))
    conn.commit()
    conn.close()
    return redirect(url_for('anja'))

# CHRISTINA
@app.route('/moi')
@login_required
def moi():
    conn = get_db()
    today = date.today().strftime('%Y-%m-%d')
    rows = conn.execute('SELECT * FROM commandes ORDER BY date DESC,id DESC').fetchall()
    commandes = []
    for r in rows:
        arts = get_articles(conn, r['id'])
        commandes.append({**dict(r),'total':calc_total(arts),'types':calc_types(arts),'articles':[dict(a) for a in arts]})
    retours = [c for c in commandes if c['retour_anja']==1 and c['retour_christina']==0 and c['statut'] in ('ann','ret','chg')]
    stock = conn.execute('SELECT * FROM stock ORDER BY categorie,ref').fetchall()
    ventes = conn.execute('SELECT * FROM ventes_directes ORDER BY date DESC').fetchall()
    achats = conn.execute('SELECT * FROM achats ORDER BY date DESC').fetchall()
    versements = conn.execute('SELECT * FROM versements ORDER BY date DESC').fetchall()
    avances = conn.execute('SELECT * FROM avances ORDER BY date DESC').fetchall()
    excedents = conn.execute('SELECT * FROM excedents ORDER BY date DESC').fetchall()
    depenses = conn.execute('SELECT * FROM depenses ORDER BY date DESC').fetchall()
    all_refs = [(ref,cat) for cat,refs in CATEGORIES.items() for ref in refs]
    ca_liv = sum(c['total'] for c in commandes if c['statut']=='liv')
    ca_mm = sum(c['total'] for c in commandes if c['statut'] in ('mvola','orange','airtel'))
    ca_vd = sum(v['qte']*v['prix_unitaire'] for v in ventes)
    ca_achats = sum(a['montant']+a['frais_port'] for a in achats)
    tot_vers = sum(v['montant'] for v in versements)
    tot_av = sum(a['montant'] for a in avances)
    tot_remb = sum(a['rembourse'] for a in avances)
    tot_dep = sum(d['montant'] for d in depenses)
    today_cmd = [c for c in commandes if c['date']==today]
    ca_jour = sum(c['total'] for c in today_cmd)
    ca_jour_vd = sum(v['qte']*v['prix_unitaire'] for v in ventes if v['date']==today)
    dep_jour = sum(d['montant'] for d in depenses if d['date']==today)
    conn.close()
    return render_template('moi.html',
        commandes=commandes, retours=retours, stock=stock,
        ventes=ventes, achats=achats, versements=versements,
        avances=avances, excedents=excedents, depenses=depenses,
        today=today, categories=CATEGORIES, all_refs=all_refs,
        prix_def=PRIX_DEF, livreurs=LIVREURS,
        ca_liv=ca_liv, ca_mm=ca_mm, ca_vd=ca_vd,
        ca_achats=ca_achats, tot_vers=tot_vers,
        tot_av=tot_av, tot_remb=tot_remb, tot_dep=tot_dep,
        ca_jour=ca_jour+ca_jour_vd, dep_jour=dep_jour)

@app.route('/moi/commande/nouvelle', methods=['POST'])
@login_required
def nouvelle_commande():
    conn = get_db()
    heure = datetime.now().strftime('%H:%M')
    cid = conn.execute('''INSERT INTO commandes
        (date,heure,client,contact,adresse,facebook,livreur,frais,paiement,paiement_timing,coordonne,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
        (request.form['date'], heure,
         request.form['client'], request.form.get('contact',''),
         request.form.get('adresse',''), request.form.get('facebook',''),
         request.form['livreur'], int(request.form.get('frais') or 0),
         request.form.get('paiement','espece'),
         request.form.get('paiement_timing','apres'),
         request.form.get('coordonne','non_recu'),
         request.form.get('notes',''))).lastrowid
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#cmd-'+str(cid))

@app.route('/moi/article/ajouter', methods=['POST'])
@login_required
def ajouter_article():
    conn = get_db()
    cid = int(request.form['commande_id'])
    ref = request.form['ref']
    cat = request.form['categorie']
    qte = int(request.form.get('qte') or 1)
    pu = int(request.form.get('pu') or 0)
    nom = request.form.get('nom','')
    conn.execute('INSERT INTO articles (commande_id,categorie,ref,nom,qte,prix_unitaire) VALUES (?,?,?,?,?,?)',(cid,cat,ref,nom,qte,pu))
    conn.execute('UPDATE stock SET qte=MAX(0,qte-?) WHERE ref=?',(qte,ref))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#cmd-'+str(cid))

@app.route('/moi/articles/ajouter_multiple', methods=['POST'])
@login_required
def ajouter_articles_multiple():
    conn = get_db()
    cid = int(request.form['commande_id'])
    refs = request.form.getlist('ref[]')
    noms = request.form.getlist('nom[]')
    qtes = request.form.getlist('qte[]')
    pus = request.form.getlist('pu[]')
    for i in range(len(refs)):
        ref = refs[i]
        qte = int(qtes[i] or 1)
        pu = int(pus[i] or 0)
        nom = noms[i] if i < len(noms) else ''
        # Get categorie from ref
        cat = ''
        for c, rs in CATEGORIES.items():
            if ref in rs:
                cat = c
                break
        if ref and qte > 0:
            conn.execute('INSERT INTO articles (commande_id,categorie,ref,nom,qte,prix_unitaire) VALUES (?,?,?,?,?,?)',
                (cid, cat, ref, nom, qte, pu))
            conn.execute('UPDATE stock SET qte=MAX(0,qte-?) WHERE ref=?', (qte, ref))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#cmd-'+str(cid))

@app.route('/moi/article/supprimer/<int:aid>', methods=['POST'])
@login_required
def supprimer_article(aid):
    conn = get_db()
    a = conn.execute('SELECT * FROM articles WHERE id=?',(aid,)).fetchone()
    cid = a['commande_id']
    conn.execute('UPDATE stock SET qte=qte+? WHERE ref=?',(a['qte'],a['ref']))
    conn.execute('DELETE FROM articles WHERE id=?',(aid,))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#cmd-'+str(cid))

@app.route('/moi/commandes/envoyer_tout', methods=['POST'])
@login_required
def envoyer_tout_anja():
    conn = get_db()
    conn.execute('UPDATE commandes SET envoye_anja=1 WHERE envoye_anja=0')
    conn.commit()
    conn.close()
    return redirect(url_for('moi'))

@app.route('/moi/commande/envoyer/<int:cid>', methods=['POST'])
@login_required
def envoyer_anja(cid):
    conn = get_db()
    conn.execute('UPDATE commandes SET envoye_anja=1 WHERE id=?',(cid,))
    conn.commit()
    conn.close()
    return redirect(url_for('moi'))

@app.route('/moi/commande/coordonne/<int:cid>', methods=['POST'])
@login_required
def update_coordonne(cid):
    conn = get_db()
    conn.execute('UPDATE commandes SET coordonne=? WHERE id=?',(request.form['coordonne'],cid))
    conn.commit()
    conn.close()
    return redirect(url_for('moi'))

@app.route('/moi/commande/supprimer/<int:cid>', methods=['POST'])
@login_required
def supprimer_commande(cid):
    conn = get_db()
    arts = conn.execute('SELECT * FROM articles WHERE commande_id=?',(cid,)).fetchall()
    for a in arts:
        conn.execute('UPDATE stock SET qte=qte+? WHERE ref=?',(a['qte'],a['ref']))
    conn.execute('DELETE FROM articles WHERE commande_id=?',(cid,))
    conn.execute('DELETE FROM commandes WHERE id=?',(cid,))
    conn.commit()
    conn.close()
    return redirect(url_for('moi'))

@app.route('/moi/retour/confirmer/<int:cid>', methods=['POST'])
@login_required
def confirmer_retour(cid):
    conn = get_db()
    conn.execute('UPDATE commandes SET retour_christina=1,montant_retour=0 WHERE id=?',(cid,))
    conn.commit()
    conn.close()
    return redirect(url_for('moi'))

@app.route('/moi/vente/ajouter', methods=['POST'])
@login_required
def vente_ajouter():
    conn = get_db()
    ref = request.form['ref']
    qte = int(request.form.get('qte') or 1)
    conn.execute('INSERT INTO ventes_directes (date,client,contact,ref,categorie,qte,prix_unitaire,paiement,notes) VALUES (?,?,?,?,?,?,?,?,?)',
        (request.form['date'], request.form.get('client',''), request.form.get('contact',''),
         ref, request.form.get('categorie',''), qte,
         int(request.form.get('pu') or 0), request.form.get('paiement','espece'),
         request.form.get('notes','')))
    conn.execute('UPDATE stock SET qte=MAX(0,qte-?) WHERE ref=?',(qte,ref))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#ventes')

@app.route('/moi/vente/supprimer/<int:vid>', methods=['POST'])
@login_required
def vente_supprimer(vid):
    conn = get_db()
    v = conn.execute('SELECT * FROM ventes_directes WHERE id=?',(vid,)).fetchone()
    if v:
        conn.execute('UPDATE stock SET qte=qte+? WHERE ref=?',(v['qte'],v['ref']))
        conn.execute('DELETE FROM ventes_directes WHERE id=?',(vid,))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#ventes')

@app.route('/moi/achat/ajouter', methods=['POST'])
@login_required
def achat_ajouter():
    conn = get_db()
    conn.execute('INSERT INTO achats (date,description,montant,frais_port,notes) VALUES (?,?,?,?,?)',
        (request.form['date'], request.form['description'],
         int(request.form.get('montant') or 0), int(request.form.get('frais_port') or 0),
         request.form.get('notes','')))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#achats')

@app.route('/moi/versement/ajouter', methods=['POST'])
@login_required
def versement_ajouter():
    conn = get_db()
    conn.execute('INSERT INTO versements (date,montant,notes) VALUES (?,?,?)',
        (request.form['date'], int(request.form.get('montant') or 0), request.form.get('notes','')))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#finances')

@app.route('/moi/versement/supprimer/<int:vid>', methods=['POST'])
@login_required
def versement_supprimer(vid):
    conn = get_db()
    conn.execute('DELETE FROM versements WHERE id=?',(vid,))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#finances')

@app.route('/moi/avance/ajouter', methods=['POST'])
@login_required
def avance_ajouter():
    conn = get_db()
    conn.execute('INSERT INTO avances (date,montant,description) VALUES (?,?,?)',
        (request.form['date'], int(request.form.get('montant') or 0), request.form['description']))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#remb')

@app.route('/moi/avance/rembourser/<int:aid>', methods=['POST'])
@login_required
def avance_rembourser(aid):
    conn = get_db()
    conn.execute('UPDATE avances SET rembourse=MIN(montant,rembourse+?) WHERE id=?',
        (int(request.form.get('montant') or 0), aid))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#remb')

@app.route('/moi/excedent/ajouter', methods=['POST'])
@login_required
def excedent_ajouter():
    conn = get_db()
    conn.execute('INSERT INTO excedents (date,montant,notes) VALUES (?,?,?)',
        (request.form['date'], int(request.form.get('montant') or 0), request.form.get('notes','')))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#finances')

@app.route('/moi/depense/ajouter', methods=['POST'])
@login_required
def depense_ajouter():
    conn = get_db()
    conn.execute('INSERT INTO depenses (date,categorie,montant,notes) VALUES (?,?,?,?)',
        (request.form['date'], request.form['categorie'],
         int(request.form.get('montant') or 0), request.form.get('notes','')))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#depenses')

@app.route('/moi/depense/supprimer/<int:did>', methods=['POST'])
@login_required
def depense_supprimer(did):
    conn = get_db()
    conn.execute('DELETE FROM depenses WHERE id=?',(did,))
    conn.commit()
    conn.close()
    return redirect(url_for('moi')+'#depenses')

# ─── STOCK MODULE ─────────────────────────────────────────────────────────────
import os, base64
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/photos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/stock')
@login_required
def stock_view():
    conn = get_db()
    stock = conn.execute('SELECT * FROM stock ORDER BY categorie, ref').fetchall()
    # Get mouvements
    mouvements = conn.execute('SELECT * FROM stock_mouvements ORDER BY date DESC, id DESC LIMIT 50').fetchall()
    # Calc sorties auto from ventes + commandes
    today = date.today().strftime('%Y-%m-%d')
    conn.close()
    return render_template('stock.html', stock=stock, mouvements=mouvements, today=today, categories=CATEGORIES)

@app.route('/stock/prix/<ref>', methods=['POST'])
@login_required
def stock_prix(ref):
    conn = get_db()
    prix_achat = int(request.form.get('prix_achat') or 0)
    prix_vente = int(request.form.get('prix_vente') or 0)
    conn.execute('UPDATE stock SET prix_achat=?, prix_vente=? WHERE ref=?', (prix_achat, prix_vente, ref))
    conn.commit()
    conn.close()
    return redirect(url_for('stock_view'))

@app.route('/stock/entree', methods=['POST'])
@login_required
def stock_entree():
    conn = get_db()
    ref = request.form['ref']
    qte = int(request.form.get('qte') or 0)
    prix_achat = int(request.form.get('prix_achat') or 0)
    notes = request.form.get('notes', '')
    # Update stock
    conn.execute('UPDATE stock SET qte=qte+?, prix_achat=?, qte_init=qte_init+? WHERE ref=?', (qte, prix_achat, qte, ref))
    # Log mouvement
    conn.execute('INSERT INTO stock_mouvements (date,ref,type,qte,prix_achat,notes) VALUES (?,?,?,?,?,?)',
        (date.today().strftime('%Y-%m-%d'), ref, 'entree', qte, prix_achat, notes))
    conn.commit()
    conn.close()
    return redirect(url_for('stock_view'))

@app.route('/stock/defaut', methods=['POST'])
@login_required
def stock_defaut():
    conn = get_db()
    ref = request.form['ref']
    qte = int(request.form.get('qte') or 0)
    notes = request.form.get('notes', '')
    conn.execute('UPDATE stock SET qte=MAX(0,qte-?) WHERE ref=?', (qte, ref))
    conn.execute('INSERT INTO stock_mouvements (date,ref,type,qte,notes) VALUES (?,?,?,?,?)',
        (date.today().strftime('%Y-%m-%d'), ref, 'defaut', qte, notes))
    conn.commit()
    conn.close()
    return redirect(url_for('stock_view'))

@app.route('/stock/vente_collegue', methods=['POST'])
@login_required
def stock_vente_collegue():
    conn = get_db()
    ref = request.form['ref']
    qte = int(request.form.get('qte') or 0)
    prix_achat = int(request.form.get('prix_achat') or 0)
    remise = int(request.form.get('remise') or 0)
    notes = request.form.get('notes', '')
    conn.execute('UPDATE stock SET qte=MAX(0,qte-?) WHERE ref=?', (qte, ref))
    conn.execute('INSERT INTO stock_mouvements (date,ref,type,qte,prix_achat,remise,notes) VALUES (?,?,?,?,?,?,?)',
        (date.today().strftime('%Y-%m-%d'), ref, 'collegue', qte, prix_achat, remise, notes))
    conn.commit()
    conn.close()
    return redirect(url_for('stock_view'))

@app.route('/stock/photo/<ref>', methods=['POST'])
@login_required
def stock_photo(ref):
    if 'photo' not in request.files:
        return redirect(url_for('stock_view'))
    file = request.files['photo']
    if file.filename == '':
        return redirect(url_for('stock_view'))
    ext = file.filename.rsplit('.', 1)[-1].lower()
    filename = secure_filename(ref + '.' + ext)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    conn = get_db()
    conn.execute('UPDATE stock SET photo=? WHERE ref=?', (filename, ref))
    conn.commit()
    conn.close()
    return redirect(url_for('stock_view'))

if __name__ == '__main__':
    init_db()
    print('\n✅  Logiciel Andravohangy démarré !')
    print('🚚  Anja       → http://localhost:5000/anja')
    print('📊  Christina  → http://localhost:5000/moi')
    print('🔑  Mot de passe : christina2026\n')
    app.run(debug=True, port=5000)
