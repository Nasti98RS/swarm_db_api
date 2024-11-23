from typing import List
from fastapi import FastAPI, HTTPException

import core
from project.api_models import ChatResponse, ChatRequest
from project.api_utils import AgentSwitchHandler, process_tool_calls, format_message



app = FastAPI()

client = core.client
starting_agent = core.triage_agent

# Diccionario para mantener el agente actual por usuario
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=7000, reload=True)
