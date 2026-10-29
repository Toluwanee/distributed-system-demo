import os # this is in place so that we can read environment variables, this is the way the containers can discover their identity and peers
import time # to handle time-related functions or simulating delays in the network

from flask import Flask, request, jsonify # Flask is the main framework, request represents incoming http request to this node
import requests as http_requests  #requests is used to send outgoing http calls to peer nodes. it is renamed as http_requests so that I and python will not be confused.

app = Flask(__name__) # __name__ tells Flask where the file is located so that it can setup internal path. This is where the application instance is created or can run. app is just a variable holding the _name__ instance

store = {} # Empty python dictionary. It acts as our local in memory store. No need to worry about database state files.

# Configuration from environment
NODE_NAME = os.environ.get("NODE_NAME", default="node1") #Asks the OS for an environment variabe named "NODE_NAME", if it doesn't find it, the name defaults to "node1"

# Parse comma-separated PEERS string into a clean list (e.g., "node2:5000,node3:5000" -> ["node2:5000", "node3:5000"])
raw_peers = os.environ.get("PEERS", default="")
PEERS = [peer.strip() for peer in raw_peers.split(",") if peer.strip()]

MODE = os.environ.get("MODE", default="CP") #This sets our starting coordination mode, either AP or CP, default here is CP


@app.route("/data", methods=["GET"])  # @is a python decorator, "app.route" registers the function below it with Flask. It tells flask that when an incoming http request matches the /data path and it uses the get method, run the function directly below.
# Decorator: acts as a wrapper, executing code before or after the target function runs, keeping your code clean and reusable, methos is written as a python lsit because a simple html request can support multiple methods
def get_all_data(): #python function declaration without argument
    return jsonify({"node": NODE_NAME, "mode": MODE, "store": store})  #return, returns the response back to the client, the jsonify is a helper function from flask, it converts the python dictionary(key value pair) to json before it is returned. Why? Because APIs and web Browsers communicate via json. It also adds the correct HTTP header (Content-Type: application/json
    #what is returned? A json format of the node, mode, and store


@app.route("/data/<key>", methods=["GET"]) #this has a dynamic url parameter <key>, anything after /data/ should be treated a variable
def get_data(key):
    if key in store:  #member safety check, checking if a key exists in a dictionary is done using the in operator, like a loop that checks
        return jsonify({"node": NODE_NAME, "key": key, "value": store[key]}) #if success returns node name, mode
    return jsonify({"error": "Key not found"}), 404 #404 error code, if successful 20o is returned by default

#/data returns all value, #/data/key returns a single value by key or 404 if the key does not exist


#PUT endpoint 
@app.route("/data/<key>", methods=["PUT"])
def put_data(key):
    global MODE
    value = request.json.get("value")  #The user sends a PUT request, the request lib recieves it and it is parsed to json

    if MODE == "CP":
        # CP Mode: Replicates to all peers before confirming
        for peer in PEERS:   #loops through our list of peer adrdress
            try:
                resp = http_requests.post(f"http://{peer}/replicate", json={"key": key, "value": value}, timeout=2,) 
                # resp, the http_requests posts the key value content to the current peer
                if resp.status_code != 200:  #if the status code returned is not 200, then if failed to reach the peer and replicate the request 
                    return jsonify({
                        "error": f"Replication to {peer} failed",
                        "reason": "Write rejected to maintain consistency (CP mode)",
                    }), 503
            except http_requests.exceptions.RequestException:
                return jsonify({
                    "error": f"Cannot reach {peer}",
                    "reason": "Write rejected to maintain consistency (CP mode)",
                }), 503

        store[key] = value  # simplest Python syntax for dictionary assignment
        return jsonify({
            "status": "ok",
            "node": NODE_NAME,
            "key": key,
            "value": value,
            "mode": "CP",
            "message": "All nodes consistent",
                })

    else:
        # AP Mode: Write locally first, replicate best-effort
        store[key] = value

        replication_results = [] # This line initializes an empty list to keep track of those peer statuses that eill be looped over.
        for peer in PEERS:
            try:
                http_requests.post( # requests.post post the key-value pair on the peer the loop is running over.
                    f"http://{peer}/replicate",
                    json={"key": key, "value": value},
                    timeout=1,
                )
                replication_results.append({"peer": peer, "status": "replicated"})
            except http_requests.exceptions.RequestException:
                replication_results.append({"peer": peer, "status": "unreachable"})

        return jsonify({
            "status": "ok",
            "node": NODE_NAME,
            "key": key,
            "value": value,
            "mode": "AP",
            "replication": replication_results,
        })



if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)







 