from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify, flash
import pyodbc
import os
from conexiune import get_connection
from datetime import datetime

app = Flask(__name__)
app.secret_key = '1234'

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
    return send_from_directory(assets_dir, filename)

@app.after_request
def set_response_headers(response):
    rute_protejate = [
        '/portal', '/angajati', '/stoc', '/rapoarte', '/vanzare','/vizualizare', '/performante', '/istoric', '/interes']
    
    if any(request.path.startswith(ruta) for ruta in rute_protejate):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.context_processor
def inject_global_data():
    marci_list = []
    cos_count = 0
    cereri_noi_count = 0
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql_marci = "SELECT DISTINCT Marca FROM Modele_Auto ORDER BY Marca ASC;"
            cursor.execute(sql_marci)
            marci_list = [row[0] for row in cursor.fetchall()]

            if session.get('logged_in') and session.get('rol') == 'Client':
                id_client = session.get('id_client')
                if id_client:
                    sql_cos = "SELECT COUNT(*) FROM Cos_Client WHERE ID_Client = ?;"
                    cursor.execute(sql_cos, (id_client,))
                    cos_count = cursor.fetchone()[0]
            
            if session.get('logged_in') and session.get('rol') == 'Vanzator':
                sql_cereri = "SELECT COUNT(*) FROM Cereri_Achizitie WHERE Status_Cerere = 'In Asteptare';"
                cursor.execute(sql_cereri)
                cereri_noi_count = cursor.fetchone()[0]
                    
        except Exception as e:
            print(f"Eroare context processor: {e}")
        finally:
            conn.close()

    return dict(marci_list=marci_list, cos_count=cos_count, cereri_noi_count=cereri_noi_count)


@app.route('/cos/solicita/<vin>', methods=['POST'])
def solicita_achizitie(vin):
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    id_client = session.get('id_client')
    mesaj = request.form.get('mesaj', '')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("""SELECT Status_Vanzare FROM Masini_Stoc WHERE VIN = ?""", (vin,))
            result = cursor.fetchone()
            
            if not result or result[0] != 'Disponibil':
                flash('Mașina nu mai este disponibilă.', 'error')
                return redirect(url_for('route_cos'))
            
            cursor.execute("""SELECT ID_Cerere FROM Cereri_Achizitie WHERE ID_Client = ? AND VIN_Masina = ? AND Status_Cerere IN ('In Asteptare', 'Preluata')""", (id_client, vin))
            
            if cursor.fetchone():
                flash('Ai deja o cerere activă pentru această mașină.', 'info')
                return redirect(url_for('route_cos'))
            
            sql = """INSERT INTO Cereri_Achizitie (ID_Client, VIN_Masina, Mesaj_Client, Status_Cerere) VALUES (?, ?, ?, 'In Asteptare');"""
            cursor.execute(sql, (id_client, vin, mesaj if mesaj else None))
            
            cursor.execute("""UPDATE Masini_Stoc SET Status_Vanzare = 'Rezervat' WHERE VIN = ?""", (vin,))            
            cursor.execute("""DELETE FROM Cos_Client WHERE ID_Client = ? AND VIN_Masina = ?""", (id_client, vin))
            
            conn.commit()
            flash('Cererea de achiziție a fost trimisă! Vei fi contactat de un vânzător.', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_cereri_client'))


@app.route('/cereri', methods=['GET'])
def route_cereri_client():
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    cereri = []
    id_client = session.get('id_client')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            sql = """
                SELECT 
                    CA.ID_Cerere,
                    CA.VIN_Masina,
                    M.Marca,
                    M.Nume_Model,
                    MS.Culoare_Exterior,
                    MS.Pret,
                    CA.Data_Cerere,
                    CA.Status_Cerere,
                    CA.Mesaj_Client,
                    A.Nume + ' ' + A.Prenume AS Vanzator,
                    CA.Data_Preluare
                FROM Cereri_Achizitie CA
                INNER JOIN Masini_Stoc MS ON CA.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                LEFT JOIN Angajati A ON CA.ID_Vanzator_Preluat = A.ID_Angajat
                WHERE CA.ID_Client = ?
                ORDER BY 
                    CASE CA.Status_Cerere 
                        WHEN 'In Asteptare' THEN 1 
                        WHEN 'Preluata' THEN 2 
                        ELSE 3 
                    END,
                    CA.Data_Cerere DESC;
            """
            cursor.execute(sql, (id_client,))
            cereri = cursor.fetchall()
            
        except Exception as e:
            print(f"Eroare: {e}")
        finally:
            conn.close()
    
    return render_template('cereri_client.html', logged_in=True, username=session.get('username'),rol=session.get('rol'),cereri=cereri)

@app.route('/cereri/anuleaza/<int:id_cerere>', methods=['POST'])
def anuleaza_cerere_client(id_cerere):
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    id_client = session.get('id_client')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""SELECT VIN_Masina FROM Cereri_Achizitie WHERE ID_Cerere = ?  AND Status_Cerere = 'In Asteptare'""", (id_cerere,))
            
            result = cursor.fetchone()
            if not result:
                flash('Cererea nu poate fi anulată.', 'error')
                return redirect(url_for('route_cereri_client'))
            
            vin = result[0]
            
            cursor.execute("""UPDATE Cereri_Achizitie SET Status_Cerere = 'Anulata' WHERE ID_Cerere = ?""", (id_cerere,))
            
            cursor.execute("""UPDATE Masini_Stoc SET Status_Vanzare = 'Disponibil' WHERE VIN = ?""", (vin,))
            
            conn.commit()
            flash('Cererea a fost anulată.', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_cereri_client'))

@app.route('/cos', methods=['GET'])
def route_cos():
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    masini_cos = []
    id_client = session.get('id_client')   
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql = """
                SELECT 
                    CC.ID_Cos,
                    MS.VIN,
                    M.Marca,
                    M.Nume_Model,
                    M.Tip_Caroserie,
                    M.Combustibil,
                    M.Putere,
                    MS.Culoare_Exterior,
                    MS.Pret,
                    MS.Status_Vanzare,
                    CC.Data_Adaugare
                FROM Cos_Client CC
                INNER JOIN Masini_Stoc MS ON CC.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                WHERE CC.ID_Client = ?
                ORDER BY CC.Data_Adaugare DESC;
            """
            cursor.execute(sql, (id_client,))
            masini_cos = cursor.fetchall()  
        except Exception as e:
            print(f"Eroare la preluarea coșului: {e}")
        finally:
            conn.close() 
    return render_template('cos_client.html',logged_in=True,username=session.get('username'),rol=session.get('rol'), masini_cos=masini_cos)

@app.route('/cos/adauga/<vin>', methods=['POST'])
def adauga_in_cos(vin):
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return jsonify({'success': False, 'message': 'Trebuie să fiți autentificat ca și client.'}), 401
    
    id_client = session.get('id_client')   
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""SELECT Status_Vanzare FROM Masini_Stoc WHERE VIN = ?""", (vin,))
            result = cursor.fetchone()
            
            if not result:
                flash('Mașina nu a fost găsită.', 'error')
                return redirect(request.referrer or url_for('dashboard'))
            
            if result[0] == 'Vandut':
                flash('Această mașină a fost deja vândută.', 'error')
                return redirect(request.referrer or url_for('dashboard'))

            cursor.execute("""SELECT ID_Cos FROM Cos_Client WHERE ID_Client = ? AND VIN_Masina = ?""", (id_client, vin))
            
            if cursor.fetchone():
                flash('Mașina este deja în coșul tău.', 'info')
                return redirect(request.referrer or url_for('dashboard'))
            
            sql = """
                INSERT INTO Cos_Client (ID_Client, VIN_Masina, Data_Adaugare)
                VALUES (?, ?, GETDATE());
            """
            cursor.execute(sql, (id_client, vin))
            conn.commit()
            flash('Mașina a fost adăugată în coș!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/cos/sterge/<int:id_cos>', methods=['POST'])
def sterge_din_cos(id_cos):
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    id_client = session.get('id_client')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql = "DELETE FROM Cos_Client WHERE ID_Cos = ? AND ID_Client = ?;"
            cursor.execute(sql, (id_cos, id_client))
            conn.commit()
            flash('Mașina a fost eliminată din coș.', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_cos'))


@app.route('/cos/goleste', methods=['POST'])
def goleste_cos():
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    id_client = session.get('id_client')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql = "DELETE FROM Cos_Client WHERE ID_Client = ?;"
            cursor.execute(sql, (id_client,))
            conn.commit()
            flash('Coșul a fost golit.', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_cos'))


@app.route('/masini/<marca>', methods=['GET'])
def masini_marca(marca):
    masini = []
    conn = get_connection()
    
    if conn:
        try:
            cursor = conn.cursor() 
            sql = """
                SELECT 
                    MS.VIN,
                    M.Marca,
                    M.Nume_Model,
                    M.Tip_Caroserie,
                    M.Combustibil,
                    M.Putere,
                    M.Transmisie,
                    MS.Culoare_Exterior,
                    MS.Pret,
                    MS.Status_Vanzare
                FROM Masini_Stoc MS
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                WHERE M.Marca = ? AND MS.Status_Vanzare = 'Disponibil'
                ORDER BY M.Nume_Model, MS.Pret;
            """
            cursor.execute(sql, (marca,))
            masini = cursor.fetchall()     
        except Exception as e:
            print(f"Eroare: {e}")
        finally:
            conn.close()  
    return render_template('masini_marca.html', marca=marca, masini=masini, logged_in=session.get('logged_in'), username=session.get('username'), rol=session.get('rol'))

@app.route('/', methods=['GET'])
def dashboard():
    return render_template('home.html')

@app.route('/portal', methods=['GET'])
def portal():
    if not session.get('logged_in'):
        return redirect(url_for('dashboard'))
    
    rol = session.get('rol')
    if rol == 'Admin':
        return redirect(url_for('route_angajati'))
    elif rol == 'Vanzator':
        return redirect(url_for('route_vanzare_noua'))
    elif rol == 'Client':
        return redirect(url_for('route_istoric_tranzactii'))
    else:
        return render_template('dashboard.html', logged_in=True, username=session.get('username'), rol=rol)

@app.route('/auth', methods=['GET', 'POST'])
def login_register():
    error = None
    success_message = None
    if request.method == 'POST':
        conn = get_connection()
        if conn is None:
            error = "Eroare critică: Nu s-a putut stabili conexiunea la baza de date."
        else:
            try:
                cursor = conn.cursor()

                if 'btn_login' in request.form:
                    username = request.form.get('login_username')
                    password = request.form.get('login_password')
                    
                    sql_query = """
                        SELECT Rol, ID_Angajat_FK, ID_Client_FK 
                        FROM Utilizatori 
                        WHERE NumeUtilizator = ? AND Parola = ?;
                    """
                    cursor.execute(sql_query, (username, password))
                    result = cursor.fetchone()

                    if result:
                        session['logged_in'] = True
                        session['username'] = username
                        session['rol'] = result[0]
                        session['id_angajat'] = result[1] 
                        session['id_client'] = result[2]  
                        return redirect(url_for('portal')) 
                    else:
                        error = "Nume de utilizator sau parolă incorecte."

                elif 'btn_register' in request.form:
                    nume = request.form.get('reg_nume')
                    prenume = request.form.get('reg_prenume')
                    tip_client = request.form.get('reg_tip_client')
                    tara = request.form.get('reg_tara')
                    oras = request.form.get('reg_oras')
                    strada = request.form.get('reg_strada')
                    numar_strada = request.form.get('reg_numar_strada')
                    telefon = request.form.get('reg_telefon')
                    username = request.form.get('reg_username')
                    password = request.form.get('reg_password')
                    
                    cursor.execute("SELECT UserID FROM Utilizatori WHERE NumeUtilizator = ?", (username,))
                    if cursor.fetchone():
                        error = "Numele de utilizator este deja folosit."
                    else:
                        conn.autocommit = False 
                        try:
                            sql_client = """
                                INSERT INTO Clienti (Tip_Client, Nume, Prenume, Tara, Oras, Strada, Numar_Strada, Telefon)
                                OUTPUT INSERTED.ID_Client
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """
                            cursor.execute(sql_client, (tip_client, nume, prenume, tara, oras, strada, numar_strada, telefon))
                            new_client_id = cursor.fetchone()[0]
                            
                            sql_user = """
                                INSERT INTO Utilizatori (NumeUtilizator, Parola, Rol, ID_Client_FK) 
                                VALUES (?, ?, 'Client', ?)
                            """
                            cursor.execute(sql_user, (username, password, new_client_id))
                            
                            conn.commit()
                            success_message = "Contul a fost creat cu succes! Vă puteți autentifica acum."
                            
                        except Exception as e:
                            conn.rollback()
                            error = f"Eroare la înregistrare: {e}"
                            
            finally:
                if conn:
                    conn.close()

    return render_template('auth.html', error=error, success_message=success_message)

@app.route('/logout')
def logout():
    session.clear() 
    return redirect(url_for('login_register'))

@app.route('/angajati', methods=['GET'])
def route_angajati():
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    angajati = []
    conn = get_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            sql = """
            SELECT 
                A.ID_Angajat,
                A.Nume,
                A.Prenume,
                A.Data_Angajare,
                U.NumeUtilizator AS ContUtilizator
            FROM Angajati A
            INNER JOIN Utilizatori U ON A.ID_Angajat = U.ID_Angajat_FK
            ORDER BY A.Nume ASC;
        """
            cursor.execute(sql)
            angajati = cursor.fetchall()
            
        except Exception as e:
            print(f"Eroare la preluarea angajaților: {e}")
        finally:
            conn.close()

    return render_template('angajati_admin.html', logged_in=True, username=session.get('username'), rol=session.get('rol'), angajati=angajati)

@app.route('/angajati/adauga', methods=['POST'])
def adauga_angajat():
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    nume = request.form.get('nume')
    prenume = request.form.get('prenume')
    data_angajare = request.form.get('data_angajare')
    username = request.form.get('username')
    parola = request.form.get('parola')
    rol = request.form.get('rol')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM Utilizatori WHERE NumeUtilizator = ?", (username,))
            if cursor.fetchone()[0] > 0:
                flash('Username-ul există deja!', 'error')
                return redirect(url_for('route_angajati'))
            
            cursor.execute("""
                INSERT INTO Angajati (Nume, Prenume, Data_Angajare)
                OUTPUT INSERTED.ID_Angajat
                VALUES (?, ?, ?)
            """, (nume, prenume, data_angajare))
            new_id_angajat = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO Utilizatori (NumeUtilizator, Parola, Rol, ID_Angajat_FK)
                VALUES (?, ?, ?, ?)
            """, (username, parola, rol, new_id_angajat))
            
            conn.commit()
            flash(f'Angajatul {nume} {prenume} a fost adăugat cu contul {username}!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare la adăugarea angajatului: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_angajati'))


@app.route('/angajati/modifica/<int:id_angajat>', methods=['POST'])
def modifica_angajat(id_angajat):
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    nume = request.form.get('nume')
    prenume = request.form.get('prenume')
    data_angajare = request.form.get('data_angajare')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql = """
                UPDATE Angajati 
                SET Nume = ?, Prenume = ?, Data_Angajare = ?
                WHERE ID_Angajat = ?;
            """
            cursor.execute(sql, (nume, prenume, data_angajare, id_angajat))
            conn.commit()
            flash('Datele angajatului au fost actualizate!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare la modificarea angajatului: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_angajati'))


@app.route('/angajati/sterge/<int:id_angajat>', methods=['POST'])
def sterge_angajat(id_angajat):
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM Vanzari WHERE ID_Angajat = ?", (id_angajat,))
            nr_vanzari = cursor.fetchone()[0]
            
            if nr_vanzari > 0:
                flash(f'Nu se poate șterge angajatul! Are {nr_vanzari} vânzări asociate.', 'error')
            else:
                cursor.execute("DELETE FROM Utilizatori WHERE ID_Angajat_FK = ?", (id_angajat,))
                cursor.execute("DELETE FROM Angajati WHERE ID_Angajat = ?", (id_angajat,))
                conn.commit()
                flash('Angajatul a fost șters cu succes!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare la ștergerea angajatului: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_angajati'))


@app.route('/stoc', methods=['GET'])
def route_stoc():
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    masini = []
    modele = []  
    conn = get_connection()
    
    if conn:
        try:
            cursor = conn.cursor()

            sql_masini = """
                SELECT 
                    MS.VIN,
                    M.Marca,
                    M.Nume_Model,
                    M.Tip_Caroserie,
                    MS.Culoare_Exterior,
                    MS.Data_Intrare_Stoc,
                    MS.Cost_Achizitie,
                    MS.Pret,
                    MS.Status_Vanzare
                FROM Masini_Stoc MS
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                ORDER BY MS.Data_Intrare_Stoc DESC;
            """
            cursor.execute(sql_masini)
            masini = cursor.fetchall()

            sql_modele = """
                SELECT ID_Model, Marca, Nume_Model 
                FROM Modele_Auto 
                ORDER BY Marca, Nume_Model;
            """
            cursor.execute(sql_modele)
            modele = cursor.fetchall()
            
        except Exception as e:
            print(f"Eroare la preluarea stocului: {e}")
        finally:
            conn.close()
    
    return render_template('stoc_admin.html', logged_in=True, username=session.get('username'), rol=session.get('rol'), masini=masini,modele=modele)

@app.route('/stoc/adauga', methods=['POST'])
def adauga_masina():
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    vin = request.form.get('vin')
    culoare = request.form.get('culoare')
    data_intrare = request.form.get('data_intrare')
    cost_achizitie = request.form.get('cost_achizitie')
    pret = request.form.get('pret')
    status = 'Disponibil'
    
    nume_model = request.form.get('nume_model')
    marca = request.form.get('marca')
    generatie = request.form.get('generatie') or None
    tip_caroserie = request.form.get('tip_caroserie')
    combustibil = request.form.get('combustibil')
    capacitate = request.form.get('capacitate') or None
    putere = request.form.get('putere') or None
    transmisie = request.form.get('transmisie')
    norma_poluare = request.form.get('norma_poluare')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ID_Model FROM Modele_Auto 
                WHERE Nume_Model = ? AND Marca = ?
            """, (nume_model, marca))
            result = cursor.fetchone()
            
            if result:
                id_model = result[0]
            else:
                cursor.execute("""
                    INSERT INTO Modele_Auto (Nume_Model, Marca, Generatie, Tip_Caroserie, Combustibil, Capacitate_Cilindrica, Norma_Poluare, Putere, Transmisie)
                    OUTPUT INSERTED.ID_Model
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (nume_model, marca, generatie, tip_caroserie, combustibil, capacitate, norma_poluare, putere, transmisie))
                id_model = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO Masini_Stoc (VIN, ID_Model, Culoare_Exterior, Data_Intrare_Stoc, Cost_Achizitie, Pret, Status_Vanzare)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (vin, id_model, culoare, data_intrare, cost_achizitie, pret, status))
            
            conn.commit()
            flash(f'Mașina {marca} {nume_model} a fost adăugată în stoc!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare la adăugarea mașinii: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_stoc'))

@app.route('/stoc/modifica/<vin>', methods=['POST'])
def modifica_masina(vin):
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    culoare = request.form.get('culoare')
    cost_achizitie = request.form.get('cost_achizitie')
    pret = request.form.get('pret')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            sql = """
                UPDATE Masini_Stoc 
                SET Culoare_Exterior = ?, Cost_Achizitie = ?, Pret = ?
                WHERE VIN = ?;
            """
            cursor.execute(sql, (culoare, cost_achizitie, pret, vin))
            conn.commit()
            flash('Datele mașinii au fost actualizate!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare la modificarea mașinii: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_stoc'))

@app.route('/stoc/sterge/<vin>', methods=['POST'])
def sterge_masina(vin):
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Vanzari WHERE VIN_Masina = ?", (vin,))
            count_vanzari = cursor.fetchone()[0]
            
            if count_vanzari > 0:
                flash('Nu se poate șterge! Mașina are o vânzare înregistrată.', 'error')
                return redirect(url_for('route_stoc'))

            cursor.execute("DELETE FROM Masini_Stoc WHERE VIN = ?", (vin,))
            rows_deleted = cursor.rowcount
            
            conn.commit()
            
            if rows_deleted > 0:
                flash('Mașina a fost eliminată din stoc.', 'success')
            else:
                flash('Mașina nu a fost găsită în stoc.', 'error')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare tehnică la ștergere: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_stoc'))

@app.route('/vizualizare_stoc', methods=['GET'])
def route_vizualizare_stoc():
    if not session.get('logged_in') or session.get('rol') != 'Vanzator':
        return redirect(url_for('dashboard'))
    
    masini_disponibile = []
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql = """
                SELECT 
                    MS.VIN,
                    M.Marca,
                    M.Nume_Model,
                    M.Tip_Caroserie,
                    M.Combustibil,
                    M.Putere,
                    M.Transmisie,
                    MS.Culoare_Exterior,
                    MS.Pret
                FROM Masini_Stoc MS
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                WHERE MS.Status_Vanzare = 'Disponibil'
                ORDER BY M.Marca, M.Nume_Model;
            """
            cursor.execute(sql)
            masini_disponibile = cursor.fetchall()
            
        except Exception as e:
            print(f"Eroare: {e}")
        finally:
            conn.close()
    
    return render_template('vizualizare_stoc_angajat.html', logged_in=True, username=session.get('username'), rol=session.get('rol'), masini=masini_disponibile)

@app.route('/vanzare_noua', methods=['GET', 'POST'])
def route_vanzare_noua():
    if not session.get('logged_in') or session.get('rol') != 'Vanzator':
        return redirect(url_for('dashboard'))
    
    cereri_disponibile = []
    cereri_preluate = []
    masini = []
    clienti = []
    id_angajat = session.get('id_angajat')
    
    conn = get_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            
            sql_cereri_disponibile = """
                SELECT 
                    CA.ID_Cerere,
                    CA.VIN_Masina,
                    M.Marca,
                    M.Nume_Model,
                    MS.Culoare_Exterior,
                    MS.Pret,
                    C.Nume + ' ' + C.Prenume AS NumeClient,
                    C.Telefon,
                    C.Tip_Client,
                    CA.Data_Cerere,
                    CA.Mesaj_Client
                FROM Cereri_Achizitie CA
                INNER JOIN Masini_Stoc MS ON CA.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                INNER JOIN Clienti C ON CA.ID_Client = C.ID_Client
                WHERE CA.Status_Cerere = 'In Asteptare'
                ORDER BY CA.Data_Cerere ASC;
            """
            cursor.execute(sql_cereri_disponibile)
            cereri_disponibile = cursor.fetchall()
            
            sql_cereri_preluate = """
                SELECT 
                    CA.ID_Cerere,
                    CA.VIN_Masina,
                    M.Marca,
                    M.Nume_Model,
                    MS.Culoare_Exterior,
                    MS.Pret,
                    C.ID_Client,
                    C.Nume + ' ' + C.Prenume AS NumeClient,
                    C.Telefon,
                    C.Tip_Client,
                    CA.Data_Cerere,
                    CA.Data_Preluare,
                    CA.Mesaj_Client
                FROM Cereri_Achizitie CA
                INNER JOIN Masini_Stoc MS ON CA.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                INNER JOIN Clienti C ON CA.ID_Client = C.ID_Client
                WHERE CA.Status_Cerere = 'Preluata' AND CA.ID_Vanzator_Preluat = ?
                ORDER BY CA.Data_Preluare DESC;
            """
            cursor.execute(sql_cereri_preluate, (id_angajat,))
            cereri_preluate = cursor.fetchall()
            
            sql_masini = """
                SELECT 
                    MS.VIN,
                    M.Marca + ' ' + M.Nume_Model + ' (' + MS.Culoare_Exterior + ')' AS Descriere,
                    MS.Pret
                FROM Masini_Stoc MS
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                WHERE MS.Status_Vanzare = 'Disponibil'
                ORDER BY M.Marca, M.Nume_Model;
            """
            cursor.execute(sql_masini)
            masini = cursor.fetchall()
            
            sql_clienti = """
                SELECT 
                    ID_Client,
                    Nume + ' ' + Prenume + ' (' + Tip_Client + ')' AS NumeComplet
                FROM Clienti
                ORDER BY Nume, Prenume;
            """
            cursor.execute(sql_clienti)
            clienti = cursor.fetchall()
            
        except Exception as e:
            print(f"Eroare: {e}")
        finally:
            conn.close()
    
    return render_template('vanzare_noua_angajat.html', logged_in=True, username=session.get('username'),rol=session.get('rol'), cereri_disponibile=cereri_disponibile, cereri_preluate=cereri_preluate, masini=masini, clienti=clienti)

@app.route('/cerere/preia/<int:id_cerere>', methods=['POST'])
def preia_cerere(id_cerere):
    if not session.get('logged_in') or session.get('rol') != 'Vanzator':
        return redirect(url_for('dashboard'))
    
    id_angajat = session.get('id_angajat')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT Status_Cerere FROM Cereri_Achizitie WHERE ID_Cerere = ?
            """, (id_cerere,))
            
            result = cursor.fetchone()
            if not result or result[0] != 'In Asteptare':
                flash('Cererea nu mai este disponibilă (a fost preluată de alt vânzător).', 'error')
                return redirect(url_for('route_vanzare_noua'))
            
            sql = """
                UPDATE Cereri_Achizitie 
                SET Status_Cerere = 'Preluata', 
                    ID_Vanzator_Preluat = ?, 
                    Data_Preluare = GETDATE()
                WHERE ID_Cerere = ? AND Status_Cerere = 'In Asteptare';
            """
            cursor.execute(sql, (id_angajat, id_cerere))
            
            if cursor.rowcount == 0:
                flash('Cererea a fost preluată de alt vânzător.', 'error')
            else:
                conn.commit()
                flash('Ai preluat cererea cu succes! Contactează clientul pentru finalizare.', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_vanzare_noua'))


@app.route('/cerere/finalizeaza/<int:id_cerere>', methods=['POST'])
def finalizeaza_cerere(id_cerere):
    if not session.get('logged_in') or session.get('rol') != 'Vanzator':
        return redirect(url_for('dashboard'))
    
    id_angajat = session.get('id_angajat')
    pret_final = request.form.get('pret_final')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ID_Client, VIN_Masina 
                FROM Cereri_Achizitie 
                WHERE ID_Cerere = ? AND ID_Vanzator_Preluat = ? AND Status_Cerere = 'Preluata'
            """, (id_cerere, id_angajat))
            
            result = cursor.fetchone()
            if not result:
                flash('Cererea nu a fost găsită sau nu îți aparține.', 'error')
                return redirect(url_for('route_vanzare_noua'))
            
            id_client = result[0]
            vin = result[1]
            
            sql_vanzare = """
                INSERT INTO Vanzari (VIN_Masina, ID_Client, ID_Angajat, Data_Vanzare, Pret_Final)
                VALUES (?, ?, ?, GETDATE(), ?);
            """
            cursor.execute(sql_vanzare, (vin, id_client, id_angajat, pret_final))
            
            cursor.execute("""
                UPDATE Masini_Stoc SET Status_Vanzare = 'Vandut' WHERE VIN = ?
            """, (vin,))
            
            cursor.execute("""
                UPDATE Cereri_Achizitie SET Status_Cerere = 'Finalizata' WHERE ID_Cerere = ?
            """, (id_cerere,))
            
            conn.commit()
            flash('Vânzarea a fost înregistrată cu succes!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare la finalizarea vânzării: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_vanzare_noua'))


@app.route('/cerere/renunta/<int:id_cerere>', methods=['POST'])
def renunta_cerere(id_cerere):
    if not session.get('logged_in') or session.get('rol') != 'Vanzator':
        return redirect(url_for('dashboard'))
    
    id_angajat = session.get('id_angajat')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ID_Cerere FROM Cereri_Achizitie 
                WHERE ID_Cerere = ? AND ID_Vanzator_Preluat = ? AND Status_Cerere = 'Preluata'
            """, (id_cerere, id_angajat))
            
            if not cursor.fetchone():
                flash('Nu poți renunța la această cerere.', 'error')
                return redirect(url_for('route_vanzare_noua'))
            
            sql = """
                UPDATE Cereri_Achizitie 
                SET Status_Cerere = 'In Asteptare', 
                    ID_Vanzator_Preluat = NULL, 
                    Data_Preluare = NULL
                WHERE ID_Cerere = ?;
            """
            cursor.execute(sql, (id_cerere,))
            conn.commit()
            flash('Ai renunțat la cerere. A fost pusă înapoi în lista de așteptare.', 'info')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_vanzare_noua'))

@app.route('/vanzare_directa', methods=['POST'])
def vanzare_directa():
    if not session.get('logged_in') or session.get('rol') != 'Vanzator':
        return redirect(url_for('dashboard'))
    
    id_angajat = session.get('id_angajat')
    vin_masina = request.form.get('vin_masina')
    id_client = request.form.get('id_client')
    pret_final = request.form.get('pret_final')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()

            sql_vanzare = """
                INSERT INTO Vanzari (VIN_Masina, ID_Client, ID_Angajat, Data_Vanzare, Pret_Final)
                VALUES (?, ?, ?, GETDATE(), ?);
            """
            cursor.execute(sql_vanzare, (vin_masina, id_client, id_angajat, pret_final))
            
            cursor.execute("""
                UPDATE Masini_Stoc SET Status_Vanzare = 'Vandut' WHERE VIN = ?
            """, (vin_masina,))
            
            conn.commit()
            flash('Vânzarea a fost înregistrată cu succes!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_vanzare_noua'))

@app.route('/performante_proprii', methods=['GET'])
def route_performante_proprii():
    if not session.get('logged_in') or session.get('rol') != 'Vanzator':
        return redirect(url_for('dashboard'))
    
    vanzari = []
    total_vanzari = 0
    id_angajat = session.get('id_angajat')
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            sql = """
                SELECT 
                    V.ID_Vanzare,
                    V.Data_Vanzare,
                    M.Marca + ' ' + M.Nume_Model AS Masina,
                    C.Nume + ' ' + C.Prenume AS Client,
                    V.Pret_Final
                FROM Vanzari V
                INNER JOIN Masini_Stoc MS ON V.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                INNER JOIN Clienti C ON V.ID_Client = C.ID_Client
                WHERE V.ID_Angajat = ?
                ORDER BY V.Data_Vanzare DESC;
            """
            cursor.execute(sql, (id_angajat,))
            vanzari = cursor.fetchall()
            for v in vanzari:
                total_vanzari += float(v[4]) if v[4] else 0
            
        except Exception as e:
            print(f"Eroare: {e}")
        finally:
            conn.close()
    
    return render_template('performanta_angajat.html', logged_in=True, username=session.get('username'), rol=session.get('rol'), vanzari=vanzari, total=total_vanzari)

@app.route('/istoric_tranzactii', methods=['GET'])
def route_istoric_tranzactii():
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    tranzactii = []
    plati = []
    id_client = session.get('id_client')
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            sql_tranzactii = """
                SELECT 
                    V.ID_Vanzare,
                    V.Data_Vanzare,
                    M.Marca + ' ' + M.Nume_Model AS Masina,
                    MS.Culoare_Exterior,
                    A.Nume + ' ' + A.Prenume AS Vanzator,
                    V.Pret_Final,
                    CASE WHEN P.ID_Plata IS NOT NULL THEN 1 ELSE 0 END AS Platit
                FROM Vanzari V
                INNER JOIN Masini_Stoc MS ON V.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                INNER JOIN Angajati A ON V.ID_Angajat = A.ID_Angajat
                LEFT JOIN Plati P ON V.ID_Vanzare = P.ID_Vanzare
                WHERE V.ID_Client = ?
                ORDER BY V.Data_Vanzare DESC;
            """
            cursor.execute(sql_tranzactii, (id_client,))
            tranzactii = cursor.fetchall()
            sql_plati = """
                SELECT 
                    P.ID_Plata,
                    P.Data_Platii,
                    P.Suma_Platita,
                    P.Metoda_Plata,
                    M.Marca + ' ' + M.Nume_Model AS MasinaPlata
                FROM Plati P
                INNER JOIN Vanzari V ON P.ID_Vanzare = V.ID_Vanzare
                INNER JOIN Masini_Stoc MS ON V.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                WHERE V.ID_Client = ?
                ORDER BY P.Data_Platii DESC;
            """
            cursor.execute(sql_plati, (id_client,))
            plati = cursor.fetchall()
            
        except Exception as e:
            print(f"Eroare: {e}")
        finally:
            conn.close()
    
    return render_template('tranzactii_client.html', logged_in=True, username=session.get('username'), rol=session.get('rol'), tranzactii=tranzactii, plati=plati)

@app.route('/plata/<int:id_vanzare>', methods=['POST'])
def proceseaza_plata(id_vanzare):
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    id_client = session.get('id_client')
    metoda_plata = request.form.get('metoda_plata', 'Card')
    
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT V.Pret_Final 
                FROM Vanzari V
                LEFT JOIN Plati P ON V.ID_Vanzare = P.ID_Vanzare
                WHERE V.ID_Vanzare = ? AND V.ID_Client = ? AND P.ID_Plata IS NULL
            """, (id_vanzare, id_client))
            
            result = cursor.fetchone()
            if not result:
                flash('Plata nu poate fi procesată.', 'error')
                return redirect(url_for('route_istoric_tranzactii'))
            
            pret_final = result[0]
            
            cursor.execute("""
                INSERT INTO Plati (ID_Vanzare, Data_Platii, Suma_Platita, Metoda_Plata)
                VALUES (?, GETDATE(), ?, ?)
            """, (id_vanzare, pret_final, metoda_plata))
            
            conn.commit()
            flash('Plata a fost înregistrată cu succes!', 'success')
            
        except Exception as e:
            conn.rollback()
            flash(f'Eroare la procesarea plății: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('route_istoric_tranzactii'))

@app.route('/rapoarte', methods=['GET'])
def route_rapoarte_complexe():
    if not session.get('logged_in') or session.get('rol') != 'Admin':
        return redirect(url_for('dashboard'))
    
    filtru_an = request.args.get('an', '')
    filtru_luna = request.args.get('luna', '')
    filtru_pret_min = request.args.get('pret_min', '')
    filtru_pret_max = request.args.get('pret_max', '')
    
    rapoarte = {}
    conn = get_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
            sql_top_marci = """
                SELECT TOP 3
                    M.Marca,
                    COUNT(V.ID_Vanzare) AS NumarVanzari,
                    SUM(V.Pret_Final) AS ValoareTotala
                FROM Vanzari V
                INNER JOIN Masini_Stoc MS ON V.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                GROUP BY M.Marca
                ORDER BY NumarVanzari DESC;
            """
            cursor.execute(sql_top_marci)
            rapoarte['top_marci'] = cursor.fetchall()
            
# ============================================================
# INTEROGARE COMPLEXA #1: Angajati cu performante peste medie
# Foloseste subcerere in HAVING pentru a compara cu media
# ============================================================

            sql_angajati_performanti = """
                SELECT 
                    A.Nume + ' ' + A.Prenume AS Angajat,
                    COUNT(V.ID_Vanzare) AS NrVanzari,
                    SUM(V.Pret_Final) AS TotalVanzari
                FROM Angajati A
                INNER JOIN Vanzari V ON A.ID_Angajat = V.ID_Angajat
                GROUP BY A.ID_Angajat, A.Nume, A.Prenume
                HAVING SUM(V.Pret_Final) > (
                    SELECT AVG(SubTotal) 
                    FROM (
                        SELECT SUM(Pret_Final) AS SubTotal
                        FROM Vanzari
                        GROUP BY ID_Angajat
                    ) AS AvgPerAngajat
                )
                ORDER BY TotalVanzari DESC;
            """
            cursor.execute(sql_angajati_performanti)
            rapoarte['angajati_performanti'] = cursor.fetchall()

# ============================================================
# INTEROGARE COMPLEXA #2: Masini peste pretul mediu al marcii
# Foloseste 2 subcereri corelate (in SELECT si WHERE)
# Parametru variabil: filtru_an (anul intrarii in stoc)
# ============================================================

            if filtru_an:
                sql_masini_premium = """
                    SELECT 
                        M.Marca,
                        M.Nume_Model,
                        MS.Pret,
                        (SELECT AVG(MS2.Pret) 
                         FROM Masini_Stoc MS2 
                         INNER JOIN Modele_Auto M2 ON MS2.ID_Model = M2.ID_Model
                         WHERE M2.Marca = M.Marca) AS PretMediuMarca
                    FROM Masini_Stoc MS
                    INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                    WHERE MS.Pret > (
                        SELECT AVG(MS3.Pret) 
                        FROM Masini_Stoc MS3 
                        INNER JOIN Modele_Auto M3 ON MS3.ID_Model = M3.ID_Model
                        WHERE M3.Marca = M.Marca
                    )
                    AND YEAR(MS.Data_Intrare_Stoc) = ?
                    ORDER BY M.Marca, MS.Pret DESC;
                """
                cursor.execute(sql_masini_premium, (int(filtru_an),))
            else:
                sql_masini_premium = """
                    SELECT 
                        M.Marca,
                        M.Nume_Model,
                        MS.Pret,
                        (SELECT AVG(MS2.Pret) 
                         FROM Masini_Stoc MS2 
                         INNER JOIN Modele_Auto M2 ON MS2.ID_Model = M2.ID_Model
                         WHERE M2.Marca = M.Marca) AS PretMediuMarca
                    FROM Masini_Stoc MS
                    INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                    WHERE MS.Pret > (
                        SELECT AVG(MS3.Pret) 
                        FROM Masini_Stoc MS3 
                        INNER JOIN Modele_Auto M3 ON MS3.ID_Model = M3.ID_Model
                        WHERE M3.Marca = M.Marca
                    )
                    ORDER BY M.Marca, MS.Pret DESC;
                """
                cursor.execute(sql_masini_premium)
            
            rapoarte['masini_premium'] = cursor.fetchall()

            conditii = []
            parametri = []
            
# ==============================================================================================
# INTEROGARE SIMPLA: Statistici vanzari cu parametri variabili
# Parametri: filtru_an, filtru_luna, filtru_pret_min, filtru_pret_max pentru "sql_statistici_base"
# ===============================================================================================

            sql_statistici_base = """
                SELECT 
                    YEAR(V.Data_Vanzare) AS An,
                    MONTH(V.Data_Vanzare) AS Luna,
                    COUNT(V.ID_Vanzare) AS NrVanzari,
                    SUM(V.Pret_Final) AS TotalVanzari,
                    AVG(V.Pret_Final) AS PretMediu,
                    MIN(V.Pret_Final) AS PretMinim,
                    MAX(V.Pret_Final) AS PretMaxim
                FROM Vanzari V
            """
            
            if filtru_an:
                conditii.append("YEAR(V.Data_Vanzare) = ?")
                parametri.append(int(filtru_an))
            
            if filtru_luna:
                conditii.append("MONTH(V.Data_Vanzare) = ?")
                parametri.append(int(filtru_luna))
            
            if filtru_pret_min:
                conditii.append("V.Pret_Final >= ?")
                parametri.append(float(filtru_pret_min))
            
            if filtru_pret_max:
                conditii.append("V.Pret_Final <= ?")
                parametri.append(float(filtru_pret_max))
            
            if conditii:
                sql_statistici_base += " WHERE " + " AND ".join(conditii)
            
            sql_statistici_base += """
                GROUP BY YEAR(V.Data_Vanzare), MONTH(V.Data_Vanzare)
                ORDER BY An DESC, Luna DESC;
            """
            
            cursor.execute(sql_statistici_base, parametri)
            rapoarte['statistici_perioada'] = cursor.fetchall()
            
            sql_clienti_fideli = """
                SELECT 
                    C.Nume + ' ' + C.Prenume AS Client,
                    C.Tip_Client,
                    COUNT(V.ID_Vanzare) AS NrAchizitii,
                    SUM(V.Pret_Final) AS TotalCheltuit
                FROM Clienti C
                INNER JOIN Vanzari V ON C.ID_Client = V.ID_Client
                GROUP BY C.ID_Client, C.Nume, C.Prenume, C.Tip_Client
                HAVING COUNT(V.ID_Vanzare) > 1
                ORDER BY NrAchizitii DESC, TotalCheltuit DESC;
            """
            cursor.execute(sql_clienti_fideli)
            rapoarte['clienti_fideli'] = cursor.fetchall()
            
            sql_marja_profit = """
                SELECT 
                    M.Marca,
                    COUNT(V.ID_Vanzare) AS NrVandute,
                    SUM(MS.Cost_Achizitie) AS CostTotal,
                    SUM(V.Pret_Final) AS VenitTotal,
                    SUM(V.Pret_Final) - SUM(MS.Cost_Achizitie) AS ProfitBrut,
                    CAST(
                        ((SUM(V.Pret_Final) - SUM(MS.Cost_Achizitie)) * 100.0 / 
                        NULLIF(SUM(MS.Cost_Achizitie), 0)) AS DECIMAL(10,2)
                    ) AS MarjaProcentuala
                FROM Vanzari V
                INNER JOIN Masini_Stoc MS ON V.VIN_Masina = MS.VIN
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                GROUP BY M.Marca
                ORDER BY ProfitBrut DESC;
            """
            cursor.execute(sql_marja_profit)
            rapoarte['marja_profit'] = cursor.fetchall()
            
        except Exception as e:
            print(f"Eroare la generarea rapoartelor: {e}")
            rapoarte['error'] = str(e)
        finally:
            conn.close()
    
    return render_template('rapoarte_admin.html', logged_in=True, username=session.get('username'), rol=session.get('rol'), rapoarte=rapoarte, filtru_an=filtru_an, filtru_luna=filtru_luna, filtru_pret_min=filtru_pret_min, filtru_pret_max=filtru_pret_max)

@app.route('/interes_modele', methods=['GET', 'POST'])
def route_interes_modele():
    if not session.get('logged_in') or session.get('rol') != 'Client':
        return redirect(url_for('dashboard'))
    
    modele_interes = []
    modele_disponibile = []
    id_client = session.get('id_client')
    
    conn = get_connection()
    
    if conn:
        try:
            cursor = conn.cursor()
# ============================================================
# INTEROGARE COMPLEXA #3: Modele de interes cu disponibilitate
# Foloseste subcerere corelata in SELECT pentru VIN disponibil
# ============================================================
            sql_interes = """
                SELECT 
                    M.ID_Model,
                    M.Marca,
                    M.Nume_Model,
                    M.Tip_Caroserie,
                    M.Combustibil,
                    M.Putere,
                    (SELECT TOP 1 MS.VIN 
                     FROM Masini_Stoc MS 
                     WHERE MS.ID_Model = M.ID_Model AND MS.Status_Vanzare = 'Disponibil') AS VIN_Disponibil
                FROM Clienti_Modele_Auto CM
                INNER JOIN Modele_Auto M ON CM.ID_Model = M.ID_Model
                WHERE CM.ID_Client = ?
                ORDER BY M.Marca, M.Nume_Model;
            """
            cursor.execute(sql_interes, (id_client,))
            modele_interes = cursor.fetchall()
            
# ============================================================
# INTEROGARE COMPLEXA #4: Modele disponibile pentru adaugare
# Foloseste subcerere cu NOT IN în WHERE
# ============================================================   
        
            sql_disponibile = """
                SELECT 
                    M.ID_Model,
                    M.Marca + ' ' + M.Nume_Model AS NumeComplet
                FROM Modele_Auto M
                WHERE M.ID_Model NOT IN (
                    SELECT ID_Model FROM Clienti_Modele_Auto WHERE ID_Client = ?
                )
                ORDER BY M.Marca, M.Nume_Model;
            """
            cursor.execute(sql_disponibile, (id_client,))
            modele_disponibile = cursor.fetchall()
            
            if request.method == 'POST':
                actiune = request.form.get('actiune')
                id_model = request.form.get('id_model')
                
                if actiune == 'adauga' and id_model:
                    sql_insert = "INSERT INTO Clienti_Modele_Auto (ID_Client, ID_Model) VALUES (?, ?);"
                    cursor.execute(sql_insert, (id_client, id_model))
                    conn.commit()
                    flash('Modelul a fost adăugat la lista de interes!', 'success')
                    
                elif actiune == 'sterge' and id_model:
                    sql_delete = "DELETE FROM Clienti_Modele_Auto WHERE ID_Client = ? AND ID_Model = ?;"
                    cursor.execute(sql_delete, (id_client, id_model))
                    conn.commit()
                    flash('Modelul a fost eliminat din lista de interes!', 'success')
                
                return redirect(url_for('route_interes_modele'))
            
        except Exception as e:
            print(f"Eroare: {e}")
            flash(f'Eroare: {e}', 'error')
        finally:
            conn.close()
    
    return render_template('interes_modele.html',logged_in=True, username=session.get('username'),  rol=session.get('rol'), modele_interes=modele_interes, modele_disponibile=modele_disponibile)

@app.route('/search', methods=['GET'])
def search_results():
    search_query = request.args.get('query')
    results = []
    
    if search_query:
        conn = get_connection()
        if conn is None:
            return "Eroare BD la căutare.", 500
        
        try:
            cursor = conn.cursor()
            sql = """
                SELECT 
                    M.Marca,
                    M.Nume_Model, 
                    MS.VIN, 
                    M.Tip_Caroserie, 
                    MS.Culoare_Exterior, 
                    MS.Pret, 
                    MS.Status_Vanzare
                FROM Masini_Stoc MS
                INNER JOIN Modele_Auto M ON MS.ID_Model = M.ID_Model
                WHERE M.Nume_Model LIKE ? 
                   OR M.Marca LIKE ? 
                   OR MS.VIN LIKE ?
                   OR MS.Culoare_Exterior LIKE ?
                ORDER BY M.Marca, M.Nume_Model;
            """
            search_term = '%' + search_query + '%'
            cursor.execute(sql, (search_term, search_term, search_term, search_term))
            results = cursor.fetchall()
            
        except pyodbc.Error as ex:
            return f"Eroare SQL la executarea căutării: {ex}", 500
        finally:
            conn.close()

    return render_template('search.html', query=search_query, results=results)

@app.route('/api/modele/<marca>')
def api_modele_marca(marca):
    conn = get_connection()
    modele = []
    
    if conn:
        try:
            cursor = conn.cursor()
            sql = """
                SELECT ID_Model, Nume_Model 
                FROM Modele_Auto 
                WHERE Marca = ?
                ORDER BY Nume_Model;
            """
            cursor.execute(sql, (marca,))
            modele = [{'id': row[0], 'nume': row[1]} for row in cursor.fetchall()]
        except Exception as e:
            print(f"Eroare API: {e}")
        finally:
            conn.close()
    
    return jsonify(modele)

@app.route('/about')
def about():
    return render_template('about.html',logged_in=session.get('logged_in'), username=session.get('username'), rol=session.get('rol'))

if __name__ == '__main__':
    app.run(debug=True)