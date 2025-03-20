import pika, logging, sys, argparse
from argparse import RawTextHelpFormatter
from time import sleep
import os

if __name__ == '__main__':
    examples = sys.argv[0] + " -p 5672 -s rabbitmq -m 'Hello' "
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter,
                                 description='Run producer.py',
                                 epilog=examples)
    parser.add_argument('-p', '--port', action='store', dest='port', help='The port to listen on.')
    parser.add_argument('-s', '--server', action='store', dest='server', help='The RabbitMQ server.')
    parser.add_argument('-m', '--message', action='store', dest='message', help='The message to send', required=False, default='Hello')
    # Removed repeat argument as we now send messages infinitely
    args = parser.parse_args()
    
    if args.port == None:
        print "Missing required argument: -p/--port"
        sys.exit(1)
    if args.server == None:
        print "Missing required argument: -s/--server"
        sys.exit(1)
        
    # sleep a few seconds to allow RabbitMQ server to come up
    print("going to sleep for 12 seconds")
    sleep(12)
    
    logging.basicConfig(level=logging.INFO)
    LOG = logging.getLogger(__name__)
    
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
    
    q = channel.queue_declare('pc')
    q_name = q.method.queue
    
    # Turn on delivery confirmations
    channel.confirm_delivery()
    
    message_count = 0
    try:
        while True:  # Infinite loop
            if channel.basic_publish('', q_name, args.message):
                message_count += 1
                LOG.info('Message #%d has been delivered', message_count)
            else:
                LOG.warning('Message NOT delivered')
            sleep(20)  # Sleep for 20 seconds between messages
    except KeyboardInterrupt:
        LOG.info('Producer stopped by user')
    except Exception as e:
        LOG.error("Error in message publishing loop: {}".format(str(e)))
    finally:
        LOG.info("Closing connection to RabbitMQ")
        try:
            connection.close()
        except:
            pass