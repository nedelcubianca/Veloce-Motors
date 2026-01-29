import pyodbc
CONNECTION_STRING = (
    r"DRIVER={ODBC Driver 11 for SQL Server};"
    r"SERVER=(local)\SQLEXPRESS;"
    r"DATABASE=Vanzare Masini Dealer Auto;"   
    r"Trusted_Connection=yes;"                
)

def get_connection():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        return conn
    except pyodbc.Error as ex:
        error_details = ex.args[0]
        
        print(f"\nEROARE CRITICA DE CONEXIUNE LA BAZA DE DATE!")
        print(f"Server: LAPTOP-BIANCA\\SQLEXPRESS, Driver: ODBC Driver 11")
        print(f"Detaliu eroare SQL: {error_details}")
           
        return None