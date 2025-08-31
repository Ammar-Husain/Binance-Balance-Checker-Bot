def run_server():
    from threading import Thread

    from flask import Flask

    server = Flask(__name__)

    @server.route("/", methods=["GET"])
    def greet():
        print("Request")
        return "Binance Bot is UP!"

    def flask_thread():
        server.run("0.0.0.0", port=8000)
        print("Server runs succefully")

    thread = Thread(target=flask_thread)
    thread.start()
