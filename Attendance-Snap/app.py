from backend.app import app, PORT


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=PORT, debug=False)
