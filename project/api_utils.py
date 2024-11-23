import core
from swarm import Agent
from typing import Optional
from project.api_models import ChatResponse, ToolCall



class AgentSwitchHandler:
    def __init__(self):
        self.agent_functions = {
            "talk_to_lister": core.agent_lister,
            "talk_to_adder": core.agent_adder,
            "talk_to_deleter": core.agent_deleter,
            "talk_to_updater": core.agent_updater,
            "talk_to_triage_agent": core.triage_agent,
        }

    def handle_tool_call(self, tool_call: dict) -> Optional[Agent]:
        """
        Maneja una tool call y retorna el agente correspondiente si es un cambio de agente
        """
        if not tool_call or "function" not in tool_call:
            return None

        function_name = tool_call["function"]["name"]
        new_agent = self.agent_functions.get(function_name)

        # Solo retornamos el nuevo agente si es diferente al actual
        if new_agent:
            return new_agent
        return None


def process_tool_calls(
    message: dict, agent_switch_handler: AgentSwitchHandler
) -> Optional[Agent]:
    """
    Procesa los tool calls de un mensaje y retorna el nuevo agente si hay un cambio
    """
    if not message:
        return None
        
    if "tool_calls" not in message or not message["tool_calls"]:
        return None
        
    for tool_call in message["tool_calls"]:
        new_agent = agent_switch_handler.handle_tool_call(tool_call)
        if new_agent:
            return new_agent
    return None


def format_message(
    message: dict, agent_switch: Optional[str] = None
) -> Optional[ChatResponse]:
    """
    Formatea un mensaje para la respuesta de la API
    Retorna None si el mensaje está vacío o no tiene contenido
    """
    # Verificar si el mensaje tiene contenido
    if not message.get("content"):
        return None

    # Asegurarse de que siempre haya un sender válido
    sender = message.get("sender") or message.get("role") or "assistant"

    response = ChatResponse(
        sender=sender, content=message.get("content"), agent_switch=agent_switch
    )

    if "tool_calls" in message and message["tool_calls"]:
        response.tool_calls = [
            ToolCall(
                id=tool_call["id"],
                type=tool_call["type"],
                function=tool_call["function"],
            )
            for tool_call in message["tool_calls"]
        ]

    return response