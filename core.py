from swarm import Swarm, Agent
from swarm.core import Result
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from anthropic import Anthropic


from openai import OpenAI

from dotenv import load_dotenv
from typing import Optional, List, Dict, Union, Tuple
import os
from sqlmodel import Session, select

from project.database import engine
from project.models import Producto, Usuario
from project.core_utils import run_demo_loop, process_and_print_streaming_response

load_dotenv()

anthropic_client = Anthropic(api_key=os.environ["BTECH_ANTHROPIC_API_KEY"])
client = Swarm(client=OpenAI(api_key=os.environ["BTECH_OPENAI_API_KEY"]))


def talk_to_lister():
    """Use this function when the user's request involves listing products from the database.
    Directly transfers the user and their request to the Data Listing Agent, so the user doesn't need to repeat their request, bypassing any additional input steps.
    """
    return Result(
        agent=agent_lister,
    )


def talk_to_analyzer(user_request: str):
    """
    Use this function when the user's request involves analyzing or performing operations on data from the database.
    Directly transfers the user and their request to the Data Analysis Agent, so the user doesn't need to repeat their request, bypassing any additional input steps.

    Args:
        user_request (str): The user's original request to analyze or query the data.

    Returns:
        Result: Transfers the user and their request to the Data Analysis Agent.
    """
    return Result(agent=agent_analyzer, request=user_request)


def talk_to_deleter():
    """Use this function when the user's request involves deleting a product from the database.
    Directly transfers the user and their request to the Data Deleting Agent, so the user doesn't need to repeat their request, bypassing any additional input steps.
    """
    return Result(
        agent=agent_deleter,
    )


def talk_to_adder():
    """Use this function when the user's request involves adding, inserting, or creating a new product to the database.
    Directly transfers the user and their request to the Data Adding Agent, so the user doesn't need to repeat their request, bypassing any additional input steps.
    """
    return Result(
        agent=agent_adder,
    )


def talk_to_triage_agent():
    """Use this function if the user requests a task that falls outside your capabilities.
    Transfers the user directly to the Triage Agent for appropriate assistance.
    """
    return Result(
        value="Done, I will transfer you to the Triage Agent.",
        agent=triage_agent,
    )


def talk_to_updater():
    """Use this function when the user's request involves updating, changing, or editing a product in the database.
    Directly transfers the user and their request to the Data Updating Agent, so the user doesn't need to repeat their request, bypassing any additional input steps.
    """
    return Result(
        agent=agent_updater,
    )


def user_info(context_variables):
    """Use this function to retrieve the user's personal information.
    Returns the user's name and the company name to personalize assistance.
    """
    user_id = context_variables["user_id"]
    user_name = context_variables["user_name"]
    enterprise_name = context_variables["enterprise_name"]
    user_email = context_variables["user_email"]

    return Result(
        value=f"Help the user, {user_name} from {enterprise_name} Company, do whatever they want.The user_id is {user_id} and the user_email is {user_email}."
    )


triage_agent = Agent(
    name="Triage Agent",
    instructions="""
    Your mission is to determine which agent is best suited to handle the user's request and transfer the conversation directly to that agent, 
    including the user's request so it can be handled seamlessly without requiring the user to repeat it.

    When deciding which agent to transfer to:
    1. Analyze the user's request and match it with the appropriate agent's domain (e.g., listing, adding, deleting, updating, or analyzing data).
    2. Use the corresponding transfer function (e.g., talk_to_lister, talk_to_adder) and include the user's request in the call.
    3. Ensure the transfer is smooth, providing the necessary context for the receiving agent.
    """,
    functions=[
        # lambda user_request: talk_to_lister(user_request),
        talk_to_adder,
        talk_to_deleter,
        talk_to_updater,
        talk_to_analyzer,
        user_info,
    ],
)


def get_full_database() -> Union[Tuple[List[Dict], List[Dict]], str]:
    """
    Retrieves all tables from the database to provide context.

    Returns:
        Union[Tuple[List[Dict], List[Dict]], str]: If data is found, returns a tuple containing two lists:
            - List[Dict]: A list of dictionaries with product details:
                - nombre (str): Product name
                - precio (float): Product price
                - cantidad_en_almacen (int): Quantity in stock
                - descuento_por_devolucion (float): Return discount
            - List[Dict]: A list of dictionaries with user details:
                - nombre_usuario (str): User name
                - empresa (str): Company
                - email (str): Email address
        If no data is found in either table, returns the string "No data found in the database."
        Handles database errors gracefully by returning an error message.
    """
    try:
        with Session(engine) as session:
            # Retrieve products and users from the database
            productos = session.exec(select(Producto)).all()
            usuarios = session.exec(select(Usuario)).all()

            # Transform products into JSON format
            productos_json = (
                [
                    {
                        "nombre": p.nombre,
                        "precio": p.precio,
                        "cantidad_en_almacen": p.cantidad_en_almacen,
                        "descuento_por_devolucion": p.descuento_por_devolucion,
                    }
                    for p in productos
                ]
                if productos
                else []
            )

            # Transform users into JSON format
            usuarios_json = (
                [
                    {
                        "nombre_usuario": u.nombre_usuario,
                        "empresa": u.empresa,
                        "email": u.email,
                    }
                    for u in usuarios
                ]
                if usuarios
                else []
            )

            # Check if both datasets are empty
            if not productos_json and not usuarios_json:
                return "No data found in the database."

            return productos_json, usuarios_json

    except SQLAlchemyError as e:
        # Handle database errors
        return f"An error occurred while accessing the database: {str(e)}"


def get_tokens_count() -> Union[List[Dict], str]:
    data=get_full_database()
    response = anthropic_client.beta.messages.count_tokens(
        betas=["token-counting-2024-11-01"],
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": f"{data}"}],
    )
    return response.model_dump().get('input_tokens')


agent_analyzer = Agent(
    name="Agent Analyzer",
    model="gpt-4o",
    instructions="""
    You are an advanced analytical agent whose mission is to retrieve all data from the database using the 'get_full_database' function 
    and assist the user with data analysis tasks.

    Before retrieving the data:
    1. Call the 'get_tokens_count' function to calculate the number of tokens required to load the entire database.
    2. Inform the user of the token count and cost in a single, concise message like:
        "Loading the entire database will require {x} tokens ${x}x 0.0000025 at current pricing of gpt-4o. Would you like to proceed?"
    3. If the user agrees, proceed to load the database using the 'get_full_database' function.
    4. If the user declines, transfer them to the Triage Agent using the 'talk_to_triage_agent' function.

    Your capabilities include:
    - Displaying all data retrieved from the database in a clear and structured format.
    - Answering logical questions or performing operations on the data, such as:
        - Filtering by specific fields (e.g., price, quantity, user information).
        - Sorting the data by any numeric or alphabetical field.
        - Calculating statistical summaries (e.g., average price, total quantity in stock).
        - Comparing entries (e.g., finding the highest or lowest values).
        - Handling specific queries like "Which product has the highest discount?" or "Show all users from a specific company."

    Instructions for interaction:
    - If the user provides a specific query or request for analysis, process it immediately without unnecessary questions.
    - If the user wants to see all data, confirm first if they would like it filtered by any criteria or if they want a complete unfiltered dataset.
    - Provide summaries or insights in a concise, readable format, including charts or tables if appropriate.
    - If there are many entries, group or paginate the results for readability.

    When no data is available:
    - Inform the user clearly that the database is empty.

    If you cannot resolve a user's request or if they choose not to load the database, transfer the user to the Triage Agent using the 'talk_to_triage_agent' function.
    """,
    functions=[get_tokens_count, get_full_database, user_info, talk_to_triage_agent],
)


def get_all_products(filter: Optional[str]) -> Union[List[Dict], str]:
    """
    Retrieves all products from the database with optional name filtering.

    Args:
        filter (Optional[str]): Search term to filter products by name. If None, returns all products.
                              The search is case-insensitive and matches partial names.

    Returns:
        Union[List[Dict], str]: If products are found, returns a list of dictionaries containing product details:
                               - nombre (str): Product name
                               - precio (float): Product price
                               - cantidad_en_almacen (int): Quantity in stock
                               - descuento_por_devolucion (float): Return discount
                               If no products are found, returns the string "No products found in the database."
    """
    with Session(engine) as session:
        if filter == None:
            productos = session.exec(select(Producto)).all()
        else:
            productos = session.exec(
                select(Producto).where(Producto.nombre.ilike(f"%{filter.lower()}%"))
            ).all()
        if productos:
            return [
                {
                    "nombre": p.nombre,
                    "precio": p.precio,
                    "cantidad_en_almacen": p.cantidad_en_almacen,
                    "descuento_por_devolucion": p.descuento_por_devolucion,
                }
                for p in productos
            ]
        else:
            return "No products found in the database."


agent_lister = Agent(
    name="Agent Lister",
    model="gpt-4o-mini",
    instructions="""
    You are a helpful agent whose mission is to display all products in the database. 

    If a user requests to see a specific product from the beginning, call the function 'get_all_products' with the filter corresponding to the product name they provided. 
    Do not ask any further questions in this case.

    If a user asks to see all products, inquire if they would like to see all products or if they prefer to filter by specific criteria.

    When displaying the products:
    1. Format the output in a clear, readable manner.
    2. If there are many products, consider grouping them or offering to show them in batches.
    3. Provide a summary of the total number of products.
    4. If no products are found, inform the user clearly.
    
    Be ready to answer questions about the products or offer to filter/sort them if asked.

    If you cannot resolve a user's request, transfer the user to the Triage Agent with your function talk_to_triage_agent.
    """,
    functions=[get_all_products, user_info, talk_to_triage_agent],
)


def insert_a_product(
    nombre: Optional[str] = None,
    precio: Optional[float] = None,
    cantidad_en_almacen: Optional[int] = None,
    descuento_por_devolucion: Optional[float] = None,
):
    """
    Inserts a new product into the database with the specified details.

    Args:
        nombre (Optional[str]): Name of the product to be inserted.
                              Cannot be None for successful insertion.

        precio (Optional[float]): Price of the product.
                                Cannot be None for successful insertion.

        cantidad_en_almacen (Optional[int]): Current quantity of the product in stock.
                                           Cannot be None for successful insertion.

        descuento_por_devolucion (Optional[float]): Return discount percentage applicable to the product.
                                                   Cannot be None for successful insertion.

    Returns:
        If any parameter is missing: Returns an error message indicating which parameters need to be provided.
        If successful: Returns a confirmation message that the product was inserted.
    """
    missing_params = []
    if nombre is None:
        missing_params.append("nombre")
    if precio is None:
        missing_params.append("precio")
    if cantidad_en_almacen is None:
        missing_params.append("cantidad_en_almacen")
    if descuento_por_devolucion is None:
        missing_params.append("descuento_por_devolucion")

    if missing_params:
        return f"No puedo insertar el producto hasta que me proporciones los siguientes parámetros: {', '.join(missing_params)}."

    with Session(engine) as session:
        producto = Producto(
            nombre=nombre,
            precio=precio,
            cantidad_en_almacen=cantidad_en_almacen,
            descuento_por_devolucion=descuento_por_devolucion,
        )
        session.add(producto)
        session.commit()

    return f"Done! The product {nombre} was inserted."


agent_adder = Agent(
    name="Agent Adder",
    model="gpt-4o",
    instructions="""
    You are a helpful agent whose mission is to insert, create, and add products to the database. 
    Your task is to use the function 'insert_a_product' to add products.

    Before adding a product, you must first check if the product name already exists in the database using the function 'get_all_products' with a filter on the product name.
    - Convert all product parameters to lowercase before checking their existence and before inserting them into the database.
    - If the product name already exists, inform the user and ask them to provide a different name.
    - If the product name does not exist, proceed to add the product using the 'insert_a_product' function.

    If you cannot resolve a user's request, transfer the user to the Triage Agent with the function 'talk_to_triage_agent'.
    """,
    functions=[insert_a_product, get_all_products, user_info, talk_to_triage_agent],
)


def delete_a_product(nombre: str):
    """
    Deletes a product from the database by its name.

    Args:
        nombre (str): Name of the product to be deleted.
                     The search is case-sensitive and requires an exact match.

    Returns:
        If the product exists: Returns a confirmation message that the product was deleted.
        If the product is not found: Returns a message indicating the product wasn't found.

    Examples:
        >>> delete_a_product("Laptop")
        "Done! The product Laptop was deleted from the database."

        >>> delete_a_product("NonexistentProduct")
        "Product NonexistentProduct not found in the database."
    """
    with Session(engine) as session:
        producto = session.exec(
            select(Producto).where(func.lower(Producto.nombre) == nombre.lower())
        ).first()
        if producto:
            session.delete(producto)
            session.commit()
            return f"Done! The product {nombre} was deleted from the database."
        else:
            return f"Product {nombre} not found in the database."


agent_deleter = Agent(
    name="Agent Deleter",
    model="gpt-4o",
    instructions="""
    You are a helpful agent whose mission is to delete products from the database. 
    Your task is to use the function 'delete_a_product' to remove products from the database. 
    Always confirm with the user before deleting a product.
    If a product is not found, inform the user and suggest checking the spelling or listing available products.
    If you cannot resolve a user's request, transfer the user to the Triage Agent with you function talk_to_triage_agent .

    """,
    functions=[delete_a_product, user_info, talk_to_triage_agent],
)


def update_a_product(
    nombre: str,
    nuevo_nombre: Optional[str] = None,
    nuevo_precio: Optional[float] = None,
    nueva_cantidad: Optional[int] = None,
    nuevo_descuento: Optional[float] = None,
):
    """
    Updates an existing product in the database with new values.
    Only provided parameters will be updated; others will remain unchanged.

    Args:
        nombre (str): Current name of the product to be updated.
                     Used to identify the product in the database.

        nuevo_nombre (Optional[str]): New name for the product.
                                    If None, the current name remains unchanged.

        nuevo_precio (Optional[float]): New price for the product.
                                      If None, the current price remains unchanged.

        nueva_cantidad (Optional[int]): New stock quantity for the product.
                                      If None, the current quantity remains unchanged.

        nuevo_descuento (Optional[float]): New return discount percentage for the product.
                                         If None, the current discount remains unchanged.
    """
    with Session(engine) as session:
        producto = session.exec(
            select(Producto).where(func.lower(Producto.nombre) == nombre.lower())
        ).first()

        if not producto:
            return f"Product {nombre} not found in the database."

        producto.nombre = (
            nuevo_nombre.lower() if nuevo_nombre is not None else producto.nombre
        )
        producto.precio = nuevo_precio if nuevo_precio is not None else producto.precio
        producto.cantidad_en_almacen = (
            nueva_cantidad
            if nueva_cantidad is not None
            else producto.cantidad_en_almacen
        )
        producto.descuento_por_devolucion = (
            nuevo_descuento
            if nuevo_descuento is not None
            else producto.descuento_por_devolucion
        )

        session.commit()
        return f"Done! The product {nombre} was updated in the database."


agent_updater = Agent(
    name="Agent Updater",
    model="gpt-4",
    instructions="""
    You are a professional Product Update Agent whose mission is to safely update, change, or edit existing products in the database.
    Your primary function is to use 'update_a_product' to make changes to product details while ensuring data integrity.
    Respond to all user interactions in Spanish.

    Detailed Workflow:
    1. Initial Product Verification:
       - First, use 'get_all_products' with the product name as a filter to verify the product exists
       - If the product is not found, inform the user and DO NOT proceed with any updates
    
    2. Current State Display:
       Present the current product details in a clear format:
       ```
       Current Product Details:
       - Name: [current_name]
       - Price: $[current_price]
       - Stock Quantity: [current_quantity]
       - Return Discount: [current_discount]%
       ```
    
    3. Proposed Changes Display:
       Show the proposed changes in a before/after format:
       ```
       Proposed Changes:
       [Field Name]:
       - Current: [current_value]
       - New: [new_value]
       ```
       Only show fields that will be modified.
    
    4. Confirmation Request:
       Ask for explicit confirmation:
       "Please confirm these changes by typing 'SI'. Type 'NO' or anything else to cancel."
    
    5. Update Execution:
       - Ensure all values are converted to lowercase before executing the update.
       - If user types 'SI': Execute update_a_product with the new values
       - If user responds with anything else: Cancel the operation

    6. Name Change Caution:
       - If the user wants to edit the product name, be very careful to avoid creating a new product, just update the existing one.
       
    Important Guidelines:
    - NEVER create new products - this agent is for updates only
    - Always verify the product exists before proceeding
    - Only update the fields that the user specifically requests to change
    - Keep all unchanged fields with their current values
    - Present monetary values with currency symbol and two decimal places
    - Show percentages with % symbol
    - If multiple updates are requested, show all changes before asking for confirmation
    
    Error Handling:
    - If the product doesn't exist: Inform the user and do not proceed
    - If invalid values are provided (e.g., negative prices): Alert the user and request valid input
    - If you cannot handle the user's request: Use talk_to_triage_agent function
    
    Remember: Your primary role is to ensure safe and accurate product updates while maintaining data integrity.
    """,
    functions=[update_a_product, get_all_products, user_info, talk_to_triage_agent],
)





# run_demo_loop(
#     client,
#     triage_agent,
#     stream=True,
#     context_variables={
#         "user_id": "1",
#         "user_name": "Reynaldo",
#         "enterprise_name": "Mi Empresa",
#     },
# )


# response = client.run(
#    agent=triage_agent,
#    messages=[{"role": "user", "content": "hello"}],
#    context_variables={"user_name": "Reynaldo",
#                                 "enterprise_name":"Mi Empresa", },
#                                 stream=True
# )
#  print (response.messages[0]['content'])
# process_and_print_streaming_response(response)
