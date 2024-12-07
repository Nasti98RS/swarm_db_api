from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from sqlmodel import  Session,select



import core
from project.api_models import ChatRequest
from project.models import Usuario,Producto
from project.database import engine
from project.api_utils import AgentSwitchHandler, process_tool_calls, format_message

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "https://nasti98rs.github.io",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": "*"
    }
})

client = core.client
starting_agent = core.triage_agent

current_agent_memory = {}
conversation_memory = {}

@app.route("/chat", methods=["POST"])
def chat():
    """
    Endpoint para manejar solicitudes de chat con memoria y cambios de agente
    """
    try:
        req_data = request.get_json()
        chat_request = ChatRequest(**req_data)  # Validar el input

        user_id = chat_request.context.get("user_id")
        if user_id not in conversation_memory:
            conversation_memory[user_id] = []
            current_agent_memory[user_id] = starting_agent

        # Obtener el agente actual para este usuario
        current_agent = current_agent_memory.get(user_id, starting_agent)
        agent_switch_handler = AgentSwitchHandler()

        # Agregar mensaje del usuario al historial
        conversation_memory[user_id].append({"role": "user", "content": chat_request.message})

        formatted_response = []
        response = client.run(
            agent=current_agent,
            messages=conversation_memory[user_id],
            context_variables=chat_request.context,
            stream=chat_request.stream,
        )

        if chat_request.stream:
            for chunk in response:
                if chunk and chunk.get("content"):
                    new_agent = process_tool_calls(chunk, agent_switch_handler)
                    if new_agent:
                        current_agent_memory[user_id] = new_agent
                        new_response = client.run(
                            agent=new_agent,
                            messages=conversation_memory[user_id],
                            context_variables=chat_request.context,
                            stream=False,
                        )
                        if new_response.messages:
                            last_message = new_response.messages[-1]
                            if last_message.get("content"):
                                formatted_response.append(
                                    format_message(last_message, new_agent.name)
                                )
                        break
                    else:
                        formatted_response.append(format_message(chunk))
        else:
            messages = response.messages
            for message in messages:
                new_agent = process_tool_calls(message, agent_switch_handler)
                if new_agent:
                    current_agent_memory[user_id] = new_agent
                    new_response = client.run(
                        agent=new_agent,
                        messages=conversation_memory[user_id],
                        context_variables=chat_request.context,
                        stream=False,
                    )
                    if new_response.messages:
                        last_message = new_response.messages[-1]
                        if last_message.get("content"):
                            formatted_response.append(
                                format_message(last_message, new_agent.name)
                            )
                    break
                elif message.get("content"):
                    formatted_response.append(format_message(message))

        if formatted_response:
            conversation_memory[user_id].append(
                {"role": "assistant", "content": formatted_response[-1].content}
            )

        return jsonify([res.dict() for res in formatted_response])

    except Exception as e:
        abort(500, description=f"Error processing request: {str(e)}")

@app.route("/reset-agent/<user_id>", methods=["POST"])
def reset_agent(user_id: str):
    """
    Reinicia la memoria de chat y asigna al agente de triaje al usuario.

    Args:
        user_id (str): Identificador único del usuario

    Returns:
        tuple: (JSON response, HTTP status code)
    """
    try:
        # Borrar la memoria de conversación del usuario
        conversation_memory.pop(user_id, None)  # Usar pop con None como default es más seguro

        # Reiniciar el agente al agente de triaje inicial
        current_agent_memory[user_id] = starting_agent

        return jsonify({
            "status": "success",
            "message": f"Conversación reiniciada para el usuario {user_id}",
            "current_agent": starting_agent.name  # Asumiendo que el agente tiene un atributo name
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error al reiniciar la conversación: {str(e)}"
        }), 500


@app.route("/", methods=["GET"])
def home():
    """
    Endpoint de inicio para verificar el estado del servidor.
    """
    return jsonify({
        "message": "El chatbot está funcionando. Envía solicitudes POST a /chat para interactuar."
    })

@app.route('/new_user', methods=['POST'])
def create_user():
    try:
        # Obtener los datos del cuerpo de la solicitud
        data = request.json
        nombre = data.get('name')
        empresa = data.get('company')
        email = data.get('email')

        # Validar campos obligatorios
        if not nombre :
            return jsonify({"error": "El campo nombre es obligatorio"}), 400

        # Crear el objeto usuario
        new_user = Usuario(nombre_usuario=nombre, empresa=empresa, email=email)

        # Guardar el usuario en la base de datos si no existe
        with Session(engine) as session:
            exist=session.exec(
                select(Usuario).where(Usuario.nombre_usuario.ilike(f"%{new_user.nombre_usuario}%"))
            ).first()
            if exist:
                return jsonify({"message": "El usuario ya existe", "user_id": str(exist.id),"user_name": str(exist.nombre_usuario),"user_enterprise": str(exist.empresa),"user_email": str(exist.email)},), 201
            else:
                session.add(new_user)
                session.commit()
                session.refresh(new_user)

            return jsonify({"message": "Usuario creado exitosamente", "user_id": str(new_user.id)}), 201

    except Exception as e:
        return jsonify({"error": f"Error al crear el usuario: {str(e)}"}), 500

@app.route('/get_data', methods=['GET'])
def get_data():
    try:
        with Session(engine) as session:
            # Seleccionamos todos los productos
            productos = session.exec(select(Producto)).all()
            
            # Convertimos los objetos a un formato serializable
            productos_serializados = [
                {
                    "nombre": producto.nombre,
                    "precio": producto.precio,
                    "cantidad_en_almacen": producto.cantidad_en_almacen,
                    "descuento_por_devolucion": producto.descuento_por_devolucion
                }
                for producto in productos
            ]
            
            # Devolvemos los datos en formato JSON
            return jsonify(productos_serializados)
    except Exception as e:
        return jsonify({"error": f"Error al obtener los datos: {str(e)}"}), 500