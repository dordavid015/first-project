import pika, logging, sys, argparse
from argparse import RawTextHelpFormatter
from time import sleep
import threading
from prometheus_client import Counter, start_http_server
import os

# Define Prometheus metrics
MESSAGE_COUNTER = Counter('consumer_messages_count', 
                         'Number of messages consumed', 
                         ['message_body'])

def on_message(channel, method_frame, header_frame, body):
    message_body = body.decode('utf-8') if isinstance(body, bytes) else body
    print method_frame.delivery_tag
    print message_body
    print
    
    # Increment Prometheus counter for this message body
    MESSAGE_COUNTER.labels(message_body=message_body).inc()
    
    LOG.info('Message has been received %s', message_body)
    channel.basic_ack(delivery_tag=method_frame.delivery_tag)

if __name__ == '__main__':
    examples = sys.argv[0] + " -p 5672 -s rabbitmq "
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                 description='Run consumer.py',
                                 epilog=examples)
    parser.add_argument('-p', '--port', action='store', dest='port', help='The port to listen on.')
    parser.add_argument('-s', '--server', action='store', dest='server', help='The RabbitMQ server.')
    args = parser.parse_args()
    
    if args.port == None:
        print "Missing required argument: -p/--port"
        sys.exit(1)
    if args.server == None:
        print "Missing required argument: -s/--server" 
        sys.exit(1)
    
    print("going to sleep for 12 seconds")
    # sleep a few seconds to allow RabbitMQ server to come up
    sleep(12)
    
    logging.basicConfig(level=logging.INFO)
    LOG = logging.getLogger(__name__)
    
    # Start Prometheus metrics server
    try:
        start_http_server(9422)
        LOG.info('Prometheus metrics server started at port 9422')
    except Exception as e:
        LOG.error("Failed to start Prometheus metrics server: {}".format(str(e)))
        sys.exit(1)
    
    username = os.environ.get("MQ_USER", "user")
    password = os.environ.get("MQ_PASS", "password")
    credentials = pika.PlainCredentials(username, password)
    credentials = pika.PlainCredentials("guest","guest")

    parameters = pika.ConnectionParameters(args.server,
                                           int(args.port),
                                           '/',
                                           credentials)
    
    # Add retry logic for connection
    retry_count = 0
    max_retries = 30
    connected = False
    
    while retry_count < max_retries and not connected:
        try:
            LOG.info("Attempting to connect to RabbitMQ (attempt {}/{})...".format(retry_count+1, max_retries))
            connection = pika.BlockingConnection(parameters)
            connected = True
            LOG.info("Successfully connected to RabbitMQ")
        except pika.exceptions.AMQPConnectionError as e:
            retry_count += 1
            LOG.warning("Connection attempt {}/{} failed: {}".format(retry_count, max_retries, str(e)))
            sleep(5)
    
    if not connected:
        LOG.error("Failed to connect to RabbitMQ after multiple attempts")
        sys.exit(1)
        
    channel = connection.channel()
    
    channel.queue_declare('pc')
    channel.basic_consume(on_message, 'pc')
    
    try:
        LOG.info('Consumer started - metrics available at http://localhost:9422/metrics')
        channel.start_consuming()
    except KeyboardInterrupt:
        LOG.info("Consumer stopped by user")
        channel.stop_consuming()
    except Exception as e:
        LOG.error("Error in message consumption: {}".format(str(e)))
    finally:
        LOG.info("Closing connection to RabbitMQ")
        try:
            connection.close()
        except:
            pass