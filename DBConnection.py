import mysql.connector

def create_db_connection(host_name, user_name, user_password, db_name):
    connection = None
    try:
        connection = mysql.connector.connect(
            host=host_name,
            user=user_name,
            passwd=user_password,
            database=db_name
        )
        print("MySQL Database connection successful")
    except Exception as err:
        print(f"Error: '{err}'")

    return connection

def execute_sql_statement(connection:mysql.connector.CMySQLConnection, query):
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        connection.commit()
        print("SQL statement executed successfully")
    except Exception as err:
        print(f"Error: '{err}'")
    finally:
        if cursor:
            cursor.close()

# Beispiel für die Verwendung der Funktionen
connection = create_db_connection("localhost", "your_username", "your_password", "testdb")