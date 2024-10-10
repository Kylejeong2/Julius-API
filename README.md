# Julius API

Prompt Julius with curl

How to use: 

first run the server:

```
cd julius-api-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

if you want to use curl, you have to host the server.

i recommend using ngrok to host the server.

download ngrok from https://ngrok.com/download
then run:
```
ngrok http http://127.0.0.1:5000/
```

then run the client from the root directory: (WIP)

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit.py
```

and you should be able to prompt it there.
