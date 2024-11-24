import requests
import json

# URL del endpoint
url = "https://nasti98rs.pythonanywhere.com/chat"  # Cambia esto por la URL pública de tu aplicación en PythonAnywhere

# Datos ficticios para el request body
data = {
    "message": "todos , sin filtro",
    "context": {
        "user_id": "12345",
        "session_id": "abcdefg12345",
        "stream": False
    }
}

# Convertir el cuerpo de la solicitud a JSON
headers = {'Content-Type': 'application/json'}
response = requests.post(url, data=json.dumps(data), headers=headers)

# Verificar la respuesta
if response.status_code == 200:
    print("Respuesta del chat:", response.json())
else:
    print(f"Error al llamar al endpoint: {response.status_code} - {response.text}")


