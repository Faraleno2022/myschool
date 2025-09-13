#!/usr/bin/env python3
"""
Script simple pour tester la connexion MySQL
"""
import pymysql

def test_connection():
    try:
        print("Tentative de connexion à MySQL...")
        
        connection = pymysql.connect(
            host='myschoolgn.mysql.pythonanywhere-services.com',
            user='myschoolgn',
            password='Faraleno1994@',
            database='myschoolgn$myschooldb',
            port=3306,
            charset='utf8mb4',
            connect_timeout=10
        )
        
        print("✅ Connexion MySQL réussie!")
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"Version MySQL: {version[0]}")
            
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print(f"Nombre de tables: {len(tables)}")
            
            if tables:
                print("Tables trouvées:")
                for table in tables[:5]:  # Afficher les 5 premières
                    print(f"  - {table[0]}")
        
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"❌ Erreur MySQL: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        return False

if __name__ == "__main__":
    test_connection()
