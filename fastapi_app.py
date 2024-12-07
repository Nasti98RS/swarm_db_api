from typing import List
from fastapi import FastAPI, HTTPException
from sqlmodel import  Session,select


import core
from project.api_models import ChatResponse, ChatRequest,UsuarioCreate
from project.api_utils import AgentSwitchHandler, process_tool_calls, format_message
from project.models import Usuario,Producto
from project.database import engine


app = FastAPI()

client = core.client
starting_agent = core.triage_agent

current_agent_memory = {}
conversation_memory = {}


@app.post("/chat", response_model=List[ChatResponse])
async def chat(request: ChatRequest):
    """
    Endpoint para manejar solicitudes de chat con memoria y cambios de agente
    """
    user_id = request.context.get("user_id")
    if user_id not in conversation_memory:
        conversation_memory[user_id] = []
        current_agent_memory[user_id] = starting_agent

    # Obtener el agente actual para este usuario
    current_agent = current_agent_memory.get(user_id, starting_agent)
    agent_switch_handler = AgentSwitchHandler()

    # Agregar mensaje del usuario al historial
    conversation_memory[user_id].append({"role": "user", "content": request.message})

    formatted_response = []
    try:
        # Enviar historial completo al cliente usando el agente actual
        response = client.run(
            agent=current_agent,
            messages=conversation_memory[user_id],
            context_variables=request.context,
            stream=request.stream,
        )

        if request.stream:
            for chunk in response:
                if chunk and chunk.get("content"):
                    new_agent = process_tool_calls(chunk, agent_switch_handler)
                    if new_agent:
                        current_agent_memory[user_id] = new_agent
                        # Hacer una nueva llamada con el nuevo agente
                        new_response = client.run(
                            agent=new_agent,
                            messages=conversation_memory[user_id],
                            context_variables=request.context,
                            stream=False,
                        )
                        # Solo tomamos la última respuesta del nuevo agente
                        if new_response.messages:
                            last_message = new_response.messages[-1]
                            if last_message.get("content"):
                                formatted_response.append(
                                    format_message(last_message, new_agent.name)
                                )
                        break  # Salimos del loop después del cambio de agente
                    else:
                        formatted_response.append(format_message(chunk))
        else:
            messages = response.messages
            # Verificar si hay un cambio de agente en cualquiera de los mensajes
            for message in messages:
                new_agent = process_tool_calls(message, agent_switch_handler)
                if new_agent:
                    current_agent_memory[user_id] = new_agent
                    # Hacer una nueva llamada con el nuevo agente
                    new_response = client.run(
                        agent=new_agent,
                        messages=conversation_memory[user_id],
                        context_variables=request.context,
                        stream=False,
                    )
                    # Solo tomamos la última respuesta del nuevo agente
                    if new_response.messages:
                        last_message = new_response.messages[-1]
                        if last_message.get("content"):
                            formatted_response.append(
                                format_message(last_message, new_agent.name)
                            )
                    break  # Salimos del loop después del cambio de agente
                elif message.get("content"):
                    formatted_response.append(format_message(message))

        # Solo actualizamos la memoria de conversación con la última respuesta
        if formatted_response:
            conversation_memory[user_id].append(
                {"role": "assistant", "content": formatted_response[-1].content}
            )

        return formatted_response

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


# Endpoint para reiniciar al agente inicial
@app.post("/reset-agent/{user_id}")
async def reset_agent(user_id: str):
    """
    Reinicia el agente al agente de triaje inicial
    """
    conversation_memory.pop(user_id, None)  # Usar pop con None como default es más seguro
    current_agent_memory[user_id] = starting_agent
    return {"message": "Agent reset to triage agent", "agent_name": starting_agent.name}


@app.get("/")
async def home():
    """
    Endpoint de inicio para verificar el estado del servidor.
    """
    return {
        "message": "El chatbot está funcionando. Envía solicitudes POST a /chat para interactuar."
    }

@app.post("/new_user", response_model=dict, status_code=200)
def create_user(user: UsuarioCreate):
    try:
        # Crear el objeto usuario
        new_user = Usuario(nombre_usuario=user.name, empresa=user.company, email=user.email)

        # Guardar el usuario en la base de datos si no existe
        with Session(engine) as session:
            exist=session.exec(
                select(Usuario).where(Usuario.nombre_usuario.ilike(f"%{new_user.nombre_usuario}%"))
            ).first()
            if exist:
                return {"message": "El usuario ya existe", "user_id": str(exist.id),"user_name": str(exist.nombre_usuario),"user_enterprise": str(exist.empresa),"user_email": str(exist.email)}
            else:
                session.add(new_user)
                session.commit()
                session.refresh(new_user)
            

        # Devolver respuesta
        return {"message": "Usuario creado exitosamente", "user_id": str(new_user.id)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear el usuario: {str(e)}")

@app.get('/get_data')
def get_data():
    try:
        with Session(engine) as session:
            # Select all products
            productos = session.exec(select(Producto)).all()
            
            # Serialize the product objects
            productos_serializados = [
                {
                    "nombre": producto.nombre,
                    "precio": producto.precio,
                    "cantidad_en_almacen": producto.cantidad_en_almacen,
                    "descuento_por_devolucion": producto.descuento_por_devolucion
                }
                for producto in productos
            ]
            
            # Return the data as a dictionary
            return {"data": productos_serializados}
    except Exception as e:
        # Return an error message with status code 500
        return {"error": f"Error al obtener los datos: {str(e)}"}, 500




if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fastapi_app:app", host="127.0.0.1", port=7000, reload=True)
