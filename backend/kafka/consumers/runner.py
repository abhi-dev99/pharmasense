import asyncio
import structlog
from backend.kafka.consumers.po_generator import po_generator_consumer
from backend.kafka.consumers.whatsapp_notifier import whatsapp_notifier_consumer

log = structlog.get_logger()

class KafkaRunner:
    def __init__(self):
        self.tasks = []

    def start(self):
        log.info("kafka.runner.starting_consumers")
        self.tasks.append(asyncio.create_task(po_generator_consumer()))
        self.tasks.append(asyncio.create_task(whatsapp_notifier_consumer()))

    async def stop(self):
        log.info("kafka.runner.stopping_consumers")
        for task in self.tasks:
            task.cancel()
            
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()

kafka_runner = KafkaRunner()
