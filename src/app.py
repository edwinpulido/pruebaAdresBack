from flask import Flask, request, jsonify
from flask_cors import CORS
import pyodbc

app = Flask(__name__)
CORS(app)

# --- Configuración de la conexión a SQL Server ---
SERVER = 'EDWIN'
DATABASE = 'requerimientos'
CONNECTION_STRING = f'DRIVER={{SQL Server}};SERVER={SERVER};DATABASE={DATABASE};Trusted_Connection=yes;'

def get_db_connection():
    try:
        connection = pyodbc.connect(CONNECTION_STRING)
        return connection
    except Exception as ex:
        print(f"Error al conectar a la base de datos: {ex}")
        return None

# GET - Listar todos los requerimientos con filtros opcionales
@app.route('/requerimientos', methods=['GET'])
def listar_requerimientos():
    connection = get_db_connection()
    requerimientos = []
    if connection:
        cursor = connection.cursor()
        sql = "SELECT * FROM Requerimientos WHERE activo=1"
        params = []

        if request.args.get('presupuesto'):
            sql += " AND presupuesto LIKE ?"
            params.append(f"%{request.args.get('presupuesto')}%")
        if request.args.get('unidad'):
            sql += " AND unidad LIKE ?"
            params.append(f"%{request.args.get('unidad')}%")
        if request.args.get('tipo_bien_servicio'):
            sql += " AND tipo_bien_servicio LIKE ?"
            params.append(f"%{request.args.get('tipo_bien_servicio')}%")
        if request.args.get('fecha_adquisicion'):
            sql += " AND CAST(fecha_adquisicion AS DATE) = ?"
            params.append(request.args.get('fecha_adquisicion'))
        if request.args.get('proveedor'):
            sql += " AND proveedor LIKE ?"
            params.append(f"%{request.args.get('proveedor')}%")

        cursor.execute(sql, params)
        columns = [column[0] for column in cursor.description]
        for row in cursor.fetchall():
            requerimientos.append(dict(zip(columns, row)))
        cursor.close()
        connection.close()
        return jsonify(requerimientos)
    return jsonify({'mensaje': 'Error al conectar a la base de datos'}), 500

# GET - Obtener un requerimiento por ID
@app.route('/requerimientos/<int:id>', methods=['GET'])
def obtener_requerimiento(id):
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        print(f"Tipo del objeto cursor: {type(cursor)}")
        cursor.execute("SELECT id, presupuesto, unidad, tipo_bien_servicio, cantidad, valor_unitario, valor_total, fecha_adquisicion, proveedor, documentacion,  activo FROM Requerimientos WHERE id = ?", id)

        columns = None
        if hasattr(cursor, 'description'):
            columns = [column[0] for column in cursor.description]
        else:
            print("¡Advertencia! El objeto cursor no tiene el atributo 'description'.")
            cursor.close()
            connection.close()
            return jsonify({'mensaje': 'Error al obtener descripción de columnas'}), 500

        row = cursor.fetchone()
        cursor.close()
        connection.close()

        if row:
            requerimiento = dict(zip(columns, row))
            if requerimiento.get('fecha_adquisicion'):
                requerimiento['fecha_adquisicion'] = requerimiento['fecha_adquisicion'].isoformat()
            return jsonify(requerimiento)
        return jsonify({'mensaje': 'Requerimiento no encontrado'}), 404
    return jsonify({'mensaje': 'Error al conectar a la base de datos'}), 500


# GET - Obtener el historial de modificaciones de un requerimiento por ID
@app.route('/requerimientos/<int:id>/historial', methods=['GET'])
def obtener_historial_requerimiento(id):
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT id, fecha_cambio, detalles
            FROM HistorialRequerimientos
            WHERE requerimientos_id = ?
            ORDER BY fecha_cambio DESC
        """, id)
        columns = [column[0] for column in cursor.description]
        historial = []
        for row in cursor.fetchall():
            historial.append(dict(zip(columns, row)))
        cursor.close()
        connection.close()
        return jsonify(historial)
    return jsonify({'mensaje': 'Error al conectar a la base de datos'}), 500

# POST - Crear un nuevo requerimiento
@app.route('/requerimientos', methods=['POST'])
def crear_requerimiento():
    data = request.get_json()
    if not data or 'presupuesto' not in data or 'unidad' not in data or \
            'tipoBienServicio' not in data or 'cantidad' not in data or \
            'valorUnitario' not in data or 'proveedor' not in data:
        return jsonify({'mensaje': 'Datos incompletos'}), 400

    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO Requerimientos (presupuesto, unidad, tipo_bien_servicio, cantidad, valor_unitario, valor_total, proveedor, documentacion, activo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (data['presupuesto'], data['unidad'], data['tipoBienServicio'], data['cantidad'], data['valorUnitario'], data.get('valor_total'), data['proveedor'], data.get('documentacion')))
            connection.commit()
            cursor.execute("SELECT TOP 1 id, presupuesto, unidad, tipo_bien_servicio, cantidad, valor_unitario, valor_total, proveedor, documentacion FROM Requerimientos ORDER BY id DESC")
            print(f"Datos recibidos para crear requerimiento: {data}")
            nuevo_requerimiento = cursor.fetchone()
            columns = [column[0] for column in cursor.description]
            return jsonify(dict(zip(columns, nuevo_requerimiento))), 201
        except Exception as ex:
            connection.rollback()
            return jsonify({'mensaje': f'Error al crear el requerimiento: {ex}'}), 500
        finally:
            cursor.close()
            connection.close()
    return jsonify({'mensaje': 'Error al conectar a la base de datos'}), 500

# PUT - Actualizar un requerimiento existente
@app.route('/requerimientos/<int:id>', methods=['PUT'])
def actualizar_requerimiento(id):
    data = request.get_json()
    if not data:
        return jsonify({'mensaje': 'No se proporcionaron datos para actualizar'}), 400

    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            set_clauses = []
            params = []
            for key, value in data.items():
                if key in ['presupuesto', 'unidad', 'tipoBienServicio', 'cantidad', 'valorUnitario', 'valorTotal', 'proveedor', 'documentacion']:
                    set_clauses.append(f"{key} = ?")
                    params.append(value)
            params.append(id)
            sql = f"UPDATE Requerimientos SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(sql, params)
            if cursor.rowcount > 0:
                connection.commit()
                cursor.execute("SELECT id, presupuesto, unidad, tipo_bien_servicio, cantidad, valor_unitario, valor_total, proveedor, documentacion FROM Requerimientos WHERE id = ?", id)
                updated_requerimiento = cursor.fetchone()
                columns = [column[0] for column in cursor.description]
                return jsonify(dict(zip(columns, updated_requerimiento)))
            else:
                return jsonify({'mensaje': 'Requerimiento no encontrado'}), 404
        except Exception as ex:
            connection.rollback()
            return jsonify({'mensaje': f'Error al actualizar el requerimiento: {ex}'}), 500
        finally:
            cursor.close()
            connection.close()
    return jsonify({'mensaje': 'Error al conectar a la base de datos'}), 500

# PUT - Desactivar un requerimiento
@app.route('/requerimientos/desactivar/<int:id>', methods=['PUT'])
def desactivar_requerimiento(id):
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            cursor.execute("UPDATE Requerimientos SET activo = 0 WHERE id = ?", id)
            if cursor.rowcount > 0:
                connection.commit()
                return jsonify({'mensaje': f'Requerimiento con ID {id} desactivado'})
            else:
                return jsonify({'mensaje': 'Requerimiento no encontrado'}), 404
        except Exception as ex:
            connection.rollback()
            return jsonify({'mensaje': f'Error al desactivar el requerimiento: {ex}'}), 500
        finally:
            cursor.close()
            connection.close()
    return jsonify({'mensaje': 'Error al conectar a la base de datos'}), 500

@app.route('/')
def index():
    return "¡Hola desde Flask!"

if __name__ == '__main__':
    app.run(debug=True)