from flask import Flask, render_template, request, redirect, url_for, flash, session
from pymongo import MongoClient
from geopy.distance import geodesic
import bcrypt
from dotenv import load_dotenv
import os
import requests
from bson import ObjectId

load_dotenv()
app = Flask(__name__)
app.secret_key = os.urandom(24)
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


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')

        # Buscar o usuário pelo e-mail
        usuario = usuarios_col.find_one({'email': email})

        if usuario:
            if bcrypt.checkpw(senha.encode('utf-8'), usuario['senha']):
                flash('Login realizado com sucesso!', 'success')
                session['cliente_id'] = str(usuario['_id'])  # Salvar o ID do cliente na sessão
                return redirect(url_for('pesquisa'))  # Redireciona para a página de pesquisa
            else:
                flash('Senha incorreta.', 'error')
                return render_template('login.html')  # Volta ao formulário de login com mensagem
        else:
            flash('E-mail não encontrado.', 'error')
            return render_template('login.html')  # Mesma abordagem acima

    return render_template('login.html')

@app.route('/login-restaurante', methods=['GET', 'POST'])
def login_restaurante():
    if request.method == 'POST':
        nome_restaurante = request.form.get('nome_restaurante')
        id_restaurante = request.form.get('id_restaurante')

        # Buscar o restaurante pelo nome e ID
        restaurante = restaurantes_col.find_one({
            'name': nome_restaurante,
            'restaurant_id': id_restaurante
        })

        if restaurante:
            flash('Login de restaurante realizado com sucesso!', 'success')
            # Aqui você pode salvar informações na sessão, se necessário
            return redirect(url_for('ver_restaurante', restaurante_id=id_restaurante))
        else:
            flash('Nome ou ID do restaurante incorretos.', 'error')
            return redirect(url_for('login'))

    return render_template('login_restaurante.html')



@app.route('/cadastro-cliente', methods=['GET', 'POST'])
def cadastro_cliente():
    if request.method == 'POST':
        nome = request.form['nome']
        telefone = request.form['telefone']
        email = request.form['email']
        senha = request.form['senha']

        # Hash da senha
        hashed_senha = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt())
        
        # Criar o cliente para inserção no banco
        cliente = {
            'nome': nome,
            'telefone': telefone,
            'email': email,
            'senha': hashed_senha
        }

        # Inserir cliente no banco de dados
        usuarios_col.insert_one(cliente)
        flash('Cadastro de cliente realizado com sucesso!')
        return redirect(url_for('login'))  # Redirecionar para o login após cadastro

    return render_template('cadastro_cliente.html')


def get_coordinates(address):
    API_KEY = "32e975ec94e94b5fbe981e5f9cac0a11"  # Substitua pela sua chave de API do OpenCage
    BASE_URL = "https://api.opencagedata.com/geocode/v1/json"

    params = {
        "q": address,  # Endereço completo
        "key": API_KEY,
        "language": "pt",  # Retorno em português
        "pretty": 1
    }

    response = requests.get(BASE_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        if data["results"]:
            latitude = data["results"][0]["geometry"]["lat"]
            longitude = data["results"][0]["geometry"]["lng"]
            return latitude, longitude
        else:
            return None, None
    else:
        print("Erro na API:", response.status_code)
        return None, None

@app.route('/cadastro-restaurante', methods=['GET', 'POST'])
def cadastro_restaurante():
    if request.method == 'POST':
        name = request.form['name']
        building = request.form['address[building]']
        street = request.form['address[street]']
        zipcode = request.form['address[zipcode]']
        borough = request.form['borough']
        cuisine = request.form['cuisine']
        restaurant_id = request.form['restaurant_id']

        # Montar o endereço completo
        address = f"{building} {street}, {borough}, {zipcode}"

        # Obter as coordenadas (latitude, longitude)
        latitude, longitude = get_coordinates(address)

        if latitude and longitude:
            print(f"Coordenadas de {name}: Latitude = {latitude}, Longitude = {longitude}")
            # Montar o objeto restaurante com as coordenadas
            restaurante = {
                'name': name,
                'address': {
                    'building': building,
                    'street': street,
                    'zipcode': zipcode,
                    'borough': borough,
                    'coord': [latitude, longitude]  # Armazenando coordenadas
                },
                'cuisine': cuisine,
                'restaurant_id': restaurant_id
            }

            # Inserir restaurante no banco de dados
            restaurantes_col.insert_one(restaurante)
            flash('Restaurante cadastrado com sucesso!')
            return redirect(url_for('login'))  # Redireciona para a página inicial após cadastro
        else:
            return "Erro ao obter as coordenadas."

    return render_template('cadastro_restaurante.html')



@app.route('/pesquisa', methods=['GET', 'POST'])
def pesquisa():
    restaurantes = []
    per_page = 10  # Número de resultados por página
    page = int(request.args.get('page', 1))  # Página atual, padrão é 1
    total = 0  # Valor padrão para total

    if request.method == 'POST' or 'nome' in request.args:
        # Captura dos filtros
        nome = request.form.get('nome', request.args.get('nome', '')).strip()
        tipo_cozinha = request.form.get('tipo_cozinha', request.args.get('tipo_cozinha', '')).strip()
        nota_minima = request.form.get('nota', request.args.get('nota', '')).strip()
        bairro = request.form.get('bairro', request.args.get('bairro', '')).strip()

        query = {}

        if nome:
            query['name'] = {'$regex': nome, '$options': 'i'}
        if tipo_cozinha:
            query['cuisine'] = tipo_cozinha
        if bairro:
            query['borough'] = {'$regex': bairro, '$options': 'i'}
        if nota_minima:
            try:
                query['grades.score'] = {'$gte': float(nota_minima)}
            except ValueError:
                pass

        # Paginação com MongoDB
        try:
            total = restaurantes_col.count_documents(query)  # Conta o número total de resultados
            restaurantes = list(restaurantes_col.find(query)
                                .skip((page - 1) * per_page)
                                .limit(per_page))
        except Exception as e:
            print(f"Erro ao consultar o banco de dados: {e}")

        return render_template(
            'pesquisa.html',
            restaurantes=restaurantes,
            total=total,
            page=page,  # Passando a variável page para o template
            per_page=per_page,  # Passando a variável per_page para o template
            nome=nome,
            tipo_cozinha=tipo_cozinha,
            nota_minima=nota_minima,
            bairro=bairro
        )

    return render_template(
        'pesquisa.html',
        restaurantes=restaurantes,
        total=total,
        per_page=per_page,  # Passando a variável per_page para o template
        page=page  # Passando a variável page para o template
    )



@app.route('/reservar/<restaurante_id>', methods=['GET', 'POST'])
def reservar(restaurante_id):
    # Recuperar as informações do restaurante
    restaurante = restaurantes_col.find_one({'_id': ObjectId(restaurante_id)})
    
    # Recuperar o cliente logado
    cliente_id = session.get('cliente_id')
    if cliente_id:
        cliente = usuarios_col.find_one({'_id': ObjectId(cliente_id)})
        nome_cliente = cliente['nome'] if cliente else ''
    else:
        flash('Você precisa estar logado para fazer uma reserva.', 'error')
        return redirect(url_for('login'))  # Redireciona para o login se o cliente não estiver logado
    
    if request.method == 'POST':
        nome = request.form.get('nome')
        horario = request.form.get('horario')
        data = request.form.get('data')
        quantidade = request.form.get('quantidade')

        # Adicionar o nome do restaurante diretamente na reserva
        reserva = {
            'restaurante_id': restaurante_id,
            "cliente_id": cliente_id,
            'nome': nome,
            'horario': horario,
            'data': data,
            'qtd_p': quantidade,
            'restaurante_nome': restaurante['name']  # Adicionando o nome do restaurante
        }

        reservas_col.insert_one(reserva)
        flash('Reserva realizada com sucesso!', 'success')
        return redirect(url_for('pesquisa'))  # Redireciona de volta para a página inicial após a reserva

    # Passar o nome do cliente logado para o template
    return render_template('reservar.html', restaurante=restaurante, nome_cliente=nome_cliente)


    
@app.route('/cliente/editar', methods=['GET', 'POST'])
def editar_cliente():
    cliente_id = session.get('cliente_id')
    cliente = usuarios_col.find_one({'_id': ObjectId(cliente_id)})
    if request.method == 'POST':
        nome = request.form['nome']
        telefone = request.form['telefone']
        email = request.form['email']
        # Atualizar as informações no banco de dados
        usuarios_col.update_one({'_id': ObjectId(cliente_id)}, {'$set': {
            'nome': nome,
            'telefone': telefone,
            'email': email
        }})
        flash('Informações atualizadas com sucesso!')
        return redirect(url_for('pesquisa'))  # Voltar para a página inicial após edição
    return render_template('editar_cliente.html', cliente=cliente)


@app.route('/cliente/excluir', methods=['POST'])
def excluir_cliente():
    cliente_id = session.get('cliente_id')  # Recupera o ID do cliente da sessão

    if cliente_id:
        # Excluir o cliente do banco de dados
        usuarios_col.delete_one({'_id': ObjectId(cliente_id)})
        flash('Sua conta foi excluída com sucesso!', 'success')
        session.pop('cliente_id', None)  # Remover o ID da sessão
        return redirect(url_for('index'))  # Ou redireciona para a página de login
    else:
        flash('Erro: você não está logado.', 'error')
        return redirect(url_for('login'))  # Redireciona para o login caso não haja ID na sessão



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

@app.route('/restaurante/excluir/<restaurante_id>', methods=['POST'])
def excluir_restaurante(restaurante_id):
    # Excluir o restaurante do banco de dados
    restaurantes_col.delete_one({'restaurant_id': restaurante_id})
    flash('Restaurante excluído com sucesso!', 'success')
    return redirect(url_for('index'))  # Redireciona para a página inicial após exclusão

@app.route('/reservas_feitas', methods=['GET', 'POST'])
def reservas_feitas():
    cliente_id = session.get('cliente_id')
    if cliente_id:
        # Buscar todas as reservas feitas pelo cliente logado
        reservas = reservas_col.find({'cliente_id': cliente_id})
        return render_template('reservas_feitas.html', reservas=reservas)
    else:
        flash('Você precisa estar logado para visualizar suas reservas.', 'error')
        return redirect(url_for('login'))

@app.route('/reservas_feitas/editar/<reserva_id>', methods=['GET', 'POST'])
def editar_reserva(reserva_id):
    cliente_id = session.get('cliente_id')
    reserva = reservas_col.find_one({'_id': ObjectId(reserva_id)})
    
    if reserva and reserva['cliente_id'] == cliente_id:  # Verifica se a reserva pertence ao cliente
        if request.method == 'POST':
            horario = request.form['horario']
            data = request.form['data']
            quantidade = request.form['quantidade']

            # Atualiza os dados da reserva no banco de dados
            reservas_col.update_one(
                {'_id': ObjectId(reserva_id)},
                {'$set': {
                    'horario': horario,
                    'data': data,
                    'qtd_p': quantidade
                }}
            )
            flash('Reserva atualizada com sucesso!', 'success')
            return redirect(url_for('reservas_feitas'))  # Redireciona para a página de reservas feitas
        return render_template('editar_reserva.html', reserva=reserva)
    else:
        flash('Reserva não encontrada ou não pertence a você.', 'error')
        return redirect(url_for('reservas_feitas'))

@app.route('/reservas_feitas/excluir/<reserva_id>', methods=['POST'])
def excluir_reserva(reserva_id):
    cliente_id = session.get('cliente_id')
    reserva = reservas_col.find_one({'_id': ObjectId(reserva_id)})

    if reserva and reserva['cliente_id'] == cliente_id:  # Verifica se a reserva pertence ao cliente
        # Excluir a reserva do banco de dados
        reservas_col.delete_one({'_id': ObjectId(reserva_id)})
        flash('Reserva excluída com sucesso!', 'success')
        return redirect(url_for('reservas_feitas'))  # Redireciona para a página de reservas feitas
    else:
        flash('Reserva não encontrada ou não pertence a você.', 'error')
        return redirect(url_for('reservas_feitas'))




@app.route('/confirmacao')
def confirmacao():
    return "Reserva confirmada!"

@app.route('/logout')
def logout():
    # Limpar dados da sessão
    session.pop('user_id', None)  # Se você estiver usando 'user_id' para controlar o login
    # Redirecionar para a página inicial
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
