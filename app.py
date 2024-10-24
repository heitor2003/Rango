from flask import Flask, render_template, request, redirect, url_for
from pymongo import MongoClient
from geopy.distance import geodesic

app = Flask(__name__)

# Conectando ao MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["RangoDB"]
restaurantes_col = db["restaurantes"]
reservas_col = db["reservas"]
usuarios_col = db["usuarios"]

@app.route('/')
def index():
    restaurantes = list(restaurantes_col.find())
    print(restaurantes)
    return render_template('index.html', restaurantes=restaurantes)

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/pesquisa', methods=['GET', 'POST'])
def pesquisa():
    if request.method == 'POST':
        nome = request.form.get('nome')
        tipo_cozinha = request.form.get('tipo_cozinha')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        query = {}

        # Busca por nome
        if nome:
            query['name'] = {'$regex': nome, '$options': 'i'}

        # Filtro por tipo de cozinha
        if tipo_cozinha:
            query['cuisine'] = tipo_cozinha

        # Consulta básica com os filtros aplicados
        restaurantes = list(restaurantes_col.find(query))

        # Se coordenadas são fornecidas, filtrar por proximidade
        if latitude and longitude:
            coord_usuario = (float(latitude), float(longitude))
            restaurantes = [r for r in restaurantes if 'coord' in r['address'] and geodesic(coord_usuario, (r['address']['coord'][1], r['address']['coord'][0])).km <= 5]

        return render_template('pesquisa.html', restaurantes=restaurantes)

    return render_template('pesquisa.html', restaurantes=[])

@app.route('/reservar/<restaurante_id>', methods=['GET', 'POST'])
def reservar(restaurante_id):
    if request.method == 'POST':
        nome_usuario = request.form['nome']
        horario = request.form['horario']
        reserva = {
            'nome_usuario': nome_usuario,
            'restaurante_id': restaurante_id,
            'horario': horario
        }
        reservas_col.insert_one(reserva)
        return redirect(url_for('confirmacao'))
 
    # Exibir detalhes do restaurante
    restaurante = restaurantes_col.find_one({'restaurant_id': restaurante_id})
    return render_template('reservar.html', restaurante=restaurante)
 
@app.route('/confirmacao')
def confirmacao():
    return "Reserva confirmada!"

if __name__ == '__main__':
    app.run(debug=True)
