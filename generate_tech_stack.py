import graphviz
import math

dot = graphviz.Digraph(engine='neato', format='png')
dot.attr(bgcolor='white', overlap='false', splines='true', dpi='300')

# Center node
dot.node('Center', 'PharmaSense\nTech Stack', shape='circle', style='filled', fillcolor='#f8fafc', color='#cbd5e1', penwidth='3', width='1.8', height='1.8', fontname='Arial', fontsize='24', fontcolor='#0f172a', fontbold='true')

# Nodes formatting
dot.attr('node', shape='box', style='filled', fillcolor='#ffffff', color='#94a3b8', penwidth='2', fontname='Arial', fontsize='14', margin='0.4')

boxes = {
    'Frontend': 'Frontend & UI\n\n• Next.js 16 (App Router)\n• React 19\n• Tailwind CSS 4\n• Mapbox GL / Deck.gl',
    'Backend': 'Backend API Core\n\n• Python 3.11+\n• FastAPI Framework\n• Uvicorn Server\n• Pydantic v2',
    'AI': 'AI / ML Models\n\n• PyTorch Geometric (ST-GNN)\n• Meta Prophet\n• LightGBM\n• Scikit-Learn',
    'Data': 'Database & Cache\n\n• Supabase (PostgreSQL)\n• Redis (In-Memory)\n• SQLite (Local fallback)',
    'Events': 'Event Stream & APIs\n\n• Apache Kafka\n• Twilio (WhatsApp)\n• Google Trends API',
    'Deploy': 'Infrastructure\n\n• Vercel (Edge Network)\n• Railway (Containers)\n• GitHub Actions'
}

radius = 4.5
angle_step = 2 * math.pi / len(boxes)

for i, (name, label) in enumerate(boxes.items()):
    angle = i * angle_step
    x = radius * math.cos(angle)
    y = radius * math.sin(angle)
    dot.node(name, label, pos=f"{x},{y}!")
    dot.edge('Center', name, dir='both', arrowhead='none', arrowtail='none', color='#cbd5e1', penwidth='2')

dot.render('pharmasense_tech_stack_final', view=False)
