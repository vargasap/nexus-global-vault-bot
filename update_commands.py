import os
import requests

token = '9176578200:AAEK08QowB8IqaDXKyKQnl9-YN1EScbJQBE'
base_url = f'https://api.telegram.org/bot{token}'

commands = [
    {'command': 'menu', 'description': '🛠️ Menú Oficial (8 Servicios)'},
    {'command': 'juego', 'description': '🎰 Ruleta y Cofres (Mini App)'},
    {'command': 'video', 'description': '🎬 1. Descargar Video HD'},
    {'command': 'mp3', 'description': '🎵 2. Extraer Audio MP3'},
    {'command': 'sticker', 'description': '🪄 3. Creador de Stickers'},
    {'command': 'mejorar', 'description': '📸 4. Mejorar Calidad HD'},
    {'command': 'pdf', 'description': '📄 5. Foto a PDF Oficial'},
    {'command': 'qr', 'description': '📱 6. Generar Código QR'},
    {'command': 'traductor', 'description': '🌐 7. Traductor Universal'},
    {'command': 'resumir', 'description': '⚡ 8. Resumir con IA'},
    {'command': 'invitar', 'description': '🎁 Invita y Gana Usos Gratis'},
    {'command': 'planes', 'description': '💳 Paquetes ($0.99 - $9.99)'}
]

r = requests.post(f'{base_url}/setMyCommands', json={'commands': commands})
print('setMyCommands:', r.json())
