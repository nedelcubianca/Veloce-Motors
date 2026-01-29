# 🚗 Veloce Motors

**Sistem de Gestiune pentru Dealer Auto** - Proiect Baze de Date

## 📋 Descriere

Veloce Motors este o aplicație web completă pentru digitalizarea operațiunilor unui dealer auto. Sistemul permite administrarea stocului de vehicule, gestionarea clienților, procesarea vânzărilor și generarea rapoartelor.

## 🛠️ Tehnologii

| Componenta | Tehnologie |
|------------|------------|
| Backend | Python 3.x + Flask |
| Baza de date | Microsoft SQL Server |
| Conectivitate | PyODBC |
| Frontend | HTML5, CSS3, JavaScript |
| Template Engine | Jinja2 |

## 👥 Roluri Utilizatori

- **Administrator** - Gestiune angajați, stoc, rapoarte
- **Vânzător** - Procesare cereri, vânzări directe, performanțe
- **Client** - Navigare catalog, coș, cereri achiziție, plăți

## 🗄️ Structura Bazei de Date

**10 tabele:**
- `Angajati`, `Clienti`, `Utilizatori`
- `Modele_Auto`, `Masini_Stoc`
- `Vanzari`, `Plati`
- `Cereri_Achizitie`, `Cos_Client`
- `Clienti_Modele_Auto` (relație N:N)

**Relații:**
- 2 relații 1:1
- 8 relații 1:N  
- 1 relație N:N

## 🚀 Instalare

1. **Clonează repository-ul**
```bash
git clone https://github.com/USERNAME/veloce-motors.git
cd veloce-motors
```

2. **Instalează dependențele**
```bash
pip install flask pyodbc
```

3. **Configurează conexiunea la baza de date**

Editează `conexiune.py` cu datele tale:
```python
CONNECTION_STRING = (
    r"DRIVER={ODBC Driver 17 for SQL Server};"
    r"SERVER=localhost\SQLEXPRESS;"
    r"DATABASE=Vanzare Masini Dealer Auto;"
    r"Trusted_Connection=yes;"
)
```

4. **Importă baza de date**

Rulează scriptul `database.sql` în SQL Server Management Studio.

5. **Pornește aplicația**
```bash
python app.py
```

6. **Accesează în browser**
```
http://localhost:5000
```

## 📁 Structura Proiectului

```
veloce-motors/
├── app.py              # Aplicația Flask principală
├── conexiune.py        # Configurare conexiune BD
├── database.sql        # Script creare bază de date
├── templates/          # Template-uri HTML
│   ├── app.html
│   ├── home.html
│   ├── auth.html
│   └── ...
├── static/             # CSS, JS, imagini
│   └── css/
│       └── style.css
└── assets/             # Resurse adiționale
```

## 📊 Funcționalități Principale

### Administrator
- ✅ CRUD Angajați (cu creare automată cont)
- ✅ CRUD Stoc Mașini (cu creare automată model)
- ✅ Rapoarte: Top mărci, angajați performanți, mașini premium, marja profit

### Vânzător
- ✅ Vizualizare și preluare cereri
- ✅ Finalizare vânzări
- ✅ Vânzări directe
- ✅ Istoric performanțe proprii

### Client
- ✅ Navigare catalog pe mărci
- ✅ Căutare vehicule
- ✅ Coș de cumpărături
- ✅ Trimitere cereri de achiziție
- ✅ Efectuare plăți (Card/Cash/Transfer)
- ✅ Liste de modele favorite

## 📝 Documentație

Documentația completă se găsește în fișierul `Documentatie_Veloce_Motors.pdf`.

## 👩‍💻 Autor

**Nedelcu Bianca-Nicoleta**  
Universitatea Politehnica din București  
Facultatea de Automatică și Calculatoare

---

*Proiect realizat pentru cursul de Baze de Date, 2025*
