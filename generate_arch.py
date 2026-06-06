from diagrams import Diagram, Cluster, Edge
from diagrams.programming.framework import React, FastAPI
from diagrams.programming.language import Python
from diagrams.onprem.database import PostgreSQL
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.queue import Kafka
from diagrams.onprem.compute import Server
from diagrams.onprem.analytics import Spark
from diagrams.onprem.network import Nginx

with Diagram("PharmaSense Architecture", show=False, filename="pharmasense_architecture_official", outformat="png"):

    with Cluster("Client / Frontend"):
        ui = React("Next.js UI\nReact / Tailwind")

    with Cluster("Backend Services"):
        api = FastAPI("FastAPI Server\nPython 3.11")
        workers = Python("Background Jobs\nAPScheduler")

    with Cluster("Data & Cache"):
        db = PostgreSQL("Supabase\nPostgreSQL")
        cache = Redis("Redis\nIn-Memory Cache")

    with Cluster("AI / ML Engine"):
        stgnn = Server("ST-GNN\nPyTorch / PyG")
        prophet = Server("Meta Prophet\nStrategic Planning")
        lgbm = Server("LightGBM\nOutbreak Scoring")
        ai_group = [stgnn, prophet, lgbm]

    with Cluster("Event Stream"):
        kafka = Kafka("Apache Kafka\nEvent Bus")

    with Cluster("External APIs"):
        twilio = Server("Twilio API\nWhatsApp Alerts")
        google = Server("Google Trends\nSearch Intel")

    ui >> Edge(color="darkgreen", label="REST / HTTPS") >> api
    
    api >> Edge(color="blue") >> db
    api >> Edge(color="orange") >> cache
    
    api >> Edge(color="purple", label="Inference") >> ai_group
    
    api >> Edge(color="black", label="Publish Event") >> kafka
    kafka >> Edge(color="black", label="Consume") >> workers
    
    workers >> Edge(color="darkgreen", label="Trigger Alert") >> twilio
    
    stgnn >> Edge(color="gray", label="Fetch Data") >> google
    prophet >> Edge(color="gray") >> google
