from flask import Flask, render_template, request, redirect, url_for, flash
from pymongo import MongoClient
from geopy.distance import geodesic
import bcrypt
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
conexao = os.getenv('CONNECTION')

# Conectando ao MongoDB
client = MongoClient(conexao)
db = client["RangoDB"]

restaurantes_col = db["restaurantes"]
reservas_col = db["reservas"]
usuarios_col = db["clientes"]

@app.route('/')
def index():
    return render_template("index.html", restaurantes=restaurantes_col.find())


@app.route('/login', methods=['GET, POST'])
def login():
    email = request.form['email']
    senha = request.form['senha']

    # Buscar o usuário pelo e-mail
    usuario = usuarios_col.find_one({'email': email})
    
    if usuario and bcrypt.checkpw(senha.encode('utf-8'), usuario['senha']):
        flash('Login realizado com sucesso!')
        return redirect(url_for('index'))  # Redireciona para a página inicial ou outra página após login
    else:
        flash('E-mail ou senha incorretos. Tente novamente.')
        return redirect(url_for('login'))

@app.route('/cadastro-usuario', methods=['GET', 'POST'])
def cadastro_usuario():
    nome = request.form['nome']
    telefone = request.form['telefone']
    email = request.form['email']
    senha = request.form['senha']

    # Criptografando a senha
    hashed_senha = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())

    # Inserindo dados na coleção de usuários
    usuario = {
        'nome': nome,
        'telefone': telefone,
        'email': email,
        'senha': hashed_senha
    }

    # Inserindo o usuário no MongoDB
    usuarios_col.insert_one(usuario)
    flash('Cadastro realizado com sucesso!')
    return redirect(url_for('login'))


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

@app.route('/restaurante/ver/<restaurante_id>', methods=['GET', 'POST'])
def ver_restaurante(restaurante_id):
    restaurante = restaurantes_col.find_one({"restaurant_id": restaurante_id})
    return render_template("ver_restaurante.html", restaurante=restaurante)

@app.route('/restaurante/editar/<restaurante_id>', methods=['GET', 'POST'])
def editar_restaurante(restaurante_id):
    if request.method == 'POST':
        restaurantes_col.update_one(
            {"restaurant_id": restaurante_id},
            {
                "$set": {
                    "name": request.form['name'],
                    "address.building": request.form['building'],
                    "address.street": request.form['street'],
                    "address.zipcode": request.form['zipcode'],
                    "borough": request.form['borough'],
                    "cuisine": request.form['cuisine']
                }
            }
        )
        return redirect(url_for("ver_restaurante", restaurante_id=restaurante_id))

    restaurante = restaurantes_col.find_one({"restaurant_id": restaurante_id})
    return render_template("editar_restaurante.html", restaurante=restaurante)

@app.route('/confirmacao')
def confirmacao():
    return "Reserva confirmada!"

if __name__ == '__main__':
    app.run(debug=True)
